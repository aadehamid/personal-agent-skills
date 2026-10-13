#!/usr/bin/env python3
"""Run pi-review.sh against a fake ollama and gh and a real throwaway repository.

The fake ollama reads the scenario from FAKE_PI, finds the result path in the
prompt, and writes what the scenario says. The fake gh counts PR comments.
"""
import json
import os
import re
import stat
import subprocess
import tempfile
import textwrap
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pi-review.sh")

FAKE_OLLAMA = textwrap.dedent(r'''
    #!/usr/bin/env python3
    import json, os, re, sys
    s = os.environ["FAKE_PI"].split(",")
    state = os.environ["FAKE_STATE"]
    prompt = sys.argv[-1]
    open(os.path.join(state, "prompt"), "w").write(prompt)
    open(os.path.join(state, "cwd"), "w").write(os.getcwd())
    import subprocess
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    open(os.path.join(state, "clone_head"), "w").write(head)
    m = re.search(r"to exactly this path: (\S+)\. Its first line|Write the same first line, MERGE or HOLD, to (\S+)\.", prompt)
    path = m.group(1) or m.group(2)
    if "crash" in s:
        print("pi: model unavailable"); sys.exit(1)
    if "hang" in s:
        # Like `ollama launch`, the parent runs Pi as a child and waits for it, and does
        # not pass a signal on. The child would post its verdict late.
        import time
        child = os.fork()
        if child == 0:
            open(os.path.join(state, "pi_child"), "w").write(str(os.getpid()))
            time.sleep(30); open(path, "w").write("MERGE\nlate\n"); os._exit(0)
        os.waitpid(child, 0); sys.exit(0)
    if "nothing" in s:
        sys.exit(0)
    verdict = next((v for v in ("MERGE", "HOLD", "READY", "FIX", "Looks") if v.lower() in s), "MERGE")
    open(path, "w").write(verdict + "\nfindings\n")
    n = os.path.join(state, "comments.json")
    comments = json.load(open(n))
    if "other" in s:
        # Someone else comments while Pi works; it must not count as Pi's verdict.
        comments.append({"id": "c8", "body": "Thanks, looking now"})
    if "collide" in s:
        # Someone else posts the same one-word verdict, without Pi's mark.
        comments.append({"id": "c7", "body": verdict})
    if "headmoves" in s:
        # Someone pushes to the PR while Pi reviews.
        open(os.path.join(state, "moved_head"), "w").write("e" * 40)
    if "post" in s:
        mark = re.search(r"last line is exactly (<!-- \S+ -->)", prompt).group(1)
        said = "HOLD" if "postsother" in s else verdict
        comments.append({"id": "c9", "body": said + "\nfindings\n" + mark})
    json.dump(comments, open(n, "w"))
''').lstrip()

# The fake herdr runs the same fake Pi when it is prompted, and records each call.
FAKE_HERDR = textwrap.dedent(r'''
    #!/usr/bin/env python3
    import json, os, subprocess, sys
    s = os.environ["FAKE_PI"].split(",")
    state = os.environ["FAKE_STATE"]
    args = sys.argv[1:]
    with open(os.path.join(state, "herdr_calls"), "a") as f:
        f.write(json.dumps(args) + "\n")
    cmd = " ".join(args[:2])
    def out(obj):
        print(json.dumps(obj)); sys.exit(0)
    if cmd == "tab create":
        out({"result": {"tab": {"tab_id": "w2:t5"}, "root_pane": {"pane_id": "w2:p5"}}})
    if cmd == "pane get":
        out({"result": {"pane": {"agent": None if "nostart" in s else "pi"}}})
    if cmd == "agent prompt":
        cwd = open(os.path.join(state, "clone")).read()
        if "hang" in s:
            # Pi runs on in the pane's foreground group while the prompt times out.
            import time
            pi = subprocess.Popen(["ollama", "launch", "pi", args[3]], cwd=cwd, start_new_session=True)
            open(os.path.join(state, "pane_group"), "w").write(str(pi.pid))
            while not os.path.exists(os.path.join(state, "pi_child")):
                time.sleep(0.05)
            print("timeout"); sys.exit(1)
        subprocess.run(["ollama", "launch", "pi", args[3]], cwd=cwd)
        out({"result": {}})
    if cmd == "pane process-info":
        if "infofail" in s:
            sys.exit("error: pane not found")
        group = int(open(os.path.join(state, "pane_group")).read())
        # With "shellfront", the pane's shell is in front, as when Pi has already exited.
        out({"result": {"process_info": {"foreground_process_group_id": group,
                                         "shell_pid": group if "shellfront" in s else 1}}})
    if cmd == "pane run":
        open(os.path.join(state, "clone"), "w").write(json.loads(open(os.path.join(state, "herdr_calls")).read().splitlines()[0])[5])
        out({"result": {}})
    if cmd in ("pane read", "tab close"):
        print("pane text"); sys.exit(0)
    sys.exit("unexpected " + cmd)
''').lstrip()

# The fake gh logs every call and lists the PR's comments as "<id> <first line>".
FAKE_GH = textwrap.dedent(r'''
    #!/usr/bin/env python3
    import json, os, sys
    state = os.environ["FAKE_STATE"]
    with open(os.path.join(state, "gh_calls"), "a") as f:
        f.write(json.dumps(sys.argv[1:]) + "\n")
    if "headRefOid" in sys.argv:
        moved = os.path.join(state, "moved_head")
        print(open(moved).read() if os.path.exists(moved) else os.environ["FAKE_PR_HEAD"]); sys.exit(0)
    sys.stdout.write(json.dumps({"comments": json.load(open(os.path.join(state, "comments.json")))}))
''').lstrip()


class PiReview(unittest.TestCase):
    def setUp(self):
        self.state = tempfile.mkdtemp()
        with open(os.path.join(self.state, "comments.json"), "w") as f:
            json.dump([{"id": "c1", "body": "HOLD\nan earlier round"},
                       {"id": "c2", "body": "Some earlier note"}], f)
        self.bindir = tempfile.mkdtemp()
        for name, body in (("ollama", FAKE_OLLAMA), ("gh", FAKE_GH), ("herdr", FAKE_HERDR)):
            path = os.path.join(self.bindir, name)
            with open(path, "w") as f:
                f.write(body)
            os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
        # sleep is stubbed so waiting for Pi to start runs instantly. FAKE_SLEEP makes it
        # real for the hang cases: Pi's child must exist before the script stops the group,
        # or the case would pass without a child to stop.
        stub = os.path.join(self.bindir, "sleep")
        with open(stub, "w") as f:
            f.write('#!/bin/sh\n[ -n "$FAKE_SLEEP" ] && exec /bin/sleep "$FAKE_SLEEP"\nexit 0\n')
        os.chmod(stub, 0o755)
        # A bare origin with main and one pushed commit, and a working clone of it.
        root = tempfile.mkdtemp()
        self.origin = os.path.join(root, "origin.git")
        self.work = os.path.join(root, "work")
        env = self.git_env()
        run = lambda *a, cwd=root: subprocess.run(a, cwd=cwd, env=env, check=True, capture_output=True)
        run("git", "init", "-q", "--bare", "-b", "main", self.origin)
        run("git", "clone", "-q", self.origin, self.work)
        run("git", "commit", "-q", "--allow-empty", "-m", "base", cwd=self.work)
        run("git", "push", "-q", "origin", "HEAD:main", cwd=self.work)
        run("git", "commit", "-q", "--allow-empty", "-m", "change", cwd=self.work)
        run("git", "push", "-q", "origin", "HEAD:refs/heads/topic", cwd=self.work)
        self.head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.work, env=env,
                                   check=True, capture_output=True, text=True).stdout.strip()

    pr_head = None

    def git_env(self):
        # HERDR_* is dropped so a headless case never drives the real Herdr.
        env = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "HERDR_"))}
        env.update(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
                   GIT_COMMITTER_EMAIL="t@t", GIT_CONFIG_GLOBAL=os.devnull)
        return env

    def run_case(self, scenario, *args, herdr=False, polls=None, sleep=None):
        env = self.git_env()
        if polls:
            env["PI_REVIEW_POLLS"] = polls
        if sleep:
            env["FAKE_SLEEP"] = sleep
        env.setdefault("FAKE_PR_HEAD", self.pr_head or self.head)
        if herdr:
            env["HERDR_WORKSPACE_ID"] = "w2"
        env.update(PATH=self.bindir + os.pathsep + os.environ["PATH"], FAKE_PI=scenario,
                   FAKE_STATE=self.state)
        return subprocess.run(["bash", SCRIPT, *args], cwd=self.work, env=env,
                              capture_output=True, text=True)

    def prompt(self):
        with open(os.path.join(self.state, "prompt")) as f:
            return f.read()

    def test_pr_role_prints_the_verdict_after_posting(self):
        r = self.run_case("hold,post", "--role", "pr", "--pr", "7", "--head", self.head)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(r.stdout.startswith("HOLD\n"))
        self.assertIn("gh pr comment 7", self.prompt())

    def test_pr_verdict_without_a_posted_comment_fails(self):
        r = self.run_case("merge", "--role", "pr", "--pr", "7", "--head", self.head)
        self.assertEqual(r.returncode, 1)
        self.assertIn("posted no new comment", r.stdout)

    def gh_calls(self):
        path = os.path.join(self.state, "gh_calls")
        if not os.path.exists(path):
            return []
        with open(path) as f:
            return [json.loads(line) for line in f]

    def test_independent_role_writes_a_report_and_posts_nothing(self):
        r = self.run_case("fix", "--role", "independent", "--head", self.head)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(r.stdout.startswith("FIX\n"))
        self.assertIn("Post nothing anywhere", self.prompt())
        self.assertNotIn("gh pr comment", self.prompt())
        self.assertEqual(self.gh_calls(), [])

    def test_another_new_comment_is_not_taken_as_pis_verdict(self):
        r = self.run_case("merge,other", "--role", "pr", "--pr", "7", "--head", self.head)
        self.assertEqual(r.returncode, 1)
        self.assertIn("posted no new comment starting with 'MERGE'", r.stdout)

    def test_a_posted_verdict_that_differs_from_pis_file_does_not_count(self):
        r = self.run_case("merge,post,postsother", "--role", "pr", "--pr", "7", "--head", self.head)
        self.assertEqual(r.returncode, 1)

    def test_a_head_that_is_not_the_prs_head_stops_before_pi_runs(self):
        self.pr_head = "f" * 40
        r = self.run_case("merge,post", "--role", "pr", "--pr", "7", "--head", self.head)
        self.assertEqual(r.returncode, 1)
        self.assertIn("is not PR #7's head", r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.state, "prompt")))

    def test_a_short_head_is_accepted_as_the_prs_head(self):
        r = self.run_case("merge,post", "--role", "pr", "--pr", "7", "--head", self.head[:7])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        # The short SHA is expanded to the PR's full head before checkout and the prompt.
        self.assertIn(self.head, self.prompt())
        with open(os.path.join(self.state, "clone_head")) as f:
            self.assertEqual(f.read(), self.head)

    def test_a_head_that_moves_while_pi_reviews_is_not_a_current_verdict(self):
        r = self.run_case("merge,post,headmoves", "--role", "pr", "--pr", "7", "--head", self.head)
        self.assertEqual(r.returncode, 1)
        self.assertIn("head moved", r.stdout)

    def test_a_passed_run_removes_its_clone_and_a_failed_one_keeps_it(self):
        r = self.run_case("ready", "--role", "independent", "--head", self.head)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        clone = re.search(r"Clone: (\S+)", r.stderr).group(1)
        for leftover in (clone, clone + ".log", clone + ".report.md"):
            self.assertFalse(os.path.exists(leftover), leftover)
        r = self.run_case("merge,post", "--role", "pr", "--pr", "7", "--head", self.head)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        clone = re.search(r"Clone: (\S+)", r.stderr).group(1)
        for leftover in (clone, clone + ".log", clone + ".verdict"):
            self.assertFalse(os.path.exists(leftover), leftover)
        r = self.run_case("nothing", "--role", "independent", "--head", self.head)
        clone = re.search(r"Clone: (\S+)", r.stderr).group(1)
        self.assertTrue(os.path.exists(clone))
        self.assertTrue(os.path.exists(clone + ".log"))

    def test_someone_elses_matching_verdict_does_not_count_as_pis(self):
        r = self.run_case("merge,collide", "--role", "pr", "--pr", "7", "--head", self.head)
        self.assertEqual(r.returncode, 1)

    def test_an_old_comment_with_the_same_verdict_does_not_count(self):
        # c1 already says HOLD; Pi writes HOLD but posts nothing new.
        r = self.run_case("hold", "--role", "pr", "--pr", "7", "--head", self.head)
        self.assertEqual(r.returncode, 1)

    def test_independent_review_runs_on_a_commit_not_yet_pushed(self):
        env = self.git_env()
        subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "local only"], cwd=self.work, env=env, check=True)
        local = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.work, env=env, check=True,
                               capture_output=True, text=True).stdout.strip()
        r = self.run_case("ready", "--role", "independent", "--head", local)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = self.run_case("merge,post", "--role", "pr", "--pr", "7", "--head", local)
        self.assertEqual(r.returncode, 1)

    def assert_pi_child_stopped(self):
        # The child exists, so the case tested a running Pi, and is gone, so it cannot post.
        with open(os.path.join(self.state, "pi_child")) as f:
            child = int(f.read())
        with self.assertRaises(ProcessLookupError):
            os.kill(child, 0)

    def test_a_headless_pi_that_hangs_is_stopped_at_the_limit(self):
        r = self.run_case("hang", "--role", "independent", "--head", self.head, polls="10", sleep="0.2")
        self.assertEqual(r.returncode, 1)
        self.assertIn("did not finish within an hour", r.stdout)
        self.assert_pi_child_stopped()

    def test_inside_herdr_a_prompt_that_times_out_stops_pi(self):
        r = self.run_case("hang", "--role", "independent", "--head", self.head, herdr=True, sleep="0.05")
        self.assertEqual(r.returncode, 1)
        self.assertIn("Pi is stopped", r.stdout)
        self.assert_pi_child_stopped()
        self.assertNotIn(["tab", "close", "w2:t5"], self.herdr_calls())
        self.assertIn(["pane", "process-info", "--pane", "w2:p5"], self.herdr_calls())

    def pane_group(self):
        with open(os.path.join(self.state, "pane_group")) as f:
            return int(f.read())

    def test_inside_herdr_pi_that_cannot_be_found_is_not_reported_stopped(self):
        r = self.run_case("hang,infofail", "--role", "independent", "--head", self.head, herdr=True, sleep="0.05")
        try:
            self.assertEqual(r.returncode, 1)
            self.assertIn("could not be stopped: it may still post", r.stdout)
            self.assertNotIn("Pi is stopped", r.stdout)
        finally:
            os.killpg(self.pane_group(), 9)

    def test_inside_herdr_the_panes_own_shell_is_never_stopped(self):
        r = self.run_case("hang,shellfront", "--role", "independent", "--head", self.head, herdr=True, sleep="0.05")
        try:
            self.assertEqual(r.returncode, 1)
            # The group the fake reports as the shell's is left running.
            os.killpg(self.pane_group(), 0)
        finally:
            os.killpg(self.pane_group(), 9)

    def test_inside_herdr_a_failed_check_keeps_the_tab_open(self):
        r = self.run_case("merge", "--role", "pr", "--pr", "7", "--head", self.head, herdr=True)
        self.assertEqual(r.returncode, 1)
        self.assertNotIn(["tab", "close", "w2:t5"], self.herdr_calls())

    def test_no_result_fails(self):
        r = self.run_case("nothing", "--role", "independent", "--head", self.head)
        self.assertEqual(r.returncode, 1)
        self.assertIn("wrote no result", r.stdout)

    def test_a_crashed_pi_fails_with_its_log(self):
        r = self.run_case("crash", "--role", "independent", "--head", self.head)
        self.assertEqual(r.returncode, 1)
        self.assertIn("model unavailable", r.stdout)

    def test_a_result_without_a_verdict_line_fails(self):
        r = self.run_case("looks", "--role", "independent", "--head", self.head)
        self.assertEqual(r.returncode, 1)
        self.assertIn("not a verdict", r.stdout)

    def test_a_pr_verdict_word_in_the_independent_role_fails(self):
        r = self.run_case("merge", "--role", "independent", "--head", self.head)
        self.assertEqual(r.returncode, 1)
        self.assertIn("not a verdict", r.stdout)

    def test_pi_runs_in_a_fresh_clone_not_the_working_tree(self):
        r = self.run_case("ready", "--role", "independent", "--head", self.head)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(os.path.join(self.state, "cwd")) as f:
            cwd = f.read()
        self.assertNotEqual(os.path.realpath(cwd), os.path.realpath(self.work))
        self.assertTrue(os.path.basename(cwd).startswith("pi-review-"))
        with open(os.path.join(self.state, "clone_head")) as f:
            self.assertEqual(f.read(), self.head)

    def test_since_limits_the_review_to_the_fix(self):
        r = self.run_case("ready", "--role", "independent", "--head", self.head, "--since", "abc123")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(f"git diff abc123..{self.head}", self.prompt())

    def test_without_since_the_whole_change_is_reviewed_against_the_default_branch(self):
        r = self.run_case("ready", "--role", "independent", "--head", self.head)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertRegex(self.prompt(), rf"git diff origin/main\.\.\.{self.head}")

    def test_a_commit_found_nowhere_stops_before_pi_runs(self):
        r = self.run_case("ready", "--role", "independent", "--head", "0" * 40)
        self.assertEqual(r.returncode, 1)
        self.assertFalse(os.path.exists(os.path.join(self.state, "prompt")))

    def test_pr_role_needs_a_pr_number(self):
        r = self.run_case("merge,post", "--role", "pr", "--head", self.head)
        self.assertEqual(r.returncode, 2)

    def herdr_calls(self):
        path = os.path.join(self.state, "herdr_calls")
        if not os.path.exists(path):
            return []
        with open(path) as f:
            return [json.loads(line) for line in f]

    def test_headless_run_never_calls_herdr(self):
        r = self.run_case("ready", "--role", "independent", "--head", self.head)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.herdr_calls(), [])

    def test_inside_herdr_pi_runs_interactively_in_its_own_tab(self):
        r = self.run_case("hold,post", "--role", "pr", "--pr", "7", "--head", self.head, herdr=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(r.stdout.startswith("HOLD\n"))
        calls = self.herdr_calls()
        create = calls[0]
        self.assertEqual(create[:2], ["tab", "create"])
        self.assertEqual(create[create.index("--label") + 1], "pi-pr-work")
        self.assertTrue(os.path.basename(create[create.index("--cwd") + 1]).startswith("pi-review-"))
        run = next(c for c in calls if c[:2] == ["pane", "run"])
        self.assertEqual(run[3], "ollama launch pi --model glm-5.3-flash:cloud -y")
        prompt = next(c for c in calls if c[:2] == ["agent", "prompt"])
        self.assertIn("--wait", prompt)
        self.assertIn(["tab", "close", "w2:t5"], calls)
        self.assertIn("Pi tab: w2:t5", r.stderr)

    def test_inside_herdr_a_pi_that_never_starts_fails_and_keeps_its_tab(self):
        r = self.run_case("nostart", "--role", "independent", "--head", self.head, herdr=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("did not start", r.stdout)
        self.assertNotIn(["tab", "close", "w2:t5"], self.herdr_calls())

    def test_inside_herdr_no_result_keeps_the_tab_open_to_read(self):
        r = self.run_case("nothing", "--role", "independent", "--head", self.head, herdr=True)
        self.assertEqual(r.returncode, 1)
        self.assertNotIn(["tab", "close", "w2:t5"], self.herdr_calls())

    def test_verify_claims_reach_the_prompt(self):
        r = self.run_case("ready", "--role", "independent", "--head", self.head, "--verify", "the loader refuses bad keys")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Verify: the loader refuses bad keys.", self.prompt())

    def test_prompt_applies_review_standards_and_forbids_edits(self):
        self.run_case("ready", "--role", "independent", "--head", self.head)
        self.assertRegex(self.prompt(), r"review standards files .* and apply them")
        self.assertIn("Do not edit, create or delete any file", self.prompt())


if __name__ == "__main__":
    unittest.main()
