#!/usr/bin/env python3
"""Tests for watch-pr.sh (against a fake gh) and after-merge.sh (against real git repositories).

after-merge.sh deletes branches, so each case builds a throwaway origin and clone and
checks what is left on both sides. watch-pr.sh gets its gh answers from FAKE_GH_SEQ,
one JSON document per call; the fake applies the script's own --jq filter with jq.
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
WATCH = os.path.join(HERE, "watch-pr.sh")
AFTER = os.path.join(HERE, "after-merge.sh")
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
    path = os.path.join(os.environ["FAKE_STATE"], "calls")
    n = int(open(path).read()) if os.path.exists(path) else 0
    open(path, "w").write(str(n + 1))
    doc = seq[min(n, len(seq) - 1)]
    if doc is None:
        sys.exit(1)                      # a failed gh call
    jq = sys.argv[sys.argv.index("--jq") + 1]
    sys.exit(subprocess.run([os.environ["FAKE_JQ"], "-r", jq], input=json.dumps(doc), text=True).returncode)
''').lstrip()


def pr(state="OPEN", reviews=0, comments=0, checks=()):
    return {"state": state, "reviews": [{}] * reviews, "comments": [{}] * comments,
            "statusCheckRollup": list(checks)}


def check(status, conclusion=""):
    return {"name": "ci", "status": status, "conclusion": conclusion}


@unittest.skipUnless(JQ, "jq is needed to apply the script's filter")
class WatchPr(unittest.TestCase):
    def run_watch(self, seq):
        state, bindir = tempfile.mkdtemp(), tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, state, True)
        self.addCleanup(shutil.rmtree, bindir, True)
        for name, body in (("gh", FAKE_GH), ("sleep", "#!/bin/sh\nexit 0\n")):
            path = os.path.join(bindir, name)
            with open(path, "w") as f:
                f.write(body)
            os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
        env = dict(os.environ, PATH=bindir + os.pathsep + os.environ["PATH"],
                   FAKE_GH_SEQ=json.dumps(seq), FAKE_STATE=state, FAKE_JQ=JQ)
        r = subprocess.run(["bash", WATCH, "7"], env=env, capture_output=True, text=True, timeout=30)
        with open(os.path.join(state, "calls")) as f:
            return r, int(f.read())

    def test_already_merged_exits_at_once(self):
        r, calls = self.run_watch([pr("MERGED")])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(calls, 1)
        self.assertIn("start: MERGED", r.stdout)

    def test_a_check_starting_is_not_a_change_but_finishing_is(self):
        r, calls = self.run_watch([pr(checks=[check("QUEUED")]), pr(checks=[check("IN_PROGRESS")]),
                                   pr(checks=[check("COMPLETED", "SUCCESS")])])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(calls, 3)
        self.assertIn("changed: OPEN\t0\t0\tci=SUCCESS", r.stdout)

    def test_a_pending_commit_status_is_not_a_change(self):
        r, calls = self.run_watch([pr(), pr(checks=[{"context": "ci", "state": "PENDING"}]),
                                   pr(checks=[{"context": "ci", "state": "FAILURE"}])])
        self.assertEqual(calls, 3)
        self.assertIn("ci=FAILURE", r.stdout)

    def test_a_new_review_is_a_change(self):
        r, calls = self.run_watch([pr(), pr(), pr(reviews=1)])
        self.assertEqual(calls, 3)
        self.assertIn("changed: OPEN\t1\t0", r.stdout)

    def test_a_merge_is_a_change(self):
        r, calls = self.run_watch([pr(), pr("MERGED")])
        self.assertEqual(calls, 2)
        self.assertIn("changed: MERGED", r.stdout)

    def test_ten_failures_in_a_row_stop_the_watch(self):
        r, calls = self.run_watch([None])
        self.assertEqual(r.returncode, 1)
        self.assertEqual(calls, 10)
        self.assertIn("gh failed 10 times in a row", r.stderr)

    def test_a_failed_gh_call_is_retried(self):
        r, calls = self.run_watch([None, pr(), None, pr(comments=1)])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(calls, 4)
        self.assertIn("changed: OPEN\t0\t1", r.stdout)


class AfterMerge(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
                        GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com",
                        GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
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

    def merge_on_origin(self, squash=False):
        """Merge feat into main the way a review bot would, from a separate clone."""
        other = os.path.join(self.tmp, "other")
        self.git(self.tmp, "clone", "--quiet", self.origin, other)
        if squash:
            self.git(other, "merge", "--quiet", "--squash", "origin/feat")
            self.git(other, "commit", "--quiet", "-m", "squash")
        else:
            self.git(other, "merge", "--quiet", "--no-ff", "-m", "merge", "origin/feat")
        self.git(other, "push", "--quiet", "origin", "main")

    def run_after(self, *args):
        return subprocess.run(["bash", AFTER, *args], cwd=self.repo, env=self.env,
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
        other = os.path.join(self.tmp, "late")
        self.git(self.tmp, "clone", "--quiet", "-b", "feat", self.origin, other)
        self.commit("late", other)
        self.git(other, "push", "--quiet", "origin", "feat")
        r = self.run_after("feat")
        self.assertEqual(r.returncode, 1)
        self.assertIn("origin/feat has commits that are not in main", r.stderr)
        self.assertTrue(self.branches()[1])

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

    def test_unreadable_origin_deletes_nothing(self):
        self.merge_on_origin()
        os.rename(self.origin, self.origin + ".moved")
        r = self.run_after("feat")
        os.rename(self.origin + ".moved", self.origin)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("feat", self.git(self.repo, "branch", "--format=%(refname:short)").split())

    def test_base_branch_is_refused(self):
        r = self.run_after("main")
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
