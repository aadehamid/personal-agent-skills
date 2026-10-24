#!/usr/bin/env python3
"""Run herdr-review.sh against a fake herdr, once per case the review recipe met in practice.

The fake herdr on PATH reads the scenario from FAKE_HERDR and records each call,
so a test can check both the exit status and which herdr commands ran.
"""
import json
import os
import re
import stat
import subprocess
import tempfile
import textwrap
import time
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "herdr-review.sh")

FAKE = textwrap.dedent(r'''
    #!/usr/bin/env python3
    import json, os, re, sys
    s = os.environ["FAKE_HERDR"].split(",")
    state = os.environ["FAKE_STATE"]
    args = sys.argv[1:]
    cmd = " ".join(args[:2])
    with open(os.path.join(state, "calls"), "a") as f:
        f.write(cmd + "\n")
    with open(os.path.join(state, "argv"), "a") as f:
        f.write(json.dumps(args) + "\n")
    def out(obj, code=0):
        print(json.dumps(obj)); sys.exit(code)
    def err(code, message=None):
        out({"error": {"code": code, **({"message": message} if message else {})}}, 1)
    if cmd == "tab list":
        # A same-named review tab in another workspace; --workspace must filter it out.
        tabs = [{"tab_id": "w9:t1", "label": "review-repo", "workspace_id": "w9"}]
        if "newtab" not in s:
            tabs.append({"tab_id": "w2:t3", "label": "review-repo", "workspace_id": "w2"})
        if "--workspace" in args:
            ws = args[args.index("--workspace") + 1]
            tabs = [t for t in tabs if t["workspace_id"] == ws]
        out({"result": {"tabs": tabs}})
    if cmd == "tab close":
        open(os.path.join(state, "closed-" + args[2]), "w").write("")
        out({"result": {}})
    if cmd == "tab create":
        root = None if "noroot" in s else {"pane_id": "w2:p3"}
        out({"result": {"tab": {"tab_id": "w2:t3"}, "root_pane": root}})
    if cmd == "pane list":
        if "panelisterr" in s: err("pane_not_found")
        out({"result": {"panes": [{"tab_id": "w9:t1", "pane_id": "w9:p1"},
                                  {"tab_id": "w2:t3", "pane_id": "w2:p3"}]}})
    if cmd == "pane get":
        if "paneerr" in s: err("pane_not_found")
        if "errpayload0" in s: out({"error": {"code": "pane_not_found"}}, 0)
        if "nullpane" in s: out({"result": {"pane": None}})
        out({"result": {"pane": {"agent": None if "fresh" in s else "codex"}}})
    if cmd == "agent start":
        # Herdr refuses a name a live agent already holds; "defaultlive" means the
        # default reviewer rev-repo is running in its own tab.
        if "defaultlive" in s and args[2] == "rev-repo": err("agent_name_taken")
        # "taken<status>": an earlier review in this work tree (cwd, possibly with spaces)
        # holds the name in tab w2:tEH until that tab is closed; "takenelsewhere": the
        # holder is in another directory.
        # "takenown<status>": the holder is the reused review tab w2:t3 itself.
        taken = [x[5:] for x in s if x.startswith("taken")]
        own = bool(taken) and taken[0].startswith("own")
        htab, hpane = ("w2:t3", "w2:p3") if own else ("w2:tEH", "w2:pJB")
        closed = os.path.exists(os.path.join(state, "closed-" + htab))
        if taken and not closed:
            cwd = "/elsewhere" if taken[0] == "elsewhere" else os.getcwd()
            status = "Working" if taken[0] == "elsewhere" else taken[0][3 if own else 0:].capitalize()
            err("agent_name_taken", "agent name %s is already used; candidates: name=%s kind=cursor "
                "pane_id=%s tab_id=%s cwd=%s status=%s" % (args[2], args[2], hpane, htab, cwd, status))
        n_path = os.path.join(state, "starts")
        n = int(open(n_path).read()) + 1 if os.path.exists(n_path) else 1
        open(n_path, "w").write(str(n))
        if "busyall" in s or ("busy2" in s and n <= 2): err("agent_pane_busy")
        if "notready" in s: err("agent_not_ready")
        out({"result": {"agent": {"name": args[2]}}})
    pending = os.path.join(state, "pending")
    rp = os.path.join(state, "report_path")
    entered = os.path.join(state, "entered")
    # "stalled" and "blockedpaste" leave the prompt unsent; the reviewer works only after
    # an Enter. "pasted" (implied by "blockedpaste") shows the unsent prompt on the input
    # line. "latepaste" draws it from the 2nd look ("latepaste13": the 13th), and the
    # reviewer acts on an Enter only once a look has shown it. "quotedpaste" shows the
    # marker in a quoted line, never on the input line.
    held = "stalled" in s or "blockedpaste" in s
    late = 13 if "latepaste13" in s else 2 if "latepaste" in s else 1
    pasted = "pasted" in s or "blockedpaste" in s or late > 1
    seen = os.path.join(state, "marker_seen")
    if cmd == "agent prompt":
        if held and os.path.exists(rp):
            # The script asks an idle reviewer once more for the report at its path.
            open(pending, "w").write("write" if "obeys" in s else "none")
            out({"result": {}})
        if held:
            # The pane shows pasted text; the report appears after the extra Enter.
            report = re.search(r"exactly this path: (\S+)\. This is required", args[3]).group(1)
            open(os.path.join(state, "report_path"), "w").write(report)
            err("agent_blocked" if "blockedpaste" in s else "agent_prompt_stalled")
        if "blockedrej" in s: err("agent_blocked")
        if "timeout" in s:
            if "writes" in s or "emptyreport" in s:
                # The reviewer wrote the report ("emptyreport": only created it), then
                # stopped on a question.
                report = re.search(r"exactly this path: (\S+)\. This is required", args[3]).group(1)
                open(report, "w").write("" if "emptyreport" in s else "REVIEW FINDINGS\n")
            err("timeout")
        report = re.search(r"exactly this path: (\S+)\. This is required", args[3]).group(1)
        if "noreport" not in s:
            open(report, "w").write("REVIEW FINDINGS\n")
        out({"result": {"agent": {"agent_status": "blocked" if "noreport" in s else "idle"}}})
    if cmd == "agent get":
        if "getfail" in s: err("agent_not_found")
        if held:
            # "latepaste13": the poll right after the Enter still reads idle.
            lag = os.path.join(state, "lag")
            if os.path.exists(lag):
                os.remove(lag)
                out({"result": {"agent": {"agent_status": "idle"}}})
            # Work the last keystroke or prompt started finishes during one "working" poll.
            if not os.path.exists(pending):
                g = os.path.join(state, "idle_gets")
                n = int(open(g).read()) + 1 if os.path.exists(g) else 1
                open(g, "w").write(str(n))
                if "idlemidwrite" in s and n == 2:
                    # The first idle poll came while the reviewer was still writing.
                    open(open(rp).read(), "a").write("MORE\n")
                out({"result": {"agent": {"agent_status": "idle"}}})
            action = open(pending).read()
            os.remove(pending)
            if action == "write":
                open(open(rp).read(), "w").write("REVIEW FINDINGS\n")
            if action == "finish":
                open(open(rp).read(), "a").write("EVIEW FINDINGS\n")
            out({"result": {"agent": {"agent_status": "working"}}})
        out({"result": {"agent": {"agent_status": "blocked"}}})
    if cmd == "agent send-keys":
        if late > 1 and not os.path.exists(seen):
            out({"result": {}})   # an Enter before the paste is drawn does nothing
        if held and os.path.exists(rp) and not os.path.exists(entered):
            open(entered, "w").write("")
            if late == 13:
                open(os.path.join(state, "lag"), "w").write("")
            if "skillreport" in s:
                # The reviewer saves only the review skill's own report(s), then goes idle.
                # FAKE_SKILL lists each run's metadata.json (null: no file); "HEAD" is the
                # test repo's commit.
                metas = json.loads(os.environ.get("FAKE_SKILL") or '[{"branch": "b", "head_sha": "HEAD"}]')
                for i, meta in enumerate(metas):
                    d = os.path.join(os.environ["TMPDIR"], "compound-engineering-%d" % os.getuid(),
                                     "ce-code-review", "20261023-01020%d-abc" % i)
                    os.makedirs(d, exist_ok=True)
                    open(os.path.join(d, "report.md"), "w").write("SKILL REPORT\n")
                    if meta is not None:
                        if meta.get("head_sha") == "HEAD":
                            meta["head_sha"] = os.environ.get("FAKE_HEAD", "")
                        open(os.path.join(d, "metadata.json"), "w").write(json.dumps(meta))
                open(pending, "w").write("none")
            elif "silent" in s:
                # The reviewer works, writes no report anywhere, and goes idle.
                open(pending, "w").write("none")
            elif "partial" in s:
                # The report file appears with its first byte while the reviewer works on.
                open(open(rp).read(), "w").write("R")
                open(pending, "w").write("finish")
            else:
                open(pending, "w").write("write")
        out({"result": {}})
    if cmd == "agent read":
        if "readfail" in s: err("agent_not_found")
        reads = os.path.join(state, "reads")
        n = int(open(reads).read()) + 1 if os.path.exists(reads) else 1
        open(reads, "w").write(str(n))
        if "quotedpaste" in s:
            print("+    marker = '[Pasted text #1'\n  \u2192 "); sys.exit(0)
        if pasted and not os.path.exists(entered) and n >= late:
            open(seen, "w").write("")
            print("  \u2192 [Pasted text #1 +1 lines]\n\n  Auto"); sys.exit(0)
        print("pane text"); sys.exit(0)
    err("unexpected " + cmd)
''').lstrip()


def reviewer_hash(kind_model):
    import hashlib
    return hashlib.sha1(kind_model.encode()).hexdigest()[:8]


class HerdrReview(unittest.TestCase):
    def run_case(self, scenario, tmpdir=None, extra=(), repo_name="repo", home=None, subdir=False,
                 git_head=False, skill=None, before=None):
        state = tempfile.mkdtemp()
        bindir = tempfile.mkdtemp()
        fake = os.path.join(bindir, "herdr")
        with open(fake, "w") as f:
            f.write(FAKE)
        os.chmod(fake, os.stat(fake).st_mode | stat.S_IEXEC)
        # sleep is stubbed so the busy retries run instantly.
        stub = os.path.join(bindir, "sleep")
        with open(stub, "w") as f:
            f.write("#!/bin/sh\nexit 0\n")
        os.chmod(stub, 0o755)
        repo = os.path.join(tempfile.mkdtemp(), repo_name)
        os.mkdir(repo)
        # Cursor reports go to a temporary folder, so the tests leave nothing in /tmp/herdr-reviews.
        self.review_dir = tempfile.mkdtemp()
        tmpdir = tmpdir or tempfile.mkdtemp()
        # The skill-report fallback searches only this test's TMPDIR, never the real /tmp.
        env = dict(os.environ, PATH=bindir + os.pathsep + os.environ["PATH"], HERDR_REVIEW_DIR=self.review_dir,
                   FAKE_HERDR=scenario, FAKE_STATE=state, HERDR_WORKSPACE_ID="w2",
                   TMPDIR=tmpdir, HERDR_REVIEW_ARTIFACT_ROOTS=tmpdir)
        if home:
            env["HOME"] = home
        if skill is not None:
            env["FAKE_SKILL"] = json.dumps(skill)
        if git_head:
            # A work tree with one commit, so the skill-report fallback has a HEAD to match.
            genv = {k: v for k, v in env.items() if not k.startswith("GIT_")}
            subprocess.run(["git", "init", "-q", repo], check=True, env=genv)
            subprocess.run(["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
                            "--allow-empty", "-m", "c"], check=True, env=genv)
            env["FAKE_HEAD"] = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"], check=True, env=genv,
                                              capture_output=True, text=True).stdout.strip()
        if before:
            before(tmpdir, env.get("FAKE_HEAD", ""))
        start = repo
        if subdir:
            # A git work tree, started from deep inside it.
            subprocess.run(["git", "init", "-q", repo], check=True,
                           env={k: v for k, v in env.items() if not k.startswith("GIT_")})
            start = os.path.join(repo, "sub", "dir")
            os.makedirs(start)
        self.repo = os.path.realpath(repo)
        r = subprocess.run(["bash", SCRIPT, "--branch", "b", "--verify", "v", *extra],
                           cwd=start, env={k: v for k, v in env.items() if not k.startswith("GIT_")} if subdir or git_head else env,
                           capture_output=True, text=True)
        calls_path = os.path.join(state, "calls")
        calls = []
        if os.path.exists(calls_path):
            with open(calls_path) as f:
                calls = f.read().splitlines()
        self.argv = []
        argv_path = os.path.join(state, "argv")
        if os.path.exists(argv_path):
            with open(argv_path) as f:
                self.argv = [json.loads(line) for line in f]
        return r, calls

    def test_reused_reviewer_prints_the_report(self):
        r, calls = self.run_case("ok")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("REVIEW FINDINGS", r.stdout)
        self.assertNotIn("agent start", calls)

    def test_report_path_is_printed_on_stderr(self):
        r, _ = self.run_case("ok")
        path = re.search(r"^Report file: (\S+)$", r.stderr, re.MULTILINE).group(1)
        with open(path) as f:
            self.assertEqual(f.read(), "REVIEW FINDINGS\n")

    def test_report_path_is_printed_even_without_a_report(self):
        r, _ = self.run_case("noreport")
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr, r"(?m)^Report file: \S+$")

    def test_new_tab_and_fresh_reviewer(self):
        r, calls = self.run_case("newtab,fresh")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(calls.count("tab create"), 1)
        self.assertEqual(calls.count("agent start"), 1)

    def test_busy_shell_is_retried_until_ready(self):
        r, calls = self.run_case("fresh,busy2")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(calls.count("agent start"), 3)

    def test_shell_busy_every_time_gives_up_after_five(self):
        r, calls = self.run_case("fresh,busyall")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(calls.count("agent start"), 5)
        self.assertNotIn("agent prompt", calls)
        self.assertIn("did not start", r.stdout)

    def test_blocked_start_stops_at_once(self):
        r, calls = self.run_case("fresh,notready,readfail")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(calls.count("agent start"), 1)
        self.assertIn("did not start", r.stdout)

    def test_failed_pane_lookup_starts_nothing(self):
        r, calls = self.run_case("paneerr")
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("agent start", calls)
        self.assertNotIn("agent prompt", calls)

    def test_prompt_rejected_while_blocked(self):
        r, _ = self.run_case("blockedrej,readfail")
        self.assertEqual(r.returncode, 1)
        self.assertIn("agent_blocked", r.stdout)

    def test_prompt_timeout_gives_the_same_report_path(self):
        r, _ = self.run_case("timeout")
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stdout, r"herdr agent wait w2:p3 --until idle --until done .*cat '.*review-")

    def test_missing_report_fails_even_if_lookups_fail(self):
        r, _ = self.run_case("noreport,getfail,readfail")
        self.assertEqual(r.returncode, 1)
        self.assertIn("No report", r.stdout)

    def test_report_prints_even_if_status_lookup_would_fail(self):
        r, calls = self.run_case("getfail")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("agent get", calls)

    def test_unwritable_tmpdir_stops_before_the_prompt(self):
        r, calls = self.run_case("ok", tmpdir="/nonexistent-dir-for-test")
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("agent prompt", calls)

    def test_error_payload_with_exit_zero_stops_before_start(self):
        r, calls = self.run_case("errpayload0,fresh")
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("agent start", calls)

    def test_missing_pane_in_a_successful_response_stops(self):
        r, calls = self.run_case("nullpane")
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("agent start", calls)
        self.assertNotIn("agent prompt", calls)

    def test_tabs_are_listed_and_created_in_this_workspace_only(self):
        r, _ = self.run_case("ok")
        self.assertEqual(r.returncode, 0, r.stderr)
        listed = [a for a in self.argv if a[:2] == ["tab", "list"]]
        self.assertEqual(listed[0][2:4], ["--workspace", "w2"])
        self.assertIn("Review tab: w2:t3 (reused)", r.stderr)
        r, _ = self.run_case("newtab,fresh")
        created = [a for a in self.argv if a[:2] == ["tab", "create"]]
        self.assertEqual(created[0][2:4], ["--workspace", "w2"])
        self.assertIn("Review tab: w2:t3 (created)", r.stderr)

    def test_new_tab_pane_comes_from_the_create_response(self):
        r, calls = self.run_case("newtab,fresh,panelisterr")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("pane list", calls)

    def test_created_tab_is_named_even_if_a_later_step_fails(self):
        r, calls = self.run_case("newtab,fresh,noroot")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Review tab: w2:t3 (created)", r.stderr)
        self.assertNotIn("agent start", calls)
        self.assertNotIn("agent prompt", calls)

    def test_reused_tab_is_named_before_pane_lookup_fails(self):
        r, _ = self.run_case("panelisterr")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Review tab: w2:t3 (reused)", r.stderr)

    def test_prompt_waits_for_the_review_with_a_timeout(self):
        r, _ = self.run_case("ok")
        self.assertEqual(r.returncode, 0, r.stderr)
        prompt = [a for a in self.argv if a[:2] == ["agent", "prompt"]][0]
        self.assertIn("--wait", prompt)
        self.assertEqual(prompt[prompt.index("--timeout") + 1], "3600000")

    def test_codex_sandbox_can_write_the_folders_the_cross_model_pass_needs(self):
        r, _ = self.run_case("newtab,fresh")
        self.assertEqual(r.returncode, 0, r.stderr)
        start = [a for a in self.argv if a[:2] == ["agent", "start"]][0]
        home = os.path.expanduser("~")
        roots = json.dumps([f"{home}/.npm", f"{home}/.claude", f"{home}/.cache", f"{home}/.config"], separators=(",", ":"))
        token = "sandbox_workspace_write.writable_roots=" + roots
        self.assertIn(token, start)
        self.assertEqual(start[start.index(token) - 1], "-c")
        self.assertIn("workspace-write", start)

    def test_the_writable_folders_exist_before_codex_starts(self):
        home = tempfile.mkdtemp()
        r, _ = self.run_case("newtab,fresh", home=home)
        self.assertEqual(r.returncode, 0, r.stderr)
        for name in (".npm", ".claude", ".cache", ".config"):
            self.assertTrue(os.path.isdir(os.path.join(home, name)), name)

    def test_a_reused_reviewer_is_reported_as_keeping_its_old_flags(self):
        r, calls = self.run_case("ok")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("agent start", calls)
        self.assertIn("keeps the flags it started with", r.stderr)

    def test_a_run_from_a_subdirectory_names_and_starts_the_tab_at_the_top(self):
        r, _ = self.run_case("newtab,fresh", subdir=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        created = [a for a in self.argv if a[:2] == ["tab", "create"]][0]
        self.assertEqual(created[created.index("--label") + 1], "review-repo")
        self.assertEqual(os.path.realpath(created[created.index("--cwd") + 1]), self.repo)

    def test_default_model_is_gpt_6_1_sol_in_the_review_tab(self):
        r, _ = self.run_case("newtab,fresh")
        self.assertEqual(r.returncode, 0, r.stderr)
        created = [a for a in self.argv if a[:2] == ["tab", "create"]][0]
        self.assertEqual(created[created.index("--label") + 1], "review-repo")
        start = [a for a in self.argv if a[:2] == ["agent", "start"]][0]
        self.assertEqual(start[start.index("-m") + 1], "gpt-6.1-sol")

    def test_another_model_gets_its_own_tab(self):
        # The plain review-repo tab exists, but a reused tab keeps its reviewer,
        # so another model must open review-repo-<model> instead.
        r, _ = self.run_case("fresh", extra=("--model", "gpt-6-astra"))
        self.assertEqual(r.returncode, 0, r.stderr)
        created = [a for a in self.argv if a[:2] == ["tab", "create"]][0]
        self.assertEqual(created[created.index("--label") + 1], "review-repo-codex-" + reviewer_hash("codex:gpt-6-astra"))
        start = [a for a in self.argv if a[:2] == ["agent", "start"]][0]
        self.assertEqual(start[start.index("-m") + 1], "gpt-6-astra")

    def test_another_model_starts_beside_a_live_default_reviewer(self):
        r, calls = self.run_case("fresh,defaultlive", extra=("--model", "gpt-6-astra"))
        self.assertEqual(r.returncode, 0, r.stderr)
        name = [a for a in self.argv if a[:2] == ["agent", "start"]][0][2]
        self.assertNotEqual(name, "rev-repo")
        self.assertRegex(name, r"^rev-repo-[0-9a-f]{8}$")
        self.assertIn("agent prompt", calls)

    def test_each_override_model_gets_its_own_stable_name(self):
        import hashlib
        names = {}
        for model in ("gpt-6-astra", "gpt-6-luna", "gpt-6-astra"):
            r, _ = self.run_case("newtab,fresh", extra=("--model", model))
            self.assertEqual(r.returncode, 0, r.stderr)
            name = [a for a in self.argv if a[:2] == ["agent", "start"]][0][2]
            self.assertEqual(name, "rev-repo-" + hashlib.sha1(f"codex:{model}".encode()).hexdigest()[:8])
            names.setdefault(model, set()).add(name)
        self.assertEqual(len(names["gpt-6-astra"]), 1)
        self.assertNotEqual(names["gpt-6-astra"], names["gpt-6-luna"])

    def test_agent_names_fit_herdr_limits_for_a_long_repo_name(self):
        for extra in ((), ("--model", "gpt-6-astra")):
            r, _ = self.run_case("newtab,fresh", extra=extra, repo_name="A Very Long Repository Name For Testing")
            self.assertEqual(r.returncode, 0, r.stderr)
            name = [a for a in self.argv if a[:2] == ["agent", "start"]][0][2]
            self.assertRegex(name, r"^[a-z][a-z0-9_-]{0,31}$", extra)

    def test_kimi_reviewer_runs_k3_in_its_own_tab(self):
        r, calls = self.run_case("fresh,defaultlive", extra=("--kind", "kimi"))
        self.assertEqual(r.returncode, 0, r.stderr)
        created = [a for a in self.argv if a[:2] == ["tab", "create"]][0]
        self.assertEqual(created[created.index("--label") + 1], "review-repo-kimi-" + reviewer_hash("kimi:kimi-code/k3"))
        start = [a for a in self.argv if a[:2] == ["agent", "start"]][0]
        self.assertEqual(start[start.index("--kind") + 1], "kimi")
        self.assertEqual(start[start.index("--") + 1:], ["-m", "kimi-code/k3", "-y"])
        self.assertRegex(start[2], r"^rev-repo-[0-9a-f]{8}$")
        self.assertIn("agent prompt", calls)

    def test_kimi_model_override_reaches_label_name_and_launch(self):
        import hashlib
        r, _ = self.run_case("newtab,fresh", extra=("--kind", "kimi", "--model", "kimi-code/k3-256k"))
        self.assertEqual(r.returncode, 0, r.stderr)
        created = [a for a in self.argv if a[:2] == ["tab", "create"]][0]
        self.assertEqual(created[created.index("--label") + 1], "review-repo-kimi-" + reviewer_hash("kimi:kimi-code/k3-256k"))
        start = [a for a in self.argv if a[:2] == ["agent", "start"]][0]
        self.assertEqual(start[start.index("--") + 1:], ["-m", "kimi-code/k3-256k", "-y"])
        self.assertEqual(start[2], "rev-repo-" + hashlib.sha1(b"kimi:kimi-code/k3-256k").hexdigest()[:8])

    def test_models_that_differ_only_in_punctuation_get_different_tabs(self):
        labels = set()
        for model in ("kimi-code/k3", "kimi-code-k3"):
            r, _ = self.run_case("newtab,fresh", extra=("--kind", "kimi", "--model", model))
            self.assertEqual(r.returncode, 0, r.stderr)
            created = [a for a in self.argv if a[:2] == ["tab", "create"]][0]
            labels.add(created[created.index("--label") + 1])
        self.assertEqual(len(labels), 2)

    def test_prompt_names_the_review_skill_file(self):
        r, _ = self.run_case("ok")
        self.assertEqual(r.returncode, 0, r.stderr)
        prompt = [a for a in self.argv if a[:2] == ["agent", "prompt"]][0][3]
        self.assertIn(os.path.expanduser("~/.agents/skills/ce-code-review/SKILL.md"), prompt)
        self.assertIn("For each finding, name the kind of defect and list every place in the repository that has it, including places outside the diff.", prompt)

    def test_cursor_reviewer_runs_grok_sandboxed_in_its_own_tab(self):
        r, calls = self.run_case("newtab,fresh", extra=("--kind", "cursor"))
        self.assertEqual(r.returncode, 0, r.stderr)
        created = [a for a in self.argv if a[:2] == ["tab", "create"]][0]
        self.assertEqual(created[created.index("--label") + 1], "review-repo-cursor-" + reviewer_hash("cursor:cursor-grok-4.6-medium"))
        start = [a for a in self.argv if a[:2] == ["agent", "start"]][0]
        self.assertEqual(start[start.index("--kind") + 1], "cursor")
        self.assertEqual(start[start.index("--") + 1:],
                         ["--model", "cursor-grok-4.6-medium", "--sandbox", "enabled", "--force", "--trust"])
        self.assertIn("agent prompt", calls)

    def test_cursor_stalled_prompt_gets_an_enter_and_waits_for_the_report(self):
        r, calls = self.run_case("newtab,fresh,stalled,pasted", extra=("--kind", "cursor"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("agent send-keys", calls)
        self.assertIn("REVIEW FINDINGS", r.stdout)

    def test_a_report_still_being_written_is_not_printed_early(self):
        r, _ = self.run_case("newtab,fresh,stalled,pasted,partial", extra=("--kind", "cursor"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("REVIEW FINDINGS\n", r.stdout)

    def test_a_report_growing_while_idle_is_printed_only_once_it_stops(self):
        r, _ = self.run_case("newtab,fresh,stalled,pasted,idlemidwrite", extra=("--kind", "cursor"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "REVIEW FINDINGS\nMORE\n")

    def test_an_idle_reviewer_without_the_report_is_asked_once_for_it(self):
        r, calls = self.run_case("newtab,fresh,stalled,pasted,skillreport,obeys", extra=("--kind", "cursor"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(calls.count("agent prompt"), 2)
        self.assertIn("REVIEW FINDINGS", r.stdout)

    def test_prompt_names_the_exact_report_path(self):
        with open(SCRIPT) as f:
            self.assertIn("write the final report as Markdown to exactly this path", f.read())

    def test_a_stalled_prompt_that_never_starts_work_exits_with_the_reason(self):
        r, calls = self.run_case("newtab,fresh,stalled")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("agent send-keys", calls)
        self.assertIn("the reviewer never started work on the prompt", r.stdout)

    # The 2026-10-23 incident: agent_blocked with the prompt still pasted in Cursor's input.
    def test_blocked_prompt_left_pasted_gets_an_enter_and_recovers(self):
        r, calls = self.run_case("newtab,fresh,blockedpaste", extra=("--kind", "cursor"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("agent send-keys", calls)
        self.assertEqual(r.stdout, "REVIEW FINDINGS\n")

    # The live rerun of 2026-10-23: stalled, status idle, pasted text drawn after the first look.
    def test_idle_reviewer_with_a_late_pasted_prompt_gets_an_enter_and_recovers(self):
        r, calls = self.run_case("newtab,fresh,stalled,latepaste", extra=("--kind", "cursor"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(calls.count("agent send-keys"), 1)
        self.assertEqual(r.stdout, "REVIEW FINDINGS\n")

    def test_idle_without_report_is_asked_once_then_this_runs_skill_report_is_copied(self):
        r, calls = self.run_case("newtab,fresh,stalled,pasted,skillreport", extra=("--kind", "cursor"), git_head=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(calls.count("agent prompt"), 2)
        self.assertEqual(r.stdout, "SKILL REPORT\n")
        self.assertIn("copied the review skill's report", r.stderr)
        path = re.search(r"^Report file: (\S+)$", r.stderr, re.MULTILINE).group(1)
        with open(path) as f:
            self.assertEqual(f.read(), "SKILL REPORT\n")

    @staticmethod
    def plant_skill_report(tmpdir, head, text, age):
        # A ce-code-review run for branch b at this HEAD; age < 0 dates it after the start.
        d = os.path.join(tmpdir, "compound-engineering-%d" % os.getuid(), "ce-code-review", "planted")
        os.makedirs(d)
        path = os.path.join(d, "report.md")
        with open(path, "w") as f:
            f.write(text)
        with open(os.path.join(d, "metadata.json"), "w") as f:
            json.dump({"branch": "b", "head_sha": head}, f)
        when = time.time() - age
        os.utime(path, (when, when))

    def test_a_skill_report_older_than_the_run_is_ignored(self):
        r, calls = self.run_case("newtab,fresh,blockedpaste,silent", extra=("--kind", "cursor"), git_head=True,
                                 before=lambda t, h: self.plant_skill_report(t, h, "OLD REPORT\n", 3600))
        self.assertEqual(r.returncode, 1)
        self.assertEqual(calls.count("agent prompt"), 2)
        self.assertNotIn("OLD REPORT", r.stdout + r.stderr)
        self.assertIn("finished without writing the report, even when asked; no skill report for this run", r.stdout)

    def assert_skill_report_refused(self, skill, reason):
        r, _ = self.run_case("newtab,fresh,stalled,pasted,skillreport", extra=("--kind", "cursor"),
                             git_head=True, skill=skill)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertNotIn("SKILL REPORT", r.stdout)
        self.assertIn(reason, r.stdout.splitlines()[-2])
        return r

    def test_a_skill_report_without_metadata_is_refused(self):
        self.assert_skill_report_refused([None], "no skill report for this run")

    def test_a_skill_report_whose_metadata_has_no_head_sha_is_refused(self):
        self.assert_skill_report_refused([{"branch": "b"}], "no skill report for this run")

    def test_a_skill_report_of_another_commit_on_this_branch_is_refused(self):
        self.assert_skill_report_refused([{"branch": "b", "head_sha": "0" * 40}], "no skill report for this run")

    def test_a_skill_report_of_another_branch_at_this_commit_is_refused(self):
        self.assert_skill_report_refused([{"branch": "other", "head_sha": "HEAD"}], "no skill report for this run")

    def test_two_skill_reports_matching_this_run_are_both_refused(self):
        r = self.assert_skill_report_refused([{"branch": "b", "head_sha": "HEAD"}, {"branch": "b", "head_sha": "HEAD"}],
                                             "several skill reports match this run; read them and pick")
        self.assertEqual(r.stdout.count("/report.md"), 2)
        self.assertRegex(r.stdout.splitlines()[-1], r"^Next: cp <the chosen report.md> '\S+' && cat '\S+'$")

    # A late paste gets its Enter before the "never started" stop is checked (review #2).
    def test_a_paste_drawn_after_a_minute_of_idle_still_gets_its_enter(self):
        r, calls = self.run_case("newtab,fresh,stalled,latepaste13", extra=("--kind", "cursor"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(calls.count("agent send-keys"), 1)
        self.assertEqual(r.stdout, "REVIEW FINDINGS\n")

    def test_the_paste_marker_on_a_codex_pane_gets_no_enter(self):
        r, calls = self.run_case("newtab,fresh,stalled,pasted")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("agent send-keys", calls)

    def test_the_paste_marker_off_the_input_line_gets_no_enter(self):
        r, calls = self.run_case("newtab,fresh,stalled,quotedpaste", extra=("--kind", "cursor"))
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("agent send-keys", calls)

    def test_a_paste_still_shown_gets_at_most_three_enters(self):
        # "blockedrej" never lets the Enter land, so the marker stays on the input line.
        r, calls = self.run_case("newtab,fresh,blockedrej,pasted", extra=("--kind", "cursor"))
        self.assertEqual(calls.count("agent send-keys"), 3)

    def test_a_prompt_rejected_as_blocked_says_answer_then_run_again(self):
        r, _ = self.run_case("blockedrej")
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stdout.splitlines()[-1],
                         r"^Next: answer it \(herdr agent send-keys w2:p3 <key>\), then run: \S*herdr-review\.sh --branch b --verify v $")

    def test_the_reviewers_own_file_wins_however_the_wait_ends(self):
        # The reviewer wrote the report, then blocked; a matching skill report is also there.
        r, _ = self.run_case("timeout,writes", git_head=True,
                             before=lambda t, h: self.plant_skill_report(t, h, "SKILL REPORT\n", -60))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout, "REVIEW FINDINGS\n")

    def test_no_report_anywhere_exits_1_with_the_reason_and_next_command(self):
        r, calls = self.run_case("newtab,fresh,stalled,pasted,silent", extra=("--kind", "cursor"))
        self.assertEqual(r.returncode, 1)
        self.assertEqual(calls.count("agent prompt"), 2)
        lines = r.stdout.splitlines()
        self.assertRegex(lines[-2], r"^No report at \S+: the reviewer finished without writing the report, even when asked; no skill report for this run\.$")
        self.assertRegex(lines[-1], r"^Next: \S*herdr-review\.sh --branch b --verify v --kind cursor $")

    def test_cursor_report_path_is_under_tmp(self):
        # The tests put Cursor reports in a temporary folder, so the default is read from the script.
        with open(SCRIPT) as f:
            self.assertIn('report_dir="${HERDR_REVIEW_DIR:-/tmp/herdr-reviews}"', f.read())
        r, _ = self.run_case("newtab,fresh", extra=("--kind", "cursor"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Report file: " + self.review_dir + "/review-", r.stderr)

    def test_a_finished_review_holding_the_name_is_closed_and_the_start_retried(self):
        r, calls = self.run_case("newtab,fresh,takendone", repo_name="my repo")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        closes = [a for a in self.argv if a[:2] == ["tab", "close"]]
        self.assertEqual(closes, [["tab", "close", "w2:tEH"]])
        self.assertEqual(calls.count("agent start"), 2)
        self.assertEqual(r.stdout, "REVIEW FINDINGS\n")

    def test_a_running_review_holding_the_name_is_left_alone(self):
        r, calls = self.run_case("newtab,fresh,takenworking")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("tab close", calls)
        self.assertNotIn("agent prompt", calls)
        lines = r.stdout.splitlines()
        self.assertEqual(lines[-2], "Reviewer did not start: another review is running in w2:tEH; wait for it or close it.")
        self.assertRegex(lines[-1], r"^Next: herdr agent wait w2:pJB --until idle --until done --timeout 3600000 && "
                                    r"\S*herdr-review\.sh --branch b --verify v $")

    def test_a_finished_reviewer_in_the_reused_tab_holding_the_name_gets_a_fresh_tab(self):
        r, calls = self.run_case("fresh,takenowndone")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Review tab: w2:t3 (reused)", r.stderr)
        self.assertEqual([a for a in self.argv if a[:2] == ["tab", "close"]], [["tab", "close", "w2:t3"]])
        self.assertEqual(calls.count("tab create"), 1)
        self.assertIn("Review tab: w2:t3 (created)", r.stderr)
        self.assertEqual(calls.count("agent start"), 2)
        self.assertEqual(r.stdout, "REVIEW FINDINGS\n")

    def test_a_working_reviewer_in_the_reused_tab_holding_the_name_is_left_alone(self):
        r, calls = self.run_case("fresh,takenownworking")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("tab close", calls)
        lines = r.stdout.splitlines()
        self.assertEqual(lines[-2], "Reviewer did not start: another review is running in w2:t3; wait for it or close it.")
        self.assertRegex(lines[-1], r"^Next: herdr agent wait w2:p3 --until idle --until done --timeout 3600000 && ")

    def test_a_name_holder_in_another_directory_is_left_alone(self):
        r, calls = self.run_case("newtab,fresh,takenelsewhere")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("tab close", calls)
        self.assertIn("did not start", r.stdout)

    def test_an_empty_report_file_still_gets_this_runs_skill_report(self):
        r, _ = self.run_case("timeout,emptyreport", git_head=True,
                             before=lambda t, h: self.plant_skill_report(t, h, "SKILL REPORT\n", -60))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout, "SKILL REPORT\n")

    def test_an_empty_report_file_keeps_the_blocked_next_command(self):
        r, _ = self.run_case("timeout,emptyreport", git_head=True)
        self.assertEqual(r.returncode, 1)
        lines = r.stdout.splitlines()
        self.assertRegex(lines[-2], r"^No report at \S+: the reviewer is waiting on a question; no skill report for this run\.$")
        self.assertRegex(lines[-1], r"^Next: answer it \(herdr agent send-keys w2:p3 <key>\), then run: "
                                    r"herdr agent wait w2:p3 --until idle --until done --timeout 3600000 && cat '\S+'$")

    def test_a_failure_before_the_prompt_ends_with_the_reason_and_next(self):
        r, _ = self.run_case("paneerr")
        self.assertEqual(r.returncode, 1)
        lines = r.stdout.splitlines()
        self.assertEqual(lines[-2], "No review: starting the reviewer failed; the error is above.")
        self.assertRegex(lines[-1], r"^Next: \S*herdr-review\.sh --branch b --verify v $")

    def test_unknown_kind_is_refused(self):
        r, calls = self.run_case("ok", extra=("--kind", "gemini"))
        self.assertEqual(r.returncode, 2)
        self.assertEqual(calls, [])

    def test_prompt_tells_the_reviewer_to_apply_review_standards(self):
        with open(SCRIPT) as f:
            self.assertRegex(f.read(), r"review standards file .* first, and apply them")


if __name__ == "__main__":
    unittest.main()
