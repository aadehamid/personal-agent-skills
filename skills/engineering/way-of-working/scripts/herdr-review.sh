#!/usr/bin/env bash
# Run the independent review in a Herdr pane, wait for it, and print its report.
#
# Usage: herdr-review.sh --branch <branch> --verify "<claims to verify>" [--kind codex|kimi|cursor] [--model <model>]
#   The default reviewer is Codex on gpt-6.1-sol. --kind kimi runs Kimi Code (model default
#   kimi-code/k3); --kind cursor runs the Cursor agent CLI (default cursor-grok-4.6-medium).
#   Any other reviewer gets its own tab, review-<repo>-<kind>-<hash of kind:model>, because
#   a reused tab keeps the reviewer it started with.
#   Run from the repository under review, inside a Herdr pane (HERDR_WORKSPACE_ID set).
#   A review takes longer than a foreground tool call allows: run this as a background
#   job the harness reports back on, with its exit status (Claude Code: run_in_background).
# Exit 0: the report is on stdout, and nothing else is.
# Exit 1: no report. Every exit 1 ends stdout with two lines, the reason and
#   "Next: <command>" to run.
#   Once the prompt was sent, stdout ends with "Prompt result: <herdr error>" (only if
#   the prompt did not complete), the pane's recent text, then "No report at <path>:
#   <reason>." and the Next line.
#   Before the prompt, a reviewer that did not start prints herdr's error and the pane,
#   then "Reviewer did not start: <reason>." and the Next line; a review still working
#   or blocked in this work tree that holds the reviewer's name gives the reason
#   "another review is running in <tab>; wait for it or close it". Any other failure
#   (HERDR_WORKSPACE_ID unset, a herdr error, no review tab or pane, an unwritable
#   report folder) prints its error on stderr, then "No review: <step> failed; the error
#   is above." and the Next line (on_exit).
#   A run that fails or is killed once the prompt is on its way ends the same way; Next
#   waits for that review and prints its report if the prompt was delivered, and runs
#   this again if not (on_exit).
# Exit 2: bad arguments.
# Every outcome of the prompt (completed, stalled, blocked, timed out) goes through one
# recovery: Enter for a Cursor prompt left pasted but unsent, a wait until the reviewer
# has worked and gone idle, one request for the report, then the reviewer's own file at
# the report path, or failing that the review skill's report.md from this run, copied
# there (see find_skill_reports for which one counts).
# Tests: test_herdr_review.py, run by the repository's scripts/check.sh.
set -euo pipefail

# Bash reads a script while it runs, and this file sits in a working tree that a commit or
# checkout can rewrite mid-review: on 2026-10-24 that killed a review. So the script runs
# from a private copy, which it removes once running (bash keeps its own handle open).
# HERDR_REVIEW_ORIGINAL names this file in the copy, for usage and Next lines.
if [ -z "${HERDR_REVIEW_ORIGINAL:-}" ]; then
  copy=$(mktemp "${TMPDIR:-/tmp}/herdr-review.copy.XXXXXX")
  cp -- "$0" "$copy"
  HERDR_REVIEW_ORIGINAL=$0 exec bash "$copy" "$@"
fi
self=$HERDR_REVIEW_ORIGINAL
unset HERDR_REVIEW_ORIGINAL
case "$0" in "${TMPDIR:-/tmp}"/herdr-review.copy.*) rm -f -- "$0" ;; esac

started_at=$(python3 -c 'import time; print(time.time())')   # the skill-report fallback takes only files newer than this
rerun=$(printf '%q ' "$self" "$@")

branch="" verify="" kind="codex" model=""
while [ $# -gt 0 ]; do
  case "$1" in
    --branch) branch="$2"; shift 2 ;;
    --verify) verify="$2"; shift 2 ;;
    --model) model="$2"; shift 2 ;;
    --kind) kind="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[ -n "$branch" ] && [ -n "$verify" ] || { echo "usage: $self --branch <branch> --verify <text>" >&2; exit 2; }
case "$kind" in
  codex) model="${model:-gpt-6.1-sol}" ;;
  kimi) model="${model:-kimi-code/k3}" ;;
  cursor) model="${model:-cursor-grok-4.6-medium}" ;;
  *) echo "--kind must be codex, kimi or cursor, got: $kind" >&2; exit 2 ;;
esac

# From here, any failure exits 1 and ends with the reason and a Next line. A path that
# prints its own two lines sets trailer=1 first; any other failure (set -e, a herdr
# error, a failed mktemp) gets them here, naming the step it was on.
# Once the prompt is on its way, Next is the wait for that review only if delivery is
# confirmed (the prompt returned, or the reviewer was seen working; at exit a prompt
# still in flight is checked once); otherwise Next starts the review again.
step="starting" trailer="" next_on_failure="$rerun" prompt_sent="" delivered="" prompt_file=""
on_exit() {
  local code=$? st
  trap '' TERM INT HUP   # a second signal must not cut the two closing lines short
  [ -z "$prompt_file" ] || rm -f "$prompt_file"
  [ "$code" -ne 0 ] && [ -z "$trailer" ] || return 0
  if [ -n "$prompt_sent" ] && [ -z "$delivered" ]; then
    # The check gets the default signal handling back and 5 seconds (perl's alarm, since
    # macOS has no timeout); a check that does not answer leaves the status unknown.
    st=$( (trap - TERM INT HUP; exec perl -e 'alarm shift; exec @ARGV' 5 herdr agent get "$review_pane") 2>/dev/null \
          | jget result.agent.agent_status 2>/dev/null || true)
    [ "$st" != working ] || delivered=1
  fi
  if [ -n "$delivered" ]; then
    next_on_failure="herdr agent wait $review_pane --until idle --until done --timeout 3600000 && cat '$report'"
  fi
  echo "No review: $step failed; the error is above."
  echo "Next: $next_on_failure"
  exit 1
}
trap on_exit EXIT
trap 'exit 1' TERM INT HUP   # a killed run (a harness timeout) also ends through on_exit
if [ -z "${HERDR_WORKSPACE_ID:-}" ]; then
  echo "HERDR_WORKSPACE_ID is not set: this runs only inside a Herdr pane." >&2
  step="checking for a Herdr pane" next_on_failure="run it from a Herdr pane: $rerun"
  exit 1
fi
default_reviewer=""
[ "$kind:$model" = "codex:gpt-6.1-sol" ] && default_reviewer=1
# The tab label and the agent name both carry this hash, so two models never share a
# tab, even when their names differ only in punctuation (kimi-code/k3, kimi-code-k3).
reviewer_hash=$(printf '%s' "$kind:$model" | shasum | cut -c1-8)

# Read one field from herdr's JSON on stdin. Every object on the path must exist;
# only the last field may be missing or null (it prints an empty line). An error
# response ({"error": ...}) or a missing object fails, so set -e stops the script.
jget() {
  python3 -c '
import json, sys
data = json.load(sys.stdin)
if "error" in data:
    sys.exit("herdr error: " + json.dumps(data["error"]))
*path, last = sys.argv[1].split(".")
for key in path:
    data = data.get(key) if isinstance(data, dict) else None
    if not isinstance(data, dict):
        sys.exit("herdr response has no " + key + ": " + sys.argv[1])
value = data.get(last)
print("" if value is None else value)' "$1"
}

# The review tab lives in this agent's own workspace. An unfiltered `tab list`
# spans every workspace, and a tab created without --workspace can open in
# whichever one the owner is looking at.
# Name and start from the work tree's top, so a run from a subdirectory finds the same tab.
step="finding the review tab"
top=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
head_sha=$(git -C "$top" rev-parse HEAD 2>/dev/null || true)   # the skill-report fallback matches this commit
repo=$(basename "$top")
label="review-$repo"
[ -n "$default_reviewer" ] || label="review-$repo-$kind-$reviewer_hash"
review_tab=$(herdr tab list --workspace "$HERDR_WORKSPACE_ID" | python3 -c '
import json, sys
label = sys.argv[1]
tabs = json.load(sys.stdin)["result"]["tabs"]
print(next((t["tab_id"] for t in tabs if t["label"] == label), ""))' "$label")
# The caller needs the tab, and whether this run created it, to close it after
# merge, so it is printed as soon as it is known, before any later step can fail.
create_review_tab() {
  local created_json
  created_json=$(herdr tab create --workspace "$HERDR_WORKSPACE_ID" --cwd "$top" --label "$label" --no-focus)
  review_tab=$(printf '%s' "$created_json" | jget result.tab.tab_id)
  echo "Review tab: $review_tab (created)" >&2
  review_pane=$(printf '%s' "$created_json" | jget result.root_pane.pane_id)
}
if [ -z "$review_tab" ]; then
  create_review_tab
else
  echo "Review tab: $review_tab (reused)" >&2
  # `herdr tab get` returns no pane; find it in the pane list.
  review_pane=$(herdr pane list | python3 -c '
import json, sys
tab = sys.argv[1]
panes = json.load(sys.stdin)["result"]["panes"]
print(next(p["pane_id"] for p in panes if p["tab_id"] == tab))' "$review_tab")
fi
[ -n "$review_tab" ] && [ -n "$review_pane" ] || { echo "herdr gave no review tab or pane" >&2; exit 1; }
step="starting the reviewer"

# Start a reviewer only if the pane has none; a reused tab keeps its reviewer.
# Different model from the writer, no approval prompts, sandboxed with network
# (Claude writing: Codex on gpt-6.1-sol at medium reasoning, the owner's choice;
# --kind and --model pick another reviewer when the owner asks). Kimi has no sandbox,
# so it runs with -y: routine commands run, risky actions still ask, and a question
# leaves the pane blocked, which the prompt step below reports.
pane_agent=$(herdr pane get "$review_pane" | jget result.pane.agent)
if [ -n "$pane_agent" ]; then
  # A running reviewer keeps the flags it started with, such as the sandbox's writable folders.
  echo "Reusing the running reviewer in $review_tab: it keeps the flags it started with. To apply this script's current flags, close the tab once (herdr tab close $review_tab) and run again." >&2
fi
if [ -z "$pane_agent" ]; then
  slug=$(printf '%s' "$repo" | tr 'A-Z' 'a-z' | tr -cs 'a-z0-9' '-')
  name="rev-$(printf '%s' "$slug" | cut -c1-28)"
  # Herdr names are unique and at most 32 characters, so another reviewer takes a
  # short hash of its kind and model, and can run beside the default one.
  if [ -z "$default_reviewer" ]; then
    name="rev-$(printf '%s' "$slug" | cut -c1-19)-$reviewer_hash"
  fi
  if [ "$kind" = kimi ]; then
    agent_args=(-m "$model" -y)
  elif [ "$kind" = cursor ]; then
    # Sandboxed, no approval prompts, workspace trusted: the Cursor match for Codex's flags.
    agent_args=(--model "$model" --sandbox enabled --force --trust)
  else
    # The review skill's cross-model pass runs npx and the Claude CLI, which write to these
    # folders; without them the sandbox fails it with npm EPERM and the pass is skipped.
    # Codex skips a writable root that is not already a directory, so make them first.
    mkdir -p "$HOME/.npm" "$HOME/.claude" "$HOME/.cache" "$HOME/.config"
    roots="[\"$HOME/.npm\",\"$HOME/.claude\",\"$HOME/.cache\",\"$HOME/.config\"]"
    agent_args=(-m "$model" -c model_reasoning_effort=medium
                -a never -s workspace-write -c sandbox_workspace_write.network_access=true
                -c "sandbox_workspace_write.writable_roots=$roots")
  fi
  # Herdr refuses a name another live agent holds, and names the holders in its error:
  # "candidates: ... pane_id=<pane> ... tab_id=<tab> cwd=<dir> status=<status>". A holder
  # in this work tree is an earlier review left open: one that is idle or done has its
  # tab closed and the start is tried once more; one still working or blocked is another
  # review running, and the script stops rather than close it. The holder can be the
  # reused review tab itself (its pane reads as having no agent while herdr still holds
  # the name); then that tab is closed and a fresh one created for the retry.
  name_holder() {
    python3 - "$top" "$1" <<'PY'
import os, re, sys
top, text = os.path.realpath(sys.argv[1]), sys.argv[2]
for m in re.finditer(r"pane_id=([^\s,;]+).*?tab_id=([^\s,;]+).*?cwd=(.*?)[,;]?\s+status=(\w+)", text):
    pane, tab, cwd, status = m.groups()
    if os.path.realpath(cwd) == top:
        print(tab, pane, status.lower())
        break
PY
  }
  # A busy pane gets five tries (a just-created tab's shell may not be ready yet). Closing
  # a name holder restarts that count, so its one retry always runs; only a failed close
  # of the review tab itself stops instead (below).
  started="" out="" holder_closed="" try=0
  while [ "$try" -lt 5 ]; do
    try=$((try + 1))
    if out=$(herdr agent start "$name" --kind "$kind" --pane "$review_pane" -- "${agent_args[@]}" 2>&1); then
      started=1; break
    fi
    case "$out" in
      *agent_pane_busy*) [ "$try" -lt 5 ] && sleep 2 ;;
      *agent_name_taken*)
        holder=$(name_holder "$out")
        [ -n "$holder" ] && [ -z "$holder_closed" ] || break
        read -r holder_tab holder_pane holder_status <<<"$holder"
        case "$holder_status" in
          idle|done)
            # Idle counts as finished: a reviewer is idle only once it finished or gave
            # up, and this script never leaves one idle mid-review (SOURCES.md 1j). A
            # failed close shows herdr's error; the retry runs either way, except when
            # the holder is the review tab itself, whose replacement needs it gone.
            if close_out=$(herdr tab close "$holder_tab" 2>&1); then
              echo "closed $holder_tab (status $holder_status)" >&2
              [ "$holder_tab" != "$review_tab" ] || create_review_tab
            else
              printf '%s\n' "$close_out" >&2
              if [ "$holder_tab" = "$review_tab" ]; then
                trailer=1
                echo "Reviewer did not start: the review tab $review_tab holds the name $name and could not be closed (error above)."
                echo "Next: herdr tab close $review_tab; $rerun"
                exit 1
              fi
            fi
            holder_closed=1 try=0 ;;
          *)
            printf '%s\n' "$out"
            trailer=1
            echo "Reviewer did not start: another review is running in $holder_tab; wait for it or close it."
            echo "Next: herdr agent wait $holder_pane --until idle --until done --timeout 3600000 && $rerun"
            exit 1 ;;
        esac ;;
      *) break ;;
    esac
  done
  if [ -z "$started" ]; then
    printf '%s\n' "$out"
    herdr agent read "$review_pane" --source recent-unwrapped --lines 30 || true
    trailer=1
    echo "Reviewer did not start: the error is above; if it is blocked on a question, answer it (herdr agent send-keys $review_pane <key>), and if the pane stayed busy, wait."
    echo "Next: $rerun"
    exit 1
  fi
fi

# Cursor's sandbox may block the macOS temporary folder ($TMPDIR, under /var/folders) but
# allows /tmp, so a Cursor reviewer gets its report path there.
report_dir="${TMPDIR:-/tmp}"
if [ "$kind" = cursor ]; then report_dir="${HERDR_REVIEW_DIR:-/tmp/herdr-reviews}"; mkdir -p "$report_dir"; fi
step="creating the report file"
report=$(mktemp "$report_dir/review-XXXXXX")   # unique; a failure stops here
rm -f "$report"                                     # absent until the reviewer writes it
echo "Report file: $report" >&2                     # findable even if the output is cut short
prompt="Read AGENTS.md and the repository's review standards file (for example REVIEW_STANDARDS.md) first, and apply them. Run the ce-code-review skill (instructions: $HOME/.agents/skills/ce-code-review/SKILL.md) on branch $branch, diff vs main. Verify: $verify. For each finding, name the kind of defect and list every place in the repository that has it, including places outside the diff. Say how this could pass review while still being wrong. Report findings only; do not apply them. When the review is finished, write the final report as Markdown to exactly this path: $report. This is required even if the review skill also saves its own report elsewhere. Then reply with that path."


pane_tail() { herdr agent read "$review_pane" --source recent-unwrapped --lines "$1" 2>/dev/null || true; }
# The Cursor agent shows a long prompt on its input line as "→ [Pasted text #1 +1 lines]"
# and waits for one more Enter. Herdr then reports the prompt stalled or the reviewer
# blocked, and the status can read idle; the text can also appear only after the first
# look. So this runs on every poll until the reviewer has worked, whatever the status.
# It reads the screen as it is now, since scrollback keeps the text after the Enter, and
# acts only for Cursor and only on the input line, never on the marker quoted elsewhere
# (a diff under review can hold it). It sends at most three Enters, and each one restarts
# the "never started" count.
enters=0
enter_if_pasted() {
  [ "$kind" = cursor ] && [ "$enters" -lt 3 ] || return 0
  local screen
  screen=$(herdr agent read "$review_pane" --source visible --lines 40 2>/dev/null || true)
  if printf '%s\n' "$screen" | grep -Eq '^[[:space:]]*→[[:space:]]*\[Pasted text'; then
    herdr agent send-keys "$review_pane" Enter >/dev/null || true
    enters=$((enters + 1)) idle_unworked=0
    echo "The prompt sat pasted but unsent; sent Enter." >&2
  fi
}

# Print the reviewer's own file at $report and exit 0, once two reads 5 seconds apart see
# it non-empty at the same size. Returns after a minute if it is still missing, empty
# (the reviewer wrote nothing yet) or changing.
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

# The fallback when the reviewer wrote no file at $report (decided 2026-10-23 by the
# coordinator under the owner's delegation; SOURCES.md 1j). A ce-code-review report.md,
# under <root>/compound-engineering-<uid>/ce-code-review/<run>/ with root /tmp or $TMPDIR
# (the skill's scratch roots; HERDR_REVIEW_ARTIFACT_ROOTS, colon-separated, overrides
# them), counts only when all of these hold: it was written after this script started;
# its metadata.json names this branch; and that metadata.json records head_sha equal to
# the HEAD this script started on (no head_sha, no match). Exactly one match is copied;
# zero or several end in exit 1. Prints one matching path per line.
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

# --wait returns when the reviewer is idle, done or blocked, or fails with
# agent_prompt_stalled, agent_blocked or timeout. A completed prompt with the report
# written is the common case; every other outcome goes to the recovery below.
step="waiting for the review"
# The prompt runs in the background and the script waits on it, so a TERM, INT or HUP
# ends the run at once through on_exit; the reviewer is left running.
prompt_ok="" prompt_out=""
prompt_file=$(mktemp "$report_dir/prompt-XXXXXX")
prompt_sent=1
herdr agent prompt "$review_pane" "$prompt" --wait --timeout 3600000 >"$prompt_file" 2>&1 &
if wait "$!"; then prompt_ok=1; fi
prompt_out=$(cat "$prompt_file")
if [ -n "$prompt_ok" ] && [ -s "$report" ]; then cat "$report"; exit 0; fi
[ -n "$prompt_ok" ] || echo "Prompt did not complete; recovering: $prompt_out" >&2
# A completed or timed-out prompt was sent and worked on; a stalled or rejected one was not.
worked=1
case "$prompt_ok:$prompt_out" in :*agent_prompt_stalled*|:*agent_blocked*) worked="" ;; esac
delivered=$worked

# Poll every 5 seconds, within 60 minutes of the start. The report counts once the
# reviewer is idle and two idle polls in a row see it at the same size, so a file still
# being written is not printed early. Idle counts only after the reviewer has worked
# since its last prompt, because it stays idle for a moment after each prompt arrives;
# a completed or timed-out prompt has already worked. A reviewer idle without the report is asked
# once for it. Each counter below ends the wait with its reason. The "never started"
# stop counts 12 idle polls after the last Enter or the request for the report, and 60
# when neither happened.
asked="" last_size="" idle_unworked=0 blocked=0 unread=0
reason="no report within 60 minutes; the review may still be running"
next="herdr agent wait $review_pane --until idle --until done --timeout 3600000 && cat '$report'"
for _ in $(seq 1 720); do
  [ "$SECONDS" -lt 3600 ] || break
  [ -n "$worked" ] || enter_if_pasted
  status=$(herdr agent get "$review_pane" | jget result.agent.agent_status || true)
  case "$status" in
    idle|done)
      unread=0 blocked=0
      if [ -s "$report" ]; then
        size=$(wc -c < "$report")
        if [ "$size" = "$last_size" ]; then cat "$report"; exit 0; fi
        last_size=$size
      elif [ -z "$worked" ]; then
        idle_unworked=$((idle_unworked + 1))
        limit=60; [ "$enters" -eq 0 ] && [ -z "$asked" ] || limit=12
        if [ "$idle_unworked" -ge "$limit" ]; then
          if [ -n "$asked" ]; then
            reason="the reviewer did not act on the request to write the report"
          else
            reason="the reviewer never started work on the prompt"
          fi
          next="$rerun"; break
        fi
      elif [ -z "$asked" ]; then
        herdr agent prompt "$review_pane" "Write your final review report as Markdown to exactly this path: $report. Then reply with that path." >/dev/null 2>&1 || true
        asked=1 worked="" idle_unworked=0
      else
        reason="the reviewer finished without writing the report, even when asked"
        next="$rerun"; break
      fi
      ;;
    blocked)
      unread=0 blocked=$((blocked + 1))
      if [ "$blocked" -ge 24 ]; then
        reason="the reviewer is waiting on a question"
        # A reviewer that never worked never got the prompt (herdr rejects a prompt to a
        # blocked agent before sending it), so after the answer the script runs again.
        if [ -n "$worked" ]; then
          next="answer it (herdr agent send-keys $review_pane <key>), then run: $next"
        else
          next="answer it (herdr agent send-keys $review_pane <key>), then run: $rerun"
        fi
        break
      fi
      ;;
    "")
      unread=$((unread + 1))
      if [ "$unread" -ge 12 ]; then reason="herdr cannot read the reviewer's status"; next="$rerun"; break; fi
      ;;
    *)
      worked=1 delivered=1 last_size="" idle_unworked=0 blocked=0 unread=0
      ;;
  esac
  sleep 5
done

# The reviewer's own file comes first, however the wait ended. A non-empty file is never
# overwritten; a missing or empty one (the reviewer wrote nothing) gets the fallback.
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
[ -n "$prompt_ok" ] || echo "Prompt result: $prompt_out"
pane_tail 60
echo "No report at $report: $reason."
echo "Next: $next"
exit 1
