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
# Exit 0: the report is on stdout, and nothing else is. Exit 1: no report; stdout ends with
#   the pane's recent text, one line "No report at <path>: <reason>." and one line
#   "Next: <command>" to run. Exit 2: bad arguments.
# Every outcome of the prompt (completed, stalled, blocked, timed out) goes through one
# recovery: Enter for a prompt left pasted but unsent, a wait until the reviewer has
# worked and gone idle, one request for the report, then the review skill's own
# report.md from this run (see find_skill_report) copied to the report path.
# Tests: test_herdr_review.py, run by the repository's scripts/check.sh.
set -euo pipefail

started_at=$(python3 -c 'import time; print(time.time())')   # the skill-report fallback takes only files newer than this
rerun=$(printf '%q ' "$0" "$@")

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
[ -n "$branch" ] && [ -n "$verify" ] || { echo "usage: $0 --branch <branch> --verify <text>" >&2; exit 2; }
: "${HERDR_WORKSPACE_ID:?run inside a Herdr pane}"
case "$kind" in
  codex) model="${model:-gpt-6.1-sol}" ;;
  kimi) model="${model:-kimi-code/k3}" ;;
  cursor) model="${model:-cursor-grok-4.6-medium}" ;;
  *) echo "--kind must be codex, kimi or cursor, got: $kind" >&2; exit 2 ;;
esac
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
top=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
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
if [ -z "$review_tab" ]; then
  created_json=$(herdr tab create --workspace "$HERDR_WORKSPACE_ID" --cwd "$top" --label "$label" --no-focus)
  review_tab=$(printf '%s' "$created_json" | jget result.tab.tab_id)
  echo "Review tab: $review_tab (created)" >&2
  review_pane=$(printf '%s' "$created_json" | jget result.root_pane.pane_id)
else
  echo "Review tab: $review_tab (reused)" >&2
  # `herdr tab get` returns no pane; find it in the pane list.
  review_pane=$(herdr pane list | python3 -c '
import json, sys
tab = sys.argv[1]
panes = json.load(sys.stdin)["result"]["panes"]
print(next(p["pane_id"] for p in panes if p["tab_id"] == tab))' "$review_tab")
fi
[ -n "$review_tab" ] && [ -n "$review_pane" ] || { echo "no review tab or pane" >&2; exit 1; }

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
  started="" out=""
  for try in 1 2 3 4 5; do   # a just-created tab's shell may not be ready yet
    if out=$(herdr agent start "$name" --kind "$kind" --pane "$review_pane" -- "${agent_args[@]}" 2>&1); then
      started=1; break
    fi
    case "$out" in *agent_pane_busy*) [ "$try" -lt 5 ] && sleep 2 ;; *) break ;; esac
  done
  if [ -z "$started" ]; then
    printf '%s\n' "$out"
    herdr agent read "$review_pane" --source recent-unwrapped --lines 30 || true
    echo "Reviewer did not start (error above). If it is blocked on a question, answer it"
    echo "(herdr agent send-keys $review_pane <key>); if the pane stayed busy, wait. Then run this again."
    exit 1
  fi
fi

# Cursor's sandbox may block the macOS temporary folder ($TMPDIR, under /var/folders) but
# allows /tmp, so a Cursor reviewer gets its report path there.
report_dir="${TMPDIR:-/tmp}"
if [ "$kind" = cursor ]; then report_dir="${HERDR_REVIEW_DIR:-/tmp/herdr-reviews}"; mkdir -p "$report_dir"; fi
report=$(mktemp "$report_dir/review-XXXXXX")   # unique; a failure stops here
rm -f "$report"                                     # absent until the reviewer writes it
echo "Report file: $report" >&2                     # findable even if the output is cut short
prompt="Read AGENTS.md and the repository's review standards file (for example REVIEW_STANDARDS.md) first, and apply them. Run the ce-code-review skill (instructions: $HOME/.agents/skills/ce-code-review/SKILL.md) on branch $branch, diff vs main. Verify: $verify. For each finding, name the kind of defect and list every place in the repository that has it, including places outside the diff. Say how this could pass review while still being wrong. Report findings only; do not apply them. When the review is finished, write the final report as Markdown to exactly this path: $report. This is required even if the review skill also saves its own report elsewhere. Then reply with that path."


pane_tail() { herdr agent read "$review_pane" --source recent-unwrapped --lines "$1" 2>/dev/null || true; }
# The Cursor agent shows a long prompt as "[Pasted text #1 +1 lines]" and waits for one
# more Enter; herdr then reports the prompt stalled or the reviewer blocked.
enter_if_pasted() {
  if pane_tail 15 | grep -q '\[Pasted text'; then
    herdr agent send-keys "$review_pane" Enter >/dev/null || true
    echo "The prompt sat pasted but unsent; sent Enter." >&2
  fi
}

# The newest report.md that ce-code-review saved since this run started, under
# <root>/compound-engineering-<uid>/ce-code-review/<run>/, where root is /tmp or $TMPDIR
# (the skill's scratch roots; HERDR_REVIEW_ARTIFACT_ROOTS, colon-separated, overrides
# them). A run whose metadata.json names another branch is skipped. Prints nothing if none.
find_skill_report() {
  python3 - "$started_at" "$branch" "$(id -u)" "${HERDR_REVIEW_ARTIFACT_ROOTS:-/tmp:${TMPDIR:-/tmp}}" <<'PY'
import glob, json, os, sys
start, branch, uid, roots = sys.argv[1:]
best = None
for root in dict.fromkeys(r for r in roots.split(":") if r):
    pattern = os.path.join(root, "compound-engineering-" + uid, "ce-code-review", "*", "report.md")
    for path in glob.glob(pattern):
        try:
            mtime = os.path.getmtime(path)
            if mtime <= float(start) or os.path.getsize(path) == 0:
                continue
        except OSError:
            continue
        try:
            with open(os.path.join(os.path.dirname(path), "metadata.json")) as f:
                other = json.load(f).get("branch")
        except (OSError, ValueError, AttributeError):
            other = None
        if other and other != branch:
            continue
        if best is None or mtime > best[0]:
            best = (mtime, path)
print(best[1] if best else "")
PY
}

# --wait returns when the reviewer is idle, done or blocked, or fails with
# agent_prompt_stalled, agent_blocked or timeout. A completed prompt with the report
# written is the common case; every other outcome goes to the recovery below.
prompt_ok="" prompt_out=""
if prompt_out=$(herdr agent prompt "$review_pane" "$prompt" --wait --timeout 3600000 2>&1); then prompt_ok=1; fi
if [ -n "$prompt_ok" ] && [ -s "$report" ]; then cat "$report"; exit 0; fi
[ -n "$prompt_ok" ] || echo "Prompt did not complete; recovering: $prompt_out" >&2
enter_if_pasted

# Poll every 5 seconds, within 60 minutes of the start. The report counts once the
# reviewer is idle and two idle polls in a row see it at the same size, so a file still
# being written is not printed early. Idle counts only after the reviewer has worked
# since its last prompt, because it stays idle for a moment after each prompt arrives;
# a completed prompt has already worked. A reviewer idle without the report is asked
# once for it. Each counter below ends the wait with its reason.
worked=$prompt_ok asked="" last_size="" idle_unworked=0 blocked=0 unread=0
reason="no report within 60 minutes; the review may still be running"
next="herdr agent wait $review_pane --until idle --until done --timeout 3600000 && cat '$report'"
for _ in $(seq 1 720); do
  [ "$SECONDS" -lt 3600 ] || break
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
        if [ "$idle_unworked" -ge 12 ]; then
          if [ -n "$asked" ]; then
            reason="the reviewer did not act on the request to write the report"
          else
            reason="the reviewer never started work on the prompt"
          fi
          next="$rerun"; break
        fi
      elif [ -z "$asked" ]; then
        herdr agent prompt "$review_pane" "Write your final review report as Markdown to exactly this path: $report. Then reply with that path." >/dev/null 2>&1 || true
        herdr agent send-keys "$review_pane" Enter >/dev/null || true
        asked=1 worked="" idle_unworked=0
      else
        reason="the reviewer finished without writing the report, even when asked"
        next="$rerun"; break
      fi
      ;;
    blocked)
      unread=0 blocked=$((blocked + 1))
      enter_if_pasted
      if [ "$blocked" -ge 24 ]; then
        reason="the reviewer is waiting on a question (answer it: herdr agent send-keys $review_pane <key>)"
        break
      fi
      ;;
    "")
      unread=$((unread + 1))
      if [ "$unread" -ge 12 ]; then reason="herdr cannot read the reviewer's status"; next="$rerun"; break; fi
      ;;
    *)
      worked=1 last_size="" idle_unworked=0 blocked=0 unread=0
      ;;
  esac
  sleep 5
done

skill_report=$(find_skill_report)
if [ -n "$skill_report" ]; then
  cp "$skill_report" "$report"
  echo "The reviewer did not write $report; copied the review skill's report from this run: $skill_report" >&2
  cat "$report"; exit 0
fi
[ -n "$prompt_ok" ] || echo "Prompt result: $prompt_out"
pane_tail 60
echo "No report at $report: $reason."
echo "Next: $next"
exit 1
