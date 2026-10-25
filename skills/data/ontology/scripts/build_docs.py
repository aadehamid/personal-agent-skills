#!/usr/bin/env python3
"""Step 10: build a released package's documentation pages with Widoco, beside the package
(references/release.md, "Documentation pages").

Run: python3 build_docs.py --jar <widoco.jar> --releases <releases folder> --docs <docs folder>
         [--package <module>/<version>]...

For each package (every released one, or each --package), Widoco reads releases/<module>/<version>/<module>.ttl
and writes its pages to <docs>/<module>/<version>/, which is emptied first; then docs-source.json records the
module, the version, the SHA-256 of the package's manifest.json, and the Widoco jar's file name, so check_docs.py
can tell when the pages no longer describe the package. Widoco runs locally (Java); nothing leaves the machine.

Exit 0 on success, 1 when Widoco fails on a package, 2 when an input is missing or the arguments are wrong.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

from check_docs import packages, sha256


def build(jar, releases, docs, module, version):
    package = os.path.join(releases, module, version)
    out = os.path.join(docs, module, version)
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    run = subprocess.run(["java", "-jar", jar, "-ontFile", os.path.join(package, f"{module}.ttl"), "-outFolder", out,
                          "-rewriteAll", "-noPlaceHolderText", "-lang", "en"],
                         capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if run.returncode != 0 or not os.path.isfile(os.path.join(out, "index-en.html")):
        print(f"FAIL widoco: {module} {version}: {(run.stdout + run.stderr).strip()[-500:]}")
        return False
    with open(os.path.join(out, "docs-source.json"), "w", encoding="utf-8") as f:
        json.dump({"module": module, "version": version, "manifest_sha256": sha256(os.path.join(package, "manifest.json")),
                   "built_with": os.path.basename(jar)}, f, indent=2, sort_keys=True)
        f.write("\n")
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
