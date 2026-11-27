#!/usr/bin/env bash
# The repository's checks, in one place. CI runs this script; the pre-push hook
# runs it. Add a gate here, not in ci.yml and not in the hook, so a local run
# and a CI run always run the same things.
#
# Usage: scripts/check.sh
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Git sets these when it runs a hook. Inherited by a test that runs `git init`, they re-initialised this
# repository instead of the test's folder: from a linked worktree that set core.bare=true on the shared
# checkout (retro of 2026-10-26). No check needs them once the working directory is the top level.
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR GIT_PREFIX

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
# These suites spend their time starting processes (each case runs a script against stub programs), so they run
# in parallel: one worker per core, at most 8. Every case makes its own temporary folders, so order does not
# matter. Keep it so when adding a case. Each file still runs alone with python3 <file>.
suites=(
  scripts/test_tree_state.py
  scripts/test_pre_push_hook.py
  scripts/test_link_skills.py
  scripts/test_playbook_html.py
  skills/engineering/way-of-working/scripts/test_herdr_review.py
  skills/engineering/way-of-working/scripts/test_rex_review.py
  skills/engineering/way-of-working/scripts/test_hc_review.py
  skills/engineering/way-of-working/scripts/test_pi_review.py
  skills/engineering/way-of-working/scripts/test_agy_review.py
  skills/engineering/way-of-working/scripts/test_review_evidence.py
  skills/engineering/way-of-working/scripts/test_pr_scripts.py
  skills/engineering/way-of-working/scripts/test_stop_cursor_review.py
  skills/engineering/way-of-working/scripts/test_guard_check_running.py
  skills/engineering/relate-project-memory/scripts/test_install.py
)
# No config file and no PYTEST_ADDOPTS: either could leave tests out without failing.
run_pytest() {
  PYTEST_ADDOPTS= uv run --no-project --with pytest==9.2.0 --with pytest-xdist==3.8.0 python3 -m pytest \
    -c /dev/null --rootdir . -q -p no:cacheprovider "$@"
}
# pytest fails only when all the files together hold no test. unittest failed each such file, so ask per file.
collected="$(run_pytest --collect-only "${suites[@]}")" || { printf '%s\n' "$collected" >&2; exit 1; }
for suite in "${suites[@]}"; do
  grep -q "^$suite::" <<<"$collected" || { echo "FAIL: $suite has no tests." >&2; exit 1; }
done
run_pytest -n auto --maxprocesses=8 "${suites[@]}"

echo
echo "== ontology skill scripts =="
(cd skills/data/ontology/scripts && uv run --no-project --with rdflib --with pyyaml --with pyshacl python3 -m unittest discover -q -p "test_*.py")
(cd skills/data/ontology && uv run --no-project --with pyyaml python3 scripts/check_sssom.py templates/mappings.sssom.tsv)
# The two tabular engines need different rdflib versions, so each runs in its own environment.
(cd skills/data/ontology/scripts && TABULAR_ENGINE=morph-kgc uv run --no-project --with morph-kgc==2.10.0 --with rdflib python3 -m unittest -q test_tabular)
(cd skills/data/ontology/scripts && TABULAR_ENGINE=maplib uv run --no-project --with maplib==0.20.26 --with polars --with rdflib python3 -m unittest -q test_tabular)

echo
echo "== ontology-to-lpg skill scripts =="
(cd skills/data/ontology-to-lpg/scripts && uv run --no-project --with rdflib --with pyshacl --with mcp-neo4j-data-modeling==0.8.2 python3 -m unittest -q test_projection test_engine_gate test_modeling test_explore test_release_record test_run_projection)
# Once more with the neo4j driver, which run_projection.py installs for the scripts it runs: with it,
# load_verify.Timed wraps every statement in neo4j.Query, and the fakes must read that as the driver does.
(cd skills/data/ontology-to-lpg/scripts && uv run --no-project --with rdflib --with pyshacl --with neo4j --with mcp-neo4j-data-modeling==0.8.2 python3 -m unittest -q test_projection test_engine_gate test_modeling test_explore test_release_record test_run_projection)
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  (cd skills/data/ontology-to-lpg/docker && LPG_RUN=/tmp/lpg-run NEO4J_PASSWORD=check \
    docker compose --profile neo4j --profile fuseki config -q) && echo "  ok  ontology-to-lpg docker/compose.yaml parses"
else
  echo "  skip  docker compose not available; the pin tests above still read compose.yaml"
fi

echo
echo "== rdf-store skill scripts =="
(cd skills/data/rdf-store/scripts && uv run --no-project --with pyoxigraph python3 -m unittest -q test_rdf_store)
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  (cd skills/data/rdf-store/docker && docker compose config -q) && echo "  ok  rdf-store docker/compose.yaml parses"
else
  echo "  skip  docker compose not available"
fi

echo
echo "== shell syntax =="
while IFS= read -r script; do
  bash -n "$script"
  echo "  ok  $script"
done < <(git ls-files 'scripts/*.sh' 'scripts/hooks/*' 'skills/*/*/scripts/*.sh' 'skills/*/*/templates/*.sh')

if [ "$(git config --get core.bare || true)" = "true" ]; then
  echo >&2
  echo "FAIL: core.bare is true after the checks: a test re-initialised this repository. Reset it with" >&2
  echo "      git config core.bare false, then find the git call that inherited the hook's variables." >&2
  exit 1
fi

after="$(tree_state)"
if [ "$before" != "$after" ]; then
  echo >&2
  echo "FAIL: the checks changed the working tree." >&2
  git status --short >&2
  exit 1
fi

echo
echo "All checks passed."
