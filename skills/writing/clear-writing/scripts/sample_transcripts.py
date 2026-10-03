#!/usr/bin/env python3
"""Sample recent Claude Code sessions and print the user prompts and assistant prose.

Tool calls, tool results, thinking, and subagent (sidechain) turns are skipped,
so the output contains only what the user typed and the text Claude showed them.

Usage:
  python sample_transcripts.py [--days 7] [--n 10] [--max-chars 4000] [--seed 0]
  python sample_transcripts.py --exclude-current SESSION_ID
"""
import argparse
import glob
import json
import os
import random
import time

ROOT = os.path.expanduser("~/.claude/projects")


def text_of(content):
    if isinstance(content, str):
        return content
    parts = []
    for block in content or []:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "\n".join(parts)


def turns(path):
    out = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("isSidechain") or rec.get("isMeta") or rec.get("type") not in ("user", "assistant"):
                continue
            msg = rec.get("message") or {}
            content = msg.get("content")
            # User records that only carry tool results are not human prompts.
            if rec["type"] == "user" and isinstance(content, list) and all(
                isinstance(b, dict) and b.get("type") == "tool_result" for b in content
            ):
                continue
            txt = text_of(content).strip()
            if not txt or txt.startswith(("<command-", "<local-command-", "<system-reminder>", "Base directory for this skill")):
                continue
            role = "USER" if rec["type"] == "user" else "CLAUDE"
            # Consecutive assistant text blocks belong to one reply.
            if out and out[-1][0] == role == "CLAUDE":
                out[-1] = (role, out[-1][1] + "\n\n" + txt)
            else:
                out.append((role, txt))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=float, default=7)
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--max-chars", type=int, default=4000, help="per session")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--exclude-current", default=None, help="session id to skip")
    a = ap.parse_args()

    cutoff = time.time() - a.days * 86400
    files = [f for f in glob.glob(os.path.join(ROOT, "*", "*.jsonl")) if os.path.getmtime(f) >= cutoff]
    # A file written in the last two minutes is almost always the live session.
    files = [f for f in files if time.time() - os.path.getmtime(f) > 120]
    if a.exclude_current:
        files = [f for f in files if a.exclude_current not in os.path.basename(f)]
    # Keep only interactive sessions that have at least one Claude reply.
    sessions = []
    for f in files:
        t = turns(f)
        if any(r == "CLAUDE" for r, _ in t):
            sessions.append((f, t))
    rng = random.Random(a.seed)
    picked = rng.sample(sessions, min(a.n, len(sessions)))

    print(f"# {len(picked)} of {len(sessions)} sessions from the last {a.days:g} days\n")
    for f, t in picked:
        project = os.path.basename(os.path.dirname(f))
        print(f"## Session {os.path.basename(f)[:8]} ({project})\n")
        budget = a.max_chars
        for role, txt in t:
            if budget <= 0:
                print("[... truncated]\n")
                break
            chunk = txt[:budget]
            budget -= len(chunk)
            print(f"**{role}:** {chunk}\n")


if __name__ == "__main__":
    main()
