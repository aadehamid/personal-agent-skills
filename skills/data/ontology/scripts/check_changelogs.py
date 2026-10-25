#!/usr/bin/env python3
"""Step 10: every release's changelog states its known gaps (references/release.md, rule 18).

Run: python3 check_changelogs.py --releases <releases folder> [--exempt <module>/<version>]...
     python3 check_changelogs.py <CHANGELOG.md>...

With --releases it reads releases/<module>/<version>/CHANGELOG.md for every package: a <version> folder named
X.Y.Z (with an optional pre-release, as check_packages.py counts them) that holds a manifest.json. --exempt leaves out
a package released before the project adopted the rule, which stays as released (rule 10). A releases folder with no
package at all fails, since there is nothing to check; one whose packages are all exempt passes.

Checks:
  packages   --releases finds at least one package
  changelog  every package has a CHANGELOG.md
  section    the changelog has a "Known gaps" heading (any level)
  content    the section says "None." or lists gaps as bullets, one per gap
  gap        every gap bullet gives its reason ("Reason:") and the decision or open question that records it
             ("Record:"), each label followed by a value, not only spaces or punctuation

Prints one FAIL line per failure. Exit 0 when nothing fails, 1 when anything fails, 2 when an input cannot be read
or the arguments are wrong.
"""
import argparse
import os
import re
import sys

HEADING = re.compile(r"^#{1,6}\s+known gaps\s*$", re.IGNORECASE)
VERSION = re.compile(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$")   # the version folders check_packages.py counts


def known_gaps(text):
    """The lines of the Known gaps section, or None when there is no such heading."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if HEADING.match(line.strip()):
            level = len(line.strip()) - len(line.strip().lstrip("#"))
            body = []
            for rest in lines[i + 1:]:
                m = re.match(r"^(#{1,6})\s", rest.strip())
                if m and len(m.group(1)) <= level:
                    break
                body.append(rest)
            return body
    return None


def check_text(text, where):
    body = known_gaps(text)
    if body is None:
        return [("section", f"{where} has no Known gaps section")]
    content = [l.strip() for l in body if l.strip()]
    bullets = [l for l in content if re.match(r"^[-*]\s+\S", l)]
    if not bullets:
        if [l.lower() for l in content] == ["none."] or [l.lower() for l in content] == ["none"]:
            return []
        return [("content", f"{where}: the Known gaps section says neither \"None.\" nor lists a gap")]
    fails = []
    for bullet in bullets:
        for label in ("Reason:", "Record:"):
            # The value runs from the label to the next label or the end, and must hold a letter or a digit:
            # space and punctuation alone ("—", "?", "...") say nothing.
            value = re.search(re.escape(label) + r"(.*?)(?=Reason:|Record:|$)", bullet)
            if not value or not re.search(r"[^\W_]", value.group(1)):
                fails.append(("gap", f"{where}: {bullet[:80]!r} has no {label} value"))
    return fails


def main(argv):
    p = argparse.ArgumentParser(prog="check_changelogs.py")
    p.add_argument("files", nargs="*")
    p.add_argument("--releases")
    p.add_argument("--exempt", action="append", default=[])
    try:
        args = p.parse_args(argv)
    except SystemExit:
        return 2
    if bool(args.files) == bool(args.releases):
        print("ERROR give either changelog files or --releases", file=sys.stderr)
        return 2
    targets = [(path, path) for path in args.files]
    fails = []
    found = 0
    if args.releases:
        if not os.path.isdir(args.releases):
            print(f"ERROR {args.releases} is not a folder", file=sys.stderr)
            return 2
        found = 0
        for module in sorted(os.listdir(args.releases)):
            mdir = os.path.join(args.releases, module)
            for version in sorted(os.listdir(mdir)) if os.path.isdir(mdir) else []:
                package = os.path.join(mdir, version)
                if not VERSION.match(version) or not os.path.isfile(os.path.join(package, "manifest.json")):
                    continue
                found += 1
                if f"{module}/{version}" in args.exempt:
                    continue
                changelog = os.path.join(package, "CHANGELOG.md")
                if not os.path.isfile(changelog):
                    fails.append(("changelog", f"{module} {version} has no CHANGELOG.md"))
                    continue
                targets.append((changelog, f"{module} {version}"))
    if args.releases and not found:
        fails.append(("packages", f"{args.releases} holds no released package (releases/<module>/<X.Y.Z>/manifest.json)"))
    for path, where in targets:
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except OSError as exc:
            print(f"ERROR cannot read {path}: {exc}", file=sys.stderr)
            return 2
        fails += check_text(text, where)
    for name, message in fails:
        print(f"FAIL {name}: {message}")
    if fails:
        print(f"{len(fails)} check(s) failed", file=sys.stderr)
        return 1
    print(f"every changelog states its known gaps ({len(targets)} file(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
