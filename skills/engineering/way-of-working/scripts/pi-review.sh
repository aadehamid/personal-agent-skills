#!/usr/bin/env bash
# Run Pi (through Ollama) as a reviewer, in a throwaway clone, and print its result.
#
# Usage: pi-review.sh --role pr|independent --head <sha> [--pr <number>] [--since <sha>] [--model <model>]
#   --role pr           Pi is the PR reviewer. It posts one comment on the PR whose first
#                       line is MERGE or HOLD. Needs --pr.
#   --role independent  Pi is the independent reviewer before a push. It writes its report
#                       to a file and posts nothing.
#   --since <sha>       Review only <sha>..<head>, the fix since the last review. Without it,
#                       review the whole change against the default branch.
#   --model             Default glm-5.3-flash:cloud.
#   Run from the repository under review, as a background job the harness reports back
#   on (Claude Code: run_in_background): a review outlasts a foreground call.
# Pi runs in a fresh clone under /tmp, never in your working tree: a reviewer that checks
# out a commit there changes the files under your feet. Inside a Herdr pane
# (HERDR_WORKSPACE_ID set), Pi runs interactively in its own tab, pi-<role>-<repo>, so
# the owner can watch it; the script closes the tab when Pi has answered. Elsewhere Pi
# runs headless.
# Exit 0: the result is printed (the verdict line for pr, the report for independent).
# Exit 1: no result; the output says why.
# Tests: test_pi_review.py, run by the repository's scripts/check.sh.
set -euo pipefail

role="" head="" pr="" since="" model="glm-5.3-flash:cloud"
while [ $# -gt 0 ]; do
  case "$1" in
    --role) role="$2"; shift 2 ;;
    --head) head="$2"; shift 2 ;;
    --pr) pr="$2"; shift 2 ;;
    --since) since="$2"; shift 2 ;;
    --model) model="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
case "$role" in
  pr) [ -n "$pr" ] || { echo "--role pr needs --pr <number>" >&2; exit 2; } ;;
  independent) ;;
  *) echo "usage: $0 --role pr|independent --head <sha> [--pr <n>] [--since <sha>]" >&2; exit 2 ;;
esac
[ -n "$head" ] || { echo "--head <sha> is required" >&2; exit 2; }

remote=$(git remote get-url origin)
# The default branch, from origin/HEAD when the clone has one, else main.
default=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null || echo origin/main)
default=${default#origin/}
clone=$(mktemp -d /tmp/pi-review-XXXXXX)
echo "Clone: $clone" >&2
git clone -q "$remote" "$clone"
git -C "$clone" fetch -q origin "+refs/pull/*/head:refs/remotes/origin/pr/*" 2>/dev/null || true
git -C "$clone" checkout -q --detach "$head" || { echo "commit $head is not on the remote; push it first" >&2; exit 1; }

if [ -n "$since" ]; then
  change="git diff $since..$head (only the fix since your last review; check that the earlier findings are closed and that the fix broke nothing next to it)"
else
  change="git diff origin/$default...$head (the whole change)"
fi
standards="Read the repository's agent instructions and review standards files if it has them (AGENTS.md, CLAUDE.md, REVIEW_STANDARDS.md), and apply them."
look="Look for anything that lets a wrong result through, breaks a stated rule, or makes a description untrue. Do not report style."
hands_off="Do not edit, create or delete any file in the repository, and do not run git commands that change it. Write scratch files under /tmp only."

if [ "$role" = pr ]; then
  out="$clone.verdict"
  prompt="You are the pull request reviewer for PR #$pr. Review alone, with no subagents.
1. $standards
2. Read the PR description and its earlier review comments: gh pr view $pr --comments.
3. Read the change: $change.
4. $look
5. Post exactly one comment on the PR with: gh pr comment $pr --body-file <file>. Its first line is exactly MERGE or HOLD. For a HOLD, list each blocking finding with the file, line and a concrete input or reason. For a MERGE, list anything non-blocking in one short list.
6. Write the same first line, MERGE or HOLD, to $out.
$hands_off"
else
  out="$clone.report.md"
  prompt="You are the independent reviewer for this change, before it is pushed for review. Review alone, with no subagents.
1. $standards
2. Read the change: $change.
3. $look Also say how this could pass review while still being wrong.
4. Write your report as Markdown to exactly this path: $out. Its first line is exactly READY or FIX. List each finding with the file, line and a concrete input or reason. Post nothing anywhere.
$hands_off"
fi

comments() { gh pr view "$pr" --json comments --jq '.comments | length'; }
[ "$role" = pr ] && before=$(comments)
if [ -n "${HERDR_WORKSPACE_ID:-}" ]; then
  repo=$(basename "$PWD")
  created=$(herdr tab create --workspace "$HERDR_WORKSPACE_ID" --cwd "$clone" --label "pi-$role-$repo" --no-focus)
  pane=$(printf '%s' "$created" | python3 -c 'import json,sys; print(json.load(sys.stdin)["result"]["root_pane"]["pane_id"])')
  tab=$(printf '%s' "$created" | python3 -c 'import json,sys; print(json.load(sys.stdin)["result"]["tab"]["tab_id"])')
  echo "Pi tab: $tab" >&2
  herdr pane run "$pane" "ollama launch pi --model $model -y" > /dev/null
  # Wait up to a minute for Pi to start; herdr reports the pane's agent once it does.
  for _ in $(seq 1 30); do
    agent=$(herdr pane get "$pane" | python3 -c 'import json,sys; print(json.load(sys.stdin)["result"]["pane"].get("agent") or "")')
    [ "$agent" = pi ] && break
    sleep 2
  done
  if [ "$agent" != pi ]; then
    herdr pane read "$pane" --lines 30 || true
    echo "Pi did not start in tab $tab. Read the pane above."
    exit 1
  fi
  herdr agent prompt "$pane" "$prompt" --wait --timeout 3600000 > "$clone.log" 2>&1 || true
  herdr pane read "$pane" --lines 200 >> "$clone.log" 2>&1 || true
  [ -s "$out" ] && herdr tab close "$tab" > /dev/null 2>&1 || true
else
  (cd "$clone" && ollama launch pi --model "$model" -y -- -p --no-session "$prompt") > "$clone.log" 2>&1 || true
fi
if [ ! -s "$out" ]; then
  tail -n 30 "$clone.log" || true
  echo "Pi wrote no result to $out. Its log is $clone.log."
  exit 1
fi
first=$(head -n 1 "$out")
case "$role:$first" in
  pr:MERGE|pr:HOLD|independent:READY|independent:FIX) ;;
  *) echo "Pi's result starts with '$first', not a verdict. Read $out and $clone.log."; exit 1 ;;
esac
# A verdict file without the comment would let a merge go ahead on a review nobody can read.
if [ "$role" = pr ] && [ "$(comments)" -le "$before" ]; then
  echo "Pi wrote '$first' but posted no comment on PR #$pr. Read $clone.log."
  exit 1
fi
cat "$out"
