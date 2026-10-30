#!/usr/bin/env python3
"""Tests for stop-cursor-review.sh against a fake gh and a fake curl.

The fake gh answers `gh pr view` with FAKE_PR_HEAD, and the check runs of commit abc123 only from
FAKE_CHECK_RUNS, applying the script's own --jq filter with jq, so the filter itself is tested. Its labels behave
like a repository's: `pr edit --add-label` fails until `label create` has made the label (FAKE_LABEL_EXISTS starts
with it). It records every call. The fake curl reads its -K config from stdin, records the request and the
header it was given, and answers from FAKE_CURSOR: {"GET <path>" or "POST <path>": [code, body]}.
"""
import json
import os
import shutil
import stat
import subprocess
import tempfile
import textwrap
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
STOP = os.path.join(HERE, "stop-cursor-review.sh")
JQ = shutil.which("jq")
KEY = "key_test_0123456789"

FAKE_GH = textwrap.dedent(r'''
    #!/usr/bin/env python3
    import json, os, subprocess, sys
    state = os.environ["FAKE_STATE"]
    args = sys.argv[1:]
    with open(os.path.join(state, "gh"), "a") as f:
        f.write(" ".join(args) + "\n")
    if os.environ.get("FAKE_GH_HANGS") and args[0] == "api":
        import time
        time.sleep(30)
    label = os.path.join(state, "label_exists")
    if args[:2] == ["pr", "view"]:
        if os.environ.get("FAKE_PR_VIEW_FAILS"):
            sys.exit(1)
        print(os.environ.get("FAKE_PR_HEAD", "abc123def"))
        sys.exit(0)
    if args[0] == "api" and args[-3] == "repos/{owner}/{repo}/commits/abc123/check-runs":
        runs = os.environ.get("FAKE_CHECK_RUNS")
        if runs is None:
            sys.exit(1)
        jq = args[args.index("--jq") + 1]
        doc = json.dumps({"check_runs": json.loads(runs)})
        sys.exit(subprocess.run([os.environ["FAKE_JQ"], "-r", jq], input=doc, text=True).returncode)
    if args[:2] == ["label", "create"]:
        if os.environ.get("FAKE_LABEL_CREATE_FAILS"):
            sys.exit(1)
        open(label, "w").close()
        sys.exit(0)
    if args[:2] == ["pr", "edit"]:
        sys.exit(0 if os.path.exists(label) and not os.environ.get("FAKE_GH_EDIT_FAILS") else 1)
    sys.exit(2)                          # any other call, such as another commit's check runs
''').lstrip()

FAKE_CURL = textwrap.dedent(r'''
    #!/usr/bin/env python3
    import json, os, sys
    state = os.environ["FAKE_STATE"]
    args = sys.argv[1:]
    config = sys.stdin.read() if "-K" in args else ""
    method, url = args[args.index("-X") + 1], args[-1]
    path = url.split("://", 1)[1].split("/", 1)[1]
    with open(os.path.join(state, "curl"), "a") as f:
        f.write(json.dumps({"call": f"{method} /{path}", "argv": args, "config": config}) + "\n")
    answers = json.loads(os.environ.get("FAKE_CURSOR", "{}"))
    code, body = answers.get(f"{method} /{path}", [404, {}])
    open(args[args.index("-o") + 1], "w").write(json.dumps(body))
    sys.stdout.write(str(code))
''').lstrip()

# A command that fails when its FAKE_<NAME>_FAILS is set and otherwise runs the real one, for failures this system
# cannot stage (macOS mktemp ignores a missing TMPDIR, and BSD sed reads a directory without an error).
FAILING = textwrap.dedent(r'''
    #!/usr/bin/env bash
    name=$(basename "$0"); flag="FAKE_$(echo "$name" | tr a-z A-Z)_FAILS"
    [ -z "${!flag:-}" ] || { echo "$name: failed (fake)" >&2; exit 1; }
    exec "/usr/bin/$name" "$@"
''').lstrip()


def check_run(name, agent):
    return {"name": name, "details_url": f"https://cursor.com/agents/{agent}"}


@unittest.skipUnless(JQ, "jq is not installed")
class StopCursorReview(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        self.bin = os.path.join(self.dir, "bin")
        os.mkdir(self.bin)
        for name, text in (("gh", FAKE_GH), ("curl", FAKE_CURL), ("mktemp", FAILING), ("sed", FAILING), ("sort", FAILING)):
            path = os.path.join(self.bin, name)
            with open(path, "w") as f:
                f.write(text)
            os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)

    def run_stop(self, *args, env=None):
        base = {k: v for k, v in os.environ.items() if not k.startswith(("CURSOR_", "FAKE_", "GH_"))}
        base.update(PATH=self.bin + os.pathsep + os.environ["PATH"], FAKE_STATE=self.dir, FAKE_JQ=JQ,
                    HOME=self.dir, CURSOR_API_KEY=KEY, FAKE_LABEL_EXISTS="1")
        base.update(env or {})
        base = {k: v for k, v in base.items() if v is not None}
        label = os.path.join(self.dir, "label_exists")
        if base.get("FAKE_LABEL_EXISTS"):
            open(label, "w").close()
        elif os.path.exists(label):
            os.remove(label)
        return subprocess.run([STOP, "42", "abc123", *args], env=base, capture_output=True, text=True)

    def calls(self, tool):
        path = os.path.join(self.dir, tool)
        if not os.path.exists(path):
            return []
        with open(path) as f:
            lines = f.read().splitlines()
        return [json.loads(line) for line in lines] if tool == "curl" else lines

    def test_cancels_the_latest_run_of_each_bot_agent_on_the_head_and_labels_the_pr(self):
        runs = [check_run("Cursor Automation: Review pull requests", "bc-aaa"),
                check_run("Cursor Approval Agent: Router", "bc-zzz"),   # another agent: left alone
                {"name": "Cursor Bugbot", "details_url": "https://cursor.com/docs/bugbot"}]
        cursor = {"GET /v1/agents/bc-aaa": [200, {"status": "RUNNING", "latestRunId": "run-1"}],
                  "POST /v1/agents/bc-aaa/runs/run-1/cancel": [200, {}]}
        r = self.run_stop(env={"FAKE_CHECK_RUNS": json.dumps(runs), "FAKE_CURSOR": json.dumps(cursor)})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("cancelled run run-1 of agent bc-aaa", r.stdout)
        self.assertEqual([c["call"] for c in self.calls("curl")],
                         ["GET /v1/agents/bc-aaa", "POST /v1/agents/bc-aaa/runs/run-1/cancel"])
        self.assertIn("pr edit 42 --add-label review-takeover", self.calls("gh"))
        self.assertIn("api --paginate repos/{owner}/{repo}/commits/abc123/check-runs", " ".join(self.calls("gh")))

    def test_a_finished_run_is_not_a_problem(self):
        runs = [check_run("Cursor Automation: Review", "bc-aaa")]
        cursor = {"GET /v1/agents/bc-aaa": [200, {"latestRunId": "run-1"}],
                  "POST /v1/agents/bc-aaa/runs/run-1/cancel": [409, {"error": {"code": "run_not_cancellable"}}]}
        r = self.run_stop(env={"FAKE_CHECK_RUNS": json.dumps(runs), "FAKE_CURSOR": json.dumps(cursor)})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("had already finished", r.stdout)

    def test_the_key_never_reaches_a_command_line_or_the_output(self):
        runs = [check_run("Cursor Automation: Review", "bc-aaa")]
        cursor = {"GET /v1/agents/bc-aaa": [200, {"latestRunId": "run-1"}],
                  "POST /v1/agents/bc-aaa/runs/run-1/cancel": [200, {}]}
        r = self.run_stop(env={"FAKE_CHECK_RUNS": json.dumps(runs), "FAKE_CURSOR": json.dumps(cursor)})
        for call in self.calls("curl"):
            self.assertNotIn(KEY, " ".join(call["argv"]))
            self.assertIn(f"Bearer {KEY}", call["config"])
            argv = call["argv"]
            self.assertEqual(argv[argv.index("--max-time") + 1], "30")  # a hung API cannot hold up the stand-in
            self.assertIn("--connect-timeout", argv)
        self.assertNotIn(KEY, r.stdout + r.stderr)

    def test_the_key_comes_from_the_env_file_when_the_environment_has_none(self):
        os.makedirs(os.path.join(self.dir, ".config", "cursor"))
        sourced = os.path.join(self.dir, "sourced")
        with open(os.path.join(self.dir, ".config", "cursor", "api.env"), "w") as f:
            f.write(f"# Cursor\ntouch {sourced}\nexport CURSOR_API_KEY='key_from_file'\n")
        runs = [check_run("Cursor Automation: Review", "bc-aaa")]
        cursor = {"GET /v1/agents/bc-aaa": [200, {"latestRunId": "run-1"}],
                  "POST /v1/agents/bc-aaa/runs/run-1/cancel": [200, {}]}
        r = self.run_stop(env={"CURSOR_API_KEY": None, "FAKE_CHECK_RUNS": json.dumps(runs),
                               "FAKE_CURSOR": json.dumps(cursor)})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.exists(sourced), "the env file was run, not read")
        for call in self.calls("curl"):
            self.assertIn("Bearer key_from_file\"", call["config"])
            self.assertNotIn("key_from_file", " ".join(call["argv"]))
        self.assertNotIn("key_from_file", r.stdout + r.stderr)

    def test_each_failure_exits_3_says_what_and_still_labels(self):
        os.makedirs(os.path.join(self.dir, "a-directory"))
        os.makedirs(os.path.join(self.dir, ".config", "cursor"))
        with open(os.path.join(self.dir, ".config", "cursor", "api.env"), "w") as f:
            f.write("CURSOR_API_KEY=key_from_file\n")
        runs = json.dumps([check_run("Cursor Automation", "bc-aaa")])
        cases = {"no key": ({"CURSOR_API_KEY": None, "FAKE_CHECK_RUNS": runs, "CURSOR_API_ENV": "/no/such/file"}, "no Cursor API key"),
                 "no HOME": ({"CURSOR_API_KEY": None, "HOME": None, "FAKE_CHECK_RUNS": runs}, "no Cursor API key"),
                 "a directory as the key file": ({"CURSOR_API_KEY": None, "CURSOR_API_ENV": os.path.join(self.dir, "a-directory"),
                                                  "FAKE_CHECK_RUNS": runs}, "no Cursor API key"),
                 "the key file unreadable": ({"CURSOR_API_KEY": None, "FAKE_SED_FAILS": "1", "FAKE_CHECK_RUNS": runs},
                                             "no Cursor API key"),
                 "no temporary file": ({"FAKE_MKTEMP_FAILS": "1", "FAKE_CHECK_RUNS": runs}, "could not make a temporary file"),
                 "no check run": ({"FAKE_CHECK_RUNS": "[]"}, "nothing to stop"),
                 "gh fails": ({}, "could not read the check runs"),
                 "gh hangs": ({"FAKE_GH_HANGS": "1", "STOP_CURSOR_TIMEOUT": "1", "FAKE_CHECK_RUNS": runs},
                              "could not read the check runs"),
                 "agent unreadable": ({"FAKE_CHECK_RUNS": runs, "FAKE_CURSOR": json.dumps({"GET /v1/agents/bc-aaa": [401, {}]})},
                                      "no latest run to stop (HTTP 401)"),
                 "cancel refused": ({"FAKE_CHECK_RUNS": runs, "FAKE_CURSOR": json.dumps(
                     {"GET /v1/agents/bc-aaa": [200, {"latestRunId": "run-1"}],
                      "POST /v1/agents/bc-aaa/runs/run-1/cancel": [500, {}]})}, "returned HTTP 500")}
        for name, (env, message) in cases.items():
            with self.subTest(name):
                open(os.path.join(self.dir, "gh"), "w").close()
                open(os.path.join(self.dir, "curl"), "w").close()
                r = self.run_stop(env=env)
                self.assertEqual(r.returncode, 3, r.stderr)
                self.assertIn(message, r.stderr)
                self.assertIn("pr edit 42 --add-label review-takeover", self.calls("gh"))

    def test_an_agent_with_two_check_runs_is_stopped_once_without_sort(self):
        runs = [check_run("Cursor Automation: Review", "bc-aaa"), check_run("Cursor Automation: Review", "bc-aaa")]
        cursor = {"GET /v1/agents/bc-aaa": [200, {"latestRunId": "run-1"}],
                  "POST /v1/agents/bc-aaa/runs/run-1/cancel": [200, {}]}
        r = self.run_stop(env={"FAKE_SORT_FAILS": "1", "FAKE_CHECK_RUNS": json.dumps(runs), "FAKE_CURSOR": json.dumps(cursor)})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([c["call"] for c in self.calls("curl")],
                         ["GET /v1/agents/bc-aaa", "POST /v1/agents/bc-aaa/runs/run-1/cancel"])

    def test_a_missing_label_is_created_and_a_failed_label_exits_3(self):
        r = self.run_stop(env={"FAKE_LABEL_EXISTS": None, "FAKE_CHECK_RUNS": "[]"})
        labels = [c.split(" --")[0] for c in self.calls("gh") if c.startswith(("pr edit", "label create"))]
        self.assertEqual(labels, ["pr edit 42", "label create review-takeover", "pr edit 42"])  # add, create, add again
        self.assertIn("labelled #42", r.stdout)
        # a label that exists is added even when creating it again would fail
        r = self.run_stop(env={"FAKE_LABEL_CREATE_FAILS": "1", "FAKE_CHECK_RUNS": "[]"})
        self.assertIn("labelled #42", r.stdout)
        r = self.run_stop(env={"FAKE_GH_EDIT_FAILS": "1", "FAKE_CHECK_RUNS": "[]"})
        self.assertEqual(r.returncode, 3)
        self.assertIn("could not add the label", r.stderr)
        r = self.run_stop(env={"FAKE_LABEL_EXISTS": None, "FAKE_LABEL_CREATE_FAILS": "1", "FAKE_CHECK_RUNS": "[]"})
        self.assertEqual(r.returncode, 3)
        self.assertIn("could not add the label", r.stderr)

    def test_a_pull_request_at_another_head_is_left_alone(self):
        runs = [check_run("Cursor Automation: Review", "bc-aaa")]
        r = self.run_stop(env={"FAKE_PR_HEAD": "fff999", "FAKE_CHECK_RUNS": json.dumps(runs)})
        self.assertEqual(r.returncode, 4)
        self.assertIn("not abc123", r.stderr)
        self.assertEqual(self.calls("curl"), [])
        self.assertFalse(any(c.startswith(("pr edit", "label create")) for c in self.calls("gh")))

    def test_an_unreadable_pull_request_exits_3_and_touches_nothing(self):
        # Codex quick check of abe3f8f: a failed lookup is not a moved head, so the stand-in still starts (exit 3)
        runs = [check_run("Cursor Automation: Review", "bc-aaa")]
        r = self.run_stop(env={"FAKE_PR_VIEW_FAILS": "1", "FAKE_CHECK_RUNS": json.dumps(runs)})
        self.assertEqual(r.returncode, 3)
        self.assertIn("could not read pull request #42", r.stderr)
        self.assertEqual(self.calls("curl"), [])
        self.assertFalse(any(c.startswith(("pr edit", "label create")) for c in self.calls("gh")))

    def test_usage_errors_exit_64(self):
        self.assertEqual(subprocess.run([STOP, "42"], capture_output=True).returncode, 64)
        self.assertEqual(subprocess.run([STOP, "42", "abc", "--label"], capture_output=True).returncode, 64)


if __name__ == "__main__":
    unittest.main()
