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
# Releases need no git (release.md, "Without a remote"), so outside a git checkout, or with no git
# installed, the guard takes the first two snapshots over every file under the folder, leaving out
# only .git and the build output the commands below may write (.venv, __pycache__, .pytest_cache).
# A failed read or stat raises, so the snapshot aborts instead of dropping the path from both sides.
snapshot() {
  python3 - <<'PY'
import hashlib, os, stat, subprocess
h = hashlib.sha256()
BUILD_OUTPUT = {".git", ".venv", "__pycache__", ".pytest_cache"}

def in_git():
    """True in a checkout, False with no git or outside any repository. Any other answer from git (a
    dubious owner, a .git file naming a missing folder) stops the snapshot, so the index and status are
    never left out in silence. Git says "(or any of the parent directories)" only after it searched
    upward and found nothing; about a broken .git it names the path instead."""
    try:
        r = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], capture_output=True,
                           env=dict(os.environ, LC_ALL="C"))
    except FileNotFoundError:
        return False
    if r.returncode == 0 and r.stdout.strip() == b"true":
        return True
    err = r.stderr.decode(errors="replace").strip()
    if r.returncode != 0 and "not a git repository (or any" in err:
        return False
    raise SystemExit("git rev-parse failed, so the guard cannot tell whether this is a checkout: " + err)

def refuse(exc):
    raise exc

def every_file():
    """Every path under the folder, relative, as bytes; a symlink to a folder is listed, not entered,
    and a folder that cannot be listed stops the snapshot."""
    found = []
    for folder, dirs, files in os.walk(os.curdir, onerror=refuse):
        dirs[:] = sorted(d for d in dirs if d not in BUILD_OUTPUT)
        for d in list(dirs):
            if os.path.islink(os.path.join(folder, d)):
                dirs.remove(d)
                files.append(d)
        found += [os.fsencode(os.path.normpath(os.path.join(folder, f))) for f in files]
    return found

git = in_git()
if git:
    listing = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                             capture_output=True, check=True)
    if listing.stderr:
        raise SystemExit("git ls-files: " + listing.stderr.decode(errors="replace").strip())
    names = [n for n in listing.stdout.split(b"\0") if n]
else:
    names = every_file()
for name in sorted(names):
    path = os.fsdecode(name)
    st = os.lstat(path)
    h.update(name + b"\0" + oct(st.st_mode).encode())
    if stat.S_ISLNK(st.st_mode):
        h.update(b"link:" + os.fsencode(os.readlink(path)))
        if not stat.S_ISREG(os.stat(path).st_mode):
            raise SystemExit(f"{path}: symlink to a non-regular file; the guard cannot read it")
    elif not stat.S_ISREG(st.st_mode):
        raise SystemExit(f"{path}: listed but not a file or symlink; the guard cannot read it")
    with open(path, "rb") as f:
        h.update(hashlib.sha256(f.read()).digest())
if git:
    h.update(subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all"]))
    h.update(subprocess.check_output(["git", "ls-files", "--stage", "-z"]))
print(h.hexdigest())
PY
}
before="$(snapshot)"

# 1. Requirements: schema and conflicts (governance rule 2). Copy the skill's check_requirements.py and
#    check_taxonomy.py to scripts/ontology/, with check_sssom.py for section 2b, build_package.py and
#    build_catalog.py for section 3, and check_shapes.py, check_cardinality.py, check_code_lists.py,
#    check_packages.py, check_changelogs.py, check_docs.py and run_regression.py for sections 4, 4b, 4c
#    and 5 below.
# TODO: uv run --no-project --with pyyaml python3 scripts/ontology/check_requirements.py requirements.yaml

# 2. Taxonomy, classes and properties: the mechanical checks (identity-taxonomy.md, Step 3, rule 13), on
#    data files only: shapes files (*-shapes.ttl) may hold blank nodes (identity-taxonomy.md, Step 2, rule 5).
# TODO: data=(); while IFS= read -r -d '' f; do data+=("$f"); done < <(find modules -name '*.ttl' ! -name '*-shapes.ttl' -print0)
# TODO: [ "${#data[@]}" -gt 0 ] || { echo "no data Turtle under modules/" >&2; exit 1; }   # an empty set must fail, not pass
# TODO: uv run --no-project --with rdflib python3 scripts/ontology/check_taxonomy.py "${data[@]}"

# 2b. Mappings: every SSSOM mapping set the project keeps (external-ontologies.md, rules 9 to 12). A project
#     with no mapping set yet runs nothing here.
# TODO: mappings=(); while IFS= read -r -d '' f; do mappings+=("$f"); done < <(find modules -name '*.sssom.tsv' -print0)
# TODO: [ "${#mappings[@]}" -eq 0 ] || uv run --no-project --with pyyaml python3 scripts/ontology/check_sssom.py "${mappings[@]}"

# 3. Generated files: every builder rebuilds into a temporary directory and its verify command compares
#    (release.md, rules 9 and 19). One line per module package, then the combined catalog, which
#    build_catalog.py builds from the packages' own catalog.ttl files plus the title and description
#    given here.
# TODO: uv run --no-project --with rdflib --with pyyaml --with pyshacl python3 scripts/ontology/build_package.py verify release/<module>-<version>.yaml --releases releases   # one per release (packaging-walkthrough.md)
# TODO: uv run --no-project --with rdflib --with pyshacl python3 scripts/ontology/build_catalog.py verify --releases releases --title "<the catalog's title>" --description "<one sentence>"

# 4. Shapes: every module's shapes, the whole-graph gate, a cardinality on every property, and the
#    release-package test (shacl.md), against the pinned shape version only (governance rule 17). The
#    code-list check also reads the shapes tests' illustration file, the one instance per class that
#    domain-model.md, rule 9, allows: the modules alone hold no instance, so no property takes a
#    code-list value there, and the check fails rather than pass with nothing to test.
# TODO: shapes=(); while IFS= read -r -d '' f; do shapes+=("$f"); done < <(find modules -name '*-shapes.ttl' -print0)
# TODO: [ "${#shapes[@]}" -gt 0 ] || { echo "no *-shapes.ttl under modules/" >&2; exit 1; }   # an empty set must fail, not pass
# TODO: uv run --no-project --with rdflib --with pyshacl python3 scripts/ontology/check_shapes.py --shapes "${shapes[@]}" --data "${data[@]}" --every-shapes-file-under modules
# TODO: uv run --no-project --with rdflib python3 scripts/ontology/check_cardinality.py --shapes "${shapes[@]}" --data "${data[@]}"
# TODO: uv run --no-project --with rdflib --with pyshacl python3 scripts/ontology/check_code_lists.py --shapes "${shapes[@]}" --data "${data[@]}" tests/illustration.ttl   # add --not-code-list=<scheme IRI> for each taxonomy scheme
# TODO: uv run --no-project --with rdflib --with pyshacl python3 scripts/ontology/check_packages.py --releases releases --expect releases/packages.txt

# 4b. Release notes: every package's changelog states its known gaps (release.md, rule 18). Add one --exempt
#     <module>/<version> for each package released before the project adopted the rule.
# TODO: python3 scripts/ontology/check_changelogs.py --releases releases

# 4c. Documentation pages: every released package has current pages beside it (release.md, rules 24 to 27).
# TODO: python3 scripts/ontology/check_docs.py --releases releases --docs docs/ontology

# 5. Regression: every competency question on the released packages (regression.md, rule 13).
# TODO: uv run --no-project --with rdflib python3 scripts/ontology/run_regression.py --expected regression/expected.csv --queries regression/queries <the newest release of each module's Turtle>

# 6. Every test file (governance rule 15).
# TODO: python3 -m pytest -q -p no:cacheprovider tests/

# 7. Records and privacy: quotes match the saved answers files (governance rule 7); no tracked file
#    names the owner (governance rule 23); figures compute from committed code (governance rule 15).
#    The skill ships none of these three: each reads the project's own records, and the name check
#    builds the owner's name from fragments inside the project's script. Write them for the project
#    (short scripts, or the way-of-working skill's shared figures tool) and name them here.
# TODO: <the project's quote check: every quoted answer against the answers file it cites>
# TODO: <the project's name check: no tracked file or path holds the owner's personal or account name>
# TODO: <the project's figures tool, run so a figure that no longer computes fails>  >/dev/null

after="$(snapshot)"  # a standalone assignment, so a failing snapshot stops the script
if [ "$before" != "$after" ]; then
  echo "the checks changed the working tree; they must only read it:" >&2
  if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then git --no-pager status --short >&2; fi
  exit 1
fi

todo_left="$(grep -c '^# TODO:' "${BASH_SOURCE[0]}" || true)"
if [ "$todo_left" -gt 0 ]; then
  echo "FAIL: this check script is still the skeleton: $todo_left '# TODO:' line(s) to replace with real commands" >&2
  exit 1
fi
echo "all checks passed"
