#!/usr/bin/env bash
# Copy to scripts/check.sh when you set up an ontology repository; CI and the pre-push hook run it.
# Rules: references/governance.md, "Checks"; the guard's full design: the way-of-working skill,
# references/guardrails.md. Replace every TODO, and delete a step only when the repo has nothing for it.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Git sets GIT_DIR and friends when it runs a hook; a test that makes its own repository would
# otherwise act on this one.
while IFS= read -r var; do unset "$var"; done < <(compgen -e | grep '^GIT_' || true)
export PYTHONDONTWRITEBYTECODE=1

run() { echo "--- $*"; "$@"; }

# No-writes guard: a check that writes to the repository is a bug. This snapshot hashes git's
# status, the index entries and the bytes of every modified or untracked file. Python, so a
# failed read raises instead of dropping the path. Add entry types, modes and symlink targets
# as guardrails.md describes if the repo has untracked scripts or links.
snapshot() {
  python3 - <<'PY'
import hashlib, os, subprocess
h = hashlib.sha256()
h.update(subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all"]))
h.update(subprocess.check_output(["git", "ls-files", "-s"]))
names = subprocess.check_output(["git", "ls-files", "-z", "-m", "-o", "--exclude-standard"]).split(b"\0")
for name in sorted(n for n in names if n):
    h.update(name + b"\0")
    path = os.fsdecode(name)
    if os.path.lexists(path):
        with open(path, "rb") as f:
            h.update(hashlib.sha256(f.read()).digest())
    else:
        h.update(b"deleted")
print(h.hexdigest())
PY
}
before="$(snapshot)"

# 1. Requirements: the machine-readable requirements file has no internal conflicts (governance rule 2).
# TODO: run "python3 requirements/check_requirements.py"

# 2. Generated files: every builder rebuilds into a temporary directory and --verify compares
#    (release.md, rules 9 and 19). One line per module package, then the catalog.
# TODO: run "python3 release/build_module.py <module> --verify"   # one per module
# TODO: run "python3 release/build_catalog.py --verify"

# 3. Shapes: every module's shapes, the whole-graph gate and the release-package test (shacl.md).
#    Validate against the pinned shape version only (governance rule 18).
# TODO: run "python3 validation/validate_all.py"

# 4. Regression: every competency question on the released packages (regression.md, rule 13).
# TODO: run "python3 regression/run.py"

# 5. Every test file.
# TODO: run "python3 -m pytest -q -p no:cacheprovider tests/"

# 6. The shared tool's consistency checks (governance rules 7, 19 and 26).
# TODO: run "python3 scripts/facts.py decisions"   # decision records agree with their index
# TODO: run "python3 scripts/facts.py quotes"      # quotes match the saved answers files
# TODO: run "python3 scripts/facts.py names"       # no tracked file names the owner
# TODO: run "python3 scripts/facts.py counts" >/dev/null   # figures compute from source

after="$(snapshot)"  # a standalone assignment, so a failing snapshot stops the script
if [ "$before" != "$after" ]; then
  echo "the checks changed the working tree; they must only read it:" >&2
  git status --short >&2
  exit 1
fi
echo "all checks passed"
