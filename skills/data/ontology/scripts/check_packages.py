#!/usr/bin/env python3
"""Step 9 and 10: every written release package is intact and conforms to its own shapes over its released
closure (references/shacl.md, rule 9; references/release.md, rules 8, 10 and 12).

Run: uv run --no-project --with rdflib --with pyshacl python3 check_packages.py --releases <dir> --expect <packages.txt>

Layout (release.md, rule 8): <dir>/<module>/<version>/ holds <module>.ttl, shapes.ttl and manifest.json,
and may hold other files the manifest lists. <version> is X.Y.Z with an optional pre-release (1.0.0-rc.1);
other folder names are not packages. The manifest is a JSON object with "files" ({"<file name>":
"<sha-256>"}, every file of the package but the manifest) and "depends_on" ({"<module>": "<version>"},
the releases the package requires; absent means none). <packages.txt> pins the packages by hand, one
"<module> <version>" per line ("#" starts a comment).

For each package:
  listed      its folder is in <packages.txt>, and every line of <packages.txt> has a folder
  intact      the files in the folder are exactly the manifest's "files" plus manifest.json, and each
              hash matches (a released package never changes)
  closure     the releases it requires, and theirs, read from each chosen release's own manifest; where
              two paths reach different releases of one module, only the highest is loaded (semantic
              versioning precedence, so 1.0.0-rc.2 < 1.0.0-rc.10 < 1.0.0), and only the chosen releases'
              requirements count
  conforms    the package, with its closure loaded, gives no SHACL result at any severity (and holds no
              sh:rule; see check_shapes.py)

Prints one FAIL line per failure. Exit 0 when nothing fails, 1 when anything fails, 2 when the arguments
are wrong, <dir> is not a directory or <packages.txt> cannot be read.
"""
import argparse
import hashlib
import json
import os
import re
import sys

from rdflib import Graph

from check_shapes import describe, results

VERSION = re.compile(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$")


def version_key(version):
    """Semantic versioning precedence (semver.org, item 11): numbers first; a release above its
    pre-releases; pre-release identifiers compared one by one, numeric ones as numbers and below
    alphanumeric ones, and a longer list above its own prefix."""
    core, _, pre = version.partition("-")
    nums = tuple(int(n) for n in core.split("."))
    if not pre:
        return nums, 1, ()
    ids = tuple((0, int(i), "") if i.isdigit() else (1, 0, i) for i in pre.split("."))
    return nums, 0, ids


def read_manifest(releases, module, version):
    """The manifest as a dict; raises ValueError when it is not the documented shape."""
    with open(os.path.join(releases, module, version, "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    if not isinstance(manifest, dict):
        raise ValueError("manifest is not a JSON object")
    for key in ("files", "depends_on"):
        if not isinstance(manifest.get(key, {}), dict):
            raise ValueError(f'manifest "{key}" is not an object')
    return manifest


def closure(releases, depends_on):
    """The releases a package loads, {module: version}: settle on the highest release of each module
    reachable from the package's own requirements through the chosen releases' requirements. A release
    that loses to a higher one contributes nothing. Raises OSError or ValueError for a chosen release
    whose manifest is missing or malformed."""
    chosen = {}
    for _ in range(1000):
        want = {}
        sources = [dict(depends_on)] + [read_manifest(releases, m, v).get("depends_on") or {} for m, v in chosen.items()]
        for deps in sources:
            for module, version in deps.items():
                if module not in want or version_key(version) > version_key(want[module]):
                    want[module] = version
        if want == chosen:
            return chosen
        chosen = want
    raise ValueError("the dependency closure does not settle")


def package_graph(releases, module, version):
    return Graph().parse(os.path.join(releases, module, version, f"{module}.ttl"))


def check_package(releases, module, version):
    """Failures for one package, each a string."""
    where = f"{module} {version}"
    folder = os.path.join(releases, module, version)
    try:
        manifest = read_manifest(releases, module, version)
    except (OSError, ValueError) as exc:
        return [f"{where}: no readable manifest.json: {exc}"]
    fails = []
    files = manifest.get("files") or {}
    present = set(os.listdir(folder)) - {"manifest.json"}
    for name in sorted(present - set(files)):
        fails.append(f"{where}: {name} is not in the manifest")
    for name, digest in sorted(files.items()):
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            fails.append(f"{where}: {name} is in the manifest but missing")
            continue
        with open(path, "rb") as f:
            if hashlib.sha256(f.read()).hexdigest() != digest:
                fails.append(f"{where}: {name} does not match its manifest hash")
    for required in (f"{module}.ttl", "shapes.ttl"):
        if required not in present:
            fails.append(f"{where}: no {required}")
    if fails:
        return fails
    try:
        data = package_graph(releases, module, version)
        for dep, dep_version in sorted(closure(releases, manifest.get("depends_on") or {}).items()):
            data += package_graph(releases, dep, dep_version)
        shapes = Graph().parse(os.path.join(folder, "shapes.ttl"))
        found = results(data, shapes)
    except (OSError, ValueError) as exc:
        return [f"{where}: cannot load the package or its closure: {exc}"]
    except Exception as exc:  # an rdflib parser error, or pySHACL rejecting a malformed shape
        return [f"{where}: cannot parse or apply the package or its closure: {exc}"]
    return [f"{where}: {describe(r)}" for r in found]


def read_expected(path):
    pins = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) != 2 or not VERSION.match(parts[1]):
                raise ValueError(f"{path}: expected '<module> <version>', got {line!r}")
            pins.add(tuple(parts))
    return pins


def on_disk(releases):
    return {(m, v) for m in os.listdir(releases) if os.path.isdir(os.path.join(releases, m))
            for v in os.listdir(os.path.join(releases, m))
            if os.path.isdir(os.path.join(releases, m, v)) and VERSION.match(v)}


def main(argv):
    p = argparse.ArgumentParser(prog="check_packages.py")
    p.add_argument("--releases", required=True)
    p.add_argument("--expect", required=True)
    try:
        args = p.parse_args(argv)
        if not os.path.isdir(args.releases):
            raise ValueError(f"not a directory: {args.releases}")
        pins = read_expected(args.expect)
    except SystemExit:
        return 2
    except (OSError, ValueError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    found = on_disk(args.releases)
    if not found:
        print(f"FAIL no release package under {args.releases}")
        return 1
    fails = [f"{m} {v}: package folder not pinned in {args.expect}" for m, v in sorted(found - pins)]
    fails += [f"{m} {v}: pinned but no package folder" for m, v in sorted(pins - found)]
    for module, version in sorted(found & pins):
        fails += check_package(args.releases, module, version)
    for line in fails:
        print("FAIL", line)
    if fails:
        print(f"{len(fails)} failure(s)", file=sys.stderr)
        return 1
    print(f"{len(found)} release packages are intact and conform over their closures")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
