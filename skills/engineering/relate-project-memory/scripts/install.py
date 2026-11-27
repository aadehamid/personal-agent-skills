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
                 the .gitignore lines. The installer creates each one once and
                 never overwrites it, because the project adapts them.

--check exits 1 if a tool-owned file is missing or differs from the skill's
template, if the project skill still holds an ADAPT marker or a {{placeholder}},
or if AGENTS.md does not mention scripts/memory.sh.
"""
import argparse
import json
import os
import re
import sys

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


def tool_files(tests_dir):
    return [
        ("memory.sh", "scripts/memory.sh", 0o755),
        ("memory/schema.cypher", "scripts/memory/schema.cypher", 0o644),
        ("memory/remember.cypher", "scripts/memory/remember.cypher", 0o644),
        ("test_memory.py", os.path.join(tests_dir, "test_memory.py"), 0o644),
    ]


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class Plan:
    def __init__(self, repo, dry_run):
        self.repo = repo
        self.dry_run = dry_run
        self.actions = []

    def path(self, rel):
        return os.path.join(self.repo, rel)

    def write(self, rel, text, mode=0o644, verb="write"):
        self.actions.append(f"{verb} {rel}")
        if self.dry_run:
            return
        os.makedirs(os.path.dirname(self.path(rel)), exist_ok=True)
        with open(self.path(rel), "w", encoding="utf-8") as fh:
            fh.write(text)
        os.chmod(self.path(rel), mode)

    def link(self, rel, target):
        self.actions.append(f"link {rel} -> {target}")
        if self.dry_run:
            return
        os.makedirs(os.path.dirname(self.path(rel)), exist_ok=True)
        os.symlink(target, self.path(rel))


def install_tool_files(plan, tests_dir, update):
    clashes = []
    for template, rel, mode in tool_files(tests_dir):
        text = read(os.path.join(TEMPLATES, template))
        target = plan.path(rel)
        if os.path.exists(target):
            same = read(target) == text and (os.stat(target).st_mode & 0o777) == mode
            if same:
                continue
            if not update:
                clashes.append(rel)
                continue
            plan.write(rel, text, mode, verb="replace")
        else:
            plan.write(rel, text, mode)
    return clashes


def install_project_skill(plan, decision_ref, decision_records):
    if os.path.lexists(plan.path(PROJECT_SKILL)):
        return None
    if not (decision_ref and decision_records):
        return "creating the project skill needs --decision-ref and --decision-records"
    text = read(os.path.join(TEMPLATES, "project-memory-SKILL.md"))
    text = text.replace("{{DECISION_REF}}", decision_ref).replace("{{DECISION_RECORDS}}", decision_records)
    plan.write(PROJECT_SKILL, text)
    return None


def install_claude_link(plan):
    if not os.path.lexists(plan.path(CLAUDE_LINK)):
        plan.link(CLAUDE_LINK, LINK_TARGET)


def load_json(plan, rel):
    if not os.path.exists(plan.path(rel)):
        return {}
    with open(plan.path(rel), encoding="utf-8") as fh:
        return json.load(fh)


def install_claude_hook(plan):
    rel = ".claude/settings.json"
    settings = load_json(plan, rel)
    groups = settings.setdefault("hooks", {}).setdefault("SessionStart", [])
    commands = [h.get("command", "") for g in groups for h in g.get("hooks", [])]
    if any(HOOK_MARK in c for c in commands):
        return
    groups.append({"hooks": [{"type": "command", "command": HOOK_COMMAND}]})
    plan.write(rel, json.dumps(settings, indent=2) + "\n", verb="update")


def install_gemini_setting(plan):
    rel = ".gemini/settings.json"
    settings = load_json(plan, rel)
    context = settings.setdefault("context", {})
    names = context.get("fileName", [])
    names = [names] if isinstance(names, str) else list(names)
    if "AGENTS.md" in names:
        return
    if not names and not os.path.exists(plan.path("GEMINI.md")):
        names = ["AGENTS.md"]
    else:
        # Keep the project's own context file and add AGENTS.md beside it.
        names = (names or ["GEMINI.md"]) + ["AGENTS.md"]
    context["fileName"] = names
    plan.write(rel, json.dumps(settings, indent=2) + "\n", verb="update")


def install_gitignore(plan):
    rel = ".gitignore"
    text = read(plan.path(rel)) if os.path.exists(plan.path(rel)) else ""
    present = {line.strip() for line in text.splitlines()}
    missing = [line for line in GITIGNORE_LINES if line not in present]
    if not missing:
        return
    block = ("\n" if text and not text.endswith("\n") else "") + ("\n" if text else "")
    block += GITIGNORE_HEADER + "\n" + "\n".join(missing) + "\n"
    plan.write(rel, text + block, verb="update")


def check(repo, tests_dir):
    problems = []
    for template, rel, mode in tool_files(tests_dir):
        target = os.path.join(repo, rel)
        if not os.path.exists(target):
            problems.append(f"{rel}: missing; run install.py")
        elif read(target) != read(os.path.join(TEMPLATES, template)):
            problems.append(f"{rel}: differs from the skill's template; run install.py --update")
        elif (os.stat(target).st_mode & 0o777) != mode:
            problems.append(f"{rel}: mode is {oct(os.stat(target).st_mode & 0o777)}, expected {oct(mode)}")
    skill = os.path.join(repo, PROJECT_SKILL)
    if not os.path.exists(skill):
        problems.append(f"{PROJECT_SKILL}: missing")
    else:
        text = read(skill)
        if "<!-- ADAPT" in text:
            problems.append(f"{PROJECT_SKILL}: still holds an ADAPT marker")
        if re.search(r"\{\{[A-Z_]+\}\}", text):
            problems.append(f"{PROJECT_SKILL}: still holds a {{{{placeholder}}}}")
    link = os.path.join(repo, CLAUDE_LINK)
    if not (os.path.islink(link) and os.path.realpath(link) == os.path.realpath(skill)):
        problems.append(f"{CLAUDE_LINK}: not a link to {PROJECT_SKILL}")
    agents = os.path.join(repo, "AGENTS.md")
    if not (os.path.exists(agents) and "scripts/memory.sh" in read(agents)):
        problems.append("AGENTS.md: does not mention scripts/memory.sh")
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
    if not os.path.isdir(os.path.join(repo, ".git")) and not os.path.isfile(os.path.join(repo, ".git")):
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

    plan = Plan(repo, args.dry_run)
    clashes = install_tool_files(plan, tests_dir, args.update)
    if clashes:
        print("install: these files differ from the skill's version; rerun with --update to replace them:",
              file=sys.stderr)
        for rel in clashes:
            print("  " + rel, file=sys.stderr)
        return 1
    error = install_project_skill(plan, args.decision_ref, args.decision_records)
    if error:
        print("install: " + error, file=sys.stderr)
        return 2
    install_claude_link(plan)
    install_claude_hook(plan)
    install_gemini_setting(plan)
    install_gitignore(plan)

    prefix = "would " if args.dry_run else ""
    for action in plan.actions:
        print(prefix + action)
    if not plan.actions:
        print("install: nothing to change")
    return 0


if __name__ == "__main__":
    sys.exit(main())
