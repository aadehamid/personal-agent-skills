#!/usr/bin/env bash
# The repository's checks, in one place. CI runs this script; the pre-push hook
# runs it. Add a gate here, not in ci.yml and not in the hook, so a local run
# and a CI run always run the same things.
#
# Usage: scripts/check.sh
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# A check that writes to the repo is a bug: a local run and a CI run would then
# disagree about what the repo contains, and a gate could pass by editing the
# thing it is supposed to be checking.
#
# Four snapshots, because each misses something the others catch:
#   contents          an edit to any file, tracked or untracked
#   type and mode     an untracked script that loses its execute bit changes
#                     neither its contents nor git's status
#   symlink targets   the content hash follows a link, so a link retargeted to
#                     a file with identical contents is otherwise invisible
#   status and index  a staged blob can change while the working file and the
#                     status wording stay the same
#
# Scope: this covers tracked and non-ignored files. Build output the repository
# ignores — .venv/, __pycache__/, .pytest_cache/, workspaces/ — is outside it,
# which is why the test commands below are run with bytecode and the pytest
# cache switched off. Anything the checks still write there is not covered.
#
# The './' prefix stops sha256sum reading a file named '-' as standard input.
# Requires GNU coreutils (Linux); `stat -c` is not the BSD spelling.
tracked_paths() {
  git ls-files -z --cached --others --exclude-standard
}

tree_state() {
  {
    # Every path goes through './' or a trailing '--', so a file named '--help'
    # is read as a path rather than as an option to the tool.
    tracked_paths | sort -z | sed -z 's|^|./|' | xargs -0 -r sha256sum -- 2>/dev/null
    # Mode, filesystem type, and — for a symlink — its target, quoted and
    # escaped by %N, so a target ending in a newline cannot collide with a
    # different name. One call covers what two would: fewer places to be wrong,
    # and no command substitution to strip a trailing newline.
    tracked_paths | sort -z | sed -z 's|^|./|' | xargs -0 -r stat -c '%A %F %N' -- 2>/dev/null
    git status --porcelain --untracked-files=all
    git ls-files --stage -z
  } | sha256sum | cut -d' ' -f1
}

before="$(tree_state)"

# Bytecode and the pytest cache are switched off so asking the question writes
# as little as possible into the repository. `uv` may still create .venv inside
# the CLI package; that path is ignored and outside the guard's scope.
export PYTHONDONTWRITEBYTECODE=1

echo "== knowledge-ingest CLI =="
(cd skills/research/knowledge-ingest/cli && uv run pytest -q -p no:cacheprovider)

echo
echo "== project-discovery validate =="
(cd skills/planning/project-discovery/scripts && python3 -m unittest test_validate)

echo
echo "== shell syntax =="
while IFS= read -r script; do
  bash -n "$script"
  echo "  ok  $script"
done < <(git ls-files 'scripts/*.sh' 'scripts/hooks/*')

after="$(tree_state)"
if [ "$before" != "$after" ]; then
  echo >&2
  echo "FAIL: the checks changed the working tree." >&2
  git status --short >&2
  exit 1
fi

echo
echo "All checks passed."
