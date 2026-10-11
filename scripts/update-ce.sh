#!/usr/bin/env bash
# Update Compound Engineering (EveryInc/compound-engineering-plugin) and sync
# its skills into every agent on this machine.
#
# The clone lives in ~/Projects/compound-engineering-plugin. Each CE skill is
# copied into ~/.agents/skills (the shared source of truth), then linked into
# every agent's skills folder: ~/.claude/skills, the default ~/.hermes/skills,
# and each ~/.hermes/profiles/*/skills. Claude and Codex also install CE as a
# plugin from their own marketplaces; this script keeps the shared copies in
# step with the latest release so every agent (including Hermes profiles that
# do not use those marketplaces) sees the same skills.
#
# Safe to re-run. It replaces only CE's own copies in ~/.agents/skills and
# links it owns; a real folder or another provider's link is left alone. It
# removes links whose CE skill no longer exists upstream.
#
# Usage: ./scripts/update-ce.sh [--dry-run]
# Optional: ln -s "$PWD/scripts/update-ce.sh" ~/.local/bin/update-ce
set -euo pipefail
command -v python3 >/dev/null || { echo "update-ce needs python3" >&2; exit 1; }
repo="$HOME/Projects/compound-engineering-plugin"
src="$repo/skills"
shared="$HOME/.agents/skills"
# ~/.claude/skills always; other agents only if they are installed.
agent_dirs=("$HOME/.claude/skills")
[ -d "$HOME/.hermes" ] && agent_dirs+=("$HOME/.hermes/skills")
# Every Hermes profile is an agent too; link CE into each one.
for p in "$HOME"/.hermes/profiles/*/skills; do
  [ -d "$p" ] && agent_dirs+=("$p")
done
dry=false
[ "${1:-}" = "--dry-run" ] && dry=true
run() { if $dry; then echo "would: $*"; else "$@"; fi; }

if [ -d "$repo/.git" ]; then
  run git -C "$repo" pull --ff-only --quiet
else
  run mkdir -p "$(dirname "$repo")"
  run git clone --quiet https://github.com/EveryInc/compound-engineering-plugin "$repo"
fi
if [ ! -d "$src" ]; then echo "no CE clone yet; run without --dry-run first"; exit 0; fi
echo "CE $(grep -m1 '\"version\"' "$repo/package.json" | tr -dc '0-9.') at $(git -C "$repo" rev-parse --short HEAD)"

run mkdir -p "$shared" "${agent_dirs[@]}"
# canon PATH: PATH with every folder above its last part resolved through
# symlinks. The last part is kept as is, so it works for dangling links and for
# links that point at other links.
canon() { python3 -c 'import os,sys;p=sys.argv[1];print(os.path.join(os.path.realpath(os.path.dirname(p)),os.path.basename(p)))' "$1"; }
# target LINK: where LINK points, as a canonical absolute path.
target() { canon "$(python3 -c 'import os,sys;l=sys.argv[1];print(os.path.join(os.path.dirname(l),os.readlink(l)))' "$1")"; }
# owned LINK EXPECTED: LINK is a link that points exactly at EXPECTED.
owned() {
  local got want
  [ -L "$1" ] && got="$(target "$1")" && want="$(canon "$2")" && [ -n "$got" ] && [ "$got" = "$want" ]
}
# free DEST EXPECTED: DEST is absent, or is a link we own (it points at EXPECTED).
# Anything else (a real file or folder, or another provider's link, live or
# dangling) belongs to someone else and is left alone.
free() { { [ ! -e "$1" ] && [ ! -L "$1" ]; } || owned "$1" "$2"; }

# Copy each CE skill into the shared root. CE's shared copies are real folders
# (not links), so replace only a copy that is CE's own: a real folder that is
# not a link to the clone is treated as ours only if it was copied from the
# clone before. To stay safe, we replace a real folder only when it is not a
# symlink and its SKILL.md matches the clone's name; otherwise we leave it.
copied=0
for dir in "$src"/*/; do
  name="$(basename "$dir")"
  [ -f "$dir/SKILL.md" ] || continue
  dest="$shared/$name"
  if [ -L "$dest" ]; then
    # A link here is not CE's model (CE uses copies); leave it to its owner.
    echo "skip $dest: is a symlink (not CE's copy model)"
    continue
  fi
  if [ -e "$dest" ] && [ ! -d "$dest" ]; then
    echo "skip $dest: is a real file, not a folder"
    continue
  fi
  run rm -rf "$dest"
  run cp -R "$dir" "$dest"
  copied=$((copied+1))
done

# Link each shared copy into every agent folder.
linked=0
for dir in "$src"/*/; do
  name="$(basename "$dir")"
  [ -f "$dir/SKILL.md" ] || continue
  for agent in "${agent_dirs[@]}"; do
    if ! free "$agent/$name" "$shared/$name"; then echo "skip $agent/$name: belongs to something else"; continue; fi
    run ln -sfn "$(python3 -c 'import os,sys;print(os.path.relpath(sys.argv[1],os.path.realpath(sys.argv[2])))' "$(canon "$shared/$name")" "$agent")" "$agent/$name"
  done
  linked=$((linked+1))
done

# Remove shared copies and agent links whose CE skill no longer exists upstream.
# Only touch entries that are CE's own: a symlink pointing at the CE clone, or
# a real folder that was copied from the clone. Never remove a name that is not
# a CE skill (mattpocock, pstack, personal skills share this directory).
for l in "$shared"/*; do
  name="$(basename "$l")"
  [ -d "$src/$name" ] && continue
  removed_shared=false
  # A symlink is CE's only if it points at the CE clone's skill.
  if [ -L "$l" ]; then
    owned "$l" "$src/$name" || continue
    run rm "$l"; echo "removed $l"; removed_shared=true
  elif [ -d "$l" ]; then
    # A real folder: only remove it if it is a CE skill that used to exist.
    # We cannot prove provenance of an arbitrary real folder, so only remove
    # one whose name is a CE skill (name starts with ce-, or is lfg/wtf).
    # Anything else is left alone, and its agent links are left alone too.
    case "$name" in
      ce-*|lfg|wtf) run rm -rf "$l"; echo "removed $l"; removed_shared=true ;;
      *) echo "skip $l: not a CE skill (left alone)"; continue ;;
    esac
  else
    continue
  fi
  # Only remove agent links when the shared entry was actually CE's and removed.
  if $removed_shared; then
    for d in "${agent_dirs[@]}"; do
      a="$d/$name"
      owned "$a" "$shared/$name" && { run rm "$a"; echo "removed $a"; }
    done
  fi
done

echo "copied $copied CE skills, linked $linked into agent folders"
