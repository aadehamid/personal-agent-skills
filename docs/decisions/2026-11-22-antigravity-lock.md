# Antigravity reviews are locked per run

Status: Decided  
Date: 2026-11-22

## Context

This is the agent's account. The project's assistant relayed the owner's choice on a decision card, "Turn it off
for reviews", about agy's `allowNonWorkspaceAccess`, the point that
[Antigravity is the first independent reviewer](2026-11-22-antigravity-first.md) left open. The link between
the card and that setting is the assistant's account: the agent never saw the card. Testing then showed that the setting alone is not enough:
a saved `command(cp)` allow rule copied an outside file into the workspace, outside the sandbox, with the
setting off, and its contents reached the model.

## Decision

The owner said "Ship it", answering the question in the answers file about shipping the Antigravity lock.

## Implementation choices

These are the agent's choices, not the owner's words.

- The lock is agy's `--settings` flag, which lasts one run. No saved agy or Gemini setting is changed, so agy
  as a working agent keeps its access, as [the reviewer file access record](2026-11-22-reviewer-file-access.md)
  decides for working agents.
- Commands, unsandboxed commands, MCP tools, file writes and URL reads are denied explicitly, because a saved
  allow rule wins over a setting.
- Skills and instruction files outside the clone cannot be read. The prompt says to load none. Two live runs on a
  repository without the skills passed with that line (way-of-working `SOURCES.md`, 1s).
- Web search stays open. No permission rule tried closes it. The prompt forbids it, which is an instruction
  and not a wall.

## Evidence

The test table is in way-of-working `SOURCES.md`, 1s.

## Alternatives considered

Turn the saved setting off: it leaves the `cp` route open and also limits agy as a working agent. Delete the
saved allow rules: that is the owner's edit, and a later rule would open the route again.

## Recorded words

From [the answers file](2026-11-22-antigravity-lock-answers.md), 18:02:52 UTC, received directly:

> Ship it

Earlier, relayed and not received directly:

> Turn it off for reviews
