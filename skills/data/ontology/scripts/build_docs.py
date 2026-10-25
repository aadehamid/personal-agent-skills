#!/usr/bin/env python3
"""Step 10: build a released package's documentation pages with Widoco, beside the package
(references/release.md, "Documentation pages").

Run: python3 build_docs.py --jar <widoco.jar> --releases <releases folder> --docs <docs folder>
         [--package <module>/<version>]...

For each package (every released one, or each --package), the builder first checks the package against its
manifest: every file the manifest lists, <module>.ttl among them, has the SHA-256 the manifest records. Only then
does Widoco read releases/<module>/<version>/<module>.ttl, into a temporary folder beside <docs>/<module>/<version>/.
When Widoco succeeds, docs-source.json records the module, the version, the SHA-256 of the package's manifest.json
and the Widoco jar's file name, and the new folder replaces the old one; when anything fails, the old pages stay as
they were. check_docs.py can then tell when the pages no longer describe the package. Widoco runs locally (Java);
nothing leaves the machine.

Exit 0 on success, 1 when a package does not match its manifest or Widoco fails on it, 2 when an input is missing
or the arguments are wrong.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

from check_docs import packages, sha256


def package_problems(package, module):
    """Why the package does not match its manifest: a missing or changed file, or no Turtle listed."""
    try:
        with open(os.path.join(package, "manifest.json"), encoding="utf-8") as f:
            files = json.load(f).get("files")
    except (OSError, ValueError):
        return ["its manifest.json cannot be read"]
    if not isinstance(files, dict) or f"{module}.ttl" not in files:
        return [f"its manifest lists no {module}.ttl"]
    problems = []
    for name, expected in sorted(files.items()):
        path = os.path.join(package, name)
        if not os.path.isfile(path):
            problems.append(f"{name} is missing")
        elif sha256(path) != expected:
            problems.append(f"{name} does not match the SHA-256 in its manifest")
    return problems


def build(jar, releases, docs, module, version):
    package = os.path.join(releases, module, version)
    problems = package_problems(package, module)
    if problems:
        print(f"FAIL package: {module} {version}: {'; '.join(problems)}")
        return False
    out = os.path.join(docs, module, version)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    staging = tempfile.mkdtemp(prefix=f".{version}.building-", dir=os.path.dirname(out))
    try:
        run = subprocess.run(["java", "-jar", jar, "-ontFile", os.path.join(package, f"{module}.ttl"), "-outFolder",
                              staging, "-rewriteAll", "-noPlaceHolderText", "-lang", "en"],
                             capture_output=True, text=True, stdin=subprocess.DEVNULL)
        if run.returncode != 0 or not os.path.isfile(os.path.join(staging, "index-en.html")):
            print(f"FAIL widoco: {module} {version}: {(run.stdout + run.stderr).strip()[-500:]}")
            return False
        with open(os.path.join(staging, "docs-source.json"), "w", encoding="utf-8") as f:
            json.dump({"module": module, "version": version,
                       "manifest_sha256": sha256(os.path.join(package, "manifest.json")),
                       "built_with": os.path.basename(jar)}, f, indent=2, sort_keys=True)
            f.write("\n")
        old = None
        if os.path.isdir(out):
            old = staging + ".old"
            os.rename(out, old)
        try:
            os.rename(staging, out)
        except OSError as exc:
            if old:
                try:
                    os.rename(old, out)   # the previous pages go back where check_docs.py looks for them
                except OSError as restore:
                    # Leave the previous pages where they are and say where, so a person can move them back.
                    print(f"FAIL promote: {module} {version}: {exc}; restoring the previous pages also failed "
                          f"({restore}); they are at {old}: move that folder back to {out}")
                    return False
            print(f"FAIL promote: {module} {version}: {exc}; the previous pages are unchanged")
            return False
        staging = None
        if old:
            shutil.rmtree(old)
    finally:
        if staging and os.path.isdir(staging):
            shutil.rmtree(staging)
    print(f"built {out}")
    return True


def main(argv):
    p = argparse.ArgumentParser(prog="build_docs.py")
    p.add_argument("--jar", required=True)
    p.add_argument("--releases", required=True)
    p.add_argument("--docs", required=True)
    p.add_argument("--package", action="append", default=[])
    try:
        args = p.parse_args(argv)
    except SystemExit:
        return 2
    if not os.path.isfile(args.jar) or not os.path.isdir(args.releases):
        print("ERROR give an existing --jar and --releases folder", file=sys.stderr)
        return 2
    wanted = sorted(tuple(x.split("/", 1)) for x in args.package) if args.package else sorted(packages(args.releases))
    missing = [w for w in wanted if len(w) != 2 or w not in packages(args.releases)]
    if missing:
        print(f"ERROR not a released package: {missing}", file=sys.stderr)
        return 2
    ok = all([build(args.jar, args.releases, args.docs, m, v) for m, v in wanted])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
