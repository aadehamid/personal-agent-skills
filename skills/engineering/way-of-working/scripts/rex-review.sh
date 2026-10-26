#!/usr/bin/env bash
# Run the independent review in a Rex pane, wait for it, and print its report.
#
# Usage: rex-review.sh --branch <branch> --verify "<claims to verify>" [--kind codex|kimi|cursor] [--model <model>]
#   herdr-review.sh hands off to this script inside Rex (REX_SESSION set, HERDR_WORKSPACE_ID
#   unset) or with --host rex, so the commands the docs name stay the same. Reviewers, models,
#   flags and prompt are herdr-review.sh's; test_rex_review.py runs both scripts and compares
#   what each launches and sends. The two stay separate files because each runs from a private
#   copy of itself, which sourcing a shared sibling would undo.
#   The first reviewer opens as a split beside this agent's pane (REX_BLOCK); when that window
#   already holds two panes, it opens in a new tab (the owner's layout, 2026-10-24). Each
#   reviewer's pane is labelled review-<repo>-<kind>-<hash of kind:model>-<hash of the work
#   tree's path>, and is reused only while that reviewer runs there.
#   A review takes longer than a foreground tool call allows: run this as a background
#   job the harness reports back on, with its exit status (Claude Code: run_in_background).
# Exit 0: the report is on stdout, and nothing else is.
# Exit 1: no report. Every exit 1 ends stdout with two lines, the reason and "Next: <command>".
# Exit 2: bad arguments.
# Rex does not know what an agent is doing: it shows the status a program reports (OSC 7501),
# and none of the reviewer CLIs reported one on 2026-10-24. So the status comes from the pane's
# process and the bottom of its screen (pane_status below). Nothing is typed into the pane
# unless the screen positively shows the reviewer's own input line, Kimi's folder-trust
# dialog for this work tree, or Kimi's idle-session question (answered "Start a new session",
# with the prompt sent again if the new session dropped it); any other screen that stays put
# is a question, and the script stops there. A reviewer that reports its usage limit is not
# available: the script stops, and Next names pi-review.sh, the next reviewer in AGENTS.md's
# order. A reused pane still working on an earlier run's review is waited for, up to 45
# minutes, and that review's report is taken when it matches this branch and HEAD.
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
    # herdr-review.sh's choice of host; this script is the Rex one.
    --host) [ "$2" = rex ] || { echo "rex-review.sh runs only with --host rex, got: $2" >&2; exit 2; } ;;
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

step="starting" trailer="" next_on_failure="$rerun" review_pane="" last_screen=""
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
if [ -z "${REX_SESSION:-}" ]; then
  echo "REX_SESSION is not set: this runs only inside a Rex pane." >&2
  step="checking for a Rex pane" next_on_failure="run it from a Rex pane: $rerun"
  exit 1
fi
# Ends the run with its reason and Next line.
stop() { trailer=1; echo "$1"; echo "Next: $2"; exit 1; }
# rex with this session: -s goes after the command's words (split, block ls, block call).
rx() {
  local n=1
  [ "$1" != block ] || n=2
  rex "${@:1:n}" -s "$REX_SESSION" "${@:n+1}"
}

step="finding the review pane"
top=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
top=$(python3 -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$top")
head_sha=$(git -C "$top" rev-parse HEAD 2>/dev/null || true)
repo=$(basename "$top")
reviewer_hash=$(printf '%s' "$kind:$model" | shasum | cut -c1-8)
tree_hash=$(printf '%s' "$top" | shasum | cut -c1-6)
label="review-$repo-$kind-$reviewer_hash-$tree_hash"
# The reviewer's program names, as the process listing shows them (name, argv0 or file name).
case "$kind" in
  kimi) expected="kimi kimi-code" ;;
  cursor) expected="cursor-agent agent" ;;
  codex) expected="codex" ;;
esac

# One word for what runs in a pane, from its process record: reviewer (this kind's program,
# started in this work tree), shell (a shell or the login wrapper: still starting, or the
# reviewer left), exited (the program ended; the pane stays open), other (another program, or
# this program in another directory), or unreadable (rex gave no answer it could parse). Only a
# shell or exited pane is ever closed.
proc_state() {
  local out
  local out st
  out=$(rx block call -b "$1" process 2>/dev/null) || { echo unreadable; return; }
  st=$(printf '%s' "$out" | python3 -c '
import json, os, sys
expected, top = sys.argv[1].split(), sys.argv[2]
try:
    p = json.load(sys.stdin)
    assert isinstance(p, dict)
except (ValueError, AssertionError):
    print("unreadable"); sys.exit()
child = p.get("child")
if child is None:
    print("exited" if p.get("last_exit") is not None else "unreadable"); sys.exit()
if not isinstance(child, dict) or not child:
    print("unreadable"); sys.exit()
names = {child.get("name") or "", child.get("argv0") or ""} | {os.path.basename(child.get(k) or "") for k in ("path", "invoked_path")}
names = {n.lstrip("-") for n in names if n}
if names & set(expected):
    cwd = child.get("cwd") or ""
    print("reviewer" if cwd and os.path.realpath(cwd) == top else "other")
elif names & {"zsh", "bash", "sh", "fish", "login"}:
    print("shell")
else:
    print("other")' "$expected" "$top" 2>/dev/null) || st=""
  # Anything the parser could not turn into a word, such as a crash on an odd shape, is unreadable.
  echo "${st:-unreadable}"
}

# The pane labelled $label (empty if none), and the number of panes in the window that holds
# this agent's pane (0 if REX_BLOCK is unset or not in this session). Counted again after a
# close below, because a closed review pane in this window frees its place for the split.
count_panes() {
  rx block ls --json | python3 -c '
import json, os, sys
label, mine = sys.argv[1], os.environ.get("REX_BLOCK", "")
blocks = json.load(sys.stdin)["blocks"]
pane = next((b["block_id"] for b in blocks if b.get("label") == label), "-")
win = next((b["window_id"] for b in blocks if b["block_id"] == mine), None)
print(pane, sum(1 for b in blocks if win and b["window_id"] == win))' "$label"
}
read -r found own_window_panes < <(count_panes)
[ "$found" != "-" ] || found=""

created=""
if [ -n "$found" ]; then
  case "$(proc_state "$found")" in
    reviewer)
      review_pane=$found
      echo "Review pane: $review_pane (reused)" >&2
      echo "Reusing the running reviewer in $review_pane: it keeps the flags it started with. To apply this script's current flags, close the pane once (rex block close -s $REX_SESSION $review_pane) and run again." >&2 ;;
    shell|exited)
      # Its reviewer left: the pane is closed and a fresh one opened. A failed close stops,
      # so two panes never share the label.
      if ! close_out=$(rx block close "$found" 2>&1); then
        printf '%s\n' "$close_out" >&2
        stop "Reviewer did not start: the pane $found holds the label $label and could not be closed (error above)." \
             "rex block close -s $REX_SESSION $found; $rerun"
      fi
      echo "closed $found (its reviewer had exited)" >&2
      read -r _ own_window_panes < <(count_panes) ;;
    unreadable)
      stop "Reviewer did not start: rex cannot read the process of the pane $found, which holds the label $label." \
           "rex block call -s $REX_SESSION -b $found process; then run: $rerun" ;;
    *)
      # Another program, or a reviewer in another directory: left alone, and not reused.
      stop "Reviewer did not start: the pane $found holds the label $label but runs something else; it was left alone." \
           "close it if it is yours (rex block close -s $REX_SESSION $found), then run: $rerun" ;;
  esac
fi

if [ -z "$review_pane" ]; then
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
show_pane() { rx capture -b "$review_pane" --trim 2>/dev/null | tail -n "$1" || true; }

# One word for what the reviewer is doing, checked in this order, so nothing is typed while a
# question shows or the program says it is busy:
#   gone        the pane's program exited
#   starting    the login shell that starts the reviewer is still in front (startup only)
#   unreadable  rex could not give the process or the screen
#   limit       the reviewer reports its usage limit (Kimi: "429 You've reached your 5-hour usage
#               limit"): it is not available, and the next reviewer in the order takes the review
#   blocked     the program reports blocked (OSC 7501)
#   working     the program reports working
#   idlesession Kimi asks how to resume a session left idle (compact, new, continue): answered once
#               with "Start a new session", since a review wants a fresh context
#   trust       Kimi's trust dialog, "Trust and continue" selected, naming this work tree on
#               its own path line, the one between its question and its choices
#   blocked     a known question is on the bottom lines
#   working     a busy marker shows
#   unsent      the reviewer's own input line still holds the prompt (Kimi's input box is read
#               whole, so a prompt wrapped over many lines inside it still counts, and so does
#               one scrolled inside it, whose visible text ends with the prompt's last sentence)
#   changing    the screen moved since the last look
#   idle        the reviewer's own input line shows, empty, and nothing moved; called with
#               "strict" (before anything is typed), also no other question or choice list
#               on the bottom lines, such as Kimi's data-migration question above its input
#   unknown     anything else that stays put: treated as a question
# Only the bottom lines are read, so the same words quoted higher up, such as in a diff, count
# for nothing. A failed look leaves the last screen as it was.
last_screen=$(mktemp "${TMPDIR:-/tmp}/rex-review.screen.XXXXXX")
pane_status() {
  local proc reported screen strict="${1:-}"
  # Liveness asks only whether the pane's program still runs: a reviewer can show up under
  # another name (the Cursor agent's pane title named node on 2026-10-24). The stricter check
  # of name and directory is for reusing a pane, above.
  proc=$(proc_state "$review_pane")
  case "$proc" in
    exited) echo gone; return ;;
    shell) echo starting; return ;;
    unreadable) echo unreadable; return ;;
  esac
  reported=$(rx block call -b "$review_pane" program_status 2>/dev/null | python3 -c '
import json, sys
try:
    recs = json.load(sys.stdin).get("records") or []
except (ValueError, AttributeError):
    recs = []
root = next((r for r in recs if isinstance(r, dict) and "id" not in r), None)
print((root or {}).get("state", ""))' || true)
  screen=$(rx capture -b "$review_pane" --trim 2>/dev/null) || { echo unreadable; return; }
  printf '%s' "$screen" | python3 -c '
import os, re, sys
kind, reported, last_path, top, strict = sys.argv[1:6]
lines = sys.stdin.read().splitlines()[-40:]
screen = "\n".join(lines)
bottom = "\n".join(lines[-12:])
# Kimi'"'"'s input box, read whole: from its top border to its bottom border, which must sit just
# above the status lines. A long prompt wraps over many lines inside it, so its "│ >" line can
# be far above the bottom twelve (2026-10-25: 23 lines up). The box is the reviewer'"'"'s own text:
# nothing inside it counts as a question.
box, box_text, scrolled = set(), None, False
if kind == "kimi":
    ends = [i for i, l in enumerate(lines) if l.strip().startswith("\u2570")]
    if ends and len(lines) - 1 - ends[-1] <= 4:
        starts = [i for i in range(ends[-1]) if lines[i].strip().startswith("\u256d")]
        if starts:
            box = set(range(starts[-1], ends[-1] + 1))
            # A prompt longer than the box scrolls inside it, and the top border then reads "↑ 13 more".
            scrolled = bool(re.search(r"\u2191\s*\d+\s+more", lines[starts[-1]]))
            inner = [re.sub(r"^\s*\u2502\s?|\s*\u2502\s*$", "", lines[i]) for i in range(starts[-1] + 1, ends[-1])]
            if inner and re.match(r"^\s*>", inner[0]):
                box_text = " ".join([re.sub(r"^\s*>\s?", "", inner[0]).strip()] + [c.strip() for c in inner[1:]]).strip()
outside = [l for i, l in enumerate(lines) if i not in box]
dialog = [l for i, l in enumerate(lines) if i >= len(lines) - 20 and i not in box]
last = open(last_path).read()
open(last_path, "w").write(screen)
# Each reviewer'"'"'s own input line: empty when ready, holding the prompt when unsent.
editor = {
    "kimi": r"^\s*│\s*>\s*(?P<text>.*?)\s*│?\s*$",
    "cursor": r"^\s*→\s*(?P<text>.*?)\s*$",
    "codex": r"^\s*›\s*(?P<text>.*?)\s*$",
}[kind]
ready_text = {"kimi": ("",), "cursor": ("Plan, search, build anything", "Add a follow-up"), "codex": None}[kind]
question = re.search(r"Run this command\?|Skip & tell the agent|Press enter to confirm|Hooks need review|"
                     r"\(y/n\)|\[y/N\]|Allow once|Trust this folder\?", "\n".join(dialog))
# Trust counts only for the dialog'"'"'s own path line: the single absolute path between its
# question and its selected choice. A path anywhere else on screen counts for nothing.
asked_at = next((i for i, l in enumerate(dialog) if l.strip() == "Trust this folder?"), None)
choice_at = next((i for i, l in enumerate(dialog) if re.match(r"^\s*❯\s*Trust and continue\s*$", l)), None)
trust = False
if kind == "kimi" and asked_at is not None and choice_at is not None and asked_at < choice_at:
    paths = [l.strip() for l in dialog[asked_at + 1:choice_at] if l.strip().startswith("/")]
    trust = len(paths) == 1 and os.path.realpath(paths[0]) == top
inputs = [box_text] if box_text is not None else [m.group("text") for m in (re.match(editor, l) for l in lines[-12:]) if m]
# A prompt longer than Kimi'"'"'s box scrolls inside it: the top border reads "↑ 13 more" and the first
# visible line is the middle of the prompt (2026-10-25, three times), so the prompt'"'"'s own last
# sentence marks it too.
held = any(t.startswith(("Read AGENTS.md", "Write your final review report", "[Pasted text")) for t in inputs) or (
    kind == "kimi" and scrolled and box_text is not None and box_text.endswith("Then reply with that path."))
# Codex: its idle placeholder text was not checked live (its hook-review prompt stood in the
# way on 2026-10-24), so any input line not holding the prompt counts as ready.
ready = any(t in ready_text for t in inputs) if ready_text is not None else bool(inputs) and not held
if kind == "kimi" and ready:
    ready = "context:" in bottom
others = [l for i, l in enumerate(lines) if i >= len(lines) - 12 and i not in box and not re.match(editor, l)]
choices = any(re.search(r"\?\s*$", l) or re.match(r"^\s*(\d+[.)]\s|❯\s|\[[ xX]\]\s)", l) for l in others)
if strict and choices:
    ready = False
# Kimi'"'"'s question when a prompt goes into a session left idle: how to resume it.
idle_session = (kind == "kimi" and any("has been idle for" in l for l in dialog)
                and any(re.match(r"^\s*\u276f?\s*Compact and continue\s*$", l) for l in dialog))
# A usage limit on the bottom lines (2026-10-26: Kimi said "429 ... reached your 5-hour usage limit").
limit = re.search(r"reached your [\w-]+ usage limit", "\n".join(outside[-20:]))
if limit:
    print("limit")
elif reported == "blocked":
    print("blocked")
elif reported == "working":
    print("working")
elif idle_session:
    print("idlesession")
elif trust:
    print("trust")
elif question:
    print("blocked")
elif re.search(r"ctrl\+c to stop|esc to interrupt|Press Ctrl\+B to run in background|Working\u2026|"
               r"Running \d+ agents?|Agent Running", "\n".join(l for l in outside[-12:])):
    print("working")
elif held:
    print("unsent")
elif screen != last:
    print("changing")
elif ready:
    print("idle")
else:
    print("unknown")' "$kind" "$reported" "$last_screen" "$top" "$strict"
}

# Right after typing or a key, the screen is still redrawing, so a "changing" look is looked at again,
# up to five times a second apart, before an Enter is decided (2026-10-25: one changing look
# held the Enter for good).
settled_status() {
  local st
  for _ in 1 2 3 4 5; do
    st=$(pane_status "$@")
    [ "$st" = changing ] || break
    sleep 1
  done
  echo "$st"
}

# Every prompt waits for the reviewer's own empty input line, in a new pane or a reused one.
# A starting pane counts as exited only after ten looks in a row (2026-10-24: one look too
# early read a starting Kimi as exited). Kimi's folder trust for this work tree is answered
# once (the owner, 2026-10-24: "it is okay to always trust the folder and continue"); Codex's
# hook review approves code, not a folder, and stays a question, like any screen that holds
# without the input line.
# The next reviewer in AGENTS.md's order when this one reports its usage limit.
pi_next="$(dirname "$self")/pi-review.sh --role independent --head ${head_sha:-<sha>} --verify $(printf '%q' "$verify")"
step="waiting for the reviewer to be ready"
settled=0 starting=0 unread=0 unknown=0 trusted=0 resumed=0 busy_at_start="" looks=0
# A reused pane can still be working on a review this script started earlier and gave up on
# (2026-10-26: "its screen never settled" while Kimi ran its agents). Working looks do not use up
# the 90 looks; they wait, up to 45 minutes, and the finished review's report is then taken below.
while [ "$looks" -lt 90 ]; do
  st=$(pane_status strict)
  if [ "$st" = working ]; then
    busy_at_start=1
    if [ "$SECONDS" -ge 2700 ]; then show_pane 30; stop "Reviewer did not start: it was still working after 45 minutes." "$rerun"; fi
    sleep 2; continue
  fi
  looks=$((looks + 1))
  [ "$st" = starting ] || starting=0
  [ "$st" = unreadable ] || unread=0
  [ "$st" = unknown ] || unknown=0
  case "$st" in
    idle) settled=1; break ;;
    starting)
      starting=$((starting + 1))
      if [ "$starting" -ge 10 ]; then show_pane 30; stop "Reviewer did not start: it exited." "$rerun"; fi ;;
    gone) show_pane 30; stop "Reviewer did not start: it exited." "$rerun" ;;
    unreadable)
      unread=$((unread + 1))
      if [ "$unread" -ge 10 ]; then stop "Reviewer did not start: rex cannot read its pane." "rex capture -s $REX_SESSION -b $review_pane --trim | tail -n 30; then run: $rerun"; fi ;;
    trust)
      if [ "$trusted" -ge 1 ]; then show_pane 30; stop "Reviewer did not start: Kimi still asks to trust $top after Trust and continue." "$answer, then run: $rerun"; fi
      if [ "$(settled_status strict)" = trust ]; then
        rx send-key -b "$review_pane" enter >/dev/null
        trusted=1
        echo "Kimi asked to trust $top; chose Trust and continue." >&2
      fi ;;
    limit)
      show_pane 30
      stop "Reviewer not available: it reports its usage limit." "$pi_next" ;;
    idlesession)
      if [ "$resumed" -ge 1 ]; then
        show_pane 30
        stop "Reviewer did not start: Kimi asks how to resume an idle session." "$answer, then run: $rerun"
      fi
      rx send-key -b "$review_pane" down >/dev/null; rx send-key -b "$review_pane" enter >/dev/null
      resumed=1
      echo "Kimi asked how to resume an idle session; chose Start a new session." >&2 ;;
    blocked|unsent)
      show_pane 30
      stop "Reviewer did not start: it is waiting on a question or an unknown screen." "$answer, then run: $rerun" ;;
    unknown)
      unknown=$((unknown + 1))
      if [ "$unknown" -ge 5 ]; then show_pane 30; stop "Reviewer did not start: it is waiting on a question or an unknown screen." "$answer, then run: $rerun"; fi ;;
  esac
  sleep 2
done
[ "$settled" = 1 ] || { show_pane 30; stop "Reviewer did not start: its screen never settled on its input line." "$rerun"; }

step="creating the report file"
report_dir="${TMPDIR:-/tmp}"
if [ "$kind" = cursor ]; then report_dir="${HERDR_REVIEW_DIR:-/tmp/herdr-reviews}"; mkdir -p "$report_dir"; fi
report=$(mktemp "$report_dir/review-XXXXXX")
rm -f "$report"
echo "Report file: $report" >&2
prompt="Read AGENTS.md and the repository's review standards file (for example REVIEW_STANDARDS.md) first, and apply them. Run the ce-code-review skill (instructions: $HOME/.agents/skills/ce-code-review/SKILL.md) on branch $branch, diff vs main. Verify: $verify. For each finding, name the kind of defect and list every place in the repository that has it, including places outside the diff. Say how this could pass review while still being wrong. Report findings only; do not apply them. When the review is finished, write the final report as Markdown to exactly this path: $report. This is required even if the review skill also saves its own report elsewhere. Then reply with that path."

# Text first, then Enter as its own key, a moment later: an Enter sent with the text can
# land as a new line in the input box (Kimi, 2026-10-24). A fresh look comes right before the
# Enter, which goes only while the input line still holds the text, so a question or status
# that appeared in that second gets no key. The poll below sends up to three more the same way.
send_prompt() {
  local st
  rx send -b "$review_pane" "$1" >/dev/null
  sleep 1
  st=$(settled_status)
  if [ "$st" = unsent ]; then
    rx send-key -b "$review_pane" enter >/dev/null
  else
    echo "Held the Enter after typing: the pane shows $st." >&2
  fi
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

# The pane was busy when this run began: an earlier run's review, now finished. Its report is this
# run's when it matches the branch and HEAD, so the review is not sent a second time.
if [ -n "$busy_at_start" ]; then
  earlier=$(find_skill_reports)
  if [ "$(printf '%s' "$earlier" | grep -c .)" = 1 ]; then
    echo "The reviewer was finishing an earlier run's review of this branch and HEAD; took its report: $earlier" >&2
    cat "$earlier"; exit 0
  fi
fi

step="waiting for the review"
send_prompt "$prompt"
next_on_failure="rex capture -s $REX_SESSION -b $review_pane --trim | tail -n 60; cat '$report'"

# Poll every 5 seconds, within 60 minutes of the start. The report counts once two looks in a
# row see it at the same size while the reviewer is neither working nor blocked; a screen that
# only changes (a spinner, a rotating tip) does not hold it back. Asking for the report, or
# deciding it never comes, waits for six idle looks in a row (30 seconds), because a reviewer
# can work quietly. ended says why the loop stopped: only a finished or timed-out wait may
# fall back to the file or the review skill's report; blocked, gone, unsent and unreadable end
# with their reason even when a file exists.
asked="" worked="" last_size="" idle_streak=0 idle_unworked=0 blocked=0 enters=0 unread=0 resend=""
ended="timeout"
reason="no report within 60 minutes; the review may still be running"
next="$next_on_failure"
for _ in $(seq 1 720); do
  [ "$SECONDS" -lt 3600 ] || break
  status=$(pane_status)
  [ "$status" = idle ] && idle_streak=$((idle_streak + 1)) || idle_streak=0
  case "$status" in blocked|trust|unknown) ;; *) blocked=0 ;; esac
  [ "$status" = unreadable ] || unread=0
  case "$status" in
    unsent)
      if [ "$enters" -ge 3 ]; then
        ended="unsent" reason="the prompt stayed unsent after three Enters" next="$rerun"; break
      fi
      enters=$((enters + 1)) idle_unworked=0
      if [ "$(settled_status)" = unsent ]; then
        rx send-key -b "$review_pane" enter >/dev/null || true
        echo "The prompt sat unsent on the input line; sent Enter." >&2
      fi
      ;;
    gone|starting)
      ended="gone" reason="the reviewer exited" next="$rerun"; break ;;
    limit)
      ended="unavailable" reason="reviewer not available: it reports its usage limit" next="$pi_next"; break ;;
    idlesession)
      if [ "$resumed" -ge 2 ]; then
        ended="blocked" reason="Kimi asks how to resume an idle session" next="$answer, then run: $next_on_failure"; break
      fi
      # The prompt went into a session left idle. A new session may drop it, so it is sent again
      # once the input line is empty and the reviewer has not started on it.
      rx send-key -b "$review_pane" down >/dev/null || true; rx send-key -b "$review_pane" enter >/dev/null || true
      resumed=$((resumed + 1)) resend=1 worked="" idle_unworked=0
      echo "Kimi asked how to resume an idle session; chose Start a new session." >&2 ;;
    unreadable)
      unread=$((unread + 1))
      if [ "$unread" -ge 12 ]; then ended="unreadable" reason="rex cannot read the reviewer's pane"; break; fi
      ;;
    blocked|trust|unknown)
      blocked=$((blocked + 1))
      if [ "$blocked" -ge 24 ]; then
        ended="blocked" reason="the reviewer is waiting on a question"
        next="$answer, then run: $next_on_failure"
        break
      fi
      ;;
    working)
      worked=1 idle_unworked=0 last_size="" resend="" ;;
    idle|changing)
      if [ -n "$resend" ] && [ "$status" = idle ] && [ "$(pane_status strict)" = idle ]; then
        send_prompt "$prompt"
        resend="" idle_unworked=0
        sleep 5; continue
      fi
      [ "$status" = idle ] || worked=1
      if [ -s "$report" ]; then
        size=$(wc -c < "$report")
        if [ "$size" = "$last_size" ]; then cat "$report"; exit 0; fi
        last_size=$size
      elif [ -z "$worked" ]; then
        idle_unworked=$((idle_unworked + 1))
        if [ "$idle_unworked" -ge 60 ]; then
          ended="idle"
          if [ -n "$asked" ]; then
            reason="the reviewer did not act on the request to write the report"
          else
            reason="the reviewer never started work on the prompt"
          fi
          next="$rerun"; break
        fi
      elif [ "$idle_streak" -ge 6 ] && [ -z "$asked" ]; then
        # Asking types into the pane, so it needs the strict look: no other question showing.
        if [ "$(pane_status strict)" = idle ]; then
          send_prompt "Write your final review report as Markdown to exactly this path: $report. Then reply with that path."
          asked=1 worked="" idle_unworked=0
        fi
        idle_streak=0
      elif [ "$idle_streak" -ge 6 ]; then
        ended="idle" reason="the reviewer finished without writing the report, even when asked" next="$rerun"; break
      fi
      ;;
  esac
  sleep 5
done

# A wait that ran out while the reviewer sat on a question ends blocked, not timed out.
if [ "$ended" = timeout ] && [ "$blocked" -gt 0 ]; then
  ended="blocked" reason="the reviewer is waiting on a question" next="$answer, then run: $next_on_failure"
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
        cat "$report"; exit 0
      elif [ "$matches" -gt 1 ]; then
        reason="$reason; several skill reports match this run; read them and pick: $(printf '%s' "$skill_reports" | tr '\n' ' ')"
        next="cp <the chosen report.md> '$report' && cat '$report'"
      else
        reason="$reason; no skill report for this run"
      fi
    fi ;;
  *)
    # A file the reviewer left while blocked or after it exited may be partial: not printed.
    [ ! -s "$report" ] || reason="$reason; the file at the report path may be partial and was not printed" ;;
esac
trailer=1
show_pane 60
echo "No report at $report: $reason."
echo "Next: $next"
exit 1
