#!/usr/bin/env python3
"""Run hc-review.sh against a fake hc, and herdr-review.sh's hand-off to it.

The fake hc on PATH reads the scenario from FAKE_HC, keeps the reviewer's state in FAKE_STATE,
draws each reviewer kind's own input line, and records each call, so a test can check the exit
status and the hc calls. Codex reports its state (OSC 7501) by default, as Codex 0.166 did on
2026-10-29; the Cursor agent and Kimi report none, so the script reads their screens.
"""
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import tempfile
import textwrap
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "hc-review.sh")
HERDR_SCRIPT = os.path.join(HERE, "herdr-review.sh")

FAKE = textwrap.dedent(r'''
    #!/usr/bin/env python3
    import json, os, re, sys
    s = os.environ["FAKE_HC"].split(",")
    state, kind, top = os.environ["FAKE_STATE"], os.environ["FAKE_KIND"], os.environ["FAKE_TOP"]
    args = sys.argv[1:]
    def path(name): return os.path.join(state, name)
    def read(name, default=""):
        return open(path(name)).read() if os.path.exists(path(name)) else default
    def write(name, text): open(path(name), "w").write(text)
    cmd = args[0]
    with open(path("calls"), "a") as f: f.write(cmd + "\n")
    with open(path("argv"), "a") as f: f.write(json.dumps(args) + "\n")
    def out(obj): print(json.dumps(obj)); sys.exit(0)
    reported = kind == "codex" and "unreported" not in s
    phase = read("phase", "none")
    report = read("report_path")
    turn = int(read("turn", "0"))
    def editor(text=""):
        if kind == "kimi":
            return " ╭──╮\n │ > %s │\n ╰──╯\n  K3.1 Pro  context: 0%%" % text
        if kind == "cursor":
            return "  → %s\n\n  Auto" % (text or "Add a follow-up")
        return "  › %s\n\n  GPT-6-Luna default" % (text or "Ask Codex to do anything")
    def start_work(asked=False):
        write("phase", "working"); write("work", "1" if asked else "3")
        if asked: write("asked", "")
    def step():
        # Each look at a working reviewer uses up one unit of work; then it writes the report.
        if phase != "working":
            return
        left = int(read("work", "0")) - 1
        write("work", str(left))
        if left <= 0:
            if "noreport" not in s or ("obeys" in s and os.path.exists(path("asked"))):
                open(report, "w").write("REVIEW FINDINGS\n")
            write("phase", "idle"); write("turn", str(turn + 1))
    if cmd == "ls":
        terms = [{"address": "t1", "agent": "claude-code", "cwd": "/Users/x", "state": "live", "status": "working"}]
        holder = next((x for x in s if x.startswith("holder")), None)
        if holder and not os.path.exists(path("holder_removed")):
            status = {"holderidle": "idle", "holderbusy": "working", "holderelsewhere": "idle"}[holder]
            terms.append({"address": "t7", "name": os.environ["FAKE_NAME"], "state": "live", "status": status,
                          "cwd": "/elsewhere/repo" if holder == "holderelsewhere" else top})
        out({"terminals": terms})
    if cmd == "run":
        task = args[-1] if kind != "kimi" else None
        m = re.search(r"exactly this path: (\S+)\. ", task or "")
        if m:
            write("report_path", m.group(1)); write("prompt", task)
        if "trustq" in s:
            write("phase", "trustq")
        elif "blocked" in s:
            write("phase", "blocked")
        elif "limit" in s:
            write("phase", "limit")
        elif "unsent" in s:
            write("phase", "unsent")
        elif kind == "kimi":
            write("phase", "ready")
        else:
            start_work()
        launch = {"address": "t9", "name": args[args.index("--name") + 1], "state": "live", "turn": 0}
        if "notsent" in s:
            launch["first_message"] = {"sent": False}
        out(launch)
    if cmd == "send":
        text = args[2]
        if text.startswith("Read AGENTS.md"):
            m = re.search(r"exactly this path: (\S+)\. ", text)
            write("report_path", m.group(1)); write("prompt", text)
            if "kimiwrapped" in s or "kimiscrolled" in s:
                write("phase", "kimiunsent")   # the prompt sits in Kimi's box until Enter
            else:
                start_work()
        elif text.startswith("Write your final review"):
            start_work(asked=True)
        out({"sent": True})
    if cmd == "keys":
        if phase == "trustq":
            write("phase", "ready" if "stilltrust" not in s else "trustq")
        elif phase == "kimiunsent":
            write("enters", str(int(read("enters", "0")) + 1)); start_work()
        elif phase == "unsent" and "neverenter" not in s:
            start_work()
        out({})
    if cmd == "get":
        step()
        phase = read("phase", phase)
        if phase == "gone":
            out({"address": "t9", "state": "finished", "status": None, "turn": turn})
        word = {"working": "working", "idle": "idle", "blocked": "blocked"}.get(phase)
        status = {"app": kind, "state": word} if reported and word else None
        out({"address": "t9", "state": "live", "status": status, "reported": reported, "turn": int(read("turn", "0"))})
    if cmd == "read":
        if phase == "trustq":
            print("  Trust this folder?\n \n  %s\n \n   ❯ Trust and continue\n     Exit" % top); sys.exit(0)
        if phase == "limit":
            print("  429 You've reached your 5-hour usage limit\n" + editor()); sys.exit(0)
        if phase == "blocked":
            print("  Run this command?\n  → Run (once) (y)"); sys.exit(0)
        if phase == "kimiunsent":
            name = "kimi-wrapped-prompt.txt" if "kimiwrapped" in s else "kimi-scrolled-prompt.txt"
            screen = open(os.path.join(os.environ["FAKE_FIXTURES"], name)).read().rstrip("\n").split("\n")
            # A busy marker or a usage limit just above the tall box (Cursor's second HOLD on #81).
            above = []
            if "busyabove" in s:
                n = int(read("busy_reads", "0")) + 1; write("busy_reads", str(n))
                if n > 3:
                    start_work()   # it was working all along; the prompt was taken
                above = ["  Running 4 agents", "  Press Ctrl+B to run in background"]
            if "limitabove" in s:
                above = ["  429 You've reached your 5-hour usage limit"]
            top_border = max(i for i, l in enumerate(screen) if l.strip().startswith("\u256d"))
            print("\n".join(screen[:top_border] + above + screen[top_border:])); sys.exit(0)
        if phase == "unsent":
            print(editor("Read AGENTS.md and the repository's review standards file")); sys.exit(0)
        if phase == "working" and not reported:
            print("  thinking %s  ctrl+c to stop\n" % read("work") + editor()); sys.exit(0)
        print("  quiet\n" + editor()); sys.exit(0)
    if cmd == "wait":
        out({"ended": True, "reason": "status", "terminal": "t9"})
    if cmd == "kill":
        if args[1] == "t7": write("holder_removed", "")
        write("phase", "gone"); out({})
    if cmd == "rm":
        out({"removed": args[1]})
    print("unexpected " + cmd, file=sys.stderr); sys.exit(1)
''').lstrip()

KINDS = {"codex": "gpt-6-luna", "kimi": "kimi-code/k3.1-pro", "cursor": "cursor-grok-4.6-medium"}


def name_for(kind, model, repo="repo"):
    return "rev-%s-%s" % (repo, hashlib.sha1(("%s:%s" % (kind, model)).encode()).hexdigest()[:8])


def stub(bindir, name, text):
    with open(os.path.join(bindir, name), "w") as f:
        f.write(text)
    os.chmod(os.path.join(bindir, name), 0o755)


def lines_of(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return f.read().splitlines()


# A host that must not be used: it records that it was called and fails.
REFUSE = "#!/bin/sh\necho \"$(basename \"$0\") $*\" >> \"$FAKE_STATE/other_hosts\"\nexit 1\n"


class HcReview(unittest.TestCase):
    def run_case(self, scenario, script=SCRIPT, extra=(), env_extra=None, kind="codex", model=None,
                 branch="b", verify="v", home=None):
        state, bindir = tempfile.mkdtemp(), tempfile.mkdtemp()
        stub(bindir, "hc", FAKE)
        stub(bindir, "sleep", "#!/bin/sh\nexit 0\n")
        stub(bindir, "herdr", REFUSE)
        stub(bindir, "rex", REFUSE)
        repo = os.path.join(tempfile.mkdtemp(), "repo")
        os.mkdir(repo)
        self.top = os.path.realpath(repo)
        self.tmpdir = tempfile.mkdtemp()
        env = {k: v for k, v in os.environ.items() if not k.startswith(("REX_", "HERDR_", "HC_", "GIT_"))}
        env.update(PATH=bindir + os.pathsep + os.environ["PATH"], FAKE_HC=scenario, FAKE_STATE=state, FAKE_KIND=kind,
                   FAKE_TOP=self.top, FAKE_FIXTURES=os.path.join(HERE, "fixtures"), FAKE_NAME=name_for(kind, model or KINDS[kind]), HC_TERMINAL_ID="t1",
                   TMPDIR=self.tmpdir, HERDR_REVIEW_ARTIFACT_ROOTS=self.tmpdir, HERDR_REVIEW_DIR=self.tmpdir,
                   HOME=home or tempfile.mkdtemp())
        env.update(env_extra or {})
        kind_args = () if kind == "codex" else ("--kind", kind)
        model_args = ("--model", model) if model else ()
        r = subprocess.run(["bash", script, "--branch", branch, "--verify", verify, *kind_args, *model_args, *extra],
                           cwd=repo, env=env, capture_output=True, text=True)
        calls_path = os.path.join(state, "calls")
        calls = lines_of(calls_path)
        self.argv = [json.loads(line) for line in lines_of(os.path.join(state, "argv"))]
        self.other_hosts = lines_of(os.path.join(state, "other_hosts"))
        return r, calls

    def launch(self):
        a = next(a for a in self.argv if a[0] == "run")
        return a, a[a.index("--") + 1:]

    # A clean review, for each kind.

    def test_codex_reports_its_state_and_its_report_is_printed(self):
        r, calls = self.run_case("ok")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout, "REVIEW FINDINGS\n")
        self.assertNotIn("send", calls)   # the prompt went in as the launch task
        a, cmd = self.launch()
        for flag in ("--bg", "--json", "--no-notify"):
            self.assertIn(flag, a)
        self.assertEqual(a[a.index("--name") + 1], name_for("codex", "gpt-6-luna"))
        self.assertEqual(a[a.index("--cwd") + 1], self.top)
        self.assertEqual(cmd[:2], ["codex", "--no-daemon"])
        self.assertTrue(cmd[-1].startswith("Read AGENTS.md"))

    def test_the_finished_reviewer_is_killed_then_removed(self):
        r, calls = self.run_case("ok")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertLess(calls.index("kill"), calls.index("rm"))
        self.assertEqual([a[1] for a in self.argv if a[0] in ("kill", "rm")], ["t9", "t9"])

    def test_every_kind_finishes_a_review(self):
        for kind in KINDS:
            r, _ = self.run_case("ok", kind=kind)
            self.assertEqual(r.returncode, 0, kind + ": " + r.stdout + r.stderr)
            self.assertEqual(r.stdout, "REVIEW FINDINGS\n", kind)

    def test_kimi_gets_its_prompt_by_send_once_its_input_line_shows(self):
        r, calls = self.run_case("ok", kind="kimi")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        _, cmd = self.launch()
        self.assertEqual(cmd, ["kimi", "-m", "kimi-code/k3.1-pro", "-y"])
        sends = [a for a in self.argv if a[0] == "send"]
        self.assertEqual(len(sends), 1)
        self.assertTrue(sends[0][2].startswith("Read AGENTS.md"))
        self.assertNotIn("--force", sends[0])

    def test_a_reviewer_reporting_no_state_is_read_from_its_screen(self):
        r, _ = self.run_case("ok,unreported")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    # Startup.

    def test_kimis_folder_trust_for_this_work_tree_is_answered_once(self):
        r, calls = self.run_case("trustq", kind="kimi")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertLess(calls.index("keys"), calls.index("send"))
        self.assertIn("chose Trust and continue", r.stderr)

    def test_a_trust_dialog_that_stays_stops_after_one_answer(self):
        r, calls = self.run_case("trustq,stilltrust", kind="kimi")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(calls.count("keys"), 1)
        self.assertNotIn("send", calls)
        self.assertRegex(r.stdout.splitlines()[-2], r"still asks to trust")

    def test_a_first_message_hc_did_not_send_stops_without_resending(self):
        r, calls = self.run_case("ok,notsent")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("send", calls)
        self.assertNotIn("kill", calls)
        lines = r.stdout.splitlines()
        self.assertEqual(lines[-2], "Reviewer did not start: hc did not send the prompt to it.")
        self.assertRegex(lines[-1], r"^Next: answer it \(hc attach t9, or hc keys t9 <key>\)")

    def test_an_idle_earlier_reviewer_here_is_removed_and_replaced(self):
        r, calls = self.run_case("ok,holderidle")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual([a[1] for a in self.argv if a[0] == "kill"][0], "t7")
        self.assertLess(calls.index("kill"), calls.index("run"))

    def test_a_working_earlier_reviewer_here_is_another_review_and_stops(self):
        r, calls = self.run_case("ok,holderbusy")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("run", calls)
        self.assertNotIn("kill", calls)
        lines = r.stdout.splitlines()
        self.assertEqual(lines[-2], "Reviewer did not start: another review is running in t7; wait for it or close it.")
        self.assertRegex(lines[-1], r"^Next: hc wait t7 --timeout 3600 && ")

    def test_a_terminal_holding_the_name_in_another_directory_is_left_alone(self):
        r, calls = self.run_case("ok,holderelsewhere")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("run", calls)
        self.assertNotIn("kill", calls)

    # Questions, limits and failures.

    def test_a_blocked_reviewer_is_a_question_for_the_owner(self):
        r, calls = self.run_case("blocked")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("send", calls)
        self.assertNotIn("keys", calls)
        self.assertNotIn("kill", calls)   # left running, so the owner can answer it
        lines = r.stdout.splitlines()
        self.assertEqual(lines[-2], "No report at %s: the reviewer is waiting on a question." % self.report_path(r))
        self.assertRegex(lines[-1], r"^Next: answer it \(hc attach t9, or hc keys t9 <key>\), then run: hc wait t9 ")

    def test_a_question_on_an_unreported_screen_is_blocked_too(self):
        r, calls = self.run_case("blocked,unreported", kind="cursor")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("keys", calls)
        self.assertRegex(r.stdout.splitlines()[-2], r"waiting on a question")

    def test_a_usage_limit_names_the_next_reviewer(self):
        r, calls = self.run_case("limit", kind="cursor")
        self.assertEqual(r.returncode, 1)
        lines = r.stdout.splitlines()
        self.assertRegex(lines[-2], r"reviewer not available: it reports its usage limit")
        self.assertRegex(lines[-1], r"^Next: \S*pi-review\.sh --role independent ")

    def test_kimi_at_its_usage_limit_is_not_sent_the_prompt(self):
        r, calls = self.run_case("limit", kind="kimi")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("send", calls)
        lines = r.stdout.splitlines()
        self.assertEqual(lines[-2], "Reviewer not available: it reports its usage limit.")
        self.assertRegex(lines[-1], r"^Next: \S*pi-review\.sh --role independent ")

    def test_a_prompt_wrapped_in_kimis_input_box_is_unsent_and_gets_its_enter(self):
        # Cursor's HOLD on #81: the box's "│ >" line sits above the bottom twelve lines.
        r, calls = self.run_case("kimiwrapped", kind="kimi")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(calls.count("keys"), 1)

    def test_a_prompt_scrolled_inside_kimis_input_box_is_unsent_and_gets_its_enter(self):
        # Cursor's HOLD on #81: the visible "│ >" line is mid-prompt; the box ends with its last sentence.
        r, calls = self.run_case("kimiscrolled", kind="kimi")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(calls.count("keys"), 1)

    def test_a_busy_marker_above_kimis_tall_box_sends_no_enter(self):
        r, calls = self.run_case("kimiwrapped,busyabove", kind="kimi")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("keys", calls)

    def test_a_usage_limit_above_kimis_tall_box_ends_unavailable_without_an_enter(self):
        r, calls = self.run_case("kimiwrapped,limitabove", kind="kimi")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("keys", calls)
        self.assertRegex(r.stdout.splitlines()[-2], r"reviewer not available: it reports its usage limit")

    def test_a_prompt_left_unsent_gets_an_enter(self):
        r, calls = self.run_case("unsent,unreported", kind="cursor")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("keys", calls)

    def test_a_prompt_that_stays_unsent_stops_after_three_enters(self):
        r, calls = self.run_case("unsent,neverenter,unreported", kind="cursor")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(calls.count("keys"), 3)
        self.assertRegex(r.stdout.splitlines()[-2], r"stayed unsent after three Enters")

    def test_an_idle_reviewer_without_the_report_is_asked_once_for_it(self):
        r, _ = self.run_case("ok,noreport,obeys")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        sends = [a for a in self.argv if a[0] == "send"]
        self.assertEqual(len(sends), 1)
        self.assertTrue(sends[0][2].startswith("Write your final review report"))

    def test_a_reviewer_that_ignores_the_request_exits_1_with_the_reason(self):
        r, _ = self.run_case("ok,noreport")
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stdout.splitlines()[-2], r"finished without writing the report, even when asked")

    def report_path(self, r):
        return re.search(r"Report file: (\S+)", r.stderr).group(1)

    # Arguments, the hand-off and the private copy.

    def test_outside_an_hc_terminal_it_stops_with_the_reason(self):
        r, calls = self.run_case("ok", env_extra={"HC_TERMINAL_ID": ""})
        self.assertEqual(r.returncode, 1)
        self.assertEqual(calls, [])
        self.assertEqual(r.stdout.splitlines()[-2], "No review: checking for an hc terminal failed; the error is above.")

    def test_a_host_other_than_hc_is_a_bad_argument(self):
        r, calls = self.run_case("ok", extra=("--host", "rex"))
        self.assertEqual(r.returncode, 2)
        self.assertEqual(calls, [])

    def test_herdr_review_refuses_an_unknown_host_naming_all_three(self):
        r, calls = self.run_case("ok", script=HERDR_SCRIPT, extra=("--host", "tmux"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("--host must be herdr, rex or hc", r.stderr)

    def test_the_copy_is_removed(self):
        self.run_case("ok")
        self.assertEqual([f for f in os.listdir(self.tmpdir) if f.startswith("hc-review.")], [])

    def test_herdr_review_hands_off_in_an_hc_terminal(self):
        r, calls = self.run_case("ok", script=HERDR_SCRIPT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("run", calls)
        self.assertEqual(self.other_hosts, [])

    def test_herdr_tui_wins_over_hc(self):
        r, calls = self.run_case("ok", script=HERDR_SCRIPT, env_extra={"HERDR_WORKSPACE_ID": "w2"})
        self.assertEqual(calls, [])
        self.assertTrue(self.other_hosts and all(h.startswith("herdr ") for h in self.other_hosts), self.other_hosts)

    def test_rex_wins_over_hc(self):
        r, calls = self.run_case("ok", script=HERDR_SCRIPT, env_extra={"REX_SESSION": "session:s", "REX_BLOCK": "block:me"})
        self.assertEqual(calls, [])
        self.assertTrue(self.other_hosts and all(h.startswith("rex ") for h in self.other_hosts), self.other_hosts)

    def test_host_hc_wins_even_inside_herdr_tui(self):
        r, calls = self.run_case("ok", script=HERDR_SCRIPT, extra=("--host", "hc"), env_extra={"HERDR_WORKSPACE_ID": "w2"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("run", calls)
        self.assertEqual(self.other_hosts, [])

    def test_hc_and_herdr_launch_and_prompt_alike(self):
        # As test_rex_review.py does for Rex: the scripts stay separate files, so this runs both and
        # compares what each starts and sends, for every kind, a custom model and awkward arguments.
        spec = importlib.util.spec_from_file_location("test_herdr_review", os.path.join(HERE, "test_herdr_review.py"))
        herdr_tests = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(herdr_tests)
        branch, verify = "feat/x y;$(echo no)", "claims with 'quotes', \"doubles\", & | * $HOME"
        home = tempfile.mkdtemp()
        norm = lambda text: re.sub(r"exactly this path: \S+\. ", "exactly this path: <report>. ", text)
        for kind in KINDS:
            model = "custom-model-" + kind
            r, _ = self.run_case("ok", kind=kind, model=model, branch=branch, verify=verify, home=home)
            self.assertEqual(r.returncode, 0, kind + ": " + r.stdout + r.stderr)
            _, hc_launch = self.launch()
            if kind == "kimi":
                hc_prompt = next(a[2] for a in self.argv if a[0] == "send")
            else:
                hc_prompt, hc_launch = hc_launch[-1], hc_launch[:-1]
            hc_prompt = norm(hc_prompt)

            state, bindir = tempfile.mkdtemp(), tempfile.mkdtemp()
            stub(bindir, "herdr", herdr_tests.FAKE)
            stub(bindir, "sleep", "#!/bin/sh\nexit 0\n")
            repo = os.path.join(tempfile.mkdtemp(), "repo")
            os.mkdir(repo)
            label, name = herdr_tests.default_identity("repo")
            env = {k: v for k, v in os.environ.items() if not k.startswith(("REX_", "HERDR_", "HC_", "GIT_"))}
            env.update(PATH=bindir + os.pathsep + os.environ["PATH"], FAKE_HERDR="newtab,fresh", FAKE_STATE=state,
                       FAKE_LABEL=label, FAKE_NAME=name, HERDR_WORKSPACE_ID="w2", HOME=home,
                       TMPDIR=tempfile.mkdtemp(), HERDR_REVIEW_DIR=tempfile.mkdtemp())
            r = subprocess.run(["bash", HERDR_SCRIPT, "--branch", branch, "--verify", verify, "--kind", kind,
                                "--model", model], cwd=repo, env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            argv = [json.loads(line) for line in lines_of(os.path.join(state, "argv"))]
            start = next(a for a in argv if a[:2] == ["agent", "start"])
            herdr_launch = start[start.index("--") + 1:]
            herdr_prompt = norm(next(a for a in argv if a[:2] == ["agent", "prompt"])[3])
            binary = {"codex": ["codex", "--no-daemon"], "kimi": ["kimi"], "cursor": ["cursor-agent"]}[kind]
            self.assertEqual(hc_launch, binary + herdr_launch, kind)
            self.assertEqual(hc_prompt, herdr_prompt, kind)


if __name__ == "__main__":
    unittest.main()
