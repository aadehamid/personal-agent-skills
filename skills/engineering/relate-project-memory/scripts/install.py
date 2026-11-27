#!/usr/bin/env python3
"""Install, update or check shared Relate project memory in a repository.

Usage:
  install.py REPO --decision-ref REF --decision-records WHERE [--tests-dir DIR] [--dry-run]
  install.py REPO --update [--tests-dir DIR] [--dry-run]
  install.py REPO --check [--tests-dir DIR]

Files fall in two groups:

  tool-owned     scripts/memory.sh, scripts/memory/*.cypher, <tests-dir>/test_memory.py.
                 The skill owns them. --update replaces them; a plain install
                 refuses to overwrite one that differs.
  project-owned  .agents/skills/project-memory/SKILL.md, its .claude link,
                 the Claude SessionStart hook, Gemini's AGENTS.md setting and
                 the .gitignore lines. A plain install creates the missing
                 ones and adds missing entries; --update never touches them.

The installer plans every change first. If anything is wrong (a clash, a
missing argument, a symlink in the way, unreadable JSON) it changes nothing.

--check exits 1 if a tool-owned file is missing, differs from the skill's
template or has lost its execute bit; if the project skill is missing or still
holds an ADAPT marker or a {{placeholder}}; if the .claude link is not the
relative link the installer makes; or if AGENTS.md does not mention
scripts/memory.sh.
"""
import argparse
import json
import os
import re
import sys
import tempfile

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(SKILL_DIR, "templates")
PROJECT_SKILL = ".agents/skills/project-memory/SKILL.md"
CLAUDE_LINK = ".claude/skills/project-memory/SKILL.md"
LINK_TARGET = "../../../.agents/skills/project-memory/SKILL.md"
HOOK_MARK = "scripts/memory.sh brief"
HOOK_COMMAND = (
    "cd \"$CLAUDE_PROJECT_DIR\" && echo 'Project memory (scripts/memory.sh, project-memory skill). "
    "Most recent current facts:' && (scripts/memory.sh brief 15 2>&1 || true) && echo 'Recall before "
    "work on a topic; save decisions, corrections and findings before you finish.'"
)
GITIGNORE_LINES = [".relate-memory/", ".relate-memory.*"]
GITIGNORE_HEADER = "# Shared agent memory (scripts/memory.sh). Git ignores it; Dropbox may sync it."
PLACEHOLDER = re.compile(r"\{\{[^{}\n]+\}\}")


class Refusal(Exception):
    def __init__(self, message, code=2):
        super().__init__(message)
        self.code = code


def tool_files(tests_dir):
    # (template, path in the repository, executable)
    return [
        ("memory.sh", "scripts/memory.sh", True),
        ("memory/schema.cypher", "scripts/memory/schema.cypher", False),
        ("memory/remember.cypher", "scripts/memory/remember.cypher", False),
        ("test_memory.py", os.path.join(tests_dir, "test_memory.py"), False),
    ]


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def symlink_in(repo, rel, include_leaf=True):
    """Return the first part of rel, from the repo down, that is a symlink."""
    parts = rel.split(os.sep)
    if not include_leaf:
        parts = parts[:-1]
    for i in range(1, len(parts) + 1):
        part = os.path.join(*parts[:i])
        if os.path.islink(os.path.join(repo, part)):
            return part
    return None


def executable(path):
    # Git records only the execute bit, and checkouts follow the local umask,
    # so the owner's execute bit is the only mode worth comparing.
    return bool(os.stat(path).st_mode & 0o100)


class Plan:
    def __init__(self, repo):
        self.repo = repo
        self.ops = []

    def path(self, rel):
        return os.path.join(self.repo, rel)

    def write(self, rel, text, executable_bit=None, verb="write"):
        self.ops.append(("write", verb, rel, text, executable_bit))

    def link(self, rel, target):
        self.ops.append(("link", "link", rel, target, None))

    def describe(self):
        return [f"{verb} {rel}" + (f" -> {payload}" if kind == "link" else "")
                for kind, verb, rel, payload, _ in self.ops]

    def apply(self):
        for kind, _, rel, payload, executable_bit in self.ops:
            target = self.path(rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            if kind == "link":
                os.symlink(payload, target)
                continue
            if executable_bit is None and os.path.exists(target):
                mode = os.stat(target).st_mode & 0o777  # keep a project file's own mode
            elif executable_bit:
                mode = 0o755
            else:
                mode = 0o644
            fd, tmp = tempfile.mkstemp(dir=os.path.dirname(target), prefix=".install-")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            os.chmod(tmp, mode)
            os.replace(tmp, target)  # replaces a file, never writes through a link


def plan_tool_files(plan, tests_dir, update):
    clashes = []
    for template, rel, exec_bit in tool_files(tests_dir):
        text = read(os.path.join(TEMPLATES, template))
        target = plan.path(rel)
        found = symlink_in(plan.repo, rel)
        if found:
            raise Refusal(f"{found} is a symlink; the installer writes only into real folders and files")
        if os.path.exists(target):
            if read(target) == text and executable(target) == exec_bit:
                continue
            if update:
                plan.write(rel, text, exec_bit, verb="replace")
            else:
                clashes.append(rel)
        else:
            plan.write(rel, text, exec_bit)
    if clashes:
        raise Refusal("these files differ from the skill's version; rerun with --update to replace them:\n  "
                      + "\n  ".join(clashes), code=1)


def plan_project_skill(plan, decision_ref, decision_records):
    found = symlink_in(plan.repo, PROJECT_SKILL)
    if found:
        raise Refusal(f"{found} is a symlink; the installer writes only into real folders and files")
    if os.path.lexists(plan.path(PROJECT_SKILL)):
        return
    if not (decision_ref and decision_records):
        raise Refusal("creating the project skill needs --decision-ref and --decision-records")
    if "\n" in decision_ref or "\n" in decision_records:
        raise Refusal("--decision-ref and --decision-records must be one line each")
    text = read(os.path.join(TEMPLATES, "project-memory-SKILL.md"))
    # The reference sits inside JSON strings in the example episode.
    text = text.replace("{{DECISION_REF}}", json.dumps(decision_ref)[1:-1])
    text = text.replace("{{DECISION_RECORDS}}", decision_records)
    plan.write(PROJECT_SKILL, text)


def plan_claude_link(plan):
    found = symlink_in(plan.repo, CLAUDE_LINK, include_leaf=False)
    if found:
        raise Refusal(f"{found} is a symlink; replace it with a folder")
    if not os.path.lexists(plan.path(CLAUDE_LINK)):
        plan.link(CLAUDE_LINK, LINK_TARGET)


def load_json(plan, rel):
    found = symlink_in(plan.repo, rel)
    if found:
        raise Refusal(f"{found} is a symlink; the installer edits only real files")
    if not os.path.exists(plan.path(rel)):
        return {}
    try:
        with open(plan.path(rel), encoding="utf-8") as fh:
            data = json.load(fh)
    except ValueError as exc:
        raise Refusal(f"{rel} is not valid JSON ({exc}); fix it and run the installer again")
    if not isinstance(data, dict):
        raise Refusal(f"{rel} is not a JSON object")
    return data


def plan_claude_hook(plan):
    rel = ".claude/settings.json"
    settings = load_json(plan, rel)
    hooks = settings.setdefault("hooks", {})
    groups = hooks.setdefault("SessionStart", []) if isinstance(hooks, dict) else None
    if not isinstance(groups, list) or not all(
            isinstance(g, dict) and isinstance(g.get("hooks", []), list)
            and all(isinstance(h, dict) and isinstance(h.get("command", ""), str) for h in g.get("hooks", []))
            for g in groups):
        raise Refusal(f"{rel}: hooks.SessionStart is not the list of hook groups Claude Code expects")
    commands = [h.get("command", "") for g in groups for h in g.get("hooks", [])]
    if any(HOOK_MARK in c for c in commands):
        return
    groups.append({"hooks": [{"type": "command", "command": HOOK_COMMAND}]})
    plan.write(rel, json.dumps(settings, indent=2) + "\n", verb="update")


def plan_gemini_setting(plan):
    rel = ".gemini/settings.json"
    settings = load_json(plan, rel)
    context = settings.setdefault("context", {})
    names = context.get("fileName", []) if isinstance(context, dict) else None
    if isinstance(names, str):
        names = [names] if names else []
    if not (isinstance(names, list) and all(isinstance(n, str) and n for n in names)):
        raise Refusal(f"{rel}: context.fileName is not a file name or a list of them")
    if "AGENTS.md" in names:
        return
    if not names and os.path.exists(plan.path("GEMINI.md")):
        names = ["GEMINI.md"]  # keep the project's own context file
    context["fileName"] = names + ["AGENTS.md"]
    plan.write(rel, json.dumps(settings, indent=2) + "\n", verb="update")


def ignores(lines, entry):
    normal = {line.strip().lstrip("/") for line in lines}
    return entry in normal or ".relate-memory*" in normal


def plan_gitignore(plan):
    rel = ".gitignore"
    found = symlink_in(plan.repo, rel)
    if found:
        raise Refusal(f"{found} is a symlink; the installer edits only real files")
    text = read(plan.path(rel)) if os.path.exists(plan.path(rel)) else ""
    lines = text.splitlines()
    missing = [entry for entry in GITIGNORE_LINES if not ignores(lines, entry)]
    if not missing:
        return
    addition = "" if not text or text.endswith("\n") else "\n"
    if len(missing) == len(GITIGNORE_LINES):
        addition += ("\n" if text else "") + GITIGNORE_HEADER + "\n"
    addition += "\n".join(missing) + "\n"
    plan.write(rel, text + addition, verb="update")


def check(repo, tests_dir):
    problems = []
    for template, rel, exec_bit in tool_files(tests_dir):
        target = os.path.join(repo, rel)
        if symlink_in(repo, rel) or not os.path.isfile(target):
            problems.append(f"{rel}: missing or not a plain file; run install.py")
        elif read(target) != read(os.path.join(TEMPLATES, template)):
            problems.append(f"{rel}: differs from the skill's template; run install.py --update")
        elif executable(target) != exec_bit:
            problems.append(f"{rel}: execute bit should be {'set' if exec_bit else 'clear'}")
    skill = os.path.join(repo, PROJECT_SKILL)
    if symlink_in(repo, PROJECT_SKILL) or not os.path.isfile(skill):
        problems.append(f"{PROJECT_SKILL}: missing")
    else:
        text = read(skill)
        if "<!-- ADAPT" in text:
            problems.append(f"{PROJECT_SKILL}: still holds an ADAPT marker")
        if PLACEHOLDER.search(text):
            problems.append(f"{PROJECT_SKILL}: still holds a {{{{placeholder}}}}")
    link = os.path.join(repo, CLAUDE_LINK)
    found = symlink_in(repo, CLAUDE_LINK, include_leaf=False)
    if found:
        problems.append(f"{found}: a symlink, not a folder")
    elif not (os.path.islink(link) and os.readlink(link) == LINK_TARGET):
        problems.append(f"{CLAUDE_LINK}: not the relative link {LINK_TARGET}")
    agents = os.path.join(repo, "AGENTS.md")
    if not (os.path.isfile(agents) and "scripts/memory.sh" in read(agents)):
        problems.append("AGENTS.md: missing or does not mention scripts/memory.sh")
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("repo")
    parser.add_argument("--tests-dir", help="where test_memory.py goes (default: tests if it exists, else scripts)")
    parser.add_argument("--decision-ref", help="short reference to the decision, such as 'D17' or 'ADR-0058'")
    parser.add_argument("--decision-records", help="where decisions live, such as '`docs/decisions.md`'")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--update", action="store_true", help="replace tool-owned files with the skill's version")
    mode.add_argument("--check", action="store_true", help="report anything out of date or unadapted")
    parser.add_argument("--dry-run", action="store_true", help="print what would change and change nothing")
    args = parser.parse_args(argv)

    repo = os.path.abspath(args.repo)
    if not os.path.exists(os.path.join(repo, ".git")):
        print(f"install: {repo} is not the root of a git repository", file=sys.stderr)
        return 2
    tests_dir = args.tests_dir or ("tests" if os.path.isdir(os.path.join(repo, "tests")) else "scripts")

    if args.check:
        problems = check(repo, tests_dir)
        for problem in problems:
            print("check: " + problem, file=sys.stderr)
        if not problems:
            print("check: shared memory is installed, current and adapted")
        return 1 if problems else 0

    plan = Plan(repo)
    try:
        plan_tool_files(plan, tests_dir, args.update)
        if not args.update:
            plan_project_skill(plan, args.decision_ref, args.decision_records)
            plan_claude_link(plan)
            plan_claude_hook(plan)
            plan_gemini_setting(plan)
            plan_gitignore(plan)
    except Refusal as refusal:
        print(f"install: {refusal}", file=sys.stderr)
        return refusal.code

    # Nothing may be written through a symlink: not the file, not a folder above it.
    # A new link may only be made in real folders.
    for kind, _, rel, _, _ in plan.ops:
        found = symlink_in(repo, rel, include_leaf=(kind == "write"))
        if found:
            print(f"install: {found} is a symlink; the installer writes only into real folders and files",
                  file=sys.stderr)
            return 2

    prefix = "would " if args.dry_run else ""
    for line in plan.describe():
        print(prefix + line)
    if not plan.ops:
        print("install: nothing to change")
    elif not args.dry_run:
        plan.apply()
    return 0


if __name__ == "__main__":
    sys.exit(main())
