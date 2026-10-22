#!/usr/bin/env bash
# After a pull request merges: sync the base branch, then delete the merged branch
# locally and on the remote, only if every commit on it is in the base.
#
# Usage: after-merge.sh <branch> [--base <branch>]   (default base: main)
#   Run from the repository. Delete only a branch you opened; someone else's is theirs.
# Exit 0: base synced, branch gone (or already gone, even if it went mid-run). Exit 1: something on the branch
#   is not in the base, or an open pull request based on it could not be listed or moved, so nothing is
#   deleted. If the run then fails after pull requests were moved, they are moved back while the branch
#   still exists, and stay on the base if it is gone; a pull request that cannot be moved back is named.
# Just before the remote delete, every open pull request whose base is the branch is moved to the base:
#   GitHub closed one when its base branch was deleted with git push --delete (enterprise-performance-model #328).
#   This needs gh, signed in.
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

# Every check below reads the one place the delete goes. With several push URLs, one
# reporting a missing ref could hide another refusing the delete, so stop instead.
push_urls=$(git remote get-url --push --all origin)
if [ "$(wc -l <<<"$push_urls")" -ne 1 ]; then
  echo "origin has several push URLs; nothing deleted. This script handles one push URL." >&2
  echo "Leave $branch, or for each URL fetch its tip, require it in $base, delete with a lease." >&2
  exit 1
fi
push_url=$push_urls

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
# Someone else (a review bot, on merge) can delete the branch at any moment. A fetch
# or delete that fails counts as done only if git's error says the ref is missing and
# the live remote then lists no such branch; a lease refusal, a server rule or a
# network error stays a failure. This trusts the remote to list every branch it has;
# a server that hides refs makes a hidden branch look deleted.
remote_rc() {   # git's exit code: 0 the branch is there, 2 it is not, other an error
  local rc=0
  git ls-remote --exit-code --heads "$push_url" "refs/heads/$branch" >/dev/null || rc=$?
  echo "$rc"
}
# Git's words for a missing ref: from fetch, from a delete the client refuses, and
# from one the server refuses.
missing_ref="couldn't find remote ref|remote ref does not exist|unable to resolve reference"
# Runs git. Returns 0 if it succeeded, 1 if the branch went missing; otherwise exits 1.
git_unless_gone() {
  local err
  err=$(LC_ALL=C git "$@" 2>&1) && return 0
  echo "$err" >&2
  if grep -Eq "$missing_ref" <<<"$err" && [ "$(remote_rc)" = 2 ]; then
    echo "origin/$branch is already gone"
    return 1
  fi
  echo "could not delete origin/$branch; nothing more deleted" >&2
  exit 1
}

# Moves every open pull request based on the branch to the base, or exits 1 having deleted nothing.
# Until the delete succeeds, an exit moves them back (restore_moved, run by the EXIT trap).
moved=""
retarget_stacked() {
  local stacked n
  stacked=$(gh pr list --base "$branch" --state open --limit 1000 --json number --jq '.[].number') \
    || { echo "gh could not list the pull requests based on $branch (is gh installed and signed in?); nothing deleted" >&2; exit 1; }
  trap restore_moved EXIT
  for n in $stacked; do
    gh pr edit "$n" --base "$base" >/dev/null || { echo "could not move #$n from $branch to $base; nothing deleted" >&2; exit 1; }
    moved="$moved $n"
    echo "moved #$n from $branch to $base"
  done
}
restore_moved() {
  local n rc
  [ -n "$moved" ] || return 0
  rc=$(remote_rc)
  if [ "$rc" = 2 ]; then
    echo "origin/$branch is gone, so the moved pull requests stay on $base:$moved" >&2
    return 0
  elif [ "$rc" != 0 ]; then
    echo "could not read origin (git ls-remote exited $rc): check the base of each moved pull request:$moved" >&2
    return 0
  fi
  for n in $moved; do
    if gh pr edit "$n" --base "$branch" >/dev/null; then
      echo "moved #$n back to $branch, since $branch was not deleted" >&2
    else
      echo "could not move #$n back to $branch: set its base by hand" >&2
    fi
  done
}

rc=$(remote_rc)
case "$rc" in
  0)
    if git_unless_gone fetch --quiet "$push_url" "refs/heads/$branch"; then
      remote_sha=$(git rev-parse FETCH_HEAD)
      if ! git merge-base --is-ancestor "$remote_sha" "origin/$base"; then
        echo "origin/$branch has commits that are not in $base; nothing deleted" >&2
        exit 1
      fi
      retarget_stacked   # after the checks that can refuse the delete; a refused push moves them back
      if git_unless_gone push --quiet "$push_url" --delete "$branch" --force-with-lease="$branch:$remote_sha"; then
        echo "deleted origin/$branch"
      fi
      moved=""; trap - EXIT   # deleted, or already gone: the moved pull requests stay on the base
    fi
    ;;
  2) echo "origin/$branch is already gone" ;;
  *) echo "could not read origin (git ls-remote exited $rc); nothing deleted" >&2; exit 1 ;;
esac

if git show-ref --verify --quiet "refs/heads/$branch"; then
  git branch -d "$branch"   # -d, never -D: git refuses an unmerged branch
fi
echo "on $base at $(git rev-parse --short HEAD)"
