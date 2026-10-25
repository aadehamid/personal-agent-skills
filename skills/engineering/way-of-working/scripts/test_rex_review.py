#!/usr/bin/env python3
"""Run rex-review.sh against a fake rex, once per case met when reviews ran in Rex by hand,
and once per case the first independent review of the script found.

The fake rex on PATH reads the scenario from FAKE_REX, draws the reviewer's screen from its
state (each reviewer kind's own input line), and records each call, so a test can check the
exit status and the rex calls.
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
SCRIPT = os.path.join(HERE, "rex-review.sh")
HERDR_SCRIPT = os.path.join(HERE, "herdr-review.sh")

FAKE = textwrap.dedent(r'''
    #!/usr/bin/env python3
    import json, os, re, sys
    s = os.environ["FAKE_REX"].split(",")
    state = os.environ["FAKE_STATE"]
    kind, top = os.environ["FAKE_KIND"], os.environ["FAKE_TOP"]
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
    def fail(): print("rex: connection refused", file=sys.stderr); sys.exit(1)
    label = os.environ["FAKE_LABEL"]
    reused = any(x.startswith("reuse") for x in s)
    phase = read("phase", ("startq" if "reuseq" in s else "idleq" if "reuseidle" in s else "ready") if reused else "start")
    report = read("report_path")
    BIN = {"kimi": "kimi", "cursor": "cursor-agent", "codex": "codex"}[kind]
    def editor(text=""):
        # Each reviewer's input line as it looked on 2026-10-24 (Codex's placeholder is a stand-in).
        if kind == "kimi":
            return " ╭──╮\n │ > %s │\n ╰──╯\n  K3.1 Pro  context: 0%%" % text
        if kind == "cursor":
            return "  → %s\n\n  Auto" % (text or "Plan, search, build anything")
        return "  › %s\n\n  100%% context left" % (text or "Ask Codex to do anything")
    PROMPT_LINE = "Read AGENTS.md and the repository's review standards file"
    def fixture(name):
        return open(os.path.join(os.environ["FAKE_FIXTURES"], name)).read().rstrip("\n")
    if cmd == "block ls":
        blocks = [{"block_id": "block:me", "window_id": "win:1", "label": "shell"}]
        if "full" in s: blocks.append({"block_id": "block:other", "window_id": "win:1", "label": "shell"})
        if (reused or "exited" in s) and not os.path.exists(path("closed")):
            # "exitedhere": the stale review pane sits beside this agent's pane, in its window.
            blocks.append({"block_id": "block:rev", "window_id": "win:1" if "exitedhere" in s else "win:2", "label": label})
        out({"blocks": blocks})
    if cmd in ("split", "run"):
        first = "startq" if "startq" in s else "unknownq" if "unknownq" in s else \
            "migrateeditor" if "migrateeditor" in s else \
            "trustq" if any(x.startswith("trust") for x in s) else "ready"
        write("phase", first)
        out({"block_ids": ["block:new"], **({"window_id": "win:3"} if cmd == "run" else {})})
    if cmd == "block close":
        if "closefail" in s: fail()
        write("closed", args[-1]); out({})
    if cmd == "block call process":
        b = opt("-b")
        if "procfailreuse" in s and b == "block:rev": fail()
        if "procfailmid" in s and phase == "working": fail()
        if "procmalformed" in s and phase == "working": print("garbage"); sys.exit(0)
        # Valid JSON whose child is not an object (round 2, finding 2).
        if ("procbadchild" in s and phase == "working") or ("badchildreuse" in s and b == "block:rev"):
            out({"child": "not-an-object", "last_exit": None})
        child = {"name": BIN, "argv0": BIN, "path": "/opt/bin/" + BIN, "cwd": top}
        if "reuseelsewhere" in s and b == "block:rev": child["cwd"] = "/elsewhere/repo"
        if "nodechild" in s: child.update(name="node", argv0="node", path="/usr/local/bin/node")
        if ("slowstart" in s and b == "block:new" and count("process_looks") <= 3) or \
                ("diesatstart" in s and b == "block:new"):
            child = {"name": "zsh", "argv0": "-zsh", "path": "/bin/zsh", "cwd": top}
        if ("exited" in s and b == "block:rev") or ("dies" in s and phase == "working") or \
                ("gonepartial" in s and phase == "working" and int(read("work", "9")) <= 0):
            out({"child": None, "last_exit": {"code": 1}})
        out({"child": child, "foreground": child, "last_exit": None})
    if cmd == "block call program_status":
        if "reported" in s and phase in ("working", "idle"):
            out({"records": [{"state": "working" if phase == "working" else "idle"}]})
        out({"records": []})
    if cmd == "send":
        text = args[-1]
        m = re.search(r"exactly this path: (\S+)\. ", text)
        if text.startswith("Read AGENTS.md"):
            write("report_path", m.group(1)); write("phase", "sent"); write("enters", "0")
            write("prompt", text)
        elif text.startswith("Write your final review"):
            write("phase", "asked")
        out({})
    if cmd == "send-key":
        if phase == "trustq":
            write("phase", "ready"); out({})
        if phase in ("sent", "asked"):
            need = 99 if ("neverenter" in s or "mixed" in s) else 2 if ("unsent" in s and phase == "sent") else 1
            if count("enters") >= need:
                if phase == "asked":
                    write("asked", "")
                write("phase", "working")
                write("work", "1" if phase == "asked" else "4" if "quietwork" in s else "2")
        out({})
    if cmd == "capture":
        n = count("captures")
        if "capfail" in s and phase == "working": fail()
        if phase == "idleq" or (phase == "working" and "idleafter" in s):
            print(fixture("kimi-idle-session.txt")); sys.exit(0)
        if phase == "sent" and "kimiwrapped" in s:
            print(fixture("kimi-wrapped-prompt.txt")); sys.exit(0)
        if phase == "startq":
            print("  Hooks need review\n  Press enter to confirm or esc to go back"); sys.exit(0)
        if phase == "migrateeditor":
            # The question and its choices above Kimi's own empty input line (round 2, finding 4).
            print("  Migrate kimi-cli data to Kimi Code?\n  1. Migrate\n  2. Skip\n" + editor()); sys.exit(0)
        if phase == "unknownq":
            print("  Migrate kimi-cli data to Kimi Code?\n  1. Migrate   2. Skip"); sys.exit(0)
        if phase == "trustq":
            if "trustspoof" in s:
                print("  some text\n   ❯ Trust and continue\n     Exit"); sys.exit(0)
            where = "/elsewhere/repo" if ("trustelsewhere" in s or "trustdecoy" in s) else top
            # "trustdecoy": this work tree's path printed just above a dialog that names another.
            if "trustdecoy" in s: print("  " + top)
            print(" ───\n  Trust this folder?\n  ↑↓ navigate · Enter select · Esc exit\n \n"
                  "  %s\n \n  No project integrations or instructions to activate.\n \n"
                  "  Trust is remembered for this folder.\n  Tool approvals follow your permission settings.\n \n"
                  "   ❯ Trust and continue\n     Exit\n ───" % where); sys.exit(0)
        if phase in ("start", "ready"):
            print("  Reviewer ready\n\n" + editor()); sys.exit(0)
        if phase in ("sent", "asked"):
            pending = PROMPT_LINE if phase == "sent" else "Write your final review report"
            print(("  Run this command?\n" if "mixed" in s else "") + editor(pending)); sys.exit(0)
        if phase == "working" and "unknownmid" in s:
            open(report, "w").write("PARTIAL\n")
            print("  Migrate kimi-cli data to Kimi Code?\n  1. Migrate   2. Skip"); sys.exit(0)
        if phase == "working" and "midtrust" in s:
            print("  Trust this folder?\n \n  %s\n \n   \u276f Trust and continue\n     Exit" % top); sys.exit(0)
        if phase == "working":
            if "question" in s:
                print("  Run this command?\n  → Run (once) (y)"); sys.exit(0)
            left = int(read("work", "0")) - 1
            write("work", str(left))
            if "blockedpartial" in s or "gonepartial" in s:
                open(report, "w").write("PARTIAL\n")
                if "blockedpartial" in s:
                    print("  Run this command?\n  → Run (once) (y)"); sys.exit(0)
            if left <= 0 and "gonepartial" not in s:
                if "noreport" not in s or ("obeys" in s and os.path.exists(path("asked"))):
                    open(report, "w").write("REVIEW FINDINGS\n")
                write("phase", "idle")
            if "reported" in s or "quietwork" in s:
                print("  quiet\n" + editor()); sys.exit(0)   # no busy marker while it works
            print("  thinking %d  ctrl+c to stop\n" % n + editor()); sys.exit(0)
        if phase == "idle":
            if "growing" in s and not os.path.exists(path("grew")):
                write("grew", ""); open(report, "a").write("MORE\n")
            print("  quiet\n" + editor()); sys.exit(0)
        print("?"); sys.exit(0)
    print("unexpected " + cmd, file=sys.stderr); sys.exit(1)
''').lstrip()

KINDS = {"codex": "gpt-6-luna", "kimi": "kimi-code/k3.1-pro", "cursor": "cursor-grok-4.6-medium"}


def label_for(kind, model, top):
    top = os.path.realpath(top)
    return "review-%s-%s-%s-%s" % (os.path.basename(top), kind, hashlib.sha1(("%s:%s" % (kind, model)).encode()).hexdigest()[:8],
                                   hashlib.sha1(top.encode()).hexdigest()[:6])


def stub(bindir, name, text, mode=0o755):
    with open(os.path.join(bindir, name), "w") as f:
        f.write(text)
    os.chmod(os.path.join(bindir, name), mode)


class RexReview(unittest.TestCase):
    def run_case(self, scenario, extra=(), script=SCRIPT, env_extra=None, kind="codex", model=None,
                 branch="b", verify="v", home=None):
        state = tempfile.mkdtemp()
        bindir = tempfile.mkdtemp()
        stub(bindir, "rex", FAKE)
        stub(bindir, "sleep", "#!/bin/sh\nexit 0\n")
        repo = os.path.join(tempfile.mkdtemp(), "repo")
        os.mkdir(repo)
        self.top = os.path.realpath(repo)
        self.tmpdir = tempfile.mkdtemp()
        env = {k: v for k, v in os.environ.items() if not k.startswith(("REX_", "HERDR_", "GIT_"))}
        env.update(PATH=bindir + os.pathsep + os.environ["PATH"], FAKE_REX=scenario, FAKE_STATE=state,
                   FAKE_KIND=kind, FAKE_TOP=self.top, FAKE_FIXTURES=os.path.join(HERE, "fixtures"), FAKE_LABEL=label_for(kind, model or KINDS[kind], repo),
                   REX_SESSION="session:s", REX_BLOCK="block:me",
                   TMPDIR=self.tmpdir, HERDR_REVIEW_ARTIFACT_ROOTS=self.tmpdir, HERDR_REVIEW_DIR=self.tmpdir,
                   HOME=home or tempfile.mkdtemp())
        env.update(env_extra or {})
        kind_args = () if kind == "codex" and "--kind" not in extra else ("--kind", kind)
        model_args = ("--model", model) if model else ()
        r = subprocess.run(["bash", script, "--branch", branch, "--verify", verify, *kind_args, *model_args, *extra],
                           cwd=repo, env=env, capture_output=True, text=True)
        calls_path = os.path.join(state, "calls")
        calls = open(calls_path).read().splitlines() if os.path.exists(calls_path) else []
        argv_path = os.path.join(state, "argv")
        self.argv = [json.loads(line) for line in open(argv_path)] if os.path.exists(argv_path) else []
        self.state = state
        return r, calls

    def created_with(self, cmd):
        return next(a for a in self.argv if a[0] == cmd)

    def keys(self):
        return [a for a in self.argv if a[0] == "send-key"]

    # Layout and reuse.

    def test_the_first_reviewer_opens_as_a_split_beside_this_pane(self):
        r, calls = self.run_case("ok")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout, "REVIEW FINDINGS\n")
        self.assertNotIn("run", calls)
        a = self.created_with("split")
        for pair in (["-b", "block:me"], ["--split=right"], ["--focus=false"],
                     ["--label", label_for("codex", "gpt-6-luna", self.top)]):
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

    def test_a_closed_review_pane_in_this_window_frees_its_place_for_the_split(self):
        # Cursor's HOLD on PR #54: the window held this agent's pane and the stale review pane;
        # once that is closed, the window holds one pane, so the new reviewer is a split.
        r, calls = self.run_case("exited,exitedhere")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("block close", calls)
        self.assertIn("split", calls)
        self.assertNotIn("run", calls)

    def test_a_failed_close_stops_with_the_reason(self):
        r, calls = self.run_case("exited,closefail")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("split", calls)
        self.assertRegex(r.stdout.splitlines()[-2], r"could not be closed")

    def test_a_reviewer_in_another_directory_is_neither_reused_nor_closed(self):
        # Finding 12: the label alone does not prove the pane is this work tree's reviewer.
        r, calls = self.run_case("reuseelsewhere")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("block close", calls)
        self.assertNotIn("send", calls)
        self.assertNotIn("send-key", calls)
        self.assertRegex(r.stdout.splitlines()[-2], r"runs something else; it was left alone")

    def test_the_label_names_the_work_tree(self):
        self.run_case("ok")
        label = self.created_with("split")[self.created_with("split").index("--label") + 1]
        self.assertTrue(label.endswith("-" + hashlib.sha1(self.top.encode()).hexdigest()[:6]), label)

    def test_a_failed_process_query_on_a_labelled_pane_leaves_it_alone(self):
        # Finding 3: a query that fails is not a reviewer that exited.
        r, calls = self.run_case("reuse,procfailreuse")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("block close", calls)
        self.assertNotIn("split", calls)
        self.assertRegex(r.stdout.splitlines()[-2], r"rex cannot read the process of the pane block:rev")

    # Reviewer flags and the prompt.

    def test_each_kind_starts_with_herdr_reviews_flags(self):
        self.run_case("ok", kind="kimi")
        a = self.created_with("split")
        self.assertEqual(a[a.index("--") + 1:], ["kimi", "-m", "kimi-code/k3.1-pro", "-y"])
        self.run_case("ok", kind="cursor")
        a = self.created_with("split")
        self.assertEqual(a[a.index("--") + 1:], ["cursor-agent", "--model", "cursor-grok-4.6-medium",
                                                 "--sandbox", "enabled", "--force", "--trust"])

    def test_prompt_text_goes_first_and_enter_as_its_own_key(self):
        # Between them, one fresh look of the pane (round 2, finding 7).
        r, calls = self.run_case("ok")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        i = calls.index("send")
        self.assertEqual(calls[i + 1:i + 5], ["block call process", "block call program_status", "capture", "send-key"])
        self.assertEqual(self.keys()[0][-1], "enter")

    def test_a_reviewer_running_under_another_program_name_still_finishes(self):
        # The Cursor agent's pane title named node on 2026-10-24; a new pane is not judged by name.
        r, _ = self.run_case("nodechild", kind="cursor")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_every_kind_finishes_a_review(self):
        for kind in KINDS:
            r, _ = self.run_case("ok", kind=kind)
            self.assertEqual(r.returncode, 0, kind + ": " + r.stdout + r.stderr)

    # Startup: nothing is typed unless the reviewer's own input line shows.

    def test_a_question_at_start_stops_before_the_prompt(self):
        r, calls = self.run_case("startq")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("send", calls)
        self.assertNotIn("send-key", calls)
        lines = r.stdout.splitlines()
        self.assertEqual(lines[-2], "Reviewer did not start: it is waiting on a question or an unknown screen.")
        self.assertRegex(lines[-1], r"^Next: answer it \(rex send-key -s session:s -b block:new <key>\), then run: ")

    def test_an_unknown_setup_screen_gets_no_key(self):
        # Finding 9: a stable screen without the input line is a question, not a ready reviewer.
        r, calls = self.run_case("unknownq", kind="kimi")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("send", calls)
        self.assertNotIn("send-key", calls)
        self.assertEqual(r.stdout.splitlines()[-2], "Reviewer did not start: it is waiting on a question or an unknown screen.")

    def test_a_reused_pane_at_a_question_gets_no_prompt(self):
        # Finding 5: the readiness check runs for a reused pane too.
        r, calls = self.run_case("reuse,reuseq")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("send", calls)
        self.assertNotIn("send-key", calls)

    def test_kimis_folder_trust_for_this_work_tree_is_answered_once(self):
        r, calls = self.run_case("trustq", kind="kimi")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertLess(calls.index("send-key"), calls.index("send"))
        self.assertEqual(len(self.keys()), 2)   # the trust answer and the prompt's Enter
        self.assertIn("chose Trust and continue", r.stderr)

    def test_the_trust_dialog_under_another_kind_gets_no_key(self):
        # Finding 2: only Kimi's folder trust is answered.
        r, calls = self.run_case("trustq", kind="codex")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("send-key", calls)

    def test_trust_for_another_folder_gets_no_key(self):
        r, calls = self.run_case("trustelsewhere", kind="kimi")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("send-key", calls)

    def test_trust_needs_the_path_on_the_dialogs_own_line(self):
        # Round 2, finding 3: this work tree's path elsewhere on screen does not authorize a dialog
        # that names another folder.
        r, calls = self.run_case("trustdecoy", kind="kimi")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("send-key", calls)

    def test_a_question_above_kimis_empty_input_line_gets_no_prompt(self):
        # Round 2, finding 4: the migration question and its choices beat the ready input line.
        r, calls = self.run_case("migrateeditor", kind="kimi")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("send", calls)
        self.assertNotIn("send-key", calls)
        self.assertEqual(r.stdout.splitlines()[-2], "Reviewer did not start: it is waiting on a question or an unknown screen.")

    def test_a_spoofed_trust_choice_gets_no_key(self):
        r, calls = self.run_case("trustspoof", kind="kimi")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("send-key", calls)

    def test_codex_hook_review_is_not_answered(self):
        r, calls = self.run_case("startq")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("send-key", calls)

    def test_a_reviewer_still_starting_is_not_read_as_exited(self):
        r, _ = self.run_case("slowstart")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_a_reviewer_that_exits_at_start_says_so_after_ten_looks(self):
        r, calls = self.run_case("diesatstart")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout.splitlines()[-2], "Reviewer did not start: it exited.")
        self.assertEqual(calls.count("block call process"), 10)

    # The wait: precedence, bounds and the report.

    def test_a_prompt_left_on_the_input_line_gets_another_enter(self):
        r, calls = self.run_case("unsent")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(calls.count("send-key"), 2)
        self.assertIn("The prompt sat unsent on the input line; sent Enter.", r.stderr)

    def test_an_unsent_marker_beside_a_question_gets_no_key(self):
        # Finding 1: a question on screen wins over the unsent prompt; no Enter answers it. Round 2,
        # finding 7: the look right before the prompt's own Enter sees the question, so even that
        # Enter is held.
        r, _ = self.run_case("mixed")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(len(self.keys()), 0)
        self.assertIn("Held the Enter after typing: the pane shows blocked.", r.stderr)
        self.assertRegex(r.stdout.splitlines()[-2], r"the reviewer is waiting on a question")

    def test_a_prompt_wrapped_in_kimis_input_box_is_unsent_and_gets_its_enter(self):
        # The live screen of 2026-10-25 (fixtures/kimi-wrapped-prompt.txt): the prompt fills Kimi's
        # box over 20 lines, its "│ >" line 23 lines up. The first look after typing sees the
        # screen redrawing; the script looks again rather than holding the Enter, and reads the
        # box whole as the unsent prompt, not as a question.
        r, _ = self.run_case("kimiwrapped", kind="kimi")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("Held the Enter", r.stderr)
        self.assertEqual(len(self.keys()), 1)

    def test_kimis_idle_session_question_before_the_prompt_is_named_and_gets_no_key(self):
        r, calls = self.run_case("reuse,reuseidle", kind="kimi")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("send", calls)
        self.assertNotIn("send-key", calls)
        self.assertEqual(r.stdout.splitlines()[-2], "Reviewer did not start: Kimi asks how to resume an idle session.")

    def test_kimis_idle_session_question_after_the_prompt_is_named_and_gets_no_key(self):
        r, _ = self.run_case("idleafter", kind="kimi")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(len(self.keys()), 1)   # the prompt's own Enter only
        self.assertRegex(r.stdout.splitlines()[-2], r"^No report at \S+: Kimi asks how to resume an idle session\.$")

    def test_a_prompt_that_stays_unsent_stops_after_three_enters(self):
        # Finding 6.
        r, _ = self.run_case("neverenter")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(len(self.keys()), 4)
        lines = r.stdout.splitlines()
        self.assertRegex(lines[-2], r"the prompt stayed unsent after three Enters")
        self.assertRegex(lines[-1], "^Next: " + re.escape(SCRIPT) + " ")

    def test_a_question_after_the_prompt_ends_with_answer_then_wait(self):
        r, _ = self.run_case("question")
        self.assertEqual(r.returncode, 1)
        lines = r.stdout.splitlines()
        self.assertRegex(lines[-2], r"^No report at \S+: the reviewer is waiting on a question\.$")
        self.assertIn("Next: answer it (rex send-key", lines[-1])

    def test_a_partial_report_left_while_blocked_is_not_printed(self):
        # Finding 7.
        r, _ = self.run_case("blockedpartial")
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stdout.splitlines()[-2], r"waiting on a question; the file at the report path may be partial")
        self.assertNotRegex(r.stdout, r"(?m)^PARTIAL$")

    def test_a_partial_report_left_by_a_reviewer_that_exited_is_not_printed(self):
        r, _ = self.run_case("gonepartial")
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stdout.splitlines()[-2], r"the reviewer exited; the file at the report path may be partial")
        self.assertNotRegex(r.stdout, r"(?m)^PARTIAL$")

    def test_an_unknown_screen_mid_review_ends_blocked_without_the_partial_file(self):
        # Round 2, finding 1: unknown screens keep the blocked count, so the run ends blocked within
        # two minutes, and never prints the partial file.
        r, calls = self.run_case("unknownmid", kind="kimi")
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stdout.splitlines()[-2], r"waiting on a question; the file at the report path may be partial")
        self.assertNotRegex(r.stdout, r"(?m)^PARTIAL$")
        self.assertLess(calls.count("capture"), 100)

    def test_a_trust_dialog_mid_review_gets_no_key_and_ends_blocked(self):
        r, calls = self.run_case("midtrust", kind="kimi")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(len(self.keys()), 1)   # the prompt's own Enter only
        self.assertRegex(r.stdout.splitlines()[-2], r"the reviewer is waiting on a question")
        self.assertLess(calls.count("capture"), 100)

    def test_a_process_child_that_is_not_an_object_is_unreadable(self):
        # Round 2, finding 2: in the wait, and on a labelled pane before reuse.
        r, _ = self.run_case("procbadchild")
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stdout.splitlines()[-2], r"rex cannot read the reviewer's pane")
        r, calls = self.run_case("reuse,badchildreuse")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("block close", calls)
        self.assertRegex(r.stdout.splitlines()[-2], r"rex cannot read the process of the pane block:rev")

    def test_a_failed_process_query_mid_review_is_not_an_exit(self):
        # Finding 3: twelve failed looks end the wait as unreadable, never as exited.
        r, calls = self.run_case("procfailmid")
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stdout.splitlines()[-2], r"rex cannot read the reviewer's pane")
        self.assertNotIn("block close", calls)

    def test_a_malformed_process_answer_is_unreadable(self):
        r, _ = self.run_case("procmalformed")
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stdout.splitlines()[-2], r"rex cannot read the reviewer's pane")

    def test_a_failed_capture_is_unreadable_and_asks_for_nothing(self):
        # Finding 4.
        r, _ = self.run_case("capfail")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(len([a for a in self.argv if a[0] == "send"]), 1)
        self.assertRegex(r.stdout.splitlines()[-2], r"rex cannot read the reviewer's pane")

    def test_a_quiet_worker_is_not_asked_for_the_report_early(self):
        # Finding 11: four quiet looks with no busy marker and no reported status.
        r, _ = self.run_case("quietwork")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len([a for a in self.argv if a[0] == "send"]), 1)

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
        r, calls = self.run_case("reported")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len([a for a in self.argv if a[0] == "send"]), 1)

    def test_a_reviewer_that_exits_mid_review_says_run_again(self):
        r, _ = self.run_case("dies,noreport")
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stdout.splitlines()[-2], r"the reviewer exited")

    # Arguments, the hand-off and the private copy.

    def test_outside_rex_it_stops_with_the_reason(self):
        r, calls = self.run_case("ok", env_extra={"REX_SESSION": ""})
        self.assertEqual(r.returncode, 1)
        self.assertEqual(calls, [])
        self.assertEqual(r.stdout.splitlines()[-2], "No review: checking for a Rex pane failed; the error is above.")

    def test_an_option_without_a_value_is_a_bad_argument(self):
        # Finding 17, in both entry points.
        for script, env in ((SCRIPT, None), (HERDR_SCRIPT, {"HERDR_WORKSPACE_ID": "w2"})):
            r, calls = self.run_case("ok", script=script, extra=("--model",), env_extra=env)
            self.assertEqual(r.returncode, 2, script + ": " + r.stdout + r.stderr)
            self.assertEqual(calls, [])
            self.assertIn("--model needs a value", r.stderr)

    def test_a_host_other_than_rex_is_a_bad_argument(self):
        for script in (SCRIPT, HERDR_SCRIPT):
            r, calls = self.run_case("ok", script=script, extra=("--host", "tmux"))
            self.assertEqual(r.returncode, 2, script)
            self.assertEqual(calls, [])

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

    def test_both_hosts_launch_and_prompt_alike(self):
        # Finding 13: the two scripts stay separate files (each runs from a private copy of
        # itself, which sourcing a shared sibling would undo), so this runs both and compares
        # what each starts and sends, for every kind, a custom model and awkward arguments.
        spec = importlib.util.spec_from_file_location("test_herdr_review", os.path.join(HERE, "test_herdr_review.py"))
        herdr_tests = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(herdr_tests)
        branch, verify = "feat/x y;$(echo no)", "claims with 'quotes', \"doubles\", & | * $HOME"
        home = tempfile.mkdtemp()
        norm = lambda text: re.sub(r"exactly this path: \S+\. ", "exactly this path: <report>. ", text)
        for kind in KINDS:
            model = "custom-model-" + kind
            self.run_case("ok", kind=kind, model=model, branch=branch, verify=verify, home=home)
            split = self.created_with("split")
            rex_launch = split[split.index("--") + 1:]
            rex_prompt = norm(next(a[-1] for a in self.argv if a[0] == "send"))

            state, bindir = tempfile.mkdtemp(), tempfile.mkdtemp()
            stub(bindir, "herdr", herdr_tests.FAKE)
            stub(bindir, "sleep", "#!/bin/sh\nexit 0\n")
            repo = os.path.join(tempfile.mkdtemp(), "repo")
            os.mkdir(repo)
            label, name = herdr_tests.default_identity("repo")
            env = {k: v for k, v in os.environ.items() if not k.startswith(("REX_", "HERDR_", "GIT_"))}
            env.update(PATH=bindir + os.pathsep + os.environ["PATH"], FAKE_HERDR="newtab,fresh", FAKE_STATE=state,
                       FAKE_LABEL=label, FAKE_NAME=name, HERDR_WORKSPACE_ID="w2", HOME=home,
                       TMPDIR=tempfile.mkdtemp(), HERDR_REVIEW_DIR=tempfile.mkdtemp())
            r = subprocess.run(["bash", HERDR_SCRIPT, "--branch", branch, "--verify", verify, "--kind", kind,
                                "--model", model], cwd=repo, env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            argv = [json.loads(line) for line in open(os.path.join(state, "argv"))]
            start = next(a for a in argv if a[:2] == ["agent", "start"])
            herdr_launch = start[start.index("--") + 1:]
            herdr_prompt = norm(next(a for a in argv if a[:2] == ["agent", "prompt"])[3])
            binary = {"codex": "codex", "kimi": "kimi", "cursor": "cursor-agent"}[kind]
            self.assertEqual(rex_launch, [binary] + herdr_launch, kind)
            self.assertEqual(rex_prompt, herdr_prompt, kind)


if __name__ == "__main__":
    unittest.main()
