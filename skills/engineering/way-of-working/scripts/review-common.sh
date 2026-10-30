# shellcheck shell=bash
# Code that rex-review.sh and hc-review.sh share, so each fact lives in one place: the arguments
# and default models, the reviewer prompt, the report file, the exit-1 trailer, the fallback to
# the review skill's report, the next reviewer after a usage limit, and the screen reading both
# use for a reviewer that reports no status.
#
# Sourced, never run. Each script copies this file into its private temporary area together
# with its own copy (see the script's header), sources that copy and removes it, so a commit or
# checkout during a review rewrites neither. A caller defines self, rerun, head_sha, branch,
# verify, step, trailer, next_on_failure and last_screen as the functions below use them, and
# two hooks: finish (print the report and exit 0) and pause <seconds> (wait between looks).
#
# herdr-review.sh does not source it: its tests run a lone copy of it from another folder, so it
# keeps its own copies of the prompt, the default models, find_skill_reports and the fallback.
# test_rex_review.py and test_hc_review.py run each script beside herdr-review.sh and fail when
# what they launch or send differs.
# Tests: test_rex_review.py and test_hc_review.py, run by the repository's scripts/check.sh.

# The arguments, as herdr-review.sh takes them; $1 is this script's host (rex or hc), the only
# value --host may have here. Sets branch, verify, kind and model; exits 2 on a bad argument.
parse_review_args() {
  local host=$1
  shift
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
      # herdr-review.sh's choice of host; the calling script is this host's.
      --host) [ "$2" = "$host" ] || { echo "$host-review.sh runs only with --host $host, got: $2" >&2; exit 2; } ;;
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
}

# Any exit 1 not already ended by stop gets the two closing lines here, naming the step it was
# on; the screen file is removed on every exit.
on_exit() {
  local code=$?
  trap '' TERM INT HUP
  [ -z "$last_screen" ] || rm -f "$last_screen"
  [ "$code" -ne 0 ] && [ -z "$trailer" ] || return 0
  echo "No review: $step failed; the error is above."
  echo "Next: $next_on_failure"
  exit 1
}
# Ends the run with its reason and Next line.
stop() { trailer=1; echo "$1"; echo "Next: $2"; exit 1; }

# Cursor's sandbox may block the macOS temporary folder ($TMPDIR, under /var/folders) but
# allows /tmp, so a Cursor reviewer gets its report path there. Sets report_dir and report.
create_report_file() {
  report_dir="${TMPDIR:-/tmp}"
  if [ "$kind" = cursor ]; then report_dir="${HERDR_REVIEW_DIR:-/tmp/herdr-reviews}"; mkdir -p "$report_dir"; fi
  report=$(mktemp "$report_dir/review-XXXXXX")
  rm -f "$report"
  echo "Report file: $report" >&2
}

# The prompt, herdr-review.sh's word for word. The screen reading below knows a prompt left
# unsent by its first words, "Read AGENTS.md", and its last sentence.
review_prompt() {
  printf '%s' "Read AGENTS.md and the repository's review standards file (for example REVIEW_STANDARDS.md) first, and apply them. Run the ce-code-review skill (instructions: $HOME/.agents/skills/ce-code-review/SKILL.md) on branch $branch, diff vs main. Verify: $verify. For each finding, name the kind of defect and list every place in the repository that has it, including places outside the diff. Say how this could pass review while still being wrong. Report findings only; do not apply them. When the review is finished, write the final report as Markdown to exactly this path: $report. This is required even if the review skill also saves its own report elsewhere. Then reply with that path."
}

# The next reviewer in AGENTS.md's order when this one reports its usage limit.
next_reviewer() {
  printf '%s' "$(dirname "$self")/pi-review.sh --role independent --head ${head_sha:-<sha>} --verify $(printf '%q' "$verify")"
}

# Print the reviewer's own file at $report (finish), once two reads 5 seconds apart see it
# non-empty at the same size. Returns after a minute if it is still missing, empty (the reviewer
# wrote nothing yet) or changing.
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

# After a finished or timed-out wait: the reviewer's own file first, then the review skill's
# report of this run, copied to the report path (finish). Otherwise adds to reason, and sets
# next when there is something to read.
report_fallback() {
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
  fi
}

# The screen reading both scripts share, as Python that each script runs ahead of its own
# decision (python3 -c "$screen_py"'...'). read_screen(kind, lines, top, last_path) takes the
# bottom 40 lines of the reviewer's screen, records them at last_path, and returns what it found
# there. Only the bottom lines are read, so the same words quoted higher up, such as in a diff,
# count for nothing. Which finding wins, and what else counts, stays in each script.
IFS= read -r -d '' screen_py <<'PY' || true   # read ends at the end of input with status 1
import os, re, sys, types


def read_screen(kind, lines, top, last_path):
    screen = "\n".join(lines)
    # Kimi's input box, read whole: from its top border to its bottom border, which must sit just
    # above the status lines. A long prompt wraps over many lines inside it, so its "│ >" line can
    # be far above the bottom twelve (2026-10-25: 23 lines up). The box is the reviewer's own text:
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
    # Each reviewer's own input line: empty when ready, holding the prompt when unsent.
    editor = {
        "kimi": r"^\s*│\s*>\s*(?P<text>.*?)\s*│?\s*$",
        "cursor": r"^\s*→\s*(?P<text>.*?)\s*$",
        "codex": r"^\s*›\s*(?P<text>.*?)\s*$",
    }[kind]
    ready_text = {"kimi": ("",), "cursor": ("Plan, search, build anything", "Add a follow-up"), "codex": None}[kind]
    question = re.search(r"Run this command\?|Skip & tell the agent|Press enter to confirm|Hooks need review|"
                         r"\(y/n\)|\[y/N\]|Allow once|Trust this folder\?", "\n".join(dialog))
    # Trust counts only for the dialog's own path line: the single absolute path between its
    # question and its selected choice. A path anywhere else on screen counts for nothing.
    asked_at = next((i for i, l in enumerate(dialog) if l.strip() == "Trust this folder?"), None)
    choice_at = next((i for i, l in enumerate(dialog) if re.match(r"^\s*❯\s*Trust and continue\s*$", l)), None)
    trust = False
    if kind == "kimi" and asked_at is not None and choice_at is not None and asked_at < choice_at:
        paths = [l.strip() for l in dialog[asked_at + 1:choice_at] if l.strip().startswith("/")]
        trust = len(paths) == 1 and os.path.realpath(paths[0]) == top
    inputs = [box_text] if box_text is not None else [m.group("text") for m in (re.match(editor, l) for l in lines[-12:]) if m]
    # A prompt longer than Kimi's box scrolls inside it: the top border reads "↑ 13 more" and the first
    # visible line is the middle of the prompt (2026-10-25, three times), so the prompt's own last
    # sentence marks it too.
    held = any(t.startswith(("Read AGENTS.md", "Write your final review report", "[Pasted text")) for t in inputs) or (
        kind == "kimi" and scrolled and box_text is not None and box_text.endswith("Then reply with that path."))
    # Codex: its idle placeholder text was not checked live (its hook-review prompt stood in the
    # way on 2026-10-24), so any input line not holding the prompt counts as ready.
    ready = any(t in ready_text for t in inputs) if ready_text is not None else bool(inputs) and not held
    if kind == "kimi" and ready:
        ready = "context:" in "\n".join(lines[-12:])
    # A usage limit on the bottom lines (2026-10-26: Kimi said "429 ... reached your 5-hour usage limit").
    limit = re.search(r"reached your [\w-]+ usage limit", "\n".join(outside[-20:]))
    busy = re.search(r"ctrl\+c to stop|esc to interrupt|Press Ctrl\+B to run in background|Working\u2026|"
                     r"Running \d+ agents?|Agent Running", "\n".join(outside[-12:]))
    return types.SimpleNamespace(box=box, dialog=dialog, editor=editor, changed=screen != last, limit=limit,
                                 question=question, trust=trust, held=held, ready=ready, busy=busy)
PY
