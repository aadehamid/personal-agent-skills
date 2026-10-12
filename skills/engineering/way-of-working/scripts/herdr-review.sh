#!/usr/bin/env bash
# Run the independent review in a Herdr pane, wait for it, and print its report.
#
# Usage: herdr-review.sh --branch <branch> --verify "<claims to verify>"
#   Run from the repository under review, inside a Herdr pane (HERDR_WORKSPACE_ID set).
#   A review takes longer than a foreground tool call allows: run this as a background
#   job the harness reports back on, with its exit status (Claude Code: run_in_background).
# Exit 0: the report is printed. Exit 1: no review; the output says what to do.
# Tests: test_herdr_review.py, run by the repository's scripts/check.sh.
set -euo pipefail

branch="" verify=""
while [ $# -gt 0 ]; do
  case "$1" in
    --branch) branch="$2"; shift 2 ;;
    --verify) verify="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[ -n "$branch" ] && [ -n "$verify" ] || { echo "usage: $0 --branch <branch> --verify <text>" >&2; exit 2; }
: "${HERDR_WORKSPACE_ID:?run inside a Herdr pane}"

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
repo=$(basename "$PWD")
review_tab=$(herdr tab list --workspace "$HERDR_WORKSPACE_ID" | python3 -c '
import json, sys
label = sys.argv[1]
tabs = json.load(sys.stdin)["result"]["tabs"]
print(next((t["tab_id"] for t in tabs if t["label"] == label), ""))' "review-$repo")
# The caller needs the tab, and whether this run created it, to close it after
# merge, so it is printed as soon as it is known, before any later step can fail.
if [ -z "$review_tab" ]; then
  created_json=$(herdr tab create --workspace "$HERDR_WORKSPACE_ID" --cwd "$PWD" --label "review-$repo" --no-focus)
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
# (Claude writing: Codex on gpt-6.1-sol at medium reasoning, the owner's choice).
pane_agent=$(herdr pane get "$review_pane" | jget result.pane.agent)
if [ -z "$pane_agent" ]; then
  name="rev-$(printf '%s' "$repo" | tr 'A-Z' 'a-z' | tr -cs 'a-z0-9' '-' | cut -c1-28)"
  started="" out=""
  for try in 1 2 3 4 5; do   # a just-created tab's shell may not be ready yet
    if out=$(herdr agent start "$name" --kind codex --pane "$review_pane" -- \
        -m gpt-6.1-sol -c model_reasoning_effort=medium \
        -a never -s workspace-write -c sandbox_workspace_write.network_access=true 2>&1); then
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

report=$(mktemp "${TMPDIR:-/tmp}/review-XXXXXX")   # unique; a failure stops here
rm -f "$report"                                     # absent until the reviewer writes it
prompt="Read AGENTS.md and the repository's review standards file (for example REVIEW_STANDARDS.md) first, and apply them. Run the ce-code-review skill on branch $branch, diff vs main. Verify: $verify. Say how this could pass review while still being wrong. Report findings only; do not apply them. Write them as Markdown to $report and reply with the path."

# --wait fails fast (agent_prompt_stalled) if the prompt never starts work, and
# otherwise returns when the reviewer is idle, done or blocked.
if ! herdr agent prompt "$review_pane" "$prompt" --wait --timeout 3600000 >/dev/null; then
  herdr agent read "$review_pane" --source recent-unwrapped --lines 60 || true
  echo "Prompt not completed. agent_blocked: the reviewer was already waiting on a question and"
  echo "got nothing; answer it (herdr agent send-keys $review_pane <key>), then run this again."
  echo "timeout: the review may still be running; wait for the same report:"
  echo "  herdr agent wait $review_pane --until idle --until done --timeout 3600000 && cat '$report'"
  exit 1
fi
if [ ! -f "$report" ]; then   # no report means no review, whatever the pane shows
  state=$(herdr agent get "$review_pane" | jget result.agent.agent_status || true)
  herdr agent read "$review_pane" --source recent-unwrapped --lines 60 || true
  echo "No report (state: $state). A blocked reviewer refuses new prompts: answer it"
  echo "(herdr agent send-keys $review_pane <key>), then wait for the same report:"
  echo "  herdr agent wait $review_pane --until idle --until done --timeout 3600000 && cat '$report'"
  exit 1
fi
cat "$report"
