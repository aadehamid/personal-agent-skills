#!/usr/bin/env bash
# Run Antigravity (agy) as the independent reviewer, in a throwaway clone, and print its report.
#
# Usage: agy-review.sh --head <sha> [--since <sha>] [--verify <claims>]
#   --since <sha>      Review only <sha>..<head>, the fix since the last review. Without it, review the
#                      whole change against the default branch on origin.
#   --verify <claims>  What the reviewer must check, as for pi-review.sh.
#   Run from the repository under review, as a background job the harness reports back on (Claude Code:
#   run_in_background): a review takes about five to nine minutes.
# The prompt holds the diff, and the full text of the changed text files when they fit in one argument (see
# max below); otherwise it tells agy to read them. Antigravity runs headless in plan mode and the sandbox,
# in a clone of <head>: it can read that clone's files and cannot run commands or tests.
# The clone holds committed files only. It is the working folder and not a wall: whether agy may read
# outside it is agy's own allowNonWorkspaceAccess setting, which this script does not touch.
#
# agy exits 0 when it wrote no review, in two ways (found 2026-11-22, SOURCES.md 1q):
#   - it asks for a shell command, headless mode refuses and cancels the turn: stdout is empty and only
#     stderr says why;
#   - plan mode answers "I wrote the plan, approve it" in place of the review.
# So a review counts only when agy exits 0 AND the first line of stdout is exactly READY or FIX, and
# stderr is never mixed into the report.
# Exit 0: the report is on stdout, and its path is on stderr as "Report:".
# Exit 1: no review. stdout ends with "Reviewer not available: <reason>." and a "Next: <command>" line
#   for the next reviewer that can start here while the Cursor bot gives the PR review. Where Pi gives
#   it, follow the order in changing.md ("Who reviews") instead.
# Exit 2: bad arguments.
# Tests: test_agy_review.py, run by the repository's scripts/check.sh.
set -euo pipefail

model="gemini-4-neon-xhigh"
here=$(cd "$(dirname "$0")" && pwd)
head="" since="" verify=""
usage() { echo "$1" >&2; echo "usage: $0 --head <sha> [--since <sha>] [--verify <claims>]" >&2; exit 2; }
while [ $# -gt 0 ]; do
  case "$1" in
    --head|--since|--verify)
      [ $# -ge 2 ] || usage "$1 needs a value"
      case "$1" in --head) head=$2 ;; --since) since=$2 ;; --verify) verify=$2 ;; esac
      shift 2 ;;
    *) usage "unknown argument: $1" ;;
  esac
done
[ -n "$head" ] || usage "--head <sha> is required"

full() { git rev-parse --verify --quiet "$1^{commit}" 2>/dev/null; }
h=$(full "$head") || usage "--head $head names no commit in this repository"
head=$h
if [ -n "$since" ]; then
  s=$(full "$since") || usage "--since $since names no commit in this repository"
  since=$s
fi

# Kimi is next where it can start (Herdr TUI, Rex or the Herdr app), otherwise Pi.
next_reviewer() {
  local quoted branch
  quoted=$(printf '%q' "${verify:-the change does what its commit messages say}")
  if [ -n "${HERDR_WORKSPACE_ID:-}${REX_SESSION:-}${HC_TERMINAL_ID:-}" ] && branch=$(git symbolic-ref --quiet --short HEAD); then
    echo "$(printf '%q' "$here/herdr-review.sh") --kind kimi --branch $(printf '%q' "$branch") --verify $quoted"
  else
    echo "$(printf '%q' "$here/pi-review.sh") --role independent --head $head${since:+ --since $since} --verify $quoted"
  fi
}
unavailable() {
  echo "Reviewer not available: $1."
  echo "Next: $(next_reviewer)"
  exit 1
}

command -v agy > /dev/null 2>&1 || unavailable "agy is not installed"

top=$(git rev-parse --show-toplevel)
if [ -n "$since" ]; then
  range="$since..$head"
else
  default=$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null || echo origin/main)
  git rev-parse --verify --quiet "$default^{commit}" > /dev/null || unavailable "$default is not here to diff against; fetch it"
  range="$default...$head"
fi

run=$(mktemp -d "${TMPDIR:-/tmp}/agy-review-XXXXXX")
trap 'rm -rf "$run/repo"' EXIT
git -C "$top" diff "$range" > "$run/diff" || unavailable "git diff $range failed"
[ -s "$run/diff" ] || unavailable "git diff $range is empty, so there is nothing to review"

git init -q "$run/repo"
if ! git -C "$run/repo" -c protocol.version=2 fetch -q "$top" "$head" || ! git -C "$run/repo" checkout -q --detach "$head"; then
  unavailable "commit $head did not reach the throwaway clone"
fi

{
  echo "You run headless. You may read files in this repository with your file-reading tool. You cannot run shell commands: never request one, because the request ends the run with no review. Do not write a plan file: your reply is the report itself."
  echo
  echo "Read and search only inside this repository, the folder you started in. If evidence lies outside it, say so and do not look for it."
  echo "You are the independent reviewer for this change, before it is pushed for review. Review alone, with no subagents."
  echo "Read the repository's agent instructions and review standards files if it has them (AGENTS.md, CLAUDE.md, REVIEW_STANDARDS.md), and apply them."
  echo "Look for anything that lets a wrong result through, breaks a stated rule, or makes a description untrue. Do not report style. For each finding, give the file, the line and why it is a defect, name the kind of defect, and list every place in the repository that has it, including places outside the diff. Say when a finding needs a test run to prove. Also say how this could pass review while still being wrong."
  [ -z "$verify" ] || echo "Verify: $verify."
  echo "Reply with your report as Markdown. Its first line is exactly READY or FIX."
  echo
  echo "===== git diff $range ====="
  cat "$run/diff"
} > "$run/prompt"

cp "$run/prompt" "$run/prompt.files"
git -C "$top" diff --name-only -z --diff-filter=d "$range" > "$run/names"
while IFS= read -r -d '' file; do
  printf '\n===== full text of %s =====\n' "$file"
  if git -C "$run/repo" grep -Iq -e '' HEAD -- ":(literal)$file"; then
    git -C "$run/repo" show "HEAD:$file"
  else
    echo "(binary or empty: not shown)"
  fi
done < "$run/names" >> "$run/prompt.files"

# agy takes the prompt as one argument. Linux caps one argument at 128 KiB and macOS all of them at 1 MiB.
if [ "$(uname)" = Darwin ]; then max=600000; else max=120000; fi
max=${AGY_REVIEW_MAX_BYTES:-$max}
if [ "$(wc -c < "$run/prompt.files")" -le "$max" ]; then
  mv "$run/prompt.files" "$run/prompt"
else
  printf '\n%s\n' "The changed files are too long to include. Read each of them in this repository with your file-reading tool." >> "$run/prompt"
  [ "$(wc -c < "$run/prompt")" -le "$max" ] || unavailable "the diff is too large for one agy prompt"
fi

code=0
(cd "$run/repo" && agy --model "$model" --mode plan --sandbox --print-timeout 1700s -p="$(cat "$run/prompt")") \
  < /dev/null > "$run/stdout" 2> "$run/stderr" || code=$?
first=$(head -n 1 "$run/stdout")
if [ "$code" -ne 0 ] || { [ "$first" != READY ] && [ "$first" != FIX ]; }; then
  cat "$run/stderr" >&2
  echo "agy's output: $run/stdout and $run/stderr" >&2
  unavailable "Antigravity wrote no review (agy exit $code, first line '${first:0:100}')"
fi
mv "$run/stdout" "$run/report.md"
cat "$run/report.md"
echo "Report: $run/report.md" >&2
