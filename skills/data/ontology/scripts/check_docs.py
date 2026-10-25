#!/usr/bin/env python3
"""Step 10: every released package has its documentation beside it, built from the package as released
(references/release.md, "Documentation pages").

Run: python3 check_docs.py --releases <releases folder> --docs <docs folder>

A package is releases/<module>/<version>/ holding manifest.json, where <version> is X.Y.Z with an optional
pre-release, as check_packages.py counts them; other folders are not packages, and only version folders under
<docs>/<module>/ are documentation (build_docs.py's temporary folders start with a dot). Its
documentation is <docs>/<module>/<version>/, built by build_docs.py, holding docs-source.json, which records the
SHA-256 of the manifest the pages were built from.

Checks:
  missing   every released package has a documentation folder
  source    every documentation folder has a readable docs-source.json naming its module, version and
            manifest_sha256
  stale     the recorded manifest_sha256 equals the SHA-256 of that package's manifest.json today
  orphan    no documentation folder exists for a package that is not released

The pages themselves are not compared: Widoco writes the generation date into them, so two builds of one package
differ. The manifest hash says which package they describe.

Prints one FAIL line per failure. Exit 0 when nothing fails, 1 when anything fails, 2 when a folder is missing or
the arguments are wrong.
"""
import argparse
import hashlib
import json
import os
import re
import sys

VERSION = re.compile(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$")   # the version folders check_packages.py counts


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def packages(root):
    """(module, version) of every releases/<module>/<version>/manifest.json under root."""
    found = set()
    for module in sorted(os.listdir(root)):
        mdir = os.path.join(root, module)
        if not os.path.isdir(mdir):
            continue
        for version in sorted(os.listdir(mdir)):
            if VERSION.match(version) and os.path.isfile(os.path.join(mdir, version, "manifest.json")):
                found.add((module, version))
    return found


def documented(root):
    found = set()
    for module in sorted(os.listdir(root)):
        mdir = os.path.join(root, module)
        if os.path.isdir(mdir):
            found |= {(module, v) for v in sorted(os.listdir(mdir))
                      if VERSION.match(v) and os.path.isdir(os.path.join(mdir, v))}
    return found


def check(releases, docs):
    fails = []
    released, docs_for = packages(releases), documented(docs)
    for module, version in sorted(released - docs_for):
        fails.append(("missing", f"{module} {version} has no documentation folder"))
    for module, version in sorted(docs_for - released):
        fails.append(("orphan", f"{module} {version} has documentation but no released package"))
    for module, version in sorted(released & docs_for):
        source = os.path.join(docs, module, version, "docs-source.json")
        try:
            with open(source, encoding="utf-8") as f:
                record = json.load(f)
        except (OSError, ValueError):
            fails.append(("source", f"{module} {version} has no readable docs-source.json"))
            continue
        if not isinstance(record, dict) or record.get("module") != module or record.get("version") != version \
                or not record.get("manifest_sha256"):
            fails.append(("source", f"{module} {version}: docs-source.json does not name module, version and "
                                    f"manifest_sha256"))
            continue
        today = sha256(os.path.join(releases, module, version, "manifest.json"))
        if record["manifest_sha256"] != today:
            fails.append(("stale", f"{module} {version}: built from manifest {record['manifest_sha256'][:12]}, "
                                   f"the package's manifest is {today[:12]}"))
    return fails


def main(argv):
    p = argparse.ArgumentParser(prog="check_docs.py")
    p.add_argument("--releases", required=True)
    p.add_argument("--docs", required=True)
    try:
        args = p.parse_args(argv)
    except SystemExit:
        return 2
    for folder in (args.releases, args.docs):
        if not os.path.isdir(folder):
            print(f"ERROR {folder} is not a folder", file=sys.stderr)
            return 2
    fails = check(args.releases, args.docs)
    for name, message in fails:
        print(f"FAIL {name}: {message}")
    if fails:
        print(f"{len(fails)} check(s) failed", file=sys.stderr)
        return 1
    print(f"every released package has current documentation ({len(packages(args.releases))} package(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
