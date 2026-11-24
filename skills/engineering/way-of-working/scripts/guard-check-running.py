#!/usr/bin/env python3
"""Claude Code PreToolUse hook: refuse an edit inside a repository whose scripts/check.sh is running.

A check reads the tree it checks. An edit made while it runs either fails it ("the checks changed the working
tree") or passes a check that never saw the edit, so the run has to be thrown away. A written rule did not stop
it (SOURCES.md, 1t).

Wire it in ~/.claude/settings.json (guardrails.md, "One check script, run everywhere"):

  "PreToolUse": [{"matcher": "Edit|Write|MultiEdit|NotebookEdit",
                  "hooks": [{"type": "command",
                             "command": "python3 ~/.agents/skills/way-of-working/scripts/guard-check-running.py"}]}]

How it finds a running check: a shell that runs a script keeps the script file open for the whole run, so a check
is a shell (bash, sh, zsh, dash) holding a file open whose path ends in scripts/check.sh. Its repository is the
folder above that scripts folder. This does not depend on how the check was started (flags, a relative or
absolute path, spaces, exec from a hook) or on where the check has changed directory to.

An Edit, Write, MultiEdit or NotebookEdit whose file is inside such a repository is refused with exit 2; the
message goes to the agent. Inside is decided by file identity, not by comparing path text, so letter case on a
case-insensitive disk, /var and /private/var, and a symlink in either direction are all handled. Every other
case exits 0, including input it cannot read and any error of its own: the guard never blocks work it cannot
show to be unsafe. It does not see edits made through the shell (sed -i, a redirect, git commit).

With --list it prints each running check as "<pid> <repository>" and changes nothing: run it before a shell edit.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
SHELLS = ("bash", "sh", "zsh", "dash")
CHECK = os.path.join("scripts", "check.sh")


def is_check(path: str) -> bool:
    return path.endswith(os.sep + CHECK)


def is_shell(name: str) -> bool:
    return os.path.basename(name).lstrip("-") in SHELLS


def open_checks() -> list[tuple[str, str]]:
    """(pid, path) for each shell holding a scripts/check.sh open. Raises OSError when it cannot look."""
    found = []
    if os.path.isdir("/proc/self/fd"):
        for pid in filter(str.isdigit, os.listdir("/proc")):
            try:
                # A script run straight from its shebang is named after the script in comm; exe is the shell.
                with open(f"/proc/{pid}/comm", errors="replace") as f:
                    comm = f.read().strip()
                if not (is_shell(comm) or is_shell(os.readlink(f"/proc/{pid}/exe"))):
                    continue
                fds = os.listdir(f"/proc/{pid}/fd")
            except OSError:
                continue
            for fd in fds:
                try:
                    path = os.readlink(f"/proc/{pid}/fd/{fd}")
                except OSError:
                    continue
                if is_check(path):
                    found.append((pid, path))
        return found
    # -c matches a name's prefix, so the command field is checked exactly below. -n and -P skip the host and port
    # lookups of sockets, which can stall on a slow network.
    args = ["lsof", "-w", "-n", "-P", "-Fpcn"] + [x for shell in SHELLS for x in ("-c", shell)]
    try:
        run = subprocess.run(args, capture_output=True, text=True, timeout=10)
    except subprocess.SubprocessError as error:
        raise OSError(f"lsof did not answer: {error}") from error
    # lsof exits 1 both when no process matched and on an error; only an error writes to stderr (-w silences
    # warnings).
    if run.returncode not in (0, 1) or (run.returncode == 1 and run.stderr.strip()):
        raise OSError(f"lsof exited {run.returncode}: {run.stderr.strip() or 'no message'}")
    pid, shell = "", False
    for line in run.stdout.splitlines():
        if line.startswith("p"):
            pid, shell = line[1:], False
        elif line.startswith("c"):
            shell = is_shell(line[1:])
        elif line.startswith("n") and shell and is_check(line[1:]):
            found.append((pid, line[1:]))
    return found


def folders_of(target: str):
    """Every existing folder that holds target, read through its written path and through its real path."""
    # The written path is walked after normpath, which drops "a/.." by text; the real path is resolved from the raw
    # path, so a "link/.." reaches the folder the system would write to.
    for path in (os.path.normpath(target), os.path.realpath(target)):
        folder = path
        while True:
            parent = os.path.dirname(folder)
            if parent == folder:
                break
            folder = parent
            try:
                yield os.stat(folder)
            except OSError:
                continue


def refusal(event) -> str | None:
    if not isinstance(event, dict) or event.get("tool_name") not in TOOLS:
        return None
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    target = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not isinstance(target, str) or not target:
        return None
    if not os.path.isabs(target):
        base = event.get("cwd")
        if not isinstance(base, str) or not os.path.isabs(base):
            return None
        target = os.path.join(base, target)
    checks = []
    for pid, path in open_checks():
        root = os.path.dirname(os.path.dirname(path))
        try:
            st = os.stat(root)
        except OSError:
            continue
        checks.append((pid, root, (st.st_dev, st.st_ino)))
    if not checks:
        return None
    holders = {(st.st_dev, st.st_ino) for st in folders_of(target)}
    for pid, root, key in checks:
        if key in holders:
            return (f"Refused: scripts/check.sh is running in {root} (process {pid}). An edit there now breaks that "
                    f"check or makes its result meaningless. Wait for it to finish, or stop it and run it again "
                    f"after the edit.")
    return None


def main() -> int:
    if sys.argv[1:] == ["--list"]:
        try:
            checks = open_checks()
        except OSError as error:
            print(f"cannot list running checks: {error}", file=sys.stderr)
            return 1
        for pid, path in checks:
            print(pid, os.path.dirname(os.path.dirname(path)))
        return 0
    try:
        message = refusal(json.load(sys.stdin))
    except Exception:                    # the guard must never block work because of its own failure
        return 0
    if message:
        print(message, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
