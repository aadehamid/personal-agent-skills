#!/usr/bin/env bash
# Watch a pull request and exit on its first new event.
#
# Usage: watch-pr.sh <number> [--interval <seconds>]   (default interval: 30)
#   Run from the repository, as a background job the harness reports back on
#   (Claude Code: run_in_background). It exits as soon as something happens, so
#   the agent wakes up then, not on a timer.
# Each poll lists the pull request's events: its state, every review, conversation
# comment and inline review comment by ID, and every finished check with its result
# and finish time. It exits 0 and prints the events that were not there at the start:
# a merge or close, a new review or comment of either kind, or a check that finished,
# including a rerun that finished with the same result. A check that only starts,
# queues or reruns is not an event, and an event that disappears wakes nothing.
# Exits 0 at once if the PR has already merged or closed. A failed gh call is retried;
# ten failures in a row (a wrong number, an expired login) exit 1 with gh's error shown.
# Tests: test_pr_scripts.py, run by the repository's scripts/check.sh.
set -euo pipefail
export LC_ALL=C   # sort and comm must agree on order

number="" interval=30
while [ $# -gt 0 ]; do
  case "$1" in
    --interval) interval="$2"; shift 2 ;;
    -*) echo "unknown argument: $1" >&2; exit 2 ;;
    *) number="$1"; shift ;;
  esac
done
[ -n "$number" ] || { echo "usage: $0 <number> [--interval <seconds>]" >&2; exit 2; }

# One event per line, sorted. Inline review comments are not in `gh pr view`'s
# comments, so they come from the pulls API.
snapshot() {
  local view inline
  view=$(gh pr view "$number" --json state,reviews,comments,statusCheckRollup --jq '
    "state:\(.state)",
    (.reviews[] | "review:\(.id)"),
    (.comments[] | "comment:\(.id)"),
    (.statusCheckRollup[]?
      | if has("status") then select(.status == "COMPLETED")
          | "check:\(.name):\(.conclusion):\(.completedAt // "")"
        else select((.state // "") != "PENDING")
          | "status:\(.context):\(.state):\(.startedAt // .createdAt // "")"
        end)') || return 1
  inline=$(gh api --paginate "repos/{owner}/{repo}/pulls/$number/comments" --jq '.[] | "inline:\(.id)"') || return 1
  printf '%s\n%s\n' "$view" "$inline" | sed '/^$/d' | sort -u
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
echo "start: $(grep '^state:' <<<"$first")"
case "$first" in *state:MERGED*|*state:CLOSED*) exit 0 ;; esac
while sleep "$interval"; do
  poll || continue
  new=$(comm -13 <(echo "$first") <(echo "$snap"))
  if [ -n "$new" ]; then
    echo "changed:"
    echo "$new"
    exit 0
  fi
done
