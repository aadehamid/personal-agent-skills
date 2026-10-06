#!/usr/bin/env bash
# Update pstack (cursor/plugins) and link its skills into every agent on this machine.
#
# The clone lives in ~/Projects/cursor-plugins. Each pstack skill is linked into
# ~/.agents/skills (Codex reads it directly), then into ~/.claude/skills and,
# when Hermes is installed, ~/.hermes/skills. pstack's subagents are linked into ~/.claude/agents.
# Cursor is skipped: it has pstack as a plugin from its own marketplace.
#
# Skills in EXCLUDE are never linked, and an existing link to them is removed.
# unslop is excluded because clear-writing replaces it.
#
# Safe to re-run. It never replaces a real folder, and it removes links whose
# target pstack skill no longer exists upstream.
#
# Usage: ./scripts/update-pstack.sh [--dry-run]
# Optional: ln -s "$PWD/scripts/update-pstack.sh" ~/.local/bin/update-pstack
set -euo pipefail
command -v python3 >/dev/null || { echo "update-pstack needs python3" >&2; exit 1; }
EXCLUDE=(unslop)
repo="$HOME/Projects/cursor-plugins"
src="$repo/pstack/skills"
shared="$HOME/.agents/skills"
# ~/.claude/skills always; other agents only if they are installed.
agent_dirs=("$HOME/.claude/skills")
[ -d "$HOME/.hermes" ] && agent_dirs+=("$HOME/.hermes/skills")
dry=false
[ "${1:-}" = "--dry-run" ] && dry=true
run() { if $dry; then echo "would: $*"; else "$@"; fi; }
excluded() { local s; for s in "${EXCLUDE[@]}"; do [ "$1" = "$s" ] && return 0; done; return 1; }

if [ -d "$repo/.git" ]; then
  run git -C "$repo" pull --ff-only --quiet
else
  run mkdir -p "$(dirname "$repo")"
  run git clone --quiet https://github.com/cursor/plugins "$repo"
fi
if [ ! -d "$src" ]; then echo "no pstack clone yet; run without --dry-run first"; exit 0; fi
echo "pstack $(grep -m1 '"version"' "$repo/pstack/.cursor-plugin/plugin.json" | tr -dc '0-9.') at $(git -C "$repo" rev-parse --short HEAD)"

run mkdir -p "$shared" "${agent_dirs[@]}" "$HOME/.claude/agents"
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
linked=0
for dir in "$src"/*/; do
  name="$(basename "$dir")"
  [ -f "$dir/SKILL.md" ] || continue
  excluded "$name" && continue
  if ! free "$shared/$name" "$src/$name"; then echo "skip $shared/$name: belongs to something else"; continue; fi
  run ln -sfn "${dir%/}" "$shared/$name"
  for agent in "${agent_dirs[@]}"; do
    if ! free "$agent/$name" "$shared/$name"; then echo "skip $agent/$name: belongs to something else"; continue; fi
    run ln -sfn "$(python3 -c 'import os,sys;print(os.path.relpath(sys.argv[1],os.path.realpath(sys.argv[2])))' "$(canon "$shared/$name")" "$agent")" "$agent/$name"
  done
  linked=$((linked+1))
done

for a in "$repo"/pstack/agents/*.md; do
  dest="$HOME/.claude/agents/$(basename "$a")"
  if ! free "$dest" "${a%/}"; then echo "skip $dest: belongs to something else"; continue; fi
  run ln -sfn "$a" "$dest"
done

# Collect pstack names to unlink: excluded skills, and shared links whose
# pstack target was removed upstream. Then remove those names everywhere,
# but only where the link points at pstack or at the shared copy.
gone=("${EXCLUDE[@]}")
for l in "$shared"/*; do
  [ ! -e "$l" ] && owned "$l" "$src/$(basename "$l")" && gone+=("$(basename "$l")")
done
for name in "${gone[@]}"; do
  # Only touch a name whose shared link is pstack's (or already gone). Another
  # skill with the same name, such as the unslop alias, keeps its links.
  if [ -L "$shared/$name" ] && ! owned "$shared/$name" "$src/$name"; then continue; fi
  [ -L "$shared/$name" ] && { run rm "$shared/$name"; echo "removed $shared/$name"; }
  [ -e "$shared/$name" ] && continue
  for d in "${agent_dirs[@]}"; do
    l="$d/$name"
    owned "$l" "$shared/$name" && { run rm "$l"; echo "removed $l"; }
  done
done
for l in "$HOME/.claude/agents"/*.md; do
  [ ! -e "$l" ] && owned "$l" "$repo/pstack/agents/$(basename "$l")" && { run rm "$l"; echo "removed $l"; }
done
echo "linked $linked pstack skills (excluded: ${EXCLUDE[*]})"

# Cursor keeps pstack as a plugin. Some pstack skills link to ../unslop/SKILL.md
# by path, so point each cached copy's unslop folder at the clear-writing alias.
# The original goes to a backup outside Cursor's folders. Re-run after Cursor
# updates the plugin (each version is a new cache folder).
alias_dir="$shared/unslop"
backup="$HOME/.local/share/pstack-unslop-backup"
if [ -e "$alias_dir/SKILL.md" ]; then
  # The cache is cache/<marketplace>/<plugin>/<version>/. The plugin folder is
  # named "pstack" on some installs and a numeric id on others, so match on the
  # name in each copy's .cursor-plugin/plugin.json instead.
  for u in "$HOME"/.cursor/plugins/cache/*/*/*/skills/unslop; do
    [ -e "$u" ] || continue
    [ -L "$u" ] && continue
    copy="$(dirname "$(dirname "$u")")"
    name="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("name",""))' "$copy/.cursor-plugin/plugin.json" 2>/dev/null || true)"
    [ "$name" = pstack ] || continue
    ver="$(basename "$copy")"
    run mkdir -p "$backup"
    # One backup per cache folder and run, so a restored copy never lands
    # inside an earlier backup.
    provider="$(basename "$(dirname "$(dirname "$copy")")")-$(basename "$(dirname "$copy")")"
    run mv "$u" "$backup/unslop-$provider-$ver-$(date +%Y%m%d%H%M%S)-$$"
    run ln -s "$alias_dir" "$u"
    echo "cursor: pstack $ver unslop now points to the clear-writing alias"
  done
fi
