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
# Usage: ./scripts/link-skills.sh [--dry-run]
set -euo pipefail
repo="$(cd "$(dirname "$0")/.." && pwd)"
shared="$HOME/.agents/skills"
dry=false
[ "${1:-}" = "--dry-run" ] && dry=true

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

find "$repo/skills" -name SKILL.md -not -path '*/node_modules/*' | while read -r f; do
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
