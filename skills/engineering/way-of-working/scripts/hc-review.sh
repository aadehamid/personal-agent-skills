#!/usr/bin/env bash
# Run the independent review in an hc terminal (herdr-core, the Herdr app), wait for it, and print its report.
#
# Usage: hc-review.sh --branch <branch> --verify "<claims to verify>" [--kind codex|kimi|cursor] [--model <model>]
#   herdr-review.sh hands off to this script in an hc terminal (HC_TERMINAL_ID set, neither
#   HERDR_WORKSPACE_ID nor REX_SESSION set) or with --host hc, so the commands the docs name stay
#   the same. Reviewers, models, flags and prompt are herdr-review.sh's; test_hc_review.py runs both
#   scripts and compares what each launches and sends. The arguments, default models, prompt,
#   report fallback and the screen reading it shares with rex-review.sh live in review-common.sh
#   beside it, which it sources from a private copy (below). hc is herdr-core's CLI, not Herdr
#   TUI's `herdr`: the two run separate servers and share no terminals (herdr.dev FAQ, 2026-10-29).
#   Each run starts its own reviewer, a child terminal of this agent's (it shows under this
#   agent in the Herdr app and ends with it), named rev-<repo>-<hash of kind:model>, with
#   --no-notify, since this script reports and hc's notes would be typed into the agent's input.
#   A review takes longer than a foreground tool call allows: run this as a background
#   job the harness reports back on, with its exit status (Claude Code: run_in_background).
# Exit 0: the report is on stdout, and nothing else is. The reviewer's terminal is then killed
#   and removed; only the terminal this run started is ever killed.
# Exit 1: no report. Every exit 1 ends stdout with two lines, the reason and "Next: <command>".
#   The reviewer's terminal is left running, so its screen can be read (hc read <t>).
# Exit 2: bad arguments.
# Status: a reviewer that reports its state (OSC 7501; Codex 0.166 did on 2026-10-29) is read
# from `hc get`. One that reports none (the Cursor agent v2026.10.22 did not; Kimi was not
# checked) is read from the bottom of its screen, as rex-review.sh does: nothing is typed unless
# the screen shows the reviewer's own input line, or Kimi's folder-trust dialog for this work
# tree. A blocked reviewer is a question for the owner: the script stops and never types past
# it (no `hc send --force`). Looks are paced by `hc wait <t> --timeout`, with a sleep only when
# that wait returns at once (pause, below).
# Codex and the Cursor agent get the prompt as their launch task, which hc's manual asks for
# ("a send to a booting agent can be dropped"); Kimi takes no interactive task argument, so its
# prompt is sent once its input line shows. A reviewer that reports its usage limit is not
# available: Next names pi-review.sh, the next reviewer in AGENTS.md's order.
# Tests: test_hc_review.py, run by the repository's scripts/check.sh.
set -euo pipefail

# The private copy, as in herdr-review.sh: a commit or checkout can rewrite this file mid-review.
# review-common.sh is copied at the same moment, from beside this file (not beside the copy), so
# the two copies match; the run sources its copy and removes it (below). When either copy cannot
# be made, both run in place.
if [ -z "${HC_REVIEW_ORIGINAL:-}" ]; then
  copy="" common=""
  if copy=$(mktemp "${TMPDIR:-/tmp}/hc-review.copy.XXXXXX" 2>/dev/null) && cp "$0" "$copy" \
     && common=$(mktemp "${TMPDIR:-/tmp}/hc-review.common.XXXXXX" 2>/dev/null) \
     && cp "$(dirname "$0")/review-common.sh" "$common" 2>/dev/null; then
    HC_REVIEW_ORIGINAL=$0 HC_REVIEW_COMMON=$common exec bash "$copy" "$@"
  fi
  if [ -n "$copy" ]; then rm -f -- "$copy"; fi
  if [ -n "$common" ]; then rm -f -- "$common"; fi
  HC_REVIEW_ORIGINAL=$0 HC_REVIEW_COMMON=""
fi
self=$HC_REVIEW_ORIGINAL
common=${HC_REVIEW_COMMON:-$(dirname "$self")/review-common.sh}
unset HC_REVIEW_ORIGINAL HC_REVIEW_COMMON
case "$0" in "${TMPDIR:-/tmp}"/hc-review.copy.*) rm -f -- "$0" ;; esac

started_at=$(python3 -c 'import time; print(time.time())')
rerun=$(printf '%q ' "$self" "$@")

# A missing review-common.sh is a broken install, not a bad argument: exit 1, with the two lines.
loaded=""
if [ -r "$common" ]; then
  # shellcheck source=review-common.sh
  . "$common"
  loaded=1
fi
case "$common" in "${TMPDIR:-/tmp}"/hc-review.common.*) rm -f -- "$common" ;; esac
if [ -z "$loaded" ]; then
  echo "cannot read $common: hc-review.sh needs review-common.sh beside it." >&2
  echo "No review: loading review-common.sh failed; the error is above."
  echo "Next: restore $(dirname "$self")/review-common.sh, then run: $rerun"
  exit 1
fi

parse_review_args hc "$@"

step="starting" trailer="" next_on_failure="$rerun" review="" last_screen=""
trap on_exit EXIT
trap 'exit 1' TERM INT HUP
if [ -z "${HC_TERMINAL_ID:-}" ]; then
  echo "HC_TERMINAL_ID is not set: this runs only inside an hc terminal (the Herdr app)." >&2
  step="checking for an hc terminal" next_on_failure="run it from an hc terminal: $rerun"
  exit 1
fi
# One field of a JSON object on stdin, by dotted path; empty when any part is missing or null.
jfield() {
  python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except ValueError:
    data = None
for key in sys.argv[1].split("."):
    data = data.get(key) if isinstance(data, dict) else None
print("" if data is None else (json.dumps(data) if isinstance(data, (dict, list)) else data))' "$1"
}

step="checking for an earlier reviewer"
top=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
top=$(python3 -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$top")
head_sha=$(git -C "$top" rev-parse HEAD 2>/dev/null || true)
repo=$(basename "$top")
reviewer_hash=$(printf '%s' "$kind:$model" | shasum | cut -c1-8)
slug=$(printf '%s' "$repo" | tr 'A-Z' 'a-z' | tr -cs 'a-z0-9' '-')
# hc names are unique among live terminals: 1-32 of a-z 0-9 - _.
name="rev-$(printf '%s' "$slug" | cut -c1-19)-$reviewer_hash"
name=${name//--/-}

# A live terminal holding the name is an earlier review. One in this work tree that is idle or
# done (or whose program ended) finished or gave up, and is removed; one working, blocked or
# reporting nothing is another review running, and the script stops rather than end it. One in
# another directory is left alone.
holder=$(hc ls --json | python3 -c '
import json, os, sys
name, top = sys.argv[1], sys.argv[2]
for t in json.load(sys.stdin).get("terminals", []):
    if t.get("name") == name or t.get("address") == name:
        here = os.path.realpath(t.get("cwd") or "") == top
        print(t.get("address", ""), "here" if here else "elsewhere", t.get("status") or "none")
        break' "$name" "$top")
if [ -n "$holder" ]; then
  read -r holder_addr holder_where holder_status <<<"$holder"
  if [ "$holder_where" = here ] && { [ "$holder_status" = idle ] || [ "$holder_status" = done ]; }; then
    hc kill "$holder_addr" --json >/dev/null
    hc wait "$holder_addr" --json --timeout 10 >/dev/null 2>&1 || true
    hc rm "$holder_addr" --json >/dev/null 2>&1 || true
    echo "removed the earlier reviewer $holder_addr (status $holder_status)" >&2
  elif [ "$holder_where" = here ]; then
    stop "Reviewer did not start: another review is running in $holder_addr; wait for it or close it." \
         "hc wait $holder_addr --timeout 3600 && $rerun"
  else
    stop "Reviewer did not start: the terminal $holder_addr holds the name $name but runs in another directory; it was left alone." \
         "end it if it is yours (hc kill $holder_addr; hc rm $holder_addr), then run: $rerun"
  fi
fi

step="creating the report file"
create_report_file
prompt=$(review_prompt)

step="starting the reviewer"
if [ "$kind" = kimi ]; then
  agent_cmd=(kimi) agent_args=(-m "$model" -y)
elif [ "$kind" = cursor ]; then
  agent_cmd=(cursor-agent) agent_args=(--model "$model" --sandbox enabled --force --trust)
else
  mkdir -p "$HOME/.npm" "$HOME/.claude" "$HOME/.cache" "$HOME/.config"
  roots="[\"$HOME/.npm\",\"$HOME/.claude\",\"$HOME/.cache\",\"$HOME/.config\"]"
  # --no-daemon: without it Codex's commands run outside hc (hc's manual).
  agent_cmd=(codex --no-daemon) agent_args=(-m "$model" -c model_reasoning_effort=medium
              -a never -s workspace-write -c sandbox_workspace_write.network_access=true
              -c "sandbox_workspace_write.writable_roots=$roots")
fi
task=()
[ "$kind" = kimi ] || task=("$prompt")
launched=$(hc run --bg --json --no-notify --name "$name" --cwd "$top" -- "${agent_cmd[@]}" "${agent_args[@]}" ${task[@]+"${task[@]}"})
review=$(printf '%s' "$launched" | jfield address)
[ -n "$review" ] || { echo "hc gave no terminal address: $launched" >&2; exit 1; }
echo "Review terminal: $review ($name)" >&2
next_on_failure="hc read $review --lines 60; cat '$report'"
answer="answer it (hc attach $review, or hc keys $review <key>)"
show_screen() { hc read "$review" --lines "$1" 2>/dev/null | tail -n "$1" || true; }
pi_next=$(next_reviewer)
# hc's launch can say the task was not delivered; then it was not, and nothing is resent blindly.
if [ "$(printf '%s' "$launched" | jfield first_message.sent)" = False ]; then
  show_screen 30
  stop "Reviewer did not start: hc did not send the prompt to it." "$answer if it shows a question, then end it (hc kill $review; hc rm $review) and run: $rerun"
fi

# One word for what the reviewer is doing:
#   gone        its program ended
#   limit       the screen reports its usage limit
#   blocked     it reports blocked, or a known question is on the bottom lines
#   error       it reports an error
#   working     it reports working, or a busy marker shows
#   trust       Kimi's trust dialog naming this work tree, "Trust and continue" selected
#   unsent      the reviewer's own input line still holds the prompt
#   changing    the screen moved since the last look (unreported reviewers only)
#   idle        it reports idle or done, or its own input line shows, empty, and nothing moved
#   unreadable  hc gave no answer
#   unknown     anything else that stays put: treated as a question
# The turn count of a reviewer that reports its state rises when it ends a turn; it is printed
# after the word.
last_screen=$(mktemp "${TMPDIR:-/tmp}/hc-review.screen.XXXXXX")
review_status() {
  local info screen
  info=$(hc get "$review" --json 2>/dev/null) || { echo unreadable 0; return; }
  screen=$(hc read "$review" 2>/dev/null) || screen=""
  # The shared reading is review-common.sh's read_screen; what follows it is hc's own.
  printf '%s' "$screen" | python3 -c "$screen_py"'
import json
kind, info, last_path, top = sys.argv[1:5]
try:
    t = json.loads(info)
except ValueError:
    print("unreadable 0"); sys.exit()
turn = t.get("turn") or 0
if t.get("state") == "finished":
    print("gone", turn); sys.exit()
status = t.get("status") if isinstance(t.get("status"), dict) else {}
reported = status.get("state") or ""
lines = [l for l in sys.stdin.read().splitlines() if not l.startswith("[hc] ")][-40:]
s = read_screen(kind, lines, top, last_path)
if s.limit:
    word = "limit"
elif reported == "blocked":
    word = "blocked"
elif reported == "error":
    word = "error"
elif reported == "working":
    word = "working"
elif s.trust:
    word = "trust"
elif s.question:
    word = "blocked"
elif reported in ("idle", "done"):
    word = "idle"
elif s.busy:
    word = "working"
elif s.held:
    word = "unsent"
elif s.changed:
    word = "changing"
elif s.ready:
    word = "idle"
else:
    word = "unknown"
print(word, turn)' "$kind" "$info" "$last_screen" "$top"
}
# The pause between looks: hc wait returns early when the reviewer's state changes or it exits.
# For a reviewer already idle, or one that reports no state, it returns at once or only at its
# timeout; a wait that returned within a second is followed by a sleep, so looks stay paced.
pause() {
  local t0=$SECONDS
  hc wait "$review" --json --timeout "$1" >/dev/null 2>&1 || true
  [ $((SECONDS - t0)) -ge 1 ] || sleep "$1"
}

# Kimi: its prompt goes in once its input line shows, after answering its folder trust for this
# work tree once (the owner, 2026-10-24: "it is okay to always trust the folder and continue").
if [ "$kind" = kimi ]; then
  step="waiting for the reviewer to be ready"
  settled="" trusted="" looks=0 unknown=0
  while [ "$looks" -lt 90 ]; do
    looks=$((looks + 1))
    read -r st _ < <(review_status)
    [ "$st" = unknown ] || unknown=0
    case "$st" in
      idle) settled=1; break ;;
      gone) show_screen 30; stop "Reviewer did not start: it exited." "$rerun" ;;
      limit) show_screen 30; stop "Reviewer not available: it reports its usage limit." "$pi_next" ;;
      trust)
        if [ -n "$trusted" ]; then show_screen 30; stop "Reviewer did not start: Kimi still asks to trust $top after Trust and continue." "$answer, then run: $rerun"; fi
        hc keys "$review" enter >/dev/null
        trusted=1
        echo "Kimi asked to trust $top; chose Trust and continue." >&2 ;;
      blocked|error|unsent) show_screen 30; stop "Reviewer did not start: it is waiting on a question or an unknown screen." "$answer, then run: $rerun" ;;
      unknown)
        unknown=$((unknown + 1))
        if [ "$unknown" -ge 5 ]; then show_screen 30; stop "Reviewer did not start: it is waiting on a question or an unknown screen." "$answer, then run: $rerun"; fi ;;
    esac
    pause 2
  done
  [ -n "$settled" ] || { show_screen 30; stop "Reviewer did not start: its screen never settled on its input line." "$rerun"; }
  hc send "$review" "$prompt" --json >/dev/null
fi

# The report, then the reviewer's terminal ended and removed: only this run's own. This and
# pause are the hooks review-common.sh's print_if_stable and report_fallback call.
finish() {
  cat "$report"
  hc kill "$review" --json >/dev/null 2>&1 || true
  hc wait "$review" --json --timeout 10 >/dev/null 2>&1 || true
  hc rm "$review" --json >/dev/null 2>&1 || true
  exit 0
}

# Look about every 5 seconds, within 60 minutes of the start. The report counts once two looks in
# a row see it at the same size while the reviewer is neither working nor blocked. A reviewer
# that reports its state has worked once its turn count rises; one that does not, once its
# screen moved or showed a busy marker. Asking for the report, or deciding it never comes, waits
# for six idle looks in a row. Only a finished or timed-out wait may fall back to the file or the
# review skill's report; blocked, gone, unsent and unreadable end with their reason.
step="waiting for the review"
asked="" worked="" last_size="" idle_streak=0 idle_unworked=0 blocked=0 unread=0 enters=0 turn0=""
ended="timeout"
reason="no report within 60 minutes; the review may still be running"
next="hc wait $review --timeout 3600; cat '$report'"
for _ in $(seq 1 720); do
  [ "$SECONDS" -lt 3600 ] || break
  read -r status turn < <(review_status)
  [ -n "$turn0" ] || turn0=$turn
  [ "$turn" -le "$turn0" ] || worked=1
  [ "$status" = idle ] && idle_streak=$((idle_streak + 1)) || idle_streak=0
  case "$status" in blocked|trust|unknown|error) ;; *) blocked=0 ;; esac
  [ "$status" = unreadable ] || unread=0
  case "$status" in
    unsent)
      if [ "$enters" -ge 3 ]; then ended="unsent" reason="the prompt stayed unsent after three Enters" next="$rerun"; break; fi
      enters=$((enters + 1)) idle_unworked=0
      read -r again _ < <(review_status)
      if [ "$again" = unsent ]; then
        hc keys "$review" enter >/dev/null 2>&1 || true
        echo "The prompt sat unsent on the input line; sent Enter." >&2
      else
        echo "Held the Enter: a fresh look shows $again." >&2
      fi ;;
    gone) ended="gone" reason="the reviewer exited" next="$rerun"; break ;;
    limit) ended="unavailable" reason="reviewer not available: it reports its usage limit" next="$pi_next"; break ;;
    unreadable)
      unread=$((unread + 1))
      if [ "$unread" -ge 12 ]; then ended="unreadable" reason="hc cannot read the reviewer's terminal"; break; fi ;;
    blocked|trust|unknown|error)
      blocked=$((blocked + 1))
      if [ "$blocked" -ge 24 ]; then
        ended="blocked" reason="the reviewer is waiting on a question"
        [ "$status" != error ] || reason="the reviewer reports an error"
        next="$answer, then run: hc wait $review --timeout 3600; cat '$report'"
        break
      fi ;;
    working) worked=1 idle_unworked=0 last_size="" ;;
    idle|changing)
      [ "$status" = idle ] || worked=1
      if [ -s "$report" ]; then
        size=$(wc -c < "$report")
        if [ "$size" = "$last_size" ]; then finish; fi
        last_size=$size
      elif [ -z "$worked" ]; then
        idle_unworked=$((idle_unworked + 1))
        if [ "$idle_unworked" -ge 60 ]; then
          ended="idle"
          if [ -n "$asked" ]; then reason="the reviewer did not act on the request to write the report"
          else reason="the reviewer never started work on the prompt"; fi
          next="$rerun"; break
        fi
      elif [ "$idle_streak" -ge 6 ] && [ -z "$asked" ]; then
        hc send "$review" "Write your final review report as Markdown to exactly this path: $report. Then reply with that path." --json >/dev/null 2>&1 || true
        asked=1 worked="" idle_unworked=0 idle_streak=0 turn0=$turn   # a later turn is the answer
      elif [ "$idle_streak" -ge 6 ]; then
        ended="idle" reason="the reviewer finished without writing the report, even when asked" next="$rerun"; break
      fi ;;
  esac
  pause 5
done

if [ "$ended" = timeout ] && [ "$blocked" -gt 0 ]; then
  ended="blocked" reason="the reviewer is waiting on a question" next="$answer, then run: hc wait $review --timeout 3600; cat '$report'"
fi
case "$ended" in
  timeout|idle)
    report_fallback ;;
  *)
    [ ! -s "$report" ] || reason="$reason; the file at the report path may be partial and was not printed" ;;
esac
trailer=1
show_screen 60
echo "No report at $report: $reason."
echo "Next: $next"
exit 1
