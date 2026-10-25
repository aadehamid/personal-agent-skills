#!/usr/bin/env python3
"""Run rex-review.sh against a fake rex, once per case met when reviews ran in Rex by hand.

The fake rex on PATH reads the scenario from FAKE_REX, draws the reviewer's screen from
its state, and records each call, so a test can check the exit status and the rex calls.
"""
import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
import textwrap
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "rex-review.sh")
HERDR_SCRIPT = os.path.join(HERE, "herdr-review.sh")

FAKE = textwrap.dedent(r'''
    #!/usr/bin/env python3
    import json, os, re, sys
    s = os.environ["FAKE_REX"].split(",")
    state = os.environ["FAKE_STATE"]
    args = sys.argv[1:]
    def path(name): return os.path.join(state, name)
    def read(name, default=""):
        return open(path(name)).read() if os.path.exists(path(name)) else default
    def write(name, text): open(path(name), "w").write(text)
    def count(name):
        n = int(read(name, "0")) + 1; write(name, str(n)); return n
    def opt(name):
        return args[args.index(name) + 1] if name in args else None
    cmd = args[0] if args[0] in ("split", "run", "capture", "send", "send-key") else " ".join(args[:2])
    if cmd == "block call":
        cmd += " " + args[-1]
    with open(path("calls"), "a") as f: f.write(cmd + "\n")
    with open(path("argv"), "a") as f: f.write(json.dumps(args) + "\n")
    def out(obj): print(json.dumps(obj)); sys.exit(0)
    label = os.environ["FAKE_LABEL"]
    phase = read("phase", "start")
    report = read("report_path")
    if cmd == "block ls":
        blocks = [{"block_id": "block:me", "window_id": "win:1", "label": "shell"}]
        if "full" in s: blocks.append({"block_id": "block:other", "window_id": "win:1", "label": "shell"})
        if ("reuse" in s or "exited" in s) and not os.path.exists(path("closed")):
            blocks.append({"block_id": "block:rev", "window_id": "win:2", "label": label})
        out({"blocks": blocks})
    if cmd in ("split", "run"):
        write("phase", "startq" if "startq" in s else "ready")
        out({"block_ids": ["block:new"], **({"window_id": "win:3"} if cmd == "run" else {})})
    if cmd == "block close":
        write("closed", args[-1]); out({})
    if cmd == "block call process":
        dead = ("exited" in s and opt("-b") == "block:rev") or ("dies" in s and phase == "working")
        out({"foreground": {"name": "zsh" if dead else "kimi"}})
    if cmd == "block call program_status":
        if "reported" in s and phase in ("working", "idle"):
            out({"records": [{"state": "working" if phase == "working" else "idle"}]})
        out({"records": []})
    if cmd == "send":
        text = args[-1]
        m = re.search(r"exactly this path: (\S+)\. ", text)
        if text.startswith("Read AGENTS.md"):
            write("report_path", m.group(1)); write("phase", "sent"); write("enters", "0")
        elif text.startswith("Write your final review"):
            write("phase", "asked")
        out({})
    if cmd == "send-key":
        if phase in ("sent", "asked"):
            need = 2 if ("unsent" in s and phase == "sent") else 1
            if count("enters") >= need:
                if phase == "asked":
                    write("asked", "")
                write("phase", "working"); write("work", "1" if phase == "asked" else "2")
        out({})
    if cmd == "capture":
        n = count("captures")
        if phase == "startq":
            print("  Hooks need review\n  Press enter to confirm or esc to go back"); sys.exit(0)
        if phase in ("start", "ready"):
            print("  Reviewer ready\n\n │ >"); sys.exit(0)
        if phase == "sent":
            print(" │ > Read AGENTS.md and the repository's review standards file"); sys.exit(0)
        if phase == "working":
            if "question" in s:
                print("  Run this command?\n  → Run (once) (y)"); sys.exit(0)
            left = int(read("work", "0")) - 1
            write("work", str(left))
            if left <= 0:
                if "noreport" not in s or ("obeys" in s and os.path.exists(path("asked"))):
                    open(report, "w").write("REVIEW FINDINGS\n")
                write("phase", "idle")
            if "reported" in s:
                print("  quiet\n │ >"); sys.exit(0)   # no busy marker: only the reported status says working
            print("  thinking %d  ctrl+c to stop" % n); sys.exit(0)
        if phase == "idle":
            if "growing" in s and not os.path.exists(path("grew")):
                write("grew", ""); open(report, "a").write("MORE\n")
            print("  quiet\n │ >"); sys.exit(0)
        print("?"); sys.exit(0)
    print("unexpected " + cmd, file=sys.stderr); sys.exit(1)
''').lstrip()


def label_for(kind_model, repo="repo"):
    kind = kind_model.split(":")[0]
    return "review-%s-%s-%s" % (repo, kind, hashlib.sha1(kind_model.encode()).hexdigest()[:8])


class RexReview(unittest.TestCase):
    def run_case(self, scenario, extra=(), script=SCRIPT, env_extra=None, kind_model="codex:gpt-6-luna"):
        state = tempfile.mkdtemp()
        bindir = tempfile.mkdtemp()
        with open(os.path.join(bindir, "rex"), "w") as f:
            f.write(FAKE)
        os.chmod(os.path.join(bindir, "rex"), 0o755)
        with open(os.path.join(bindir, "sleep"), "w") as f:
            f.write("#!/bin/sh\nexit 0\n")
        os.chmod(os.path.join(bindir, "sleep"), 0o755)
        repo = os.path.join(tempfile.mkdtemp(), "repo")
        os.mkdir(repo)
        self.tmpdir = tempfile.mkdtemp()
        env = {k: v for k, v in os.environ.items() if not k.startswith(("REX_", "HERDR_", "GIT_"))}
        env.update(PATH=bindir + os.pathsep + os.environ["PATH"], FAKE_REX=scenario, FAKE_STATE=state,
                   FAKE_LABEL=label_for(kind_model), REX_SESSION="session:s", REX_BLOCK="block:me",
                   TMPDIR=self.tmpdir, HERDR_REVIEW_ARTIFACT_ROOTS=self.tmpdir, HERDR_REVIEW_DIR=self.tmpdir,
                   HOME=tempfile.mkdtemp())
        env.update(env_extra or {})
        r = subprocess.run(["bash", script, "--branch", "b", "--verify", "v", *extra],
                           cwd=repo, env=env, capture_output=True, text=True)
        calls_path = os.path.join(state, "calls")
        calls = open(calls_path).read().splitlines() if os.path.exists(calls_path) else []
        argv_path = os.path.join(state, "argv")
        self.argv = [json.loads(line) for line in open(argv_path)] if os.path.exists(argv_path) else []
        return r, calls

    def created_with(self, cmd):
        return next(a for a in self.argv if a[0] == cmd)

    def test_the_first_reviewer_opens_as_a_split_beside_this_pane(self):
        r, calls = self.run_case("ok")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout, "REVIEW FINDINGS\n")
        self.assertNotIn("run", calls)
        a = self.created_with("split")
        for pair in (["-b", "block:me"], ["--split=right"], ["--focus=false"], ["--label", label_for("codex:gpt-6-luna")]):
            self.assertTrue(any(a[i:i + len(pair)] == pair for i in range(len(a))), (pair, a))
        self.assertIn("Review pane: block:new (created)", r.stderr)

    def test_a_window_already_holding_two_panes_gets_a_new_tab(self):
        r, calls = self.run_case("ok,full")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("split", calls)
        self.assertIn("--focus=false", self.created_with("run"))

    def test_a_running_reviewer_in_its_labelled_pane_is_reused(self):
        r, calls = self.run_case("reuse")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("split", calls)
        self.assertNotIn("run", calls)
        self.assertIn("Review pane: block:rev (reused)", r.stderr)

    def test_a_labelled_pane_whose_reviewer_exited_is_closed_and_replaced(self):
        r, calls = self.run_case("exited")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("block close", calls)
        self.assertLess(calls.index("block close"), calls.index("split"))

    def test_each_kind_starts_with_herdr_reviews_flags(self):
        self.run_case("ok", extra=("--kind", "kimi"), kind_model="kimi:kimi-code/k3.1-pro")
        a = self.created_with("split")
        self.assertEqual(a[a.index("--") + 1:], ["kimi", "-m", "kimi-code/k3.1-pro", "-y"])
        self.run_case("ok", extra=("--kind", "cursor"), kind_model="cursor:cursor-grok-4.6-medium")
        a = self.created_with("split")
        self.assertEqual(a[a.index("--") + 1:], ["cursor-agent", "--model", "cursor-grok-4.6-medium",
                                                 "--sandbox", "enabled", "--force", "--trust"])

    def test_prompt_text_goes_first_and_enter_as_its_own_key(self):
        r, calls = self.run_case("ok")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        i = calls.index("send")
        self.assertEqual(calls[i + 1], "send-key")
        self.assertEqual(self.argv[[a[0] for a in self.argv].index("send-key")][-1], "enter")

    def test_a_prompt_left_on_the_input_line_gets_another_enter(self):
        r, calls = self.run_case("unsent")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(calls.count("send-key"), 2)
        self.assertIn("The prompt sat unsent on the input line; sent Enter.", r.stderr)

    def test_a_question_at_start_stops_before_the_prompt(self):
        r, calls = self.run_case("startq")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("send", calls)
        lines = r.stdout.splitlines()
        self.assertEqual(lines[-2], "Reviewer did not start: it is waiting on a question.")
        self.assertRegex(lines[-1], r"^Next: answer it \(rex send-key -s session:s -b block:new <key>\), then run: ")

    def test_a_question_after_the_prompt_ends_with_answer_then_wait(self):
        r, _ = self.run_case("question")
        self.assertEqual(r.returncode, 1)
        lines = r.stdout.splitlines()
        self.assertRegex(lines[-2], r"^No report at \S+: the reviewer is waiting on a question; no skill report")
        self.assertIn("Next: answer it (rex send-key", lines[-1])

    def test_an_idle_reviewer_without_the_report_is_asked_once_for_it(self):
        r, calls = self.run_case("noreport,obeys")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        sends = [a[-1] for a in self.argv if a[0] == "send"]
        self.assertEqual(len(sends), 2)
        self.assertTrue(sends[1].startswith("Write your final review report"))

    def test_a_reviewer_that_ignores_the_request_exits_1_with_the_reason(self):
        r, calls = self.run_case("noreport")
        self.assertEqual(r.returncode, 1)
        lines = r.stdout.splitlines()
        self.assertRegex(lines[-2], r"the reviewer finished without writing the report, even when asked")
        self.assertRegex(lines[-1], "^Next: " + re.escape(SCRIPT) + " --branch b --verify v $")

    def test_a_report_still_growing_is_printed_only_once_it_stops(self):
        r, _ = self.run_case("growing")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout, "REVIEW FINDINGS\nMORE\n")

    def test_a_reported_status_wins_over_a_quiet_screen(self):
        # The screen shows no busy marker while working; the OSC 7501 status says working.
        r, calls = self.run_case("reported")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len([a for a in self.argv if a[0] == "send"]), 1)

    def test_a_reviewer_that_exits_mid_review_says_run_again(self):
        r, _ = self.run_case("dies,noreport")
        self.assertEqual(r.returncode, 1)
        lines = r.stdout.splitlines()
        self.assertRegex(lines[-2], r"the reviewer exited")

    def test_outside_rex_it_stops_with_the_reason(self):
        r, calls = self.run_case("ok", env_extra={"REX_SESSION": ""})
        self.assertEqual(r.returncode, 1)
        self.assertEqual(calls, [])
        self.assertEqual(r.stdout.splitlines()[-2], "No review: checking for a Rex pane failed; the error is above.")

    def test_the_copy_is_removed(self):
        self.run_case("ok")
        self.assertEqual([f for f in os.listdir(self.tmpdir) if f.startswith("rex-review.")], [])

    def test_herdr_review_hands_off_inside_rex_outside_herdr(self):
        r, calls = self.run_case("ok", script=HERDR_SCRIPT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("split", calls)

    def test_herdr_review_hands_off_with_host_rex_even_inside_herdr(self):
        r, calls = self.run_case("ok", script=HERDR_SCRIPT, extra=("--host", "rex"),
                                 env_extra={"HERDR_WORKSPACE_ID": "w2"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("split", calls)

    def test_prompt_and_reviewer_flags_match_herdr_review(self):
        # One prompt and one set of flags: a change to either script must reach the other.
        def lines(path, pattern):
            return [l.strip() for l in open(path) if re.match(pattern, l.strip())]
        for pattern in (r'^prompt="', r'^roots=', r'^-a never', r'^-c "sandbox_workspace_write\.writable_roots'):
            self.assertEqual(lines(SCRIPT, pattern), lines(HERDR_SCRIPT, pattern), pattern)
        for flags in ('(-m "$model" -y)', '(--model "$model" --sandbox enabled --force --trust)',
                      '(-m "$model" -c model_reasoning_effort=medium'):
            self.assertIn(flags, open(SCRIPT).read())
            self.assertIn(flags, open(HERDR_SCRIPT).read())


if __name__ == "__main__":
    unittest.main()
