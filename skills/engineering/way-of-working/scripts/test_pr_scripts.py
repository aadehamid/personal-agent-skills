#!/usr/bin/env python3
"""Tests for watch-pr.sh (against a fake gh) and after-merge.sh (against real git repositories).

watch-pr.sh gets its gh answers from FAKE_GH_SEQ, one entry per poll: the pull
request document and its inline review comments, or null for a failed call. The fake
applies the script's own --jq filters with jq, so the filters themselves are tested.

after-merge.sh deletes branches, so each case builds a throwaway origin and clone and
checks what is left on both sides. A git wrapper on PATH injects the failures that
cannot be staged beforehand: an unreadable origin, a push that lands between the
ancestry check and the delete, and a local commit that lands before `branch -d`.
"""
import json
import os
import shutil
import stat
import subprocess
import tempfile
import textwrap
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
WATCH = os.path.join(HERE, "watch-pr.sh")
AFTER = os.path.join(HERE, "after-merge.sh")
REAL_GIT = shutil.which("git")


def working_jq():
    """The first jq on PATH that runs. A machine can carry a jq built for another CPU."""
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        candidate = os.path.join(directory, "jq")
        if os.access(candidate, os.X_OK):
            try:
                subprocess.run([candidate, "--version"], capture_output=True, check=True)
                return candidate
            except (OSError, subprocess.CalledProcessError):
                continue
    return None


JQ = working_jq()

FAKE_GH = textwrap.dedent(r'''
    #!/usr/bin/env python3
    import json, os, subprocess, sys
    seq = json.loads(os.environ["FAKE_GH_SEQ"])
    path = os.path.join(os.environ["FAKE_STATE"], "polls")
    polls = int(open(path).read()) if os.path.exists(path) else 0
    if sys.argv[1:3] == ["pr", "view"]:
        polls += 1
        open(path, "w").write(str(polls))
    entry = seq[min(polls, len(seq)) - 1]
    if entry is None:
        sys.exit(1)                      # a failed gh call
    doc = entry["pr"] if sys.argv[1] == "pr" else [{"id": i} for i in entry["inline"]]
    jq = sys.argv[sys.argv.index("--jq") + 1]
    sys.exit(subprocess.run([os.environ["FAKE_JQ"], "-r", jq], input=json.dumps(doc), text=True).returncode)
''').lstrip()

FAKE_GIT = textwrap.dedent(r'''
    #!/usr/bin/env python3
    import os, subprocess, sys
    real, hook, args = os.environ["REAL_GIT"], os.environ.get("FAKE_GIT_HOOK", ""), sys.argv[1:]
    if hook == "ls-remote-fails" and args[:1] == ["ls-remote"]:
        sys.exit(128)
    if (hook == "push-races-delete" and args[:1] == ["push"] and "--delete" in args) or \
       (hook == "commit-races-branch-d" and args[:2] == ["branch", "-d"]):
        subprocess.run(["sh", "-c", os.environ["FAKE_GIT_HOOK_CMD"]], check=True)
    os.execv(real, [real] + args)
''').lstrip()


def write_exe(directory, name, body):
    path = os.path.join(directory, name)
    with open(path, "w") as f:
        f.write(body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)


def poll(state="OPEN", reviews=(), comments=(), inline=(), checks=()):
    return {"pr": {"state": state, "reviews": [{"id": r} for r in reviews],
                   "comments": [{"id": c} for c in comments], "statusCheckRollup": list(checks)},
            "inline": list(inline)}


def run_check(status, conclusion="", completed=""):
    return {"name": "ci", "status": status, "conclusion": conclusion, "completedAt": completed}


@unittest.skipUnless(JQ, "jq is needed to apply the script's filters")
class WatchPr(unittest.TestCase):
    def run_watch(self, seq):
        state, bindir = tempfile.mkdtemp(), tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, state, True)
        self.addCleanup(shutil.rmtree, bindir, True)
        write_exe(bindir, "gh", FAKE_GH)
        write_exe(bindir, "sleep", "#!/bin/sh\nexit 0\n")
        env = dict(os.environ, PATH=bindir + os.pathsep + os.environ["PATH"],
                   FAKE_GH_SEQ=json.dumps(seq), FAKE_STATE=state, FAKE_JQ=JQ)
        r = subprocess.run(["bash", WATCH, "7"], env=env, capture_output=True, text=True, timeout=30)
        with open(os.path.join(state, "polls")) as f:
            return r, int(f.read())

    def assertWakes(self, seq, polls, event):
        r, n = self.run_watch(seq)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(n, polls, r.stdout)
        self.assertIn(event, r.stdout.splitlines())
        return r

    def test_already_merged_exits_at_once(self):
        r, n = self.run_watch([poll("MERGED")])
        self.assertEqual((r.returncode, n), (0, 1))
        self.assertIn("start: state:MERGED", r.stdout)

    def test_already_closed_exits_at_once(self):
        r, n = self.run_watch([poll("CLOSED")])
        self.assertEqual((r.returncode, n), (0, 1))

    def test_a_merge_wakes(self):
        self.assertWakes([poll(), poll(), poll("MERGED")], 3, "state:MERGED")

    def test_a_close_wakes(self):
        self.assertWakes([poll(), poll("CLOSED")], 2, "state:CLOSED")

    def test_a_check_that_starts_does_not_wake_but_one_that_finishes_does(self):
        self.assertWakes([poll(), poll(checks=[run_check("QUEUED")]), poll(checks=[run_check("IN_PROGRESS")]),
                          poll(checks=[run_check("COMPLETED", "SUCCESS", "T1")])], 4, "check:ci:SUCCESS:T1")

    def test_a_rerun_starting_does_not_wake(self):
        done = run_check("COMPLETED", "SUCCESS", "T1")
        r = self.assertWakes([poll(checks=[done]), poll(checks=[run_check("QUEUED")]), poll("MERGED")],
                             3, "state:MERGED")
        self.assertNotIn("check:", r.stdout)

    def test_a_rerun_with_the_same_result_wakes(self):
        self.assertWakes([poll(checks=[run_check("COMPLETED", "SUCCESS", "T1")]),
                          poll(checks=[run_check("COMPLETED", "SUCCESS", "T2")])], 2, "check:ci:SUCCESS:T2")

    def test_a_pending_commit_status_does_not_wake(self):
        self.assertWakes([poll(), poll(checks=[{"context": "ci", "state": "PENDING", "startedAt": "T1"}]),
                          poll(checks=[{"context": "ci", "state": "FAILURE", "startedAt": "T1"}])],
                         3, "status:ci:FAILURE:T1")

    def test_a_new_review_wakes(self):
        self.assertWakes([poll(reviews=["R1"]), poll(reviews=["R1", "R2"])], 2, "review:R2")

    def test_a_new_conversation_comment_wakes(self):
        self.assertWakes([poll(), poll(comments=["C1"])], 2, "comment:C1")

    def test_a_new_inline_review_comment_wakes(self):
        self.assertWakes([poll(inline=[1]), poll(inline=[1]), poll(inline=[1, 2])], 3, "inline:2")

    def test_ten_failures_in_a_row_stop_the_watch(self):
        r, n = self.run_watch([None])
        self.assertEqual((r.returncode, n), (1, 10))
        self.assertIn("gh failed 10 times in a row", r.stderr)

    def test_a_success_resets_the_failure_count(self):
        seq = [poll()] + [None] * 9 + [poll()] + [None] * 9 + [poll(comments=["C1"])]
        self.assertWakes(seq, 21, "comment:C1")


class AfterMerge(unittest.TestCase):
    def setUp(self):
        self.build()

    def build(self):
        """A bare origin and a clone with branch feat pushed. Reads os.environ when called."""
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        # Git sets GIT_DIR and others for hooks; inherited, they would point these
        # test repositories at the repository being pushed.
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self.env.update(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com", GIT_COMMITTER_NAME="t",
                        GIT_COMMITTER_EMAIL="t@example.com", GIT_CONFIG_GLOBAL=os.devnull,
                        GIT_CONFIG_NOSYSTEM="1")
        self.origin = os.path.join(self.tmp, "origin.git")
        self.git(self.tmp, "init", "--quiet", "--bare", "-b", "main", self.origin)
        self.repo = os.path.join(self.tmp, "repo")
        self.git(self.tmp, "clone", "--quiet", self.origin, self.repo)
        self.commit("base")
        self.git(self.repo, "push", "--quiet", "origin", "HEAD:main")
        self.git(self.repo, "switch", "--quiet", "-c", "feat")
        self.commit("feature")
        self.git(self.repo, "push", "--quiet", "-u", "origin", "feat")

    def git(self, cwd, *args):
        return subprocess.run(["git", *args], cwd=cwd, env=self.env, check=True,
                              capture_output=True, text=True).stdout.strip()

    def commit(self, name, repo=None):
        repo = repo or self.repo
        with open(os.path.join(repo, name), "w") as f:
            f.write(name)
        self.git(repo, "add", name)
        self.git(repo, "commit", "--quiet", "-m", name)

    def clone(self, name, *args):
        path = os.path.join(self.tmp, name)
        self.git(self.tmp, "clone", "--quiet", *args, self.origin, path)
        return path

    def merge_on_origin(self, squash=False):
        """Merge feat into main the way a review bot would, from a separate clone."""
        other = self.clone("other")
        if squash:
            self.git(other, "merge", "--quiet", "--squash", "origin/feat")
            self.git(other, "commit", "--quiet", "-m", "squash")
        else:
            self.git(other, "merge", "--quiet", "--no-ff", "-m", "merge", "origin/feat")
        self.git(other, "push", "--quiet", "origin", "main")

    def run_after(self, *args, hook="", hook_cmd=""):
        bindir = tempfile.mkdtemp(dir=self.tmp)
        write_exe(bindir, "git", FAKE_GIT)
        env = dict(self.env, PATH=bindir + os.pathsep + self.env["PATH"], REAL_GIT=REAL_GIT,
                   FAKE_GIT_HOOK=hook, FAKE_GIT_HOOK_CMD=hook_cmd)
        return subprocess.run(["bash", AFTER, *args], cwd=self.repo, env=env,
                              capture_output=True, text=True, timeout=60)

    def branches(self):
        local = self.git(self.repo, "branch", "--format=%(refname:short)").split()
        remote = self.git(self.repo, "ls-remote", "--heads", "origin")
        return local, "refs/heads/feat" in remote

    def test_merged_branch_is_deleted_on_both_sides(self):
        self.merge_on_origin()
        r = self.run_after("feat")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.branches(), (["main"], False))
        self.assertEqual(self.git(self.repo, "rev-parse", "HEAD"), self.git(self.repo, "rev-parse", "origin/main"))

    def test_squash_merge_deletes_nothing(self):
        self.merge_on_origin(squash=True)
        r = self.run_after("feat")
        self.assertEqual(r.returncode, 1)
        self.assertIn("local feat has commits that are not in main", r.stderr)
        self.assertEqual(self.branches(), (["feat", "main"], True))

    def test_commit_pushed_after_the_merge_keeps_the_remote_branch(self):
        self.merge_on_origin()
        late = self.clone("late", "-b", "feat")
        self.commit("late", late)
        self.git(late, "push", "--quiet", "origin", "feat")
        r = self.run_after("feat")
        self.assertEqual(r.returncode, 1)
        self.assertIn("origin/feat has commits that are not in main", r.stderr)
        self.assertTrue(self.branches()[1])

    def test_push_racing_the_delete_is_refused_by_the_lease(self):
        self.merge_on_origin()
        late = self.clone("late", "-b", "feat")
        r = self.run_after("feat", hook="push-races-delete", hook_cmd=(
            f"cd '{late}' && git commit --quiet --allow-empty -m race && git push --quiet origin feat"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("stale info", r.stderr)
        remote = self.git(self.repo, "ls-remote", "origin", "refs/heads/feat").split()[0]
        self.assertEqual(remote, self.git(late, "rev-parse", "HEAD"))

    def test_commit_racing_the_local_delete_is_refused_by_branch_d(self):
        self.merge_on_origin()
        r = self.run_after("feat", hook="commit-races-branch-d", hook_cmd=(
            f"cd '{self.repo}' && c=$(git commit-tree feat^{{tree}} -p feat -m race) && "
            "git update-ref refs/heads/feat $c"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("feat", self.git(self.repo, "branch", "--format=%(refname:short)").split())

    def test_local_commit_not_in_the_base_deletes_nothing(self):
        self.merge_on_origin()
        self.commit("unpushed")
        r = self.run_after("feat")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.branches(), (["feat", "main"], True))

    def test_remote_already_deleted_still_deletes_the_local_branch(self):
        self.merge_on_origin()
        self.git(self.repo, "push", "--quiet", "origin", "--delete", "feat")
        r = self.run_after("feat")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("origin/feat is already gone", r.stdout)
        self.assertEqual(self.branches(), (["main"], False))

    def test_failed_remote_lookup_is_not_taken_for_a_deleted_branch(self):
        self.merge_on_origin()
        r = self.run_after("feat", hook="ls-remote-fails")
        self.assertEqual(r.returncode, 1)
        self.assertIn("could not read origin (git ls-remote exited 128)", r.stderr)
        self.assertEqual(self.branches(), (["feat", "main"], True))

    def test_base_branch_is_refused(self):
        r = self.run_after("main")
        self.assertEqual(r.returncode, 2)

    def test_inherited_git_variables_cannot_reach_another_repository(self):
        decoy = os.path.join(tempfile.mkdtemp(), "decoy.git")
        self.addCleanup(shutil.rmtree, os.path.dirname(decoy), True)
        subprocess.run(["git", "init", "--quiet", "--bare", decoy], check=True,
                       env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")})

        def snapshot():
            return sorted((root, files) for root, _, files in os.walk(decoy))

        before = snapshot()
        with mock.patch.dict(os.environ, GIT_DIR=decoy, GIT_WORK_TREE=os.path.dirname(decoy),
                             GIT_INDEX_FILE=os.path.join(decoy, "index")):
            self.build()
            self.merge_on_origin()
            r = self.run_after("feat")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(snapshot(), before)


if __name__ == "__main__":
    unittest.main()
