#!/usr/bin/env python3
"""Claude Code PreToolUse hook: refuse an edit inside a folder whose scripts/check.sh is running.

A check reads the tree it checks. An edit made while it runs either breaks the run ("the checks changed the
working tree") or passes a check that never saw the edited file, so the run has to be thrown away. A written
rule did not stop it: an agent made such an edit five times in one run (the KPI Store 1.2 night run, retro of
2026-11-24).

Wire it in ~/.claude/settings.json (guardrails.md, "One check script, run everywhere"):

  "PreToolUse": [{"matcher": "Edit|Write|MultiEdit|NotebookEdit",
                  "hooks": [{"type": "command",
                             "command": "python3 ~/.agents/skills/way-of-working/scripts/guard-check-running.py"}]}]

It reads the hook's JSON on standard input and looks at tool_input.file_path (or notebook_path). A check is a
running shell whose command runs scripts/check.sh; its folder is that process's working directory, because a
check script changes to its repository's top level first. Exit 2 blocks the edit and the message goes to the
agent. Any other case, including input it cannot read, exits 0: the guard never blocks work it cannot prove
unsafe. It does not see edits made through the shell (sed -i, a redirect): wait for the check before those too.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

SHELLS = {"bash", "sh", "zsh", "dash"}
CHECK = re.compile(r"(^|/)scripts/check\.sh$")


def runs_check(command: str) -> bool:
    words = command.split()
    if not words:
        return False
    if CHECK.search(words[0]):
        return True
    return os.path.basename(words[0]).lstrip("-") in SHELLS and any(CHECK.search(w) for w in words[1:3])


def cwd_of(pid: str) -> str | None:
    try:
        return os.readlink(f"/proc/{pid}/cwd")
    except OSError:
        pass
    try:
        out = subprocess.run(["lsof", "-a", "-p", pid, "-d", "cwd", "-Fn"], capture_output=True, text=True,
                             timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.splitlines():
        if line.startswith("n/"):
            return line[1:]
    return None


def running_checks() -> list[tuple[str, str]]:
    try:
        out = subprocess.run(["ps", "-axo", "pid=,command="], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    found = []
    for line in out.splitlines():
        pid, _, command = line.strip().partition(" ")
        if pid.isdigit() and int(pid) != os.getpid() and runs_check(command.strip()):
            root = cwd_of(pid)
            if root:
                found.append((pid, os.path.realpath(root)))
    return found


def main() -> int:
    try:
        event = json.load(sys.stdin)
        tool_input = event.get("tool_input") or {}
        target = tool_input.get("file_path") or tool_input.get("notebook_path")
    except (ValueError, AttributeError):
        return 0
    if not isinstance(target, str) or not target:
        return 0
    if not os.path.isabs(target):
        target = os.path.join(event.get("cwd") or os.getcwd(), target)
    target = os.path.realpath(target)
    for pid, root in running_checks():
        if target == root or target.startswith(root.rstrip("/") + "/"):
            print(f"Refused: scripts/check.sh is running in {root} (process {pid}). An edit there now breaks "
                  f"that check or makes its result meaningless. Wait for it to finish, or stop it and run it "
                  f"again after the edit.", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
