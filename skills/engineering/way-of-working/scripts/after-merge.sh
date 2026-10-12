#!/usr/bin/env bash
# After a pull request merges: sync the base branch, then delete the merged branch
# locally and on the remote, only if every commit on it is in the base.
#
# Usage: after-merge.sh <branch> [--base <branch>]   (default base: main)
#   Run from the repository. Delete only a branch you opened; someone else's is theirs.
# Exit 0: base synced, branch gone (or already gone, even if it went mid-run). Exit 1: something on the branch
#   is not in the base, so nothing is deleted.
# Tests: test_pr_scripts.py, run by the repository's scripts/check.sh.
set -euo pipefail

branch="" base=main
while [ $# -gt 0 ]; do
  case "$1" in
    --base) base="$2"; shift 2 ;;
    -*) echo "unknown argument: $1" >&2; exit 2 ;;
    *) branch="$1"; shift ;;
  esac
done
[ -n "$branch" ] || { echo "usage: $0 <branch> [--base <branch>]" >&2; exit 2; }
[ "$branch" != "$base" ] || { echo "refusing to delete the base branch $base" >&2; exit 2; }

git fetch --quiet origin "$base"
git switch --quiet "$base"
git merge --quiet --ff-only "origin/$base"

# A squash or rebase merge leaves the branch's own commits outside the base; so does
# a commit pushed after the merge. Either way the branch still holds work: stop.
if git show-ref --verify --quiet "refs/heads/$branch"; then
  local_sha=$(git rev-parse "refs/heads/$branch")
  if ! git merge-base --is-ancestor "$local_sha" "origin/$base"; then
    echo "local $branch has commits that are not in $base; nothing deleted" >&2
    exit 1
  fi
fi

# Read the live remote, not a cached ref, and delete under a lease on the exact
# commit checked, so a push that lands after the check makes the delete fail.
# Someone else (a review bot, on merge) can delete the branch at any moment, so a
# fetch or delete that fails counts as done only if the live remote then has no branch.
remote_rc() {   # git's exit code: 0 the branch is there, 2 it is not, other an error
  local rc=0
  git ls-remote --exit-code --heads origin "refs/heads/$branch" >/dev/null || rc=$?
  echo "$rc"
}
gone_now() {
  [ "$(remote_rc)" = 2 ] || { echo "could not delete origin/$branch; nothing more deleted" >&2; exit 1; }
  echo "origin/$branch is already gone"
}

rc=$(remote_rc)
case "$rc" in
  0)
    if git fetch --quiet origin "refs/heads/$branch"; then
      remote_sha=$(git rev-parse FETCH_HEAD)
      if ! git merge-base --is-ancestor "$remote_sha" "origin/$base"; then
        echo "origin/$branch has commits that are not in $base; nothing deleted" >&2
        exit 1
      fi
      if git push --quiet origin --delete "$branch" --force-with-lease="$branch:$remote_sha"; then
        echo "deleted origin/$branch"
      else
        gone_now
      fi
    else
      gone_now
    fi
    ;;
  2) echo "origin/$branch is already gone" ;;
  *) echo "could not read origin (git ls-remote exited $rc); nothing deleted" >&2; exit 1 ;;
esac

if git show-ref --verify --quiet "refs/heads/$branch"; then
  git branch -d "$branch"   # -d, never -D: git refuses an unmerged branch
fi
echo "on $base at $(git rev-parse --short HEAD)"
