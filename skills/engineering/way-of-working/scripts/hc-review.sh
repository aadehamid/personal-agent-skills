#!/usr/bin/env bash
# Run the independent review in an hc terminal (herdr-core, the Herdr app), wait for it, and print its report.
#
# Usage: hc-review.sh --branch <branch> --verify "<claims to verify>" [--kind codex|kimi|cursor] [--model <model>]
#   herdr-review.sh hands off to this script in an hc terminal (HC_TERMINAL_ID set, neither
#   HERDR_WORKSPACE_ID nor REX_SESSION set) or with --host hc, so the commands the docs name stay
#   the same. Reviewers, models, flags and prompt are herdr-review.sh's; test_hc_review.py runs both
#   scripts and compares what each launches and sends. hc is herdr-core's CLI, not Herdr TUI's
#   `herdr`: the two run separate servers and share no terminals (herdr.dev FAQ, 2026-10-29).
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
if [ -z "${HC_REVIEW_ORIGINAL:-}" ]; then
  copy=""
  if copy=$(mktemp "${TMPDIR:-/tmp}/hc-review.copy.XXXXXX" 2>/dev/null) && cp "$0" "$copy"; then
    HC_REVIEW_ORIGINAL=$0 exec bash "$copy" "$@"
  fi
  if [ -n "$copy" ]; then rm -f -- "$copy"; fi
  HC_REVIEW_ORIGINAL=$0
fi
self=$HC_REVIEW_ORIGINAL
unset HC_REVIEW_ORIGINAL
case "$0" in "${TMPDIR:-/tmp}"/hc-review.copy.*) rm -f -- "$0" ;; esac

started_at=$(python3 -c 'import time; print(time.time())')
rerun=$(printf '%q ' "$self" "$@")

usage="usage: $self --branch <branch> --verify <text> [--kind codex|kimi|cursor] [--model <model>]"
branch="" verify="" kind="codex" model=""
while [ $# -gt 0 ]; do
  # Every option takes a value; a missing one is a bad argument, not a later unbound variable.
  case "$1" in
    --branch|--verify|--model|--kind|--host)
      [ $# -ge 2 ] || { echo "$1 needs a value" >&2; echo "$usage" >&2; exit 2; } ;;
    *) echo "unknown argument: $1" >&2; echo "$usage" >&2; exit 2 ;;
  esac
  case "$1" in
    --branch) branch="$2" ;;
    --verify) verify="$2" ;;
    --model) model="$2" ;;
    --kind) kind="$2" ;;
    # herdr-review.sh's choice of host; this script is the hc one.
    --host) [ "$2" = hc ] || { echo "hc-review.sh runs only with --host hc, got: $2" >&2; exit 2; } ;;
  esac
  shift 2
done
[ -n "$branch" ] && [ -n "$verify" ] || { echo "$usage" >&2; exit 2; }
case "$kind" in
  codex) model="${model:-gpt-6-luna}" ;;
  kimi) model="${model:-kimi-code/k3.1-pro}" ;;
  cursor) model="${model:-cursor-grok-4.6-medium}" ;;
  *) echo "--kind must be codex, kimi or cursor, got: $kind" >&2; exit 2 ;;
esac

step="starting" trailer="" next_on_failure="$rerun" review="" last_screen=""
on_exit() {
  local code=$?
  trap '' TERM INT HUP
  [ -z "$last_screen" ] || rm -f "$last_screen"
  [ "$code" -ne 0 ] && [ -z "$trailer" ] || return 0
  echo "No review: $step failed; the error is above."
  echo "Next: $next_on_failure"
  exit 1
}
trap on_exit EXIT
trap 'exit 1' TERM INT HUP
if [ -z "${HC_TERMINAL_ID:-}" ]; then
  echo "HC_TERMINAL_ID is not set: this runs only inside an hc terminal (the Herdr app)." >&2
  step="checking for an hc terminal" next_on_failure="run it from an hc terminal: $rerun"
  exit 1
fi
# Ends the run with its reason and Next line.
stop() { trailer=1; echo "$1"; echo "Next: $2"; exit 1; }
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

# Cursor's sandbox may block the macOS temporary folder ($TMPDIR, under /var/folders) but
# allows /tmp, so a Cursor reviewer gets its report path there.
step="creating the report file"
report_dir="${TMPDIR:-/tmp}"
if [ "$kind" = cursor ]; then report_dir="${HERDR_REVIEW_DIR:-/tmp/herdr-reviews}"; mkdir -p "$report_dir"; fi
report=$(mktemp "$report_dir/review-XXXXXX")
rm -f "$report"
echo "Report file: $report" >&2
prompt="Read AGENTS.md and the repository's review standards file (for example REVIEW_STANDARDS.md) first, and apply them. Run the ce-code-review skill (instructions: $HOME/.agents/skills/ce-code-review/SKILL.md) on branch $branch, diff vs main. Verify: $verify. For each finding, name the kind of defect and list every place in the repository that has it, including places outside the diff. Say how this could pass review while still being wrong. Report findings only; do not apply them. When the review is finished, write the final report as Markdown to exactly this path: $report. This is required even if the review skill also saves its own report elsewhere. Then reply with that path."

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
pi_next="$(dirname "$self")/pi-review.sh --role independent --head ${head_sha:-<sha>} --verify $(printf '%q' "$verify")"
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
  printf '%s' "$screen" | python3 -c '
import json, os, re, sys
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
screen = "\n".join(lines)
# Kimi'"'"'s input box, read whole, as rex-review.sh reads it: from its top border to its bottom
# border just above the status lines. A long prompt wraps over many lines inside it, or scrolls
# (the top border then reads "↑ 13 more"). Nothing inside the box counts as a question.
box, box_text, scrolled = set(), None, False
if kind == "kimi":
    ends = [i for i, l in enumerate(lines) if l.strip().startswith("\u2570")]
    if ends and len(lines) - 1 - ends[-1] <= 4:
        starts = [i for i in range(ends[-1]) if lines[i].strip().startswith("\u256d")]
        if starts:
            box = set(range(starts[-1], ends[-1] + 1))
            scrolled = bool(re.search(r"\u2191\s*\d+\s+more", lines[starts[-1]]))
            inner = [re.sub(r"^\s*\u2502\s?|\s*\u2502\s*$", "", lines[i]) for i in range(starts[-1] + 1, ends[-1])]
            if inner and re.match(r"^\s*>", inner[0]):
                box_text = " ".join([re.sub(r"^\s*>\s?", "", inner[0]).strip()] + [c.strip() for c in inner[1:]]).strip()
outside = [l for i, l in enumerate(lines) if i not in box]
bottom = [l for i, l in enumerate(lines) if i >= len(lines) - 12 and i not in box]
dialog = [l for i, l in enumerate(lines) if i >= len(lines) - 20 and i not in box]
last = open(last_path).read()
open(last_path, "w").write(screen)
limit = re.search(r"reached your [\w-]+ usage limit", "\n".join(dialog))
question = re.search(r"Run this command\?|Skip & tell the agent|Press enter to confirm|Hooks need review|"
                     r"\(y/n\)|\[y/N\]|Allow once|Trust this folder\?", "\n".join(dialog))
asked_at = next((i for i, l in enumerate(dialog) if l.strip() == "Trust this folder?"), None)
choice_at = next((i for i, l in enumerate(dialog) if re.match(r"^\s*❯\s*Trust and continue\s*$", l)), None)
trust = False
if kind == "kimi" and asked_at is not None and choice_at is not None and asked_at < choice_at:
    paths = [l.strip() for l in dialog[asked_at + 1:choice_at] if l.strip().startswith("/")]
    trust = len(paths) == 1 and os.path.realpath(paths[0]) == top
editor = {"kimi": r"^\s*│\s*>\s*(?P<text>.*?)\s*│?\s*$", "cursor": r"^\s*→\s*(?P<text>.*?)\s*$",
          "codex": r"^\s*›\s*(?P<text>.*?)\s*$"}[kind]
inputs = [box_text] if box_text is not None else [m.group("text") for m in (re.match(editor, l) for l in lines[-12:]) if m]
held = any(x.startswith(("Read AGENTS.md", "Write your final review report", "[Pasted text")) for x in inputs) or (
    kind == "kimi" and scrolled and box_text is not None and box_text.endswith("Then reply with that path."))
ready_text = {"kimi": ("",), "cursor": ("Plan, search, build anything", "Add a follow-up"), "codex": None}[kind]
ready = any(x in ready_text for x in inputs) if ready_text is not None else bool(inputs) and not held
if kind == "kimi" and ready:
    ready = any("context:" in l for l in lines[-12:])
busy = re.search(r"ctrl\+c to stop|esc to interrupt|Press Ctrl\+B to run in background|Working…|"
                 r"Running \d+ agents?|Agent Running", "\n".join(bottom))
if limit:
    word = "limit"
elif reported == "blocked":
    word = "blocked"
elif reported == "error":
    word = "error"
elif reported == "working":
    word = "working"
elif trust:
    word = "trust"
elif question:
    word = "blocked"
elif reported in ("idle", "done"):
    word = "idle"
elif busy:
    word = "working"
elif held:
    word = "unsent"
elif screen != last:
    word = "changing"
elif ready:
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

print_if_stable() {
  local last="" size
  for _ in $(seq 1 12); do
    if [ -s "$report" ]; then
      size=$(wc -c < "$report")
      if [ "$size" = "$last" ]; then finish; fi
      last=$size
    else
      last=""
    fi
    pause 5
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

# The report, then the reviewer's terminal ended and removed: only this run's own.
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
        finish
      elif [ "$matches" -gt 1 ]; then
        reason="$reason; several skill reports match this run; read them and pick: $(printf '%s' "$skill_reports" | tr '\n' ' ')"
        next="cp <the chosen report.md> '$report' && cat '$report'"
      else
        reason="$reason; no skill report for this run"
      fi
    fi ;;
  *)
    [ ! -s "$report" ] || reason="$reason; the file at the report path may be partial and was not printed" ;;
esac
trailer=1
show_screen 60
echo "No report at $report: $reason."
echo "Next: $next"
exit 1
