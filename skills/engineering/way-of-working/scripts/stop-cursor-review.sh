#!/usr/bin/env bash
# Stop the Cursor review bot on a pull request's head before its stand-in starts, and label the pull request
# so the bot's automation can skip later pushes.
#
# Usage: stop-cursor-review.sh <number> <head-sha> [--repo <owner/name>] [--bot-check <name prefix>]
#                              [--label <name>]
#   Defaults: --bot-check "Cursor Automation", --label review-takeover.
#   Run it when merge-on-verdict.sh --bot-check exits 5 or 7, before the stand-in starts ("Who reviews",
#   rule 4, in references/changing.md). Run from the repository, or name it with --repo.
# How it finds the bot: each check run on <head-sha> whose name starts with the --bot-check prefix links its
# agent (details_url https://cursor.com/agents/bc-...). The Cloud Agents API's list by prUrl does not return
# automation agents (tried 2026-10-30), so the check run is the only link. For each agent it reads
# GET /v1/agents/<id> and cancels its latestRunId (POST /v1/agents/<id>/runs/<run>/cancel); 409
# run_not_cancellable means that run had already finished. Cursor Bugbot, the approval agent and the security
# agent have their own check names and are left alone.
# The key: CURSOR_API_KEY from the environment, else the CURSOR_API_KEY= line of ~/.config/cursor/api.env
# (CURSOR_API_ENV overrides the path). The file is read, never sourced, and the key reaches curl on stdin
# (curl -K -), so it never appears in a command line or in this script's output.
# The label: created in the repository if it is missing, then added to the pull request. The bot's automation
# skips a labelled pull request only once its owner adds that rule in the Cursor dashboard; the label alone
# changes nothing in Cursor.
# Exit codes:
#   0  every bot run found on the head was cancelled or had already finished, and the label is on the pull request
#   3  something could not be checked or done (no key, no bot check run on the head, an API or gh error, the
#      label not added); each line on stderr says what. Start the stand-in anyway: this never blocks it
#   64 a usage error
# Tests: test_stop_cursor_review.py, run by the repository's scripts/check.sh.
set -euo pipefail

number="" head="" bot_check="Cursor Automation" label="review-takeover"
api="${CURSOR_API_URL:-https://api.cursor.com}"
usage() { echo "$1" >&2; echo "usage: $0 <number> <head-sha> [--repo <owner/name>] [--bot-check <name prefix>] [--label <name>]" >&2; exit 64; }
while [ $# -gt 0 ]; do
  case "$1" in
    --repo|--bot-check|--label)
      [ $# -ge 2 ] && [ -n "$2" ] || usage "missing value for $1"
      case "$1" in
        --repo) export GH_REPO="$2" ;;   # every gh call, {owner}/{repo} too
        --bot-check) bot_check="$2" ;; --label) label="$2" ;;
      esac
      shift 2 ;;
    -*) usage "unknown argument: $1" ;;
    *) if [ -z "$number" ]; then number="$1"; elif [ -z "$head" ]; then head="$1"; else usage "too many arguments: $1"; fi
       shift ;;
  esac
done
[ -n "$number" ] && [ -n "$head" ] || usage "a number and a head are required"

status=0
problem() { echo "$1" >&2; status=3; }

key="${CURSOR_API_KEY:-}"
if [ -z "$key" ]; then
  env_file="${CURSOR_API_ENV:-$HOME/.config/cursor/api.env}"
  [ -r "$env_file" ] && key=$(sed -n 's/^[[:space:]]*\(export[[:space:]]\{1,\}\)\{0,1\}CURSOR_API_KEY=//p' "$env_file" | tail -1 | tr -d "\"'\r")
fi

body=$(mktemp)
trap 'rm -f "$body"' EXIT
# Calls the Cloud Agents API: cursor <method> <path>. The body lands in $body; the HTTP code is printed.
cursor() {
  local code
  code=$(printf 'header = "Authorization: Bearer %s"\n' "$key" |
    curl -sS -K - -o "$body" -w '%{http_code}' -X "$1" "$api$2") || true   # curl prints 000 when it cannot connect
  echo "${code:-000}"
}

if [ -z "$key" ]; then
  problem "no Cursor API key (CURSOR_API_KEY, or ${CURSOR_API_ENV:-~/.config/cursor/api.env}); the bot's run was not stopped"
elif ! agents=$(BOT_CHECK="$bot_check" gh api --paginate "repos/{owner}/{repo}/commits/$head/check-runs" \
    --jq '.check_runs[] | select(.name | startswith(env.BOT_CHECK)) | .details_url
          | capture("cursor\\.com/agents/(?<id>bc-[A-Za-z0-9-]+)").id'); then
  problem "could not read the check runs on $head"
elif [ -z "$agents" ]; then
  problem "no \"$bot_check\" check run on $head links an agent; nothing to stop"
else
  for agent in $(printf '%s\n' "$agents" | sort -u); do
    code=$(cursor GET "/v1/agents/$agent")
    run=""
    [ "$code" = 200 ] && run=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("latestRunId") or "")' "$body" 2>/dev/null || true)
    if [ -z "$run" ]; then problem "agent $agent: no latest run to stop (HTTP $code)"; continue; fi
    code=$(cursor POST "/v1/agents/$agent/runs/$run/cancel")
    case "$code" in
      200|202|204) echo "cancelled run $run of agent $agent" ;;
      409) echo "run $run of agent $agent had already finished" ;;
      *) problem "agent $agent: cancelling run $run returned HTTP $code" ;;
    esac
  done
fi

if ! gh api "repos/{owner}/{repo}/labels/$label" --silent 2>/dev/null &&
   ! gh label create "$label" --color BFD4F2 \
       --description "The review bot was stopped; its stand-in gives the verdict" >/dev/null; then
  problem "could not create the label $label"
elif gh pr edit "$number" --add-label "$label" >/dev/null; then
  echo "labelled #$number $label"
else
  problem "could not add the label $label to #$number"
fi
exit "$status"
