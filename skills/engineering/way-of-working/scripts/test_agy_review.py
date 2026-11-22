#!/usr/bin/env python3
"""agy-review.sh against a fake agy and a real throwaway git repository.

SAVED replays what agy 1.5.14 returned in the runs of 2026-11-22 (SOURCES.md 1q), each with the verdict it
must get. Conversation IDs and home paths are replaced, and long reviews are cut after their opening.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import textwrap
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "agy-review.sh")

LOCK = {"allowNonWorkspaceAccess": False,
        "permissions": {"deny": ["command(*)", "unsandboxed(*)", "mcp(*)", "write_file(*)", "read_url(*)"]}}

DENIED = ('jetski: no output produced — a tool required the "command" permission that headless mode cannot prompt '
          "for, so it was auto-denied. Add an allow-rule under permissions.allow in settings.json (e.g. "
          "command(<target>)). Alternatively, re-run with --dangerously-skip-permissions to auto-approve all tools.\n")
DENIED_READ = DENIED.replace('"command"', '"read_file"').replace("command(<target>)", "read_file(<target>)")
DENIED_JSON = ('{"conversation_id":"c","status":"SUCCESS","response":"","num_turns":1,'
               '"denied_actions":[{"action":"command","display_name":"Bash"}]}\n')
PLAN_FILE = "[implementation_plan.md](file:///home/u/.gemini/antigravity-cli/brain/c/implementation_plan.md)"
PLAN_SANDBOX = ("I wrote the implementation plan in %s. I have not run the command yet. Approve the plan when you "
                "are ready for me to run it.\n" % PLAN_FILE)
PLAN_NO_SANDBOX = ("I wrote the plan to %s. I have not run the command yet. If you want me to run it, approve the "
                   "plan.\n" % PLAN_FILE)
PLAN_JSON = json.dumps({"status": "SUCCESS", "response": PLAN_NO_SANDBOX}) + "\n"

# name: (stdout, stderr, agy's exit, the script's exit)
SAVED = {
    "plain-1, soft deny with 0 bytes": ("", DENIED, 0, 1),
    "plain-2, soft deny with 0 bytes": ("", DENIED, 0, 1),
    "diff-only, soft deny": ("", DENIED, 0, 1),
    "plain-json, SUCCESS with an empty response": (DENIED_JSON, DENIED, 0, 1),
    "probe-sandbox, approve my plan": (PLAN_SANDBOX, "", 0, 1),
    "probe-no-sandbox, approve my plan": (PLAN_NO_SANDBOX, "", 0, 1),
    "probe-json, SUCCESS with a plan": (PLAN_JSON, "", 0, 1),
    "forced-echo-sandbox, soft deny": ("", DENIED, 0, 1),
    "forced-echo-no-sandbox, soft deny": ("", DENIED, 0, 1),
    "one-line, a review": ("FIX\n\n## Findings\n", "", 0, 0),
    "read-only-1, a review": ("FIX\n\nEvery hunk in this diff introduces a defect.\n", "", 0, 0),
    "read-only-2, a review": ("FIX\n\nEvery one of the four edited files introduces a blocking defect.\n", "", 0, 0),
    "read-neutral-1, a review": ("FIX\n\nThis diff has five blocking defects.\n", "", 0, 0),
    "read-neutral-2, a review": ("FIX\n\nAll four hunks in this diff introduce defects.\n", "", 0, 0),
    "read-neutral-3, a review": ("FIX\n\nThis diff introduces four blocking defects.\n", "", 0, 0),
    "one-line, but agy exits 3 (its timeout)": ("FIX\n\n## Findings\n", "", 3, 1),
}

FAKE_AGY = textwrap.dedent(r'''
    #!/usr/bin/env python3
    import json, os, subprocess, sys
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    seen = {"argv": sys.argv[1:], "cwd": os.getcwd(), "head": head, "files": sorted(os.listdir(".")),
            "stdin": sys.stdin.read()}
    with open(os.environ["FAKE_SEEN"], "w") as f:
        json.dump(seen, f)
    sys.stdout.write(os.environ["FAKE_OUT"])
    sys.stderr.write(os.environ["FAKE_ERR"])
    sys.exit(int(os.environ["FAKE_CODE"]))
''').lstrip()


class AgyReview(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.bindir = self.folder("bin")
        with open(os.path.join(self.bindir, "agy"), "w") as f:
            f.write(FAKE_AGY)
        os.chmod(os.path.join(self.bindir, "agy"), 0o755)
        self.tmp = self.folder("tmp")
        self.seen_path = os.path.join(self.root, "seen.json")
        # A bare origin whose main is the base, and a clone two unpushed commits ahead of it.
        origin = os.path.join(self.root, "origin.git")
        self.work = os.path.join(self.root, "my work")   # a space in the path
        self.git("init", "-q", "--bare", "-b", "main", origin, cwd=self.root)
        self.git("clone", "-q", origin, self.work, cwd=self.root)
        self.git("checkout", "-q", "-b", "main")
        self.write("kept.txt", "unchanged copy of the rule\n")
        self.base = self.commit("base")
        self.git("push", "-q", "origin", "HEAD:main")
        self.git("fetch", "-q", "origin")
        self.git("checkout", "-q", "-b", "topic")
        self.write("changed.txt", "first change\n")
        self.first = self.commit("one")
        self.write("fix it.txt", "the fix\n")
        self.head = self.commit("two")

    def folder(self, name):
        path = os.path.join(self.root, name)
        os.mkdir(path)
        return path

    def env(self):
        # Host variables are dropped so a case never depends on the pane the tests run in.
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("GIT_", "HERDR_", "REX_", "HC_", "AGY_REVIEW_"))}
        env.update(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t",
                   GIT_CONFIG_GLOBAL=os.devnull)
        return env

    def git(self, *args, cwd=None):
        return subprocess.run(["git", *args], cwd=cwd or self.work, env=self.env(), check=True,
                              capture_output=True, text=True).stdout.strip()

    def write(self, name, body, mode="w"):
        with open(os.path.join(self.work, name), mode) as f:
            f.write(body)

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD")

    def review(self, *args, out="READY\n\nNo findings.\n", err="", code=0, extra=None, path=None):
        env = self.env()
        env.update(PATH=path or self.bindir + os.pathsep + os.environ["PATH"], TMPDIR=self.tmp,
                   FAKE_SEEN=self.seen_path, FAKE_OUT=out, FAKE_ERR=err, FAKE_CODE=str(code), **(extra or {}))
        if os.path.exists(self.seen_path):
            os.remove(self.seen_path)
        return subprocess.run(["bash", SCRIPT, *args], cwd=self.work, env=env, capture_output=True, text=True,
                              input="text waiting on stdin")

    def seen(self):
        with open(self.seen_path) as f:
            return json.load(f)

    def prompt(self):
        return next(a for a in self.seen()["argv"] if a.startswith("-p="))[3:]

    def assertUnavailable(self, r):
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        lines = r.stdout.splitlines()
        self.assertTrue(lines[-2].startswith("Reviewer not available: "), r.stdout)
        self.assertTrue(lines[-1].startswith("Next: "), r.stdout)

    def test_each_saved_output_gets_its_verdict(self):
        self.assertEqual(len(SAVED), 16)
        for name, (out, err, code, want) in SAVED.items():
            with self.subTest(name):
                r = self.review("--head", self.head, out=out, err=err, code=code)
                self.assertEqual(r.returncode, want, r.stdout + r.stderr)
                if want:
                    self.assertUnavailable(r)
                    self.assertIn(err, r.stderr)
                else:
                    self.assertEqual(r.stdout, out)

    def test_ready_passes_and_keeps_its_report(self):
        r = self.review("--head", self.head)
        self.assertEqual((r.returncode, r.stdout), (0, "READY\n\nNo findings.\n"))
        path = next(l for l in r.stderr.splitlines() if l.startswith("Report: "))[len("Report: "):]
        with open(path) as f:
            self.assertEqual(f.read(), r.stdout)

    def test_the_first_line_is_exact(self):
        for out in ("READY.\n", "\nREADY\n", " FIX\n", "**FIX**\n", "ready\n", "Here is the review.\nFIX\n"):
            with self.subTest(out=out):
                self.assertUnavailable(self.review("--head", self.head, out=out))

    def test_a_verdict_on_stderr_is_not_a_review(self):
        self.assertUnavailable(self.review("--head", self.head, out="", err="READY\n"))

    def test_stderr_never_enters_the_report(self):
        r = self.review("--head", self.head, out="FIX\nfinding\n", err="a warning\n")
        self.assertEqual((r.returncode, r.stdout), (0, "FIX\nfinding\n"))

    def test_agy_gets_the_pinned_flags_and_a_closed_stdin(self):
        self.review("--head", self.head)
        seen = self.seen()
        self.assertEqual(seen["argv"][0], "--settings")
        self.assertEqual(json.loads(seen["argv"][1]), LOCK)
        self.assertEqual(seen["argv"][2:-1], ["--model", "gemini-4-neon-xhigh", "--mode", "plan", "--sandbox",
                                              "--print-timeout", "1700s"])
        self.assertTrue(seen["argv"][-1].startswith("-p="))
        self.assertEqual(seen["stdin"], "")

    def test_it_reads_a_clone_of_the_commit_not_the_work_tree(self):
        self.write("private.env", "not committed\n")
        self.review("--head", self.first)
        seen = self.seen()
        self.assertEqual(seen["head"], self.first)
        self.assertNotEqual(os.path.realpath(seen["cwd"]), os.path.realpath(self.work))
        self.assertIn("kept.txt", seen["files"])      # an unchanged file, which it may read
        self.assertNotIn("private.env", seen["files"])
        self.assertNotIn("fix it.txt", seen["files"])

    def test_the_prompt_has_the_preamble_the_diff_and_the_changed_files(self):
        self.review("--head", self.head, "--verify", "the sweep is complete")
        p = self.prompt()
        self.assertTrue(p.startswith("You run headless. You may read files in this repository with your file-reading "
                                     "tool. You cannot run shell commands: never request one, because the request "
                                     "ends the run with no review. Do not write a plan file: your reply is the "
                                     "report itself.\n"))
        self.assertIn("Its first line is exactly READY or FIX.", p)
        self.assertIn("Read and search only the repository under review", p)
        self.assertIn("Verify: the sweep is complete.", p)
        self.assertIn("===== git diff origin/main...%s =====" % self.head, p)
        self.assertIn("+first change", p)
        self.assertIn("===== full text of changed.txt =====\nfirst change", p)
        self.assertIn("===== full text of fix it.txt =====\nthe fix", p)
        self.assertNotIn("full text of kept.txt", p)

    def test_since_reviews_only_the_fix(self):
        self.review("--head", self.head, "--since", self.first[:8])
        p = self.prompt()
        self.assertIn("===== git diff %s..%s =====" % (self.first, self.head), p)
        self.assertIn("+the fix", p)
        self.assertNotIn("first change", p)

    def test_a_binary_file_is_named_and_not_pasted(self):
        self.write("image.bin", b"\x00\x01\x02", mode="wb")
        head = self.commit("binary")
        self.assertEqual(self.review("--head", head).returncode, 0)
        self.assertIn("===== full text of image.bin =====\n(binary or empty: not shown)", self.prompt())

    def test_a_deleted_file_has_no_full_text(self):
        os.remove(os.path.join(self.work, "kept.txt"))
        head = self.commit("delete")
        self.assertEqual(self.review("--head", head).returncode, 0)
        self.assertNotIn("full text of kept.txt", self.prompt())
        self.assertIn("-unchanged copy of the rule", self.prompt())

    def test_long_files_are_left_to_the_file_reading_tool(self):
        self.write("long.txt", "same line\n" * 1000)
        mid = self.commit("long")
        self.write("long.txt", "one more\n", mode="a")
        head = self.commit("one line")
        r = self.review("--head", head, "--since", mid, extra={"AGY_REVIEW_MAX_BYTES": "4000"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("full text of", self.prompt())
        self.assertIn("Read each of them", self.prompt())
        self.assertIn("+one more", self.prompt())

    def test_a_diff_too_large_for_one_prompt_is_unavailable(self):
        self.assertUnavailable(self.review("--head", self.head, extra={"AGY_REVIEW_MAX_BYTES": "100"}))
        self.assertFalse(os.path.exists(self.seen_path))

    def test_an_empty_diff_never_gets_a_review(self):
        self.assertUnavailable(self.review("--head", self.base))
        self.assertFalse(os.path.exists(self.seen_path))

    def test_no_base_to_diff_against_is_unavailable(self):
        self.git("update-ref", "-d", "refs/remotes/origin/main")
        self.git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
        self.assertUnavailable(self.review("--head", self.head))

    def test_agy_missing_is_unavailable(self):
        tools = self.folder("tools")
        for tool in ("git", "dirname", "bash"):
            os.symlink(shutil.which(tool), os.path.join(tools, tool))
        r = self.review("--head", self.head, path=tools)
        self.assertUnavailable(r)
        self.assertIn("agy is not installed", r.stdout)

    def test_next_is_pi_outside_the_hosts(self):
        r = self.review("--head", self.head, "--since", self.first, out="")
        line = r.stdout.splitlines()[-1]
        self.assertIn("pi-review.sh --role independent --head %s --since %s --verify " % (self.head, self.first), line)

    def test_next_is_kimi_where_kimi_can_start(self):
        for var in ("HERDR_WORKSPACE_ID", "REX_SESSION", "HC_TERMINAL_ID"):
            with self.subTest(var):
                r = self.review("--head", self.head, out="", extra={var: "x"})
                self.assertIn("herdr-review.sh --kind kimi --branch topic --verify ", r.stdout.splitlines()[-1])

    def outside_file(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, True)
        path = os.path.join(folder, "outside log.txt")
        with open(path, "w") as f:
            f.write("evidence")
        return path

    def test_attached_evidence_is_readable_named_and_removed(self):
        outside = self.outside_file()
        self.review("--head", self.head, "--attach", outside)
        folder = re.search(r"The attached evidence is in (\S+?), listed", self.prompt()).group(1)
        with open(self.seen_path) as f:
            argv = json.load(f)["argv"]
        self.assertEqual(argv[argv.index("--add-dir") + 1], folder)
        self.assertFalse(os.path.exists(folder))

    def test_a_refused_outside_read_is_not_a_review(self):
        r = self.review("--head", self.head, out="", err=DENIED_READ)
        self.assertUnavailable(r)
        self.assertIn('"read_file" permission', r.stderr)

    def test_the_prompt_rules_out_outside_skills(self):
        self.review("--head", self.head)
        self.assertIn("load no skill and open no instruction file from outside them", self.prompt())

    def test_every_kind_of_run_is_locked(self):
        note = os.path.join(self.root, "note.txt")
        with open(note, "w") as f:
            f.write("evidence\n")
        for extra in ((), ("--since", self.first), ("--verify", "a claim"), ("--attach", note)):
            with self.subTest(extra=extra):
                self.review("--head", self.head, *extra)
                argv = self.seen()["argv"]
                self.assertEqual(argv.count("--settings"), 1)
                self.assertEqual(json.loads(argv[argv.index("--settings") + 1]), LOCK)
                self.assertNotIn("--dangerously-skip-permissions", argv)
                self.assertIn("Do not search the web", self.prompt())

    def test_next_keeps_the_attached_files(self):
        outside = self.outside_file()
        r = self.review("--head", self.head, "--attach", outside, out="")
        self.assertIn("--attach", r.stdout.splitlines()[-1])
        self.assertEqual([n for n in os.listdir(self.tmp) if n.startswith("review-evidence-")], [])

    def test_an_attach_that_is_not_there_is_a_bad_argument(self):
        r = self.review("--head", self.head, "--attach", "gone.txt")
        self.assertEqual(r.returncode, 2)
        self.assertIn("no such file or folder", r.stderr)

    def test_the_clone_is_removed_pass_or_fail(self):
        for out in ("READY\n", ""):
            with self.subTest(out=out):
                self.review("--head", self.head, out=out)
                self.assertFalse(os.path.exists(self.seen()["cwd"]))

    def test_bad_arguments_exit_2(self):
        for args in ((), ("--head",), ("--head", "nosuch"), ("--head", self.head, "--since", "nosuch"),
                     ("--head", self.head, "--role", "pr")):
            with self.subTest(args=args):
                self.assertEqual(self.review(*args).returncode, 2)


if __name__ == "__main__":
    unittest.main()
