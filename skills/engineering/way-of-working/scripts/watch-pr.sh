#!/usr/bin/env bash
# Watch a pull request and exit on its first meaningful change.
#
# Usage: watch-pr.sh <number> [--interval <seconds>]   (default interval: 30)
#   Run from the repository, as a background job the harness reports back on
#   (Claude Code: run_in_background). It exits as soon as something changes, so
#   the agent wakes up then, not on a timer.
# Exits 0 and prints the new state when the PR merges or closes, gets a review or a
# comment, or a check finishes. A check that only starts or queues is not a change.
# Exits 0 at once if the PR has already merged or closed. A failed gh call is retried;
# ten failures in a row (a wrong number, an expired login) exit 1 with gh's error shown.
# Tests: test_pr_scripts.py, run by the repository's scripts/check.sh.
set -euo pipefail

number="" interval=30
while [ $# -gt 0 ]; do
  case "$1" in
    --interval) interval="$2"; shift 2 ;;
    -*) echo "unknown argument: $1" >&2; exit 2 ;;
    *) number="$1"; shift ;;
  esac
done
[ -n "$number" ] || { echo "usage: $0 <number> [--interval <seconds>]" >&2; exit 2; }

# State, review count, comment count, and the conclusions of finished checks only.
snapshot() {
  gh pr view "$number" --json state,reviews,comments,statusCheckRollup --jq '
    [.state, (.reviews | length), (.comments | length),
     ([.statusCheckRollup[]?
       | select(if has("status") then .status == "COMPLETED" else (.state // "") != "PENDING" end)
       | "\(.name // .context)=\(.conclusion // .state)"] | sort | join(","))] | @tsv'
}

failures=0
# Sets $snap. A failed call counts toward the limit; a good one resets it.
poll() {
  if snap=$(snapshot); then failures=0; return 0; fi
  failures=$((failures + 1))
  if [ "$failures" -ge 10 ]; then
    echo "gh failed $failures times in a row; stopping" >&2
    exit 1
  fi
  return 1
}

until poll; do sleep "$interval"; done
first=$snap
echo "start: $first"
case "$first" in MERGED*|CLOSED*) exit 0 ;; esac
while sleep "$interval"; do
  poll || continue
  if [ "$snap" != "$first" ]; then
    echo "changed: $snap"
    exit 0
  fi
done
