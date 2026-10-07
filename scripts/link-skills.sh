#!/usr/bin/env bash
# Link every skill in this repo into ~/.agents/skills, then into the skills
# folder of every agent on this machine (Claude Code, Factory, Windsurf, Kiro, ...).
#
# A skill is any folder under skills/ with a SKILL.md.
# An agent folder is any folder under ~ that already holds a symlink into
# ~/.agents/skills. That is how `npx skills add -g` installs skills, so agents
# set up by that tool are found without a hard-coded list. ~/.claude/skills is
# always included.
#
# Safe to re-run. It never replaces a real folder, only symlinks.
#
# Usage: ./scripts/link-skills.sh [--dry-run] [--claude-md] [--tools]
#   --claude-md  also add config/claude-md-snippet.md to ~/.claude/CLAUDE.md,
#                unless that file already contains it. Without this line in
#                CLAUDE.md, Claude rarely loads the writing skill on its own.
#   --tools      also install each skill's command-line tool: any skill with a
#                cli/pyproject.toml is installed with `uv tool install --editable`,
#                so edits to the repo take effect without a reinstall. Needs uv.
set -euo pipefail
repo="$(cd "$(dirname "$0")/.." && pwd)"
shared="$HOME/.agents/skills"
dry=false
claude_md=false
tools=false
for arg in "$@"; do
  case "$arg" in
    --dry-run) dry=true ;;
    --claude-md) claude_md=true ;;
    --tools) tools=true ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

run() { if $dry; then echo "would: $*"; else "$@"; fi; }

# Make a relative link at $2 that points to $1, the same form npx skills uses.
link() {
  local src="$1" dst="$2" rel
  if [ -e "$dst" ] && [ ! -L "$dst" ]; then
    echo "skip $dst: a real folder is already there"
    return
  fi
  rel="$(python3 -c 'import os,sys; print(os.path.relpath(sys.argv[1], os.path.dirname(sys.argv[2])))' "$src" "$dst")"
  run ln -sfn "$rel" "$dst"
}

agent_dirs() {
  {
    echo "$HOME/.claude/skills"
    find "$HOME" -maxdepth 5 \
      \( -path "$HOME/Dropbox" -o -path "$HOME/Library" -o -path "$HOME/.Trash" \
         -o -path "$shared" -o -name node_modules -o -name .git \) -prune \
      -o -type l -lname '*.agents/skills/*' -print 2>/dev/null || true
  } | while read -r p; do
    # Lines from find are links. Keep their parent folder.
    if [ "$p" = "$HOME/.claude/skills" ]; then echo "$p"; else dirname "$p"; fi
  done | sort -u
}

mkdir -p "$shared" "$HOME/.claude/skills"
dirs="$(agent_dirs)"
echo "agent folders: $(echo "$dirs" | wc -l | tr -d ' ')"

# Skip dependency folders: a Python venv can hold packages that ship their own
# SKILL.md (typer does), and those must not be linked as skills.
find "$repo/skills" -name SKILL.md -not -path '*/node_modules/*' -not -path '*/.venv/*' \
  -not -path '*/site-packages/*' | while read -r f; do
  dir="$(dirname "$f")"
  name="$(basename "$dir")"
  # The shared copy points at this repo. Agent folders point at the shared copy.
  if [ -e "$shared/$name" ] && [ ! -L "$shared/$name" ]; then
    echo "skip $name: $shared/$name is a real folder"
    continue
  fi
  run ln -sfn "$dir" "$shared/$name"
  while read -r agent; do
    link "$shared/$name" "$agent/$name"
  done <<< "$dirs"
  echo "linked $name"
done

if $claude_md; then
  snippet="$repo/config/claude-md-snippet.md"
  target="$HOME/.claude/CLAUDE.md"
  # Append only the sections the target does not already carry. Each section
  # carries its own marker comment, and presence is decided by that marker: a
  # heading alone proves nothing, because the target may hold a heading of the
  # same name with different text under it.
  missing="$(python3 - "$snippet" "$target" <<'PY'
import pathlib, sys

src, dst = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
have = dst.read_text() if dst.exists() else ""

blocks, cur = [], []
for line in src.read_text().splitlines(keepends=True):
    if line.startswith("# ") and cur:
        blocks.append("".join(cur))
        cur = []
    cur.append(line)
if cur:
    blocks.append("".join(cur))

def marker(block):
    for line in block.splitlines():
        if line.startswith("<!-- way-of-working-snippet:"):
            return line.strip()
    return ""

out = []
for block in blocks:
    tag = marker(block)
    if not tag:
        raise SystemExit(
            f"snippet section has no marker comment: {block.splitlines()[0]!r}"
        )
    if tag not in have:
        out.append(block.rstrip() + "\n")
sys.stdout.write("\n".join(out))
PY
)"
  if [ -z "$missing" ]; then
    echo "CLAUDE.md already has every snippet section"
  elif $dry; then
    echo "would: append the missing section(s) of $snippet to $target"
  else
    { [ -s "$target" ] && echo; printf '%s' "$missing"; } >> "$target"
    echo "added the missing section(s) to $target"
  fi
fi

if $tools; then
  if ! command -v uv >/dev/null 2>&1; then
    echo "skip tools: uv is not installed (https://docs.astral.sh/uv/)" >&2
  else
    find "$repo/skills" -path '*/cli/pyproject.toml' -not -path '*/node_modules/*' \
      -not -path '*/.venv/*' -not -path '*/site-packages/*' | while read -r py; do
      cli="$(dirname "$py")"
      run uv tool install --editable --force "$cli"
      echo "installed tool from ${cli#$repo/}"
    done
  fi
fi
