#!/usr/bin/env bash
# Merge a pull request once its review bot says MERGE on a given head and its required check passes.
#
# Usage: merge-on-verdict.sh <number> <head-sha> [--check <name>] [--bot <login>]
#                            [--timeout <seconds>] [--interval <seconds>] [--admin-if-only-review]
#                            [--require-section <heading>]
#   Defaults: --check checks, --bot cursor[bot], --timeout 3600, --interval 30.
#   Run from the repository, as a background job the harness reports back on
#   (Claude Code: run_in_background).
# The verdict is the bot's newest review on <head-sha> (a prefix is enough): its body,
# after any leading HTML comments, starts with MERGE or HOLD. Reviews on older commits
# never count, and a bot review that starts with neither word (an approval note) is
# skipped. On MERGE the script waits for the named check to finish, then runs
# `gh pr merge --merge --match-head-commit <head>`, so GitHub refuses the merge if the
# head moved in between. It never bypasses branch rules, unless --admin-if-only-review is
# given: then, when GitHub refuses that merge, a required approving review is missing
# (reviewDecision REVIEW_REQUIRED), and nothing else --admin would skip is open (every check
# on the head passed, mergeStateStatus is BLOCKED, the head is not behind its base where the
# base's rules require an up-to-date branch, and no current review thread is unresolved), it
# merges with --admin and says so in a comment on the pull request. Where the rules do not
# require it, a branch behind its base merges without --admin too, so the flag skips no rule.
# Use the flag only where the project's owner has authorized it; it never merges past a HOLD,
# a failed or pending check, a required update from the base, an open thread or a new head.
# When it cannot admin-merge, it says why once, so a wait that will never end is visible.
# With --require-section, it merges only when the pull request's body has a Markdown heading
# with that text (the project's required section, for example "Sweep"); otherwise it exits 6.
# Exit codes:
#   0  merged, by this script or by someone else (it prints who)
#   1  the pull request was closed without a merge, or a gh call kept failing
#   2  HOLD: the review is printed
#   3  the check finished without success
#   4  the head is no longer <head-sha>: a new push needs a new verdict
#   5  timed out
#   6  the body lacks the --require-section heading
#   64 a usage error
# Tests: test_pr_scripts.py, run by the repository's scripts/check.sh.
set -euo pipefail

number="" head="" check="checks" bot="cursor[bot]" timeout=3600 interval=30 admin="" section=""
usage() { echo "$1" >&2; echo "usage: $0 <number> <head-sha> [--check <name>] [--bot <login>] [--timeout <seconds>] [--interval <seconds>] [--admin-if-only-review] [--require-section <heading>]" >&2; exit 64; }
while [ $# -gt 0 ]; do
  case "$1" in
    --check|--bot|--timeout|--interval|--require-section)
      [ $# -ge 2 ] || usage "missing value for $1"
      case "$1" in
        --check) check="$2" ;; --bot) bot="$2" ;; --timeout) timeout="$2" ;; --interval) interval="$2" ;;
        --require-section) section="$2" ;;
      esac
      shift 2 ;;
    --admin-if-only-review) admin=1; shift ;;
    -*) usage "unknown argument: $1" ;;
    *) if [ -z "$number" ]; then number="$1"; elif [ -z "$head" ]; then head="$1"; else usage "too many arguments: $1"; fi
       shift ;;
  esac
done
[ -n "$number" ] && [ -n "$head" ] || usage "a number and a head are required"

failures=0
# Runs gh in this shell and leaves its output in REPLY. A failed call counts toward the
# limit of ten in a row; a good one resets it.
call() {
  if REPLY=$("$@"); then failures=0; return 0; fi
  failures=$((failures + 1))
  if [ "$failures" -ge 10 ]; then echo "gh failed $failures times in a row; stopping" >&2; exit 1; fi
  return 1
}

# "<state> <head> <merged-by> <check-state> <review-decision> <merge-state> <all-green> <base>", where
# check-state is PENDING, SUCCESS or the check's failing conclusion, and all-green is yes when
# every check on the head, not only $check, passed. A check run reports status and conclusion;
# a commit status reports state.
pr_state() {
  call gh pr view "$number" --json state,headRefOid,mergedBy,statusCheckRollup,reviewDecision,mergeStateStatus,baseRefName --jq "
    (.statusCheckRollup // [] | map(select((.name // .context) == \"$check\")) | last) as \$c
    | (if \$c == null then \"PENDING\"
       elif (\$c | has(\"status\")) then (if \$c.status == \"COMPLETED\" then \$c.conclusion else \"PENDING\" end)
       else (if \$c.state == \"PENDING\" or \$c.state == \"EXPECTED\" then \"PENDING\" else \$c.state end) end) as \$s
    | (.statusCheckRollup // [] | all(if has(\"status\") then .status == \"COMPLETED\" and
         (.conclusion == \"SUCCESS\" or .conclusion == \"NEUTRAL\" or .conclusion == \"SKIPPED\")
         else .state == \"SUCCESS\" end) | if . then \"yes\" else \"no\" end) as \$g
    | \"\(.state) \(.headRefOid) \(.mergedBy.login // \"-\") \(\$s) \(.reviewDecision // \"-\") \(.mergeStateStatus // \"-\") \(\$g) \(.baseRefName)\""
}

# Leading HTML comments, which the bot puts before its verdict.
strip='gsub("^(\\s*<!--[\\s\\S]*?-->)+\\s*"; "")'

# Sets REPLY to "<MERGE|HOLD> <review-id>" for the bot's newest verdict on the full head $1,
# or to nothing. --paginate runs the filter once per page, so the filter prints one line per
# verdict and the last line, from the last page, is the newest.
verdict() {
  call gh api --paginate "repos/{owner}/{repo}/pulls/$number/reviews" --jq "
    .[] | select(.user.login == \"$bot\" and .commit_id == \"$1\")
        | ((.body | $strip | capture(\"^(?<v>MERGE|HOLD)\\\\b\")) // {} | .v) as \$v
        | select(\$v != null) | \"\(\$v) \(.id)\"" || return 1
  REPLY=$(printf '%s\n' "$REPLY" | sed '/^$/d' | tail -n 1)
}

# Prints how many review threads on the pull request are unresolved and not outdated, "more
# than 100" when it cannot see them all, or nothing when the call fails.
unresolved_threads() {
  gh api graphql -F owner='{owner}' -F repo='{repo}' -F n="$number" -f query='query($owner: String!, $repo: String!, $n: Int!) { repository(owner: $owner, name: $repo) {
    pullRequest(number: $n) { reviewThreads(first: 100) { pageInfo { hasNextPage } nodes { isResolved isOutdated } } } } }' \
    --jq '.data.repository.pullRequest.reviewThreads
      | if .pageInfo.hasNextPage then "more than 100"
        else [.nodes[] | select(.isResolved | not) | select(.isOutdated | not)] | length end' || true
}

# Prints "yes" when the base's rules require an up-to-date branch and the head is behind it,
# "no" when they do not or it is not, or nothing when a call fails. While a review is also
# missing GitHub reports BLOCKED, not BEHIND, so mergeStateStatus alone cannot show this.
required_update_missing() {
  local strict behind
  strict=$(gh api "repos/{owner}/{repo}/rules/branches/$base" \
    --jq 'any(.[]; .type == "required_status_checks" and .parameters.strict_required_status_checks_policy)') || return 0
  if [ "$strict" != "true" ]; then
    strict=$(gh api "repos/{owner}/{repo}/branches/$base/protection" --jq '.required_status_checks.strict // false' 2>/dev/null) \
      || strict=false                    # 404: the branch has no classic protection
  fi
  if [ "$strict" != "true" ]; then echo no; return 0; fi
  behind=$(gh api "repos/{owner}/{repo}/compare/$base...$current" --jq '.behind_by') || return 0
  if [ "$behind" = "0" ]; then echo no; else echo yes; fi
}

# Prints the first reason an admin merge cannot happen now, or nothing when it can.
admin_blocker() {
  local threads
  if [ "$review_decision" != "REVIEW_REQUIRED" ] || [ "$merge_state" != "BLOCKED" ]; then
    echo "GitHub reports review $review_decision and merge state $merge_state, not only a missing review"; return
  fi
  [ "$all_green" = "yes" ] || { echo "a check on the head besides $check has not passed"; return; }
  threads=$(unresolved_threads)
  [ "$threads" = "0" ] || { echo "${threads:-an unknown number of} review thread(s) are unresolved"; return; }
  [ "$(required_update_missing)" = "no" ] || echo "the base requires an up-to-date branch, and this one is behind it or could not be compared"
}

# Exits 6 unless the pull request's body has a Markdown heading that names $section.
require_section() {
  [ -n "$section" ] || return 0
  call gh api "repos/{owner}/{repo}/pulls/$number" --jq '.body // ""' || return 1
  if ! printf '%s\n' "$REPLY" | grep -qiE "^#{1,6}[[:space:]]+$section([[:space:]]|$)"; then
    echo "the pull request's body has no \"$section\" section: add it, then run this again" >&2; exit 6
  fi
}

said=""
deadline=$(( $(date +%s) + timeout ))
while :; do
  if pr_state; then
    read -r state current merged_by check_state review_decision merge_state all_green base <<<"$REPLY"
    case "$state" in
      MERGED) echo "merged by $merged_by"; exit 0 ;;
      CLOSED) echo "closed without a merge" >&2; exit 1 ;;
    esac
    case "$current" in
      "$head"*) ;;
      *) echo "head is $current, not $head: a new push needs a new verdict" >&2; exit 4 ;;
    esac
    if verdict "$current" && [ -n "$REPLY" ]; then
      case "$REPLY" in
        HOLD*)
          id=${REPLY#HOLD }
          if call gh api "repos/{owner}/{repo}/pulls/$number/reviews/$id" --jq ".body | $strip"; then
            echo "$REPLY"
          else
            echo "HOLD in review $id"
          fi
          exit 2 ;;
      esac
      case "$check_state" in
        PENDING) ;;
        SUCCESS)
          require_section || { [ "$(date +%s)" -lt "$deadline" ] || { echo "timed out after $timeout seconds" >&2; exit 5; }; sleep "$interval"; continue; }
          if gh pr merge "$number" --merge --match-head-commit "$current"; then
            echo "merged by this script at head $current"; exit 0
          fi
          # An admin merge would also pass a failed or pending check, a required update from the base,
          # and an unresolved conversation, so each of those must be clear first.
          blocker=""
          [ -z "$admin" ] || blocker=$(admin_blocker)
          if [ -n "$admin" ] && [ -n "$blocker" ] && [ "$blocker" != "$said" ]; then
            echo "not merging with admin privileges yet: $blocker" >&2; said=$blocker
          fi
          if [ -n "$admin" ] && [ -z "$blocker" ] \
             && gh pr merge "$number" --merge --admin --match-head-commit "$current"; then
            gh pr comment "$number" --body "Merged with admin privileges at $current: the PR reviewer's verdict on this head is MERGE and \`$check\` passed; the only unmet rule was a required approving review (merge-on-verdict.sh --admin-if-only-review, as the owner authorized)." >/dev/null || true
            echo "merged with admin privileges by this script at head $current (only a required review was missing)"; exit 0
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
