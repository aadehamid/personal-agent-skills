#!/usr/bin/env python3
"""Tests for stop-cursor-review.sh against a fake gh and a fake curl.

The fake gh answers `gh api .../check-runs` from FAKE_CHECK_RUNS and applies the script's own --jq filter with
jq, so the filter itself is tested. It answers the label lookup from FAKE_LABEL_EXISTS and records every
`label create` and `pr edit`. The fake curl reads its -K config from stdin, records the request and the
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
    if args[0] == "api" and "/check-runs" in args[-3]:
        runs = os.environ.get("FAKE_CHECK_RUNS")
        if runs is None:
            sys.exit(1)
        jq = args[args.index("--jq") + 1]
        doc = json.dumps({"check_runs": json.loads(runs)})
        sys.exit(subprocess.run([os.environ["FAKE_JQ"], "-r", jq], input=doc, text=True).returncode)
    if args[0] == "api" and "/labels/" in args[1]:
        sys.exit(0 if os.environ.get("FAKE_LABEL_EXISTS") else 1)
    if args[:2] == ["label", "create"] or args[:2] == ["pr", "edit"]:
        sys.exit(int(os.environ.get("FAKE_GH_EDIT_FAILS", "0")))
    sys.exit(2)
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


def check_run(name, agent):
    return {"name": name, "details_url": f"https://cursor.com/agents/{agent}"}


@unittest.skipUnless(JQ, "jq is not installed")
class StopCursorReview(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        self.bin = os.path.join(self.dir, "bin")
        os.mkdir(self.bin)
        for name, text in (("gh", FAKE_GH), ("curl", FAKE_CURL)):
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
        self.assertNotIn(KEY, r.stdout + r.stderr)

    def test_the_key_comes_from_the_env_file_when_the_environment_has_none(self):
        os.makedirs(os.path.join(self.dir, ".config", "cursor"))
        with open(os.path.join(self.dir, ".config", "cursor", "api.env"), "w") as f:
            f.write("# Cursor\nexport CURSOR_API_KEY='key_from_file'\n")
        runs = [check_run("Cursor Automation: Review", "bc-aaa")]
        cursor = {"GET /v1/agents/bc-aaa": [200, {"latestRunId": "run-1"}],
                  "POST /v1/agents/bc-aaa/runs/run-1/cancel": [200, {}]}
        r = self.run_stop(env={"CURSOR_API_KEY": None, "FAKE_CHECK_RUNS": json.dumps(runs),
                               "FAKE_CURSOR": json.dumps(cursor)})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Bearer key_from_file\"", self.calls("curl")[0]["config"])

    def test_nothing_checkable_exits_3_and_still_labels(self):
        cases = {"no key": {"CURSOR_API_KEY": None, "FAKE_CHECK_RUNS": "[]"},
                 "no check run": {"FAKE_CHECK_RUNS": "[]"},
                 "gh fails": {},
                 "agent unreadable": {"FAKE_CHECK_RUNS": json.dumps([check_run("Cursor Automation", "bc-aaa")]),
                                      "FAKE_CURSOR": json.dumps({"GET /v1/agents/bc-aaa": [401, {}]})}}
        for name, env in cases.items():
            with self.subTest(name):
                open(os.path.join(self.dir, "gh"), "w").close()
                r = self.run_stop(env=env)
                self.assertEqual(r.returncode, 3, r.stderr)
                self.assertIn("pr edit 42 --add-label review-takeover", self.calls("gh"))

    def test_a_missing_label_is_created_and_a_failed_label_exits_3(self):
        r = self.run_stop(env={"FAKE_LABEL_EXISTS": None, "FAKE_CHECK_RUNS": "[]"})
        self.assertTrue(any(c.startswith("label create review-takeover") for c in self.calls("gh")))
        r = self.run_stop(env={"FAKE_GH_EDIT_FAILS": "1", "FAKE_CHECK_RUNS": "[]"})
        self.assertEqual(r.returncode, 3)
        self.assertIn("could not add the label", r.stderr)

    def test_usage_errors_exit_64(self):
        self.assertEqual(subprocess.run([STOP, "42"], capture_output=True).returncode, 64)
        self.assertEqual(subprocess.run([STOP, "42", "abc", "--label"], capture_output=True).returncode, 64)


if __name__ == "__main__":
    unittest.main()
