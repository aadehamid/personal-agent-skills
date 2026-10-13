#!/usr/bin/env bash
# Run Pi (through Ollama) as a reviewer, in a throwaway clone, and print its result.
#
# Usage: pi-review.sh --role pr|independent --head <sha> [--pr <number>] [--since <sha>] [--verify <claims>] [--model <model>]
#   --role pr           Pi is the PR reviewer. It posts one comment on the PR whose first
#                       line is MERGE or HOLD and whose second names the commit it reviewed.
#                       Needs --pr.
#   --role independent  Pi is the independent reviewer before a push. It writes its report
#                       to a file and posts nothing.
#   --since <sha>       Review only <sha>..<head>, the fix since the last review. Without it,
#                       review the whole change against the default branch.
#   --verify <claims>   What the reviewer must check, as for herdr-review.sh.
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

role="" head="" pr="" since="" verify="" model="glm-5.3-flash:cloud"
while [ $# -gt 0 ]; do
  case "$1" in
    --role) role="$2"; shift 2 ;;
    --head) head="$2"; shift 2 ;;
    --pr) pr="$2"; shift 2 ;;
    --since) since="$2"; shift 2 ;;
    --verify) verify="$2"; shift 2 ;;
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
# A PR verdict counts only for the PR's head, so a stale --head reviews nothing useful.
if [ "$role" = pr ]; then
  pr_head=$(gh pr view "$pr" --json headRefOid --jq .headRefOid)
  case "$pr_head" in
    "$head"*) head=$pr_head ;;
    *) echo "--head $head is not PR #$pr's head ($pr_head); review the head" >&2; exit 1 ;;
  esac
fi

remote=$(git remote get-url origin)
# The default branch, from origin/HEAD when the clone has one, else main.
default=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null || echo origin/main)
default=${default#origin/}
clone=$(mktemp -d /tmp/pi-review-XXXXXX)
echo "Clone: $clone" >&2
git clone -q "$remote" "$clone"
git -C "$clone" fetch -q origin "+refs/pull/*/head:refs/remotes/origin/pr/*" 2>/dev/null || true
# The independent review runs before the push it gates, so its commit may exist only here.
if [ "$role" = independent ]; then git -C "$clone" fetch -q "$PWD" "$head" 2>/dev/null || true; fi
git -C "$clone" checkout -q --detach "$head" || { echo "commit $head is in neither the remote nor this repository" >&2; exit 1; }

if [ -n "$since" ]; then
  change="git diff $since..$head (only the fix since your last review; check that the earlier findings are closed and that the fix broke nothing next to it)"
else
  change="git diff origin/$default...$head (the whole change)"
fi
standards="Read the repository's agent instructions and review standards files if it has them (AGENTS.md, CLAUDE.md, REVIEW_STANDARDS.md), and apply them."
look="Look for anything that lets a wrong result through, breaks a stated rule, or makes a description untrue. Do not report style."
[ -n "$verify" ] && look="$look Verify: $verify."
hands_off="Do not edit, create or delete any file in the repository, and do not run git commands that change it. Write scratch files under /tmp only."

# A mark only this run knows, so Pi's comment can be told from anyone else's.
mark="pi-review:$(basename "$clone")"
if [ "$role" = pr ]; then
  out="$clone.verdict"
  prompt="You are the pull request reviewer for PR #$pr. Review alone, with no subagents.
1. $standards
2. Read the PR description and its earlier review comments: gh pr view $pr --comments.
3. Read the change: $change.
4. $look
5. Post exactly one comment on the PR with: gh pr comment $pr --body-file <file>. Its first line is exactly MERGE or HOLD, its second line is exactly Reviewed commit: $head, and its last line is exactly <!-- $mark -->. For a HOLD, list each blocking finding with the file, line and a concrete input or reason. For a MERGE, list anything non-blocking in one short list.
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

# Stop a whole process group: TERM, then KILL, and return 1 if it is still alive about
# 15 s later. `ollama launch` runs Pi as a child and does not pass a signal on, so
# killing the parent alone leaves Pi able to post late.
stop_group() {
  kill -TERM -- "-$1" 2>/dev/null || return 0
  for _ in $(seq 1 20); do
    kill -0 -- "-$1" 2>/dev/null || return 0
    sleep 0.5
  done
  kill -KILL -- "-$1" 2>/dev/null || true
  for _ in $(seq 1 50); do
    kill -0 -- "-$1" 2>/dev/null || return 0
    sleep 0.1
  done
  return 1
}

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
  if ! herdr agent prompt "$pane" "$prompt" --wait --timeout 3600000 > "$clone.log" 2>&1; then
    # The prompt timed out or stalled, and Pi may still be working. Stop the pane's
    # foreground group, which holds `ollama launch` and Pi, and leave the shell to read.
    # When the shell's own group is in front, Pi has already exited and there is nothing to stop.
    stopped=no
    if group=$(herdr pane process-info --pane "$pane" | python3 -c '
import json, sys
p = json.load(sys.stdin)["result"]["process_info"]
g = p.get("foreground_process_group_id")
print(g if g and g != p.get("shell_pid") else "")'); then
      if [ -z "$group" ] || stop_group "$group"; then stopped=yes; fi
    fi
    tail -n 5 "$clone.log" || true
    if [ "$stopped" = yes ]; then
      echo "Pi's prompt in tab $tab did not finish within an hour, or never started work; Pi is stopped. Its log is $clone.log."
    else
      echo "Pi's prompt in tab $tab did not finish within an hour, or never started work, and Pi could not be stopped: it may still post. Stop it in tab $tab. Its log is $clone.log."
    fi
    exit 1
  fi
  herdr pane read "$pane" --lines 200 >> "$clone.log" 2>&1 || true
else
  # Headless Pi gets the same one-hour bound as the Herdr prompt. macOS has no timeout(1).
  # Job control gives the job its own process group, so the limit can stop Pi with it.
  # A job-control job keeps the terminal as stdin, so stdin is closed explicitly.
  set -m
  (cd "$clone" && exec ollama launch pi --model "$model" -y -- -p --no-session "$prompt") < /dev/null > "$clone.log" 2>&1 &
  pi_pid=$!
  set +m
  for _ in $(seq 1 "${PI_REVIEW_POLLS:-720}"); do
    kill -0 "$pi_pid" 2>/dev/null || break
    sleep 5
  done
  if kill -0 "$pi_pid" 2>/dev/null; then
    if stop_group "$pi_pid"; then
      echo "Pi did not finish within an hour and is stopped. Its log is $clone.log."
    else
      echo "Pi did not finish within an hour, and its process group $pi_pid would not stop: it may still post. Its log is $clone.log."
    fi
    exit 1
  fi
  wait "$pi_pid" || true
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
# A verdict file without the comment would let a merge go ahead on a review nobody can
# read. Only a comment carrying this run's mark counts, with the same first line and the
# reviewed commit on its second, so a reader can tell when the verdict is stale.
if [ "$role" = pr ]; then
  posted=$(gh pr view "$pr" --json comments | MARK="$mark" V="$first" HEAD_SHA="$head" python3 -c '
import json, os, sys
mark, v = "<!-- " + os.environ["MARK"] + " -->", os.environ["V"]
reviewed = "Reviewed commit: " + os.environ["HEAD_SHA"]
for c in json.load(sys.stdin)["comments"]:
    lines = c["body"].strip().splitlines()
    if len(lines) > 1 and lines[0].strip() == v and lines[1].strip() == reviewed and mark in c["body"]:
        print("found"); break' || true)
  if [ -z "$posted" ]; then
    echo "Pi wrote '$first' but posted no new comment starting with '$first' and naming commit $head on PR #$pr. Read $clone.log."
    exit 1
  fi
  # A push that landed while Pi read leaves its verdict on a commit that is no longer the head.
  # The comment names $head, so on the PR it reads as a verdict on that older commit.
  now_head=$(gh pr view "$pr" --json headRefOid --jq .headRefOid)
  if [ "$now_head" != "$head" ]; then
    echo "PR #$pr's head moved to $now_head while Pi reviewed $head; its '$first' names $head and is not the current verdict. Review the new head."
    exit 1
  fi
fi
# The tab closes only now, after every check passed; on any failure it stays open to read.
[ -n "${tab:-}" ] && herdr tab close "$tab" > /dev/null 2>&1 || true
cat "$out"
# A passed run leaves nothing behind; a failed one keeps the clone and log to read.
rm -rf "$clone" "$clone.log" "$out"
