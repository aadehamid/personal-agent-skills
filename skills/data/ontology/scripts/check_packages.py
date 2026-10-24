#!/usr/bin/env python3
"""Step 9 and 10: every written release package is intact and conforms to its own shapes over its released
closure (references/shacl.md, rule 9; references/release.md, rules 8, 10 and 12).

Run: uv run --with rdflib --with pyshacl python3 check_packages.py --releases <dir> --expect <packages.txt>

Layout: <dir>/<module>/<version>/ holds <module>.ttl, shapes.ttl and manifest.json. The manifest is JSON
with "depends_on" ({"<module>": "<version>"}, the versions the package requires) and "files"
({"<file name>": "<sha-256>"}, every file of the package but the manifest). <packages.txt> pins the
packages by hand, one "<module> <version>" per line ("#" starts a comment).

For each package:
  listed      its folder is in <packages.txt>, and every line of <packages.txt> has a folder
  intact      the files in the folder are exactly the manifest's "files" plus manifest.json, and each
              hash matches (a released package never changes)
  closure     each version it requires exists; what a dependency requires is read from that release's
              own manifest, and where two paths reach different releases of one module, only the
              highest is loaded
  conforms    the package, with its closure loaded, gives no SHACL result at any severity

Prints one FAIL line per failure. Exit 0 when nothing fails, 1 when anything fails, 2 when the arguments
are wrong or <packages.txt> cannot be read.
"""
import argparse
import hashlib
import json
import os
import re
import sys

from rdflib import Graph

from check_shapes import results


def version_key(version):
    """1.10.0 after 1.9.0; a release candidate (1.0.0-rc.1) before its release."""
    core, _, pre = version.partition("-")
    nums = tuple(int(n) for n in core.split("."))
    return nums, (0, pre) if pre else (1, "")


def read_manifest(releases, module, version):
    with open(os.path.join(releases, module, version, "manifest.json"), encoding="utf-8") as f:
        return json.load(f)


def closure(releases, depends_on):
    """The released packages a package loads: {module: version}. Raises FileNotFoundError for a missing one."""
    found = {}
    todo = list(depends_on.items())
    while todo:
        module, version = todo.pop()
        if module in found and version_key(found[module]) >= version_key(version):
            continue
        found[module] = version
        todo += list((read_manifest(releases, module, version).get("depends_on") or {}).items())
    return found


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
        deps = closure(releases, manifest.get("depends_on") or {})
        data = package_graph(releases, module, version)
        for dep, dep_version in sorted(deps.items()):
            data += package_graph(releases, dep, dep_version)
        shapes = Graph().parse(os.path.join(folder, "shapes.ttl"))
    except (OSError, ValueError) as exc:
        return [f"{where}: cannot load the package or its closure: {exc}"]
    except Exception as exc:  # an rdflib parser error
        return [f"{where}: cannot parse the package or its closure: {exc}"]
    return [f"{where}: {sev} on {focus}" + (f" path {path}" if path else "") + f": {msg}"
            for sev, focus, path, msg in results(data, shapes)]


def read_expected(path):
    pins = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) != 2:
                raise ValueError(f"{path}: expected '<module> <version>', got {line!r}")
            pins.add(tuple(parts))
    return pins


def on_disk(releases):
    return {(m, v) for m in os.listdir(releases) if os.path.isdir(os.path.join(releases, m))
            for v in os.listdir(os.path.join(releases, m))
            if os.path.isdir(os.path.join(releases, m, v)) and re.match(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.]+)?$", v)}


def main(argv):
    p = argparse.ArgumentParser(prog="check_packages.py")
    p.add_argument("--releases", required=True)
    p.add_argument("--expect", required=True)
    try:
        args = p.parse_args(argv)
        pins = read_expected(args.expect)
    except SystemExit:
        return 2
    except (OSError, ValueError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    found = on_disk(args.releases)
    fails = [f"{m} {v}: package folder not pinned in {args.expect}" for m, v in sorted(found - pins)]
    fails += [f"{m} {v}: pinned but no package folder" for m, v in sorted(pins - found)]
    for module, version in sorted(found & pins):
        fails += check_package(args.releases, module, version)
    for line in fails:
        print("FAIL", line)
    if fails:
        print(f"{len(fails)} failure(s)", file=sys.stderr)
        return 1
    if not found:
        print(f"FAIL no release package under {args.releases}")
        return 1
    print(f"{len(found)} release packages are intact and conform over their closures")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
