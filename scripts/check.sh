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
# The snapshot is Python, not GNU coreutils, so it runs the same on Linux and
# macOS. It opens each path itself, so a file named '-' is never read as stdin.
tree_state() {
  # A failed read or stat raises, so the snapshot aborts instead of dropping the
  # path from both sides and comparing equal. Tests: scripts/test_tree_state.py.
  python3 scripts/tree-state.py
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
(cd skills/planning/project-discovery/scripts && python3 -m unittest test_validate test_subject_case)

echo
echo "== check guard and way-of-working scripts =="
python3 scripts/test_tree_state.py
python3 skills/engineering/way-of-working/scripts/test_herdr_review.py
python3 skills/engineering/way-of-working/scripts/test_pi_review.py
python3 skills/engineering/way-of-working/scripts/test_pr_scripts.py

echo
echo "== ontology skill scripts =="
(cd skills/data/ontology/scripts && uv run --no-project --with rdflib --with pyyaml --with pyshacl python3 -m unittest -q test_checks)

echo
echo "== ontology-to-lpg skill scripts =="
(cd skills/data/ontology-to-lpg/scripts && uv run --no-project --with rdflib --with pyshacl python3 -m unittest -q test_projection)

echo
echo "== shell syntax =="
while IFS= read -r script; do
  bash -n "$script"
  echo "  ok  $script"
done < <(git ls-files 'scripts/*.sh' 'scripts/hooks/*' 'skills/*/*/scripts/*.sh' 'skills/*/*/templates/*.sh')

after="$(tree_state)"
if [ "$before" != "$after" ]; then
  echo >&2
  echo "FAIL: the checks changed the working tree." >&2
  git status --short >&2
  exit 1
fi

echo
echo "All checks passed."
