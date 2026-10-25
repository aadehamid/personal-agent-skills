#!/usr/bin/env bash
# Run the independent review in a Rex pane, wait for it, and print its report.
#
# Usage: rex-review.sh --branch <branch> --verify "<claims to verify>" [--kind codex|kimi|cursor] [--model <model>]
#   herdr-review.sh hands off to this script inside Rex (REX_SESSION set, HERDR_WORKSPACE_ID
#   unset) or with --host rex, so the commands the docs name stay the same. Reviewers, models
#   and flags are herdr-review.sh's; test_rex_review.py checks that the two scripts agree.
#   The first reviewer opens as a split beside this agent's pane (REX_BLOCK); when that window
#   already holds two panes, it opens in a new tab (the owner's layout, 2026-10-24). Each
#   reviewer's pane is labelled review-<repo>-<kind>-<hash of kind:model> and reused while its
#   reviewer runs.
#   A review takes longer than a foreground tool call allows: run this as a background
#   job the harness reports back on, with its exit status (Claude Code: run_in_background).
# Exit 0: the report is on stdout, and nothing else is.
# Exit 1: no report. Every exit 1 ends stdout with two lines, the reason and "Next: <command>".
# Exit 2: bad arguments.
# Rex does not know what an agent is doing: it shows the status a program reports (OSC 7501),
# and none of the reviewer CLIs reported one on 2026-10-24. So the status comes from the
# screen (pane_status below): the input line still holding the prompt, a question, a busy
# marker, or a screen that changed since the last look. A reported status wins when present.
# Tests: test_rex_review.py, run by the repository's scripts/check.sh.
set -euo pipefail

# The private copy, as in herdr-review.sh: a commit or checkout can rewrite this file mid-review.
if [ -z "${REX_REVIEW_ORIGINAL:-}" ]; then
  copy=""
  if copy=$(mktemp "${TMPDIR:-/tmp}/rex-review.copy.XXXXXX" 2>/dev/null) && cp "$0" "$copy"; then
    REX_REVIEW_ORIGINAL=$0 exec bash "$copy" "$@"
  fi
  if [ -n "$copy" ]; then rm -f -- "$copy"; fi
  REX_REVIEW_ORIGINAL=$0
fi
self=$REX_REVIEW_ORIGINAL
unset REX_REVIEW_ORIGINAL
case "$0" in "${TMPDIR:-/tmp}"/rex-review.copy.*) rm -f -- "$0" ;; esac

started_at=$(python3 -c 'import time; print(time.time())')
rerun=$(printf '%q ' "$self" "$@")

branch="" verify="" kind="codex" model=""
while [ $# -gt 0 ]; do
  case "$1" in
    --branch) branch="$2"; shift 2 ;;
    --verify) verify="$2"; shift 2 ;;
    --model) model="$2"; shift 2 ;;
    --kind) kind="$2"; shift 2 ;;
    --host) shift 2 ;;   # herdr-review.sh's choice of host; this script is the Rex one
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[ -n "$branch" ] && [ -n "$verify" ] || { echo "usage: $self --branch <branch> --verify <text>" >&2; exit 2; }
case "$kind" in
  codex) model="${model:-gpt-6-luna}" ;;
  kimi) model="${model:-kimi-code/k3.1-pro}" ;;
  cursor) model="${model:-cursor-grok-4.6-medium}" ;;
  *) echo "--kind must be codex, kimi or cursor, got: $kind" >&2; exit 2 ;;
esac

step="starting" trailer="" next_on_failure="$rerun" review_pane=""
on_exit() {
  local code=$?
  trap '' TERM INT HUP
  [ -z "${last_screen:-}" ] || rm -f "$last_screen"
  [ "$code" -ne 0 ] && [ -z "$trailer" ] || return 0
  echo "No review: $step failed; the error is above."
  echo "Next: $next_on_failure"
  exit 1
}
trap on_exit EXIT
trap 'exit 1' TERM INT HUP
if [ -z "${REX_SESSION:-}" ]; then
  echo "REX_SESSION is not set: this runs only inside a Rex pane." >&2
  step="checking for a Rex pane" next_on_failure="run it from a Rex pane: $rerun"
  exit 1
fi
reviewer_hash=$(printf '%s' "$kind:$model" | shasum | cut -c1-8)
# rex with this session: -s goes after the command's words (split, block ls, block call).
rx() {
  local n=1
  [ "$1" != block ] || n=2
  rex "${@:1:n}" -s "$REX_SESSION" "${@:n+1}"
}

step="finding the review pane"
top=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
head_sha=$(git -C "$top" rev-parse HEAD 2>/dev/null || true)
repo=$(basename "$top")
label="review-$repo-$kind-$reviewer_hash"
# One line: the pane labelled $label (empty if none), and the number of panes in the window
# that holds this agent's pane (0 if REX_BLOCK is unset or not in this session).
read -r review_pane own_window_panes < <(rx block ls --json | python3 -c '
import json, os, sys
label, mine = sys.argv[1], os.environ.get("REX_BLOCK", "")
blocks = json.load(sys.stdin)["blocks"]
pane = next((b["block_id"] for b in blocks if b.get("label") == label), "-")
win = next((b["window_id"] for b in blocks if b["block_id"] == mine), None)
print(pane, sum(1 for b in blocks if win and b["window_id"] == win))' "$label")
[ "$review_pane" != "-" ] || review_pane=""

# The reviewer runs while the pane's foreground program is not a shell.
reviewer_running() {
  rx block call -b "$review_pane" process 2>/dev/null | python3 -c '
import json, sys
fg = (json.load(sys.stdin).get("foreground") or {}).get("name", "")
sys.exit(0 if fg and fg.lstrip("-") not in ("zsh", "bash", "sh", "fish", "login") else 1)'
}
if [ -n "$review_pane" ] && ! reviewer_running; then
  # Its reviewer exited: the pane is closed and a fresh one opened.
  rx block close "$review_pane" >/dev/null 2>&1 || true
  echo "closed $review_pane (its reviewer had exited)" >&2
  review_pane=""
fi

if [ -n "$review_pane" ]; then
  echo "Review pane: $review_pane (reused)" >&2
  echo "Reusing the running reviewer in $review_pane: it keeps the flags it started with. To apply this script's current flags, close the pane once (rex block close -s $REX_SESSION $review_pane) and run again." >&2
else
  step="starting the reviewer"
  if [ "$kind" = kimi ]; then
    agent_cmd=(kimi) agent_args=(-m "$model" -y)
  elif [ "$kind" = cursor ]; then
    agent_cmd=(cursor-agent) agent_args=(--model "$model" --sandbox enabled --force --trust)
  else
    mkdir -p "$HOME/.npm" "$HOME/.claude" "$HOME/.cache" "$HOME/.config"
    roots="[\"$HOME/.npm\",\"$HOME/.claude\",\"$HOME/.cache\",\"$HOME/.config\"]"
    agent_cmd=(codex) agent_args=(-m "$model" -c model_reasoning_effort=medium
                -a never -s workspace-write -c sandbox_workspace_write.network_access=true
                -c "sandbox_workspace_write.writable_roots=$roots")
  fi
  # The owner's layout: a split beside this agent's pane while its window holds fewer than
  # two panes, otherwise a new tab. Neither takes focus.
  if [ "$own_window_panes" -ge 1 ] && [ "$own_window_panes" -lt 2 ]; then
    created=$(rx split -b "$REX_BLOCK" --split=right --focus=false --label "$label" -c "$top" --keep-open --json -- "${agent_cmd[@]}" "${agent_args[@]}")
  else
    created=$(rx run --label "$label" -c "$top" --focus=false --keep-open --json -- "${agent_cmd[@]}" "${agent_args[@]}")
  fi
  review_pane=$(printf '%s' "$created" | python3 -c 'import json, sys; print(json.load(sys.stdin)["block_ids"][0])')
  echo "Review pane: $review_pane (created)" >&2
fi
[ -n "$review_pane" ] || { echo "rex gave no review pane" >&2; exit 1; }
answer="answer it (rex send-key -s $REX_SESSION -b $review_pane <key>)"

# One word for what the reviewer is doing: unsent (the input line still holds the prompt),
# trust (Kimi asks to trust the folder, with "Trust and continue" selected), blocked (another
# question is on screen), working (a busy marker), changing (the screen moved
# since the last look), idle, or gone (the reviewer exited). A status the program reports
# through OSC 7501 wins over the screen. Only the bottom of the screen is read for the input
# line and for questions, so the same words quoted higher up, such as in a diff, count for
# nothing.
last_screen=$(mktemp "${TMPDIR:-/tmp}/rex-review.screen.XXXXXX")
pane_status() {
  local reported screen
  if ! reviewer_running; then echo gone; return; fi
  reported=$(rx block call -b "$review_pane" program_status 2>/dev/null | python3 -c '
import json, sys
try:
    recs = json.load(sys.stdin).get("records") or []
except ValueError:
    recs = []
root = next((r for r in recs if "id" not in r), None)
state = (root or {}).get("state", "")
print({"working": "working", "blocked": "blocked"}.get(state, "idle" if state else ""))' || true)
  screen=$(rx capture -b "$review_pane" --trim 2>/dev/null | tail -n 40 || true)
  printf '%s' "$screen" | python3 -c '
import re, sys
reported, last_path = sys.argv[1], sys.argv[2]
screen = sys.stdin.read()
bottom = "\n".join(screen.splitlines()[-12:])
last = open(last_path).read()
open(last_path, "w").write(screen)
if re.search(r"(?m)^\s*(│\s*)?[>›→]\s*(\[Pasted text|Read AGENTS\.md)", bottom):
    print("unsent")
elif re.search(r"(?m)^\s*❯\s*Trust and continue\s*$", bottom):
    print("trust")
elif reported:
    print(reported)
elif re.search(r"Run this command\?|Skip & tell the agent|Press enter to confirm|Hooks need review|Trust this folder\?|\(y/n\)|\[y/N\]|Allow once", bottom):
    print("blocked")
elif re.search(r"ctrl\+c to stop|esc to interrupt|Press Ctrl\+B to run in background", bottom):
    print("working")
elif screen != last:
    print("changing")
else:
    print("idle")' "$reported" "$last_screen"
}

# A fresh reviewer gets the prompt once its screen has settled: two looks alike, or a
# question that has to be answered first. Just after the pane opens, its foreground program
# is still the login shell that starts the reviewer, so "gone" counts only after ten looks
# in a row (2026-10-24: one look too early read a starting Kimi as exited).
if [ "${created:-}" ]; then
  step="waiting for the reviewer to start"
  settled=0 gone_looks=0 trusted=0
  for _ in $(seq 1 60); do
    st=$(pane_status)
    if [ "$st" = gone ]; then
      gone_looks=$((gone_looks + 1))
      if [ "$gone_looks" -lt 10 ]; then sleep 2; continue; fi
    else
      gone_looks=0
    fi
    case "$st" in
      idle|unsent) settled=1; break ;;
      trust)
        # The owner, 2026-10-24: "it is okay to always trust the folder and continue". Folder
        # trust only: Codex's hook review approves code and stays a question.
        if [ "$trusted" -lt 2 ]; then
          rx send-key -b "$review_pane" enter >/dev/null
          trusted=$((trusted + 1))
          echo "Kimi asked to trust $top; chose Trust and continue." >&2
        fi ;;
      blocked)
        rx capture -b "$review_pane" --trim | tail -n 30 || true
        trailer=1
        echo "Reviewer did not start: it is waiting on a question."
        echo "Next: $answer, then run: $rerun"
        exit 1 ;;
      gone)
        rx capture -b "$review_pane" --trim | tail -n 30 || true
        trailer=1
        echo "Reviewer did not start: it exited."
        echo "Next: $rerun"
        exit 1 ;;
    esac
    sleep 2
  done
  [ "$settled" = 1 ] || { echo "the reviewer's screen never settled" >&2; exit 1; }
fi

step="creating the report file"
report_dir="${TMPDIR:-/tmp}"
if [ "$kind" = cursor ]; then report_dir="${HERDR_REVIEW_DIR:-/tmp/herdr-reviews}"; mkdir -p "$report_dir"; fi
report=$(mktemp "$report_dir/review-XXXXXX")
rm -f "$report"
echo "Report file: $report" >&2
prompt="Read AGENTS.md and the repository's review standards file (for example REVIEW_STANDARDS.md) first, and apply them. Run the ce-code-review skill (instructions: $HOME/.agents/skills/ce-code-review/SKILL.md) on branch $branch, diff vs main. Verify: $verify. For each finding, name the kind of defect and list every place in the repository that has it, including places outside the diff. Say how this could pass review while still being wrong. Report findings only; do not apply them. When the review is finished, write the final report as Markdown to exactly this path: $report. This is required even if the review skill also saves its own report elsewhere. Then reply with that path."

# Text first, then Enter as its own key, a moment later: an Enter sent with the text can
# land as a new line in the input box (Kimi, 2026-10-24). The poll below sends up to three
# more while the input line still shows the prompt.
send_prompt() {
  rx send -b "$review_pane" "$1" >/dev/null
  sleep 1
  rx send-key -b "$review_pane" enter >/dev/null
}

print_if_stable() {
  local last="" size
  for _ in $(seq 1 12); do
    if [ -s "$report" ]; then
      size=$(wc -c < "$report")
      if [ "$size" = "$last" ]; then cat "$report"; exit 0; fi
      last=$size
    else
      last=""
    fi
    sleep 5
  done
}

# herdr-review.sh's fallback, unchanged: the ce-code-review report.md of this run, branch
# and HEAD, when the reviewer wrote no file at the report path.
find_skill_reports() {
  python3 - "$started_at" "$branch" "$head_sha" "$(id -u)" "${HERDR_REVIEW_ARTIFACT_ROOTS:-/tmp:${TMPDIR:-/tmp}}" <<'PY'
import glob, json, os, sys
start, branch, head, uid, roots = sys.argv[1:]
for root in dict.fromkeys(r for r in roots.split(":") if r):
    pattern = os.path.join(root, "compound-engineering-" + uid, "ce-code-review", "*", "report.md")
    for path in sorted(glob.glob(pattern)):
        try:
            if os.path.getmtime(path) <= float(start) or os.path.getsize(path) == 0:
                continue
            with open(os.path.join(os.path.dirname(path), "metadata.json")) as f:
                meta = json.load(f)
        except (OSError, ValueError):
            continue
        if isinstance(meta, dict) and head and meta.get("branch") == branch and meta.get("head_sha") == head:
            print(path)
PY
}

step="waiting for the review"
send_prompt "$prompt"
next_on_failure="rex capture -s $REX_SESSION -b $review_pane --trim | tail -n 60; cat '$report'"

# Poll every 5 seconds, within 60 minutes of the start. The report counts once two looks in
# a row see it at the same size while no busy marker shows; a screen that only changes (a
# spinner, a rotating tip) does not hold it back. A reviewer idle without the report, after
# it has worked, is asked once for it. Each counter ends the wait with its reason.
asked="" worked="" last_size="" idle_unworked=0 blocked=0 enters=0
reason="no report within 60 minutes; the review may still be running"
next="$next_on_failure"
for _ in $(seq 1 720); do
  [ "$SECONDS" -lt 3600 ] || break
  status=$(pane_status)
  case "$status" in
    unsent)
      if [ "$enters" -lt 3 ]; then
        rx send-key -b "$review_pane" enter >/dev/null || true
        enters=$((enters + 1)) idle_unworked=0
        echo "The prompt sat unsent on the input line; sent Enter." >&2
      fi
      ;;
    gone)
      reason="the reviewer exited"; next="$rerun"; break ;;
    blocked)
      blocked=$((blocked + 1))
      if [ "$blocked" -ge 24 ]; then
        reason="the reviewer is waiting on a question"
        next="$answer, then run: $next_on_failure"
        break
      fi
      ;;
    working)
      worked=1 blocked=0 idle_unworked=0 last_size="" ;;
    idle|changing)
      blocked=0
      [ "$status" = idle ] || worked=1
      if [ -s "$report" ]; then
        size=$(wc -c < "$report")
        if [ "$size" = "$last_size" ]; then cat "$report"; exit 0; fi
        last_size=$size
      elif [ -z "$worked" ]; then
        idle_unworked=$((idle_unworked + 1))
        if [ "$idle_unworked" -ge 60 ]; then
          if [ -n "$asked" ]; then
            reason="the reviewer did not act on the request to write the report"
          else
            reason="the reviewer never started work on the prompt"
          fi
          next="$rerun"; break
        fi
      elif [ "$status" = idle ] && [ -z "$asked" ]; then
        send_prompt "Write your final review report as Markdown to exactly this path: $report. Then reply with that path."
        asked=1 worked="" idle_unworked=0
      elif [ "$status" = idle ]; then
        reason="the reviewer finished without writing the report, even when asked"
        next="$rerun"; break
      fi
      ;;
  esac
  sleep 5
done

print_if_stable
if [ -s "$report" ]; then
  reason="$reason; the file at the report path is still changing"
  next="cat '$report'"
else
  skill_reports=$(find_skill_reports)
  matches=$(printf '%s' "$skill_reports" | grep -c . || true)
  if [ "$matches" = 1 ]; then
    cp "$skill_reports" "$report"
    echo "The reviewer did not write $report; copied the review skill's report from this run: $skill_reports" >&2
    cat "$report"; exit 0
  elif [ "$matches" -gt 1 ]; then
    reason="$reason; several skill reports match this run; read them and pick: $(printf '%s' "$skill_reports" | tr '\n' ' ')"
    next="cp <the chosen report.md> '$report' && cat '$report'"
  else
    reason="$reason; no skill report for this run"
  fi
fi
trailer=1
rx capture -b "$review_pane" --trim 2>/dev/null | tail -n 60 || true
echo "No report at $report: $reason."
echo "Next: $next"
exit 1
