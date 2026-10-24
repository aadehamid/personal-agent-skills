#!/usr/bin/env bash
# Copy to scripts/check.sh when you set up an ontology repository; CI and the pre-push hook run it.
# Rules: references/governance.md, "Checks" (rules 15 to 17). The no-writes guard below is the
# four-snapshot guard of the way-of-working skill's references/guardrails.md, written out so the
# script works without that skill.
#
# Replace each "# TODO:" line with the command it names, and delete a step only when the repository
# has nothing for it. Until no "# TODO:" line is left, the script fails at the end, so an unfilled
# copy can never pass in CI.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Git sets GIT_DIR and friends when it runs a hook; a test that makes its own repository would
# otherwise act on this one.
while IFS= read -r var; do unset "$var"; done < <(compgen -e | grep '^GIT_' || true)
export PYTHONDONTWRITEBYTECODE=1

# No-writes guard (governance rule 15; guardrails.md "One check script, run everywhere"). Four
# snapshots, each pinned to what it must observe:
#   contents       every tracked and non-ignored untracked path, opened directly (a file named '-'
#                  is never read as stdin)
#   entry          type and permission bits from lstat, and a symlink's exact target bytes
#   index          blob id and mode of every index entry (git ls-files --stage)
#   status         git's own porcelain view
# A failed read or stat raises, so the snapshot aborts instead of dropping the path from both sides.
snapshot() {
  python3 - <<'PY'
import hashlib, os, stat, subprocess
h = hashlib.sha256()
listing = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                         capture_output=True, check=True)
if listing.stderr:
    raise SystemExit("git ls-files: " + listing.stderr.decode(errors="replace").strip())
for name in sorted(n for n in listing.stdout.split(b"\0") if n):
    path = os.fsdecode(name)
    st = os.lstat(path)
    h.update(name + b"\0" + oct(st.st_mode).encode())
    if stat.S_ISLNK(st.st_mode):
        h.update(b"link:" + os.fsencode(os.readlink(path)))
        if not stat.S_ISREG(os.stat(path).st_mode):
            raise SystemExit(f"{path}: symlink to a non-regular file; the guard cannot read it")
    elif not stat.S_ISREG(st.st_mode):
        raise SystemExit(f"{path}: listed by git but not a file or symlink; the guard cannot read it")
    with open(path, "rb") as f:
        h.update(hashlib.sha256(f.read()).digest())
h.update(subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all"]))
h.update(subprocess.check_output(["git", "ls-files", "--stage", "-z"]))
print(h.hexdigest())
PY
}
before="$(snapshot)"

# 1. Requirements: schema and conflicts (governance rule 2). Copy the skill's check_requirements.py and
#    check_taxonomy.py to scripts/ontology/, with check_shapes.py, check_code_lists.py, check_packages.py
#    and run_regression.py for steps 4 and 5.
# TODO: uv run --no-project --with pyyaml python3 scripts/ontology/check_requirements.py requirements.yaml

# 2. Taxonomy, classes and properties: the mechanical checks (identity-taxonomy.md, Step 3, rule 13), on
#    data files only: shapes files (*-shapes.ttl) may hold blank nodes (identity-taxonomy.md, Step 2, rule 5).
# TODO: data=(); while IFS= read -r -d '' f; do data+=("$f"); done < <(find modules -name '*.ttl' ! -name '*-shapes.ttl' -print0)
# TODO: [ "${#data[@]}" -gt 0 ] || { echo "no data Turtle under modules/" >&2; exit 1; }   # an empty set must fail, not pass
# TODO: uv run --no-project --with rdflib python3 scripts/ontology/check_taxonomy.py "${data[@]}"

# 3. Generated files: every builder rebuilds into a temporary directory and --verify compares
#    (release.md, rules 9 and 19). One line per module package, then the catalog.
# TODO: python3 release/build_module.py <module> --verify   # one per module
# TODO: python3 release/build_catalog.py --verify

# 4. Shapes: every module's shapes, the whole-graph gate and the release-package test (shacl.md),
#    against the pinned shape version only (governance rule 17).
# TODO: uv run --no-project --with rdflib --with pyshacl python3 scripts/ontology/check_shapes.py --shapes <every shapes file> --data <every data file> --every-shapes-file-under modules
# TODO: uv run --no-project --with rdflib --with pyshacl python3 scripts/ontology/check_code_lists.py --shapes <every shapes file> --data <every data file>
# TODO: uv run --no-project --with rdflib --with pyshacl python3 scripts/ontology/check_packages.py --releases releases --expect releases/packages.txt

# 5. Regression: every competency question on the released packages (regression.md, rule 13).
# TODO: uv run --no-project --with rdflib python3 scripts/ontology/run_regression.py --expected regression/expected.csv --queries regression/queries <every released package's Turtle>

# 6. Every test file (governance rule 15).
# TODO: python3 -m pytest -q -p no:cacheprovider tests/

# 7. Records and privacy: quotes match the saved answers files (governance rule 7); no tracked file
#    names the owner (governance rule 23); figures compute from committed code (governance rule 15).
# TODO: python3 scripts/facts.py quotes
# TODO: python3 scripts/facts.py names
# TODO: python3 scripts/facts.py counts >/dev/null

after="$(snapshot)"  # a standalone assignment, so a failing snapshot stops the script
if [ "$before" != "$after" ]; then
  echo "the checks changed the working tree; they must only read it:" >&2
  git --no-pager status --short >&2
  exit 1
fi

todo_left="$(grep -c '^# TODO:' "${BASH_SOURCE[0]}" || true)"
if [ "$todo_left" -gt 0 ]; then
  echo "FAIL: this check script is still the skeleton: $todo_left '# TODO:' line(s) to replace with real commands" >&2
  exit 1
fi
echo "all checks passed"
