#!/usr/bin/env bash
# Merge a pull request once its review bot says MERGE on a given head and its required check passes.
#
# Usage: merge-on-verdict.sh <number> <head-sha> [--check <name>] [--bot <login>]
#                            [--timeout <seconds>] [--interval <seconds>]
#   Defaults: --check checks, --bot cursor[bot], --timeout 3600, --interval 30.
#   Run from the repository, as a background job the harness reports back on
#   (Claude Code: run_in_background).
# The verdict is the bot's newest review on <head-sha> (a prefix is enough): its body,
# after any leading HTML comments, starts with MERGE or HOLD. Reviews on older commits
# never count, and a bot review that starts with neither word (an approval note) is
# skipped. On MERGE the script waits for the named check to finish, then runs
# `gh pr merge --merge --match-head-commit <head>`, so GitHub refuses the merge if the
# head moved in between. It never bypasses branch rules.
# Exit codes:
#   0  merged, by this script or by someone else (it prints who)
#   1  the pull request was closed without a merge, or a gh call kept failing
#   2  HOLD: the review is printed
#   3  the check finished without success
#   4  the head is no longer <head-sha>: a new push needs a new verdict
#   5  timed out
# Tests: test_pr_scripts.py, run by the repository's scripts/check.sh.
set -euo pipefail

number="" head="" check="checks" bot="cursor[bot]" timeout=3600 interval=30
while [ $# -gt 0 ]; do
  case "$1" in
    --check) check="$2"; shift 2 ;;
    --bot) bot="$2"; shift 2 ;;
    --timeout) timeout="$2"; shift 2 ;;
    --interval) interval="$2"; shift 2 ;;
    -*) echo "unknown argument: $1" >&2; exit 1 ;;
    *) if [ -z "$number" ]; then number="$1"; else head="$1"; fi; shift ;;
  esac
done
[ -n "$number" ] && [ -n "$head" ] || { echo "usage: $0 <number> <head-sha> [--check <name>] [--bot <login>]" >&2; exit 1; }

failures=0
# Runs gh in this shell and leaves its output in REPLY. A failed call counts toward the
# limit of ten in a row; a good one resets it.
call() {
  if REPLY=$("$@"); then failures=0; return 0; fi
  failures=$((failures + 1))
  if [ "$failures" -ge 10 ]; then echo "gh failed $failures times in a row; stopping" >&2; exit 1; fi
  return 1
}

# "<state> <head> <merged-by> <check-state>", where check-state is PENDING, SUCCESS or the
# check's failing conclusion. A check run reports status and conclusion; a commit status
# reports state.
pr_state() {
  call gh pr view "$number" --json state,headRefOid,mergedBy,statusCheckRollup --jq "
    (.statusCheckRollup // [] | map(select((.name // .context) == \"$check\")) | last) as \$c
    | (if \$c == null then \"PENDING\"
       elif (\$c | has(\"status\")) then (if \$c.status == \"COMPLETED\" then \$c.conclusion else \"PENDING\" end)
       else (if \$c.state == \"PENDING\" or \$c.state == \"EXPECTED\" then \"PENDING\" else \$c.state end) end) as \$s
    | \"\(.state) \(.headRefOid) \(.mergedBy.login // \"-\") \(\$s)\""
}

# The bot's newest MERGE or HOLD review on the head, with leading HTML comments removed.
verdict() {
  call gh api --paginate "repos/{owner}/{repo}/pulls/$number/reviews" --jq "
    [.[] | select(.user.login == \"$bot\" and (.commit_id | startswith(\"$head\")))
         | .body | gsub(\"^(\\\\s*<!--[\\\\s\\\\S]*?-->)+\\\\s*\"; \"\")
         | select(test(\"^(MERGE|HOLD)\\\\b\"))] | last // empty"
}

deadline=$(( $(date +%s) + timeout ))
while :; do
  if pr_state; then
    read -r state current merged_by check_state <<<"$REPLY"
    case "$state" in
      MERGED) echo "merged by $merged_by"; exit 0 ;;
      CLOSED) echo "closed without a merge" >&2; exit 1 ;;
    esac
    case "$current" in
      "$head"*) ;;
      *) echo "head is $current, not $head: a new push needs a new verdict" >&2; exit 4 ;;
    esac
    if verdict && [ -n "$REPLY" ]; then
      body=$REPLY
      case "$body" in
        HOLD*) echo "$body"; exit 2 ;;
      esac
      case "$check_state" in
        PENDING) ;;
        SUCCESS)
          if gh pr merge "$number" --merge --match-head-commit "$current"; then
            echo "merged by this script at head $current"; exit 0
          fi
          # Someone else may have merged it first; the next poll says so.
          ;;
        *) echo "check $check finished: $check_state" >&2; exit 3 ;;
      esac
    fi
  fi
  [ "$(date +%s)" -lt "$deadline" ] || { echo "timed out after $timeout seconds" >&2; exit 5; }
  sleep "$interval"
done
