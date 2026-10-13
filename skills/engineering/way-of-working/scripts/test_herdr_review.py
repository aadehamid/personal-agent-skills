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
    def err(code):
        out({"error": {"code": code}}, 1)
    if cmd == "tab list":
        # A same-named review tab in another workspace; --workspace must filter it out.
        tabs = [{"tab_id": "w9:t1", "label": "review-repo", "workspace_id": "w9"}]
        if "newtab" not in s:
            tabs.append({"tab_id": "w2:t3", "label": "review-repo", "workspace_id": "w2"})
        if "--workspace" in args:
            ws = args[args.index("--workspace") + 1]
            tabs = [t for t in tabs if t["workspace_id"] == ws]
        out({"result": {"tabs": tabs}})
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
        n_path = os.path.join(state, "starts")
        n = int(open(n_path).read()) + 1 if os.path.exists(n_path) else 1
        open(n_path, "w").write(str(n))
        if "busyall" in s or ("busy2" in s and n <= 2): err("agent_pane_busy")
        if "notready" in s: err("agent_not_ready")
        out({"result": {"agent": {"name": args[2]}}})
    pending = os.path.join(state, "pending")
    rp = os.path.join(state, "report_path")
    if cmd == "agent prompt":
        if "stalled" in s and os.path.exists(rp):
            # The script asks an idle reviewer once more for the report at its path.
            open(pending, "w").write("write" if "obeys" in s else "none")
            out({"result": {}})
        if "stalled" in s:
            # The pane shows pasted text; the report appears after the extra Enter.
            report = re.search(r"exactly this path: (\S+)\. This is required", args[3]).group(1)
            open(os.path.join(state, "report_path"), "w").write(report)
            err("agent_prompt_stalled")
        if "blockedrej" in s: err("agent_blocked")
        if "timeout" in s: err("timeout")
        report = re.search(r"exactly this path: (\S+)\. This is required", args[3]).group(1)
        if "noreport" not in s:
            open(report, "w").write("REVIEW FINDINGS\n")
        out({"result": {"agent": {"agent_status": "blocked" if "noreport" in s else "idle"}}})
    if cmd == "agent get":
        if "getfail" in s: err("agent_not_found")
        if "stalled" in s:
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
        if "stalled" in s and os.path.exists(rp) and not os.path.exists(os.path.join(state, "entered")):
            open(os.path.join(state, "entered"), "w").write("")
            if "skillreport" in s:
                # The reviewer saves only the review skill's own report, then goes idle.
                d = os.path.join(os.environ["TMPDIR"], "ce-code-review", "run1")
                os.makedirs(d, exist_ok=True)
                open(os.path.join(d, "report.md"), "w").write("SKILL REPORT\n")
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
        print("pane text"); sys.exit(0)
    err("unexpected " + cmd)
''').lstrip()


def reviewer_hash(kind_model):
    import hashlib
    return hashlib.sha1(kind_model.encode()).hexdigest()[:8]


class HerdrReview(unittest.TestCase):
    def run_case(self, scenario, tmpdir=None, extra=(), repo_name="repo"):
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
        env = dict(os.environ, PATH=bindir + os.pathsep + os.environ["PATH"], HERDR_REVIEW_DIR=self.review_dir,
                   FAKE_HERDR=scenario, FAKE_STATE=state, HERDR_WORKSPACE_ID="w2",
                   TMPDIR=tmpdir or tempfile.mkdtemp())
        r = subprocess.run(["bash", SCRIPT, "--branch", "b", "--verify", "v", *extra],
                           cwd=repo, env=env, capture_output=True, text=True)
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
        self.assertIn("sandbox_workspace_write.writable_roots=" + roots, start)
        self.assertIn("workspace-write", start)

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
        r, calls = self.run_case("newtab,fresh,stalled", extra=("--kind", "cursor"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("agent send-keys", calls)
        self.assertIn("REVIEW FINDINGS", r.stdout)

    def test_a_report_still_being_written_is_not_printed_early(self):
        r, _ = self.run_case("newtab,fresh,stalled,partial", extra=("--kind", "cursor"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("REVIEW FINDINGS\n", r.stdout)

    def test_a_report_growing_while_idle_is_printed_only_once_it_stops(self):
        r, _ = self.run_case("newtab,fresh,stalled,idlemidwrite", extra=("--kind", "cursor"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "REVIEW FINDINGS\nMORE\n")

    def test_an_idle_reviewer_without_the_report_is_asked_once_for_it(self):
        r, calls = self.run_case("newtab,fresh,stalled,skillreport,obeys", extra=("--kind", "cursor"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(calls.count("agent prompt"), 2)
        self.assertIn("REVIEW FINDINGS", r.stdout)

    def test_another_reviews_skill_report_is_never_taken_as_this_one(self):
        r, calls = self.run_case("newtab,fresh,stalled,skillreport", extra=("--kind", "cursor"))
        self.assertEqual(r.returncode, 1)
        self.assertEqual(calls.count("agent prompt"), 2)
        self.assertNotIn("SKILL REPORT", r.stdout)
        self.assertIn("No finished report", r.stdout)

    def test_prompt_names_the_exact_report_path(self):
        with open(SCRIPT) as f:
            self.assertIn("write the final report as Markdown to exactly this path", f.read())

    def test_a_stalled_prompt_for_another_kind_still_stops(self):
        r, calls = self.run_case("newtab,fresh,stalled")
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("agent send-keys", calls)

    def test_cursor_report_path_is_under_tmp(self):
        # The tests put Cursor reports in a temporary folder, so the default is read from the script.
        with open(SCRIPT) as f:
            self.assertIn('report_dir="${HERDR_REVIEW_DIR:-/tmp/herdr-reviews}"', f.read())
        r, _ = self.run_case("newtab,fresh", extra=("--kind", "cursor"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Report file: " + self.review_dir + "/review-", r.stderr)

    def test_unknown_kind_is_refused(self):
        r, calls = self.run_case("ok", extra=("--kind", "gemini"))
        self.assertEqual(r.returncode, 2)
        self.assertEqual(calls, [])

    def test_prompt_tells_the_reviewer_to_apply_review_standards(self):
        with open(SCRIPT) as f:
            self.assertRegex(f.read(), r"review standards file .* first, and apply them")


if __name__ == "__main__":
    unittest.main()
