#!/usr/bin/env python3
"""Start a consistency-graph tool in a repository from the skill's tested template.

Usage:
  start.py REPO NAME [--dir scripts]

Copies templates/graph_tool.py to <dir>/NAME.py and templates/test_graph_tool.py
to <dir>/test_NAME.py, renaming the module, the command name in messages and
the GRAPH_ROOT variable to NAME's. It refuses to overwrite a file, so it only
ever starts a tool; from then on the project owns the copy.
"""
import argparse
import keyword
import os
import re
import sys

TEMPLATES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")


def render(text, name):
    env = name.upper() + "_ROOT"
    text = text.replace("GRAPH_ROOT", env)
    text = re.sub(r"\bgraph_tool\b", name, text)
    return text.replace("graph_tool.py", name + ".py")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("repo")
    parser.add_argument("name", help="a Python module name, such as twin_graph or plant_graph")
    parser.add_argument("--dir", default="scripts", help="folder for the tool and its tests (default: scripts)")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[a-z][a-z0-9_]*", args.name) or args.name == "graph_tool" or keyword.iskeyword(args.name):
        print("start: NAME must be a lower-case Python module name, not a keyword or graph_tool", file=sys.stderr)
        return 2
    if os.path.isabs(args.dir) or ".." in args.dir.replace("\\", "/").split("/"):
        print("start: --dir must be a folder inside the repository, given relative to it", file=sys.stderr)
        return 2
    repo = os.path.abspath(args.repo)
    if not os.path.exists(os.path.join(repo, ".git")):
        print(f"start: {repo} is not the root of a git repository", file=sys.stderr)
        return 2
    folder = os.path.join(repo, args.dir)
    part = repo
    for piece in args.dir.replace("\\", "/").split("/"):
        part = os.path.join(part, piece)
        if os.path.islink(part):
            print(f"start: {os.path.relpath(part, repo)} is a symlink; use a real folder", file=sys.stderr)
            return 2
    targets = {"graph_tool.py": f"{args.name}.py", "test_graph_tool.py": f"test_{args.name}.py"}
    existing = [t for t in targets.values() if os.path.lexists(os.path.join(folder, t))]
    if existing:
        print(f"start: already exists in {args.dir}: {', '.join(existing)}; the project owns it now", file=sys.stderr)
        return 1
    os.makedirs(folder, exist_ok=True)
    for template, target in targets.items():
        with open(os.path.join(TEMPLATES, template), encoding="utf-8") as fh:
            text = render(fh.read(), args.name)
        path = os.path.join(folder, target)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.chmod(path, 0o755 if target == f"{args.name}.py" else 0o644)
        print(f"write {os.path.join(args.dir, target)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
