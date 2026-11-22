# Antigravity is the first independent reviewer

Status: Proposed
Date: 2026-11-22

## Context

This is the agent's account. enterprise-performance-model put Antigravity first in its own order on 2026-11-18
(EPM-DEC-001-0028, amendment of that date). This skill did not have it. On 2026-11-22 a planted-bug test compared
it with Pi, and found why it sometimes returned no review with exit 0 (way-of-working `SOURCES.md`, 1q).

## Decision

Proposed: Antigravity on gemini-4-neon-xhigh is tried first in both rows of "Who reviews".

## Implementation choices

These are the agent's choices, not the owner's words.

- Kimi, Pi and Codex keep their order after it. The owner's first message named Pi alone ("Instead of PI"), and
  did not say whether Pi leaves the order.
- A review counts only when agy exits 0 and the first line is exactly READY or FIX.
- It reviews in a throwaway clone, may read files there, and runs no commands. The check runs beside it, as with
  Pi. The author runs any test a finding needs.
- Not decided: agy's `allowNonWorkspaceAccess` setting, which lets it read outside the clone. The owner has that
  question open, and nothing here changes the setting.

## Evidence

The run table, the sealed answer key's hash and the log lines are in way-of-working `SOURCES.md`, 1q.

## Alternatives considered

Keep the order as it was, which does not answer the owner's request. Use the prompt that
forbids all tools: it caught the contradiction with an unchanged file only in part, in each of four runs.

## Recorded words

In [the answers file](2026-11-22-antigravity-first-answers.md), with how each reached the agent.
