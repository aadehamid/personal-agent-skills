#!/usr/bin/env python3
"""Tests for watch-pr.sh and merge-on-verdict.sh (against a fake gh) and after-merge.sh (against real git repositories).

watch-pr.sh gets its gh answers from FAKE_GH_SEQ, one entry per poll: the pull
request document and its inline review comments, or null for a failed call. The fake
applies the script's own --jq filters with jq, so the filters themselves are tested.
merge-on-verdict.sh gets FAKE_GH_SEQ entries of the pull request document and its
reviews, and its fake records every `gh pr merge` call.

after-merge.sh deletes branches, so each case builds a throwaway origin and clone and
checks what is left on both sides. A git wrapper on PATH injects what cannot be
staged beforehand: a failed lookup, a fetch that wrongly reports the ref missing, or a command run just before the branch
fetch, the remote delete or `branch -d` (a push, a commit, the branch deleted elsewhere).
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
MERGE = os.path.join(HERE, "merge-on-verdict.sh")
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
    if entry is None or (sys.argv[1] == "api" and entry.get("inline_fails")):
        sys.exit(1)                      # a failed gh call
    doc = entry["pr"] if sys.argv[1] == "pr" else [{"id": i} for i in entry["inline"]]
    jq = sys.argv[sys.argv.index("--jq") + 1]
    sys.exit(subprocess.run([os.environ["FAKE_JQ"], "-r", jq], input=json.dumps(doc), text=True).returncode)
''').lstrip()

FAKE_GH_MERGE = textwrap.dedent(r'''
    #!/usr/bin/env python3
    import json, os, subprocess, sys
    seq = json.loads(os.environ["FAKE_GH_SEQ"])
    state = os.environ["FAKE_STATE"]
    path = os.path.join(state, "polls")
    polls = int(open(path).read()) if os.path.exists(path) else 0
    if sys.argv[1:3] == ["pr", "view"]:
        polls += 1
        open(path, "w").write(str(polls))
    entry = seq[min(polls, len(seq)) - 1]
    if sys.argv[1:3] == ["pr", "merge"]:
        with open(os.path.join(state, "merges"), "a") as f:
            f.write(" ".join(sys.argv[3:]) + "\n")
        plain_fails = entry.get("plain_merge_fails") and "--admin" not in sys.argv
        sys.exit(1 if entry.get("merge_fails") or plain_fails else 0)
    if sys.argv[1:3] == ["pr", "comment"]:
        with open(os.path.join(state, "comments"), "a") as f:
            f.write(" ".join(sys.argv[3:]) + "\n")
        sys.exit(0)
    if entry is None:
        sys.exit(1)                      # a failed gh call
    jq = sys.argv[sys.argv.index("--jq") + 1]
    target = next((a for a in sys.argv if a.startswith("repos/")), "")
    if "/rules/branches/" in target or target.endswith("/protection") or "/compare/" in target:
        if target.endswith("/protection"):
            sys.exit(1)                  # no classic protection: gh exits non-zero on the 404
        doc = ({"behind_by": entry.get("behind", 0)} if "/compare/" in target else
               [{"type": "required_status_checks",
                 "parameters": {"strict_required_status_checks_policy": entry.get("strict", False)}}])
        sys.exit(subprocess.run([os.environ["FAKE_JQ"], "-r", jq], input=json.dumps(doc), text=True).returncode)
    if target.rsplit("/", 1)[-1].isdigit() and target.split("/")[-2] == "pulls":
        doc = {"body": entry.get("body", "")}  # the pull request itself, for --require-section
        sys.exit(subprocess.run([os.environ["FAKE_JQ"], "-r", jq], input=json.dumps(doc), text=True).returncode)
    if sys.argv[1:3] == ["api", "graphql"]:
        threads = [{"isResolved": False, "isOutdated": False}] * entry.get("unresolved", 0)
        doc = {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": threads, "pageInfo": {"hasNextPage": entry.get("more_threads", False)}}}}}}
        sys.exit(subprocess.run([os.environ["FAKE_JQ"], "-r", jq], input=json.dumps(doc), text=True).returncode)
    if sys.argv[1] == "pr":
        docs = [entry["pr"]]
    else:                                # reviews come in pages; --paginate runs the filter per page
        pages = entry["reviews"] if entry.get("paged") else [entry["reviews"]]
        path = next(a for a in sys.argv if a.startswith("repos/"))
        if not path.endswith("/reviews"):
            wanted = int(path.rsplit("/", 1)[1])
            docs = [r for page in pages for r in page if r["id"] == wanted]
        else:
            docs = pages
    for doc in docs:
        code = subprocess.run([os.environ["FAKE_JQ"], "-r", jq], input=json.dumps(doc), text=True).returncode
        if code:
            sys.exit(code)
''').lstrip()

FAKE_GIT = textwrap.dedent(r'''
    #!/usr/bin/env python3
    import os, subprocess, sys
    real, hook, args = os.environ["REAL_GIT"], os.environ.get("FAKE_GIT_HOOK", ""), sys.argv[1:]
    branch_fetch = args[:1] == ["fetch"] and any(a.startswith("refs/heads/") for a in args)
    if hook == "ls-remote-fails" and args[:1] == ["ls-remote"]:
        sys.exit(128)
    if hook == "fetch-fails" and branch_fetch:   # claims the ref is missing; the remote still has it
        sys.exit("fatal: couldn't find remote ref refs/heads/feat")
    before = {"before-fetch": branch_fetch,
              "before-push-delete": args[:1] == ["push"] and "--delete" in args,
              "before-branch-delete": args[:1] == ["branch"] and any(a in ("-d", "-D", "--delete") for a in args)}
    if before.get(hook):
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

    def test_a_merge_wakes_even_if_the_inline_lookup_fails(self):
        merged = dict(poll("MERGED"), inline_fails=True)
        self.assertWakes([poll(), merged], 2, "state:MERGED")

    def test_already_merged_exits_at_once_even_if_the_inline_lookup_fails(self):
        r, n = self.run_watch([dict(poll("MERGED"), inline_fails=True)])
        self.assertEqual((r.returncode, n), (0, 1), r.stderr)

    def test_ten_failures_in_a_row_stop_the_watch(self):
        r, n = self.run_watch([None])
        self.assertEqual((r.returncode, n), (1, 10))
        self.assertIn("gh failed 10 times in a row", r.stderr)

    def test_a_success_resets_the_failure_count(self):
        seq = [poll()] + [None] * 9 + [poll()] + [None] * 9 + [poll(comments=["C1"])]
        self.assertWakes(seq, 21, "comment:C1")


HEAD = "abc1234def5678"


def pr(state="OPEN", head=HEAD, merged_by=None, checks=(), review_decision=None, merge_state="BLOCKED"):
    return {"state": state, "headRefOid": head, "statusCheckRollup": list(checks),
            "mergedBy": {"login": merged_by} if merged_by else None, "reviewDecision": review_decision,
            "mergeStateStatus": merge_state, "baseRefName": "main"}


_ids = iter(range(1, 10**6))


def review(body, commit=HEAD, user="cursor[bot]"):
    return {"id": next(_ids), "user": {"login": user}, "commit_id": commit, "body": body}


def step(pr_doc=None, reviews=(), **extra):
    return dict({"pr": pr_doc or pr(), "reviews": list(reviews)}, **extra)


PASSED = {"name": "checks", "status": "COMPLETED", "conclusion": "SUCCESS"}
RUNNING = {"name": "checks", "status": "IN_PROGRESS", "conclusion": ""}
FAILED = {"name": "checks", "status": "COMPLETED", "conclusion": "FAILURE"}


@unittest.skipUnless(JQ, "jq is needed to apply the script's filters")
class MergeOnVerdict(unittest.TestCase):
    def run_merge(self, seq, *args):
        state, bindir = tempfile.mkdtemp(), tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, state, True)
        self.addCleanup(shutil.rmtree, bindir, True)
        write_exe(bindir, "gh", FAKE_GH_MERGE)
        write_exe(bindir, "sleep", "#!/bin/sh\nexit 0\n")
        env = dict(os.environ, PATH=bindir + os.pathsep + os.environ["PATH"],
                   FAKE_GH_SEQ=json.dumps(seq), FAKE_STATE=state, FAKE_JQ=JQ)
        r = subprocess.run(["bash", MERGE, "7", HEAD[:7], *args], env=env, capture_output=True, text=True, timeout=30)
        merges_path = os.path.join(state, "merges")
        merges = open(merges_path).read().splitlines() if os.path.exists(merges_path) else []
        comments_path = os.path.join(state, "comments")
        self.comments = open(comments_path).read().splitlines() if os.path.exists(comments_path) else []
        polls_path = os.path.join(state, "polls")
        self.polls = int(open(polls_path).read()) if os.path.exists(polls_path) else 0
        return r, merges

    def test_merge_waits_for_the_check_then_merges_on_the_full_head(self):
        merge = review("MERGE. Looks fine.")
        r, merges = self.run_merge([step(reviews=[merge]), step(pr(checks=[RUNNING]), [merge]),
                                    step(pr(checks=[PASSED]), [merge])])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(merges, [f"7 --merge --match-head-commit {HEAD}"])
        self.assertNotIn("--admin", " ".join(merges))

    def test_admin_merge_only_when_only_a_review_is_missing(self):
        blocked = pr(checks=[PASSED], review_decision="REVIEW_REQUIRED")
        r, merges = self.run_merge([step(blocked, [review("MERGE")], plain_merge_fails=True)], "--admin-if-only-review")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(merges, [f"7 --merge --match-head-commit {HEAD}", f"7 --merge --admin --match-head-commit {HEAD}"])
        self.assertEqual(len(self.comments), 1)
        self.assertIn("admin privileges", self.comments[0])

    def test_a_body_without_the_required_section_is_not_merged(self):
        r, merges = self.run_merge([step(pr(checks=[PASSED]), [review("MERGE")], body="## What this does\nText.\n")],
                                   "--require-section", "Sweep")
        self.assertEqual(r.returncode, 6, r.stderr)
        self.assertEqual(merges, [])
        self.assertIn('no "Sweep" section', r.stderr)

    def test_a_body_with_the_required_section_is_merged(self):
        r, merges = self.run_merge([step(pr(checks=[PASSED]), [review("MERGE")], body="Intro.\n\n## Sweep\nRan it.\n")],
                                   "--require-section", "Sweep")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(merges, [f"7 --merge --match-head-commit {HEAD}"])

    def test_the_reason_an_admin_merge_waits_is_said_once(self):
        blocked = pr(checks=[PASSED], review_decision="REVIEW_REQUIRED")
        r, merges = self.run_merge([step(blocked, [review("MERGE")], plain_merge_fails=True, unresolved=1)],
                                   "--admin-if-only-review", "--timeout", "1")
        self.assertEqual(r.returncode, 5)
        self.assertNotIn("--admin", " ".join(merges))
        self.assertEqual(r.stderr.count("not merging with admin privileges yet: 1 review thread(s) are unresolved"), 1)

    def test_no_admin_merge_without_the_flag(self):
        blocked = pr(checks=[PASSED], review_decision="REVIEW_REQUIRED")
        r, merges = self.run_merge([step(blocked, [review("MERGE")], plain_merge_fails=True)], "--timeout", "0")
        self.assertEqual(r.returncode, 5)
        self.assertNotIn("--admin", " ".join(merges))

    def test_admin_merge_of_a_branch_behind_its_base_only_where_no_update_is_required(self):
        blocked = pr(checks=[PASSED], review_decision="REVIEW_REQUIRED")
        r, merges = self.run_merge([step(blocked, [review("MERGE")], plain_merge_fails=True, behind=3)], "--admin-if-only-review")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("--admin", merges[-1])
        r, merges = self.run_merge([step(blocked, [review("MERGE")], plain_merge_fails=True, strict=True, behind=0)], "--admin-if-only-review")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("--admin", merges[-1])

    def test_no_admin_merge_when_something_else_blocks(self):
        # The review is not what is missing (e.g. a conflict or another required check), so no admin merge.
        other = pr(checks=[PASSED], review_decision="APPROVED")
        r, merges = self.run_merge([step(other, [review("MERGE")], plain_merge_fails=True)], "--admin-if-only-review", "--timeout", "0")
        self.assertEqual(r.returncode, 5)
        self.assertNotIn("--admin", " ".join(merges))

    def test_no_admin_merge_past_another_check_a_required_update_or_an_open_thread(self):
        # A review is required, but so is something --admin would also skip.
        lint_failed = {"name": "lint", "status": "COMPLETED", "conclusion": "FAILURE"}
        lint_running = {"name": "lint", "status": "IN_PROGRESS", "conclusion": ""}
        for blocker in (step(pr(checks=[PASSED, lint_failed], review_decision="REVIEW_REQUIRED"), [review("MERGE")], plain_merge_fails=True),
                        step(pr(checks=[PASSED, lint_running], review_decision="REVIEW_REQUIRED"), [review("MERGE")], plain_merge_fails=True),
                        step(pr(checks=[PASSED], review_decision="REVIEW_REQUIRED", merge_state="BEHIND"), [review("MERGE")], plain_merge_fails=True),
                        step(pr(checks=[PASSED], review_decision="REVIEW_REQUIRED"), [review("MERGE")], plain_merge_fails=True, unresolved=1),
                        step(pr(checks=[PASSED], review_decision="REVIEW_REQUIRED"), [review("MERGE")], plain_merge_fails=True, more_threads=True),
                        step(pr(checks=[PASSED], review_decision="REVIEW_REQUIRED"), [review("MERGE")], plain_merge_fails=True, strict=True, behind=3)):
            r, merges = self.run_merge([blocker], "--admin-if-only-review", "--timeout", "0")
            self.assertEqual(r.returncode, 5, r.stderr)
            self.assertNotIn("--admin", " ".join(merges))
            self.assertEqual(self.comments, [])

    def test_no_admin_merge_past_a_hold_or_a_failed_check(self):
        blocked = pr(checks=[PASSED], review_decision="REVIEW_REQUIRED")
        r, merges = self.run_merge([step(blocked, [review("HOLD. No.")], plain_merge_fails=True)], "--admin-if-only-review")
        self.assertEqual((r.returncode, merges), (2, []))
        failed = pr(checks=[FAILED], review_decision="REVIEW_REQUIRED")
        r, merges = self.run_merge([step(failed, [review("MERGE")], plain_merge_fails=True)], "--admin-if-only-review")
        self.assertEqual((r.returncode, merges), (3, []))

    def test_hold_prints_the_review_and_merges_nothing(self):
        r, merges = self.run_merge([step(pr(checks=[PASSED]), [review("HOLD. Fix the row.")])])
        self.assertEqual(r.returncode, 2)
        self.assertIn("HOLD. Fix the row.", r.stdout)
        self.assertEqual(merges, [])

    def test_failed_check_merges_nothing(self):
        r, merges = self.run_merge([step(pr(checks=[FAILED]), [review("MERGE")])])
        self.assertEqual(r.returncode, 3)
        self.assertEqual(merges, [])

    def test_a_review_on_an_older_commit_does_not_count(self):
        old = review("MERGE", commit="0000000old")
        r, merges = self.run_merge([step(pr(checks=[PASSED]), [old]),
                                    step(pr(checks=[PASSED]), [old, review("HOLD. New finding.")])])
        self.assertEqual(r.returncode, 2)
        self.assertEqual(merges, [])

    def test_a_leading_html_comment_is_stripped(self):
        body = "<!-- CURSOR_AUTOMATION_ID: x | RUN_ID: y -->\nMERGE\n\nChecked."
        r, merges = self.run_merge([step(pr(checks=[PASSED]), [review("<!-- id -->\nApproved.")]),
                                    step(pr(checks=[PASSED]), [review(body)])])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((len(merges), self.polls), (1, 2))

    def test_an_approval_note_is_not_a_verdict(self):
        note = review("<!-- id -->\nApproved. Not MERGEable until HOLD clears, says the note.")
        r, merges = self.run_merge([step(pr(checks=[PASSED]), [note]),
                                    step(pr(checks=[PASSED]), [note, review("MERGE")])])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((len(merges), self.polls), (1, 2))

    def test_the_newest_verdict_on_the_head_wins(self):
        r, merges = self.run_merge([step(pr(checks=[PASSED]), [review("HOLD. One."), review("MERGE")])])
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_a_newer_hold_on_a_later_page_wins(self):
        r, merges = self.run_merge([step(pr(checks=[PASSED]), [[review("MERGE")], [review("<!-- id -->\nHOLD. Late.")]],
                                         paged=True)])
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("HOLD. Late.", r.stdout)
        self.assertEqual(merges, [])

    def test_a_review_on_a_head_sharing_the_prefix_does_not_count(self):
        twin = review("MERGE", commit=HEAD[:7] + "ffffff")
        r, merges = self.run_merge([step(pr(checks=[PASSED]), [twin])], "--timeout", "0")
        self.assertEqual(r.returncode, 5)
        self.assertEqual(merges, [])

    def test_another_users_merge_does_not_count(self):
        r, merges = self.run_merge([step(pr(checks=[PASSED]), [review("MERGE", user="someone")])],
                                   "--timeout", "0")
        self.assertEqual(r.returncode, 5)
        self.assertEqual(merges, [])

    def test_already_merged_reports_who_merged(self):
        r, merges = self.run_merge([step(pr("MERGED", merged_by="app/cursor"))])
        self.assertEqual(r.returncode, 0)
        self.assertIn("merged by app/cursor", r.stdout)
        self.assertEqual(merges, [])

    def test_a_merge_by_someone_else_during_the_wait_is_success(self):
        r, merges = self.run_merge([step(pr(checks=[PASSED]), [review("MERGE")], merge_fails=True),
                                    step(pr("MERGED", merged_by="app/cursor"))])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("merged by app/cursor", r.stdout)

    def test_a_new_head_stops_the_wait(self):
        r, merges = self.run_merge([step(pr(head="fff9999newhead", checks=[PASSED]), [review("MERGE")])])
        self.assertEqual(r.returncode, 4)
        self.assertEqual(merges, [])

    def test_a_closed_pull_request_stops_the_wait(self):
        r, merges = self.run_merge([step(pr("CLOSED"))])
        self.assertEqual(r.returncode, 1)

    def test_a_commit_status_counts_as_the_check(self):
        status = {"context": "checks", "state": "SUCCESS"}
        r, merges = self.run_merge([step(pr(checks=[{"context": "checks", "state": "PENDING"}]), [review("MERGE")]),
                                    step(pr(checks=[status]), [review("MERGE")])])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(merges), 1)

    def test_another_check_does_not_stand_in(self):
        other = {"name": "lint", "status": "COMPLETED", "conclusion": "SUCCESS"}
        r, merges = self.run_merge([step(pr(checks=[other]), [review("MERGE")])], "--timeout", "0")
        self.assertEqual(r.returncode, 5)
        self.assertEqual(merges, [])

    def test_a_success_resets_the_failure_count(self):
        seq = [None] * 9 + [step()] + [None] * 9 + [step(pr("MERGED", merged_by="app/cursor"))]
        r, merges = self.run_merge(seq)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.polls, 20)

    def test_a_usage_error_has_its_own_exit_code(self):
        for args in (["7"], ["7", HEAD, "--check"], ["7", HEAD, "--timeout"], ["7", HEAD, "extra"], ["7", HEAD, "--wat"]):
            with self.subTest(args=args):
                r = subprocess.run(["bash", MERGE, *args], capture_output=True, text=True, timeout=30)
                self.assertEqual(r.returncode, 64, r.stderr)

    def test_ten_failures_in_a_row_stop_the_wait(self):
        r, merges = self.run_merge([None])
        self.assertEqual(r.returncode, 1)
        self.assertIn("gh failed 10 times in a row", r.stderr)


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
        r = self.run_after("feat", hook="before-push-delete", hook_cmd=(
            f"cd '{late}' && git commit --quiet --allow-empty -m race && git push --quiet origin feat"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("stale info", r.stderr)
        remote = self.git(self.repo, "ls-remote", "origin", "refs/heads/feat").split()[0]
        self.assertEqual(remote, self.git(late, "rev-parse", "HEAD"))

    def test_commit_racing_the_local_delete_is_refused_by_branch_d(self):
        self.merge_on_origin()
        marker = os.path.join(self.tmp, "raced")
        r = self.run_after("feat", hook="before-branch-delete", hook_cmd=(
            f"cd '{self.repo}' && c=$(git commit-tree feat^{{tree}} -p feat -m race) && "
            f"git update-ref refs/heads/feat $c && echo $c > '{marker}'"))
        with open(marker) as f:                      # the race happened
            raced = f.read().strip()
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.git(self.repo, "rev-parse", "refs/heads/feat"), raced)

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

    def delete_elsewhere(self):
        return f"git --git-dir='{self.origin}' update-ref -d refs/heads/feat"

    def test_remote_deleted_before_the_fetch_still_deletes_the_local_branch(self):
        self.merge_on_origin()
        r = self.run_after("feat", hook="before-fetch", hook_cmd=self.delete_elsewhere())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("origin/feat is already gone", r.stdout)
        self.assertEqual(self.branches(), (["main"], False))

    def test_remote_deleted_before_the_push_still_deletes_the_local_branch(self):
        self.merge_on_origin()
        r = self.run_after("feat", hook="before-push-delete", hook_cmd=self.delete_elsewhere())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("origin/feat is already gone", r.stdout)
        self.assertEqual(self.branches(), (["main"], False))

    def test_failed_fetch_of_a_branch_still_there_deletes_nothing(self):
        self.merge_on_origin()
        r = self.run_after("feat", hook="fetch-fails")
        self.assertEqual(r.returncode, 1)
        self.assertIn("could not delete origin/feat", r.stderr)
        self.assertEqual(self.branches(), (["feat", "main"], True))

    def hide_on_origin(self, *extra):
        """Make origin stop listing feat, though it still has it: a server that hides refs."""
        cmds = [f"git --git-dir='{self.origin}' config uploadpack.hideRefs refs/heads/feat"]
        cmds += [f"git --git-dir='{self.origin}' config {setting}" for setting in extra]
        return " && ".join(cmds)

    def assertFeatKept(self, r):
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("could not delete origin/feat", r.stderr)
        self.assertIn("feat", self.branches()[0])
        self.git(self.tmp, "--git-dir", self.origin, "show-ref", "--verify", "refs/heads/feat")

    def test_lease_refusal_is_not_taken_for_a_deleted_branch_when_the_ref_is_hidden(self):
        self.merge_on_origin()
        late = self.clone("late", "-b", "feat")
        r = self.run_after("feat", hook="before-push-delete", hook_cmd=(
            f"cd '{late}' && git commit --quiet --allow-empty -m race && git push --quiet origin feat && "
            + self.hide_on_origin()))
        self.assertIn("stale info", r.stderr)
        self.assertFeatKept(r)

    def test_refused_delete_is_not_taken_for_a_deleted_branch_when_the_ref_is_hidden(self):
        self.merge_on_origin()
        r = self.run_after("feat", hook="before-push-delete",
                           hook_cmd=self.hide_on_origin("receive.denyDeletes true"))
        self.assertIn("deletion prohibited", r.stderr)
        self.assertFeatKept(r)

    def test_several_push_urls_delete_nothing(self):
        self.merge_on_origin()
        second = self.clone("second", "--bare")
        self.git(self.repo, "remote", "set-url", "--add", "--push", "origin", self.origin)
        self.git(self.repo, "remote", "set-url", "--add", "--push", "origin", second)
        r = self.run_after("feat")
        self.assertEqual(r.returncode, 1)
        self.assertIn("origin has several push URLs; nothing deleted", r.stderr)
        self.assertIn("require it in main", r.stderr)
        self.assertEqual(self.branches(), (["feat", "main"], True))
        self.git(self.tmp, "--git-dir", second, "show-ref", "--verify", "refs/heads/feat")

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
            entries = []
            for root, dirs, files in os.walk(decoy):
                for name in sorted(dirs + files):
                    path = os.path.join(root, name)
                    content = None
                    if os.path.isfile(path):
                        with open(path, "rb") as f:
                            content = f.read()
                    entries.append((path, content))
            return sorted(entries)

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
