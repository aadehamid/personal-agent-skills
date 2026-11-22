#!/usr/bin/env bash
# Copy the files and folders a review was handed (--attach) into one new folder, and print its path.
#
# Usage: review-evidence.sh <parent folder> <path>...
#   The review scripts call it before the reviewer starts, so the reviewer reads a fixed copy.
#   Copies are named <n>-<name>, and MANIFEST.txt lists where each came from. A path that is a link is
#   copied as what it points at. A folder holding a link or a special file is refused, because the copy
#   would lead the reviewer back out to what nobody attached.
#   It does not look inside the files: what is attached reaches the reviewer's model provider.
# Exit 2: a path cannot be attached; nothing is left behind.
# Tests: test_review_evidence.py, run by the repository's scripts/check.sh.
set -euo pipefail

[ $# -ge 2 ] || { echo "usage: $0 <parent folder> <path>..." >&2; exit 2; }
parent=$1
shift
dest="" copied=""
discard() {
  [ -z "$copied" ] && [ -n "$dest" ] || return 0
  chmod -R u+rwX "$dest" 2>/dev/null || true
  rm -rf "$dest"
}
trap discard EXIT
trap 'exit 2' TERM INT HUP
refuse() { echo "cannot attach '$1': $2" >&2; exit 2; }
# A path that starts with "-" would read as an option to find and cp.
as_path() { case "$1" in -*) printf './%s' "$1" ;; *) printf '%s' "$1" ;; esac; }

for given in "$@"; do
  [ -n "$given" ] && [ -e "$given" ] || refuse "$given" "no such file or folder"
  src=$(as_path "$given")
  if [ -d "$src" ]; then
    other=$(find -H "$src" ! -type f ! -type d -print) || refuse "$given" "it cannot be read"
    [ -z "$other" ] || refuse "$given" "it holds a link or special file ($other); attach its target by name"
  elif [ ! -f "$src" ]; then
    refuse "$given" "not a file or folder"
  fi
done

mkdir -p "$parent" || refuse "$1" "$parent cannot be made"
dest=$(mktemp -d "${parent%/}/review-evidence-XXXXXX") || refuse "$1" "$parent cannot be written"
n=0
for given in "$@"; do
  n=$((n + 1))
  src=$(as_path "$given")
  copy="$n-$(basename -- "$given")"
  if [ -d "$src" ]; then
    mkdir "$dest/$copy" && cp -R "$src/." "$dest/$copy/" || refuse "$given" "the copy failed"
  else
    cp "$src" "$dest/$copy" || refuse "$given" "the copy failed"
  fi
  printf '%s <- %s\n' "$copy" "$given" >> "$dest/MANIFEST.txt"
done
# cp keeps a read-only folder read-only, and the caller must be able to remove the copy.
chmod -R u+rwX "$dest" || refuse "$1" "the copy cannot be made removable"
copied=1
echo "$dest"
