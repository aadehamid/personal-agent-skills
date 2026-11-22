# Antigravity is the first independent reviewer

Status: Decided  
Date: 2026-11-22

## Context

This is the agent's account. enterprise-performance-model put Antigravity first in its own order on 2026-11-18
(EPM-DEC-001-0028, amendment of that date). This skill did not have it. On 2026-11-22 a planted-bug test compared
it with Pi, and found why it sometimes returned no review with exit 0 (way-of-working `SOURCES.md`, 1q).

## Decision

The owner said to ship Antigravity first.

## Implementation choices

These are the agent's choices, not the owner's words.

- Reading "first" as both rows of "Who reviews" is the agent's: the question named no row. The model is
  gemini-4-neon-xhigh, which the question and the relayed word "Xhigh" name.
- Kimi, Pi and Codex keep their order after it. The owner's first message named Pi alone ("Instead of PI"), and
  did not say whether Pi leaves the order.
- A review counts only when agy exits 0 and the first line is exactly READY or FIX.
- It reviews in a throwaway clone, may read files there, and runs no commands. The check runs beside it, as with
  Pi. The author runs any test a finding needs.
- Not decided by this record: agy's `allowNonWorkspaceAccess` setting, which lets it read outside the clone. The
  owner had that question open when this was written, and nothing here changes the setting.
  Amended 2026-11-22 by [Antigravity reviews are locked per run](2026-11-22-antigravity-lock.md), which closed that
  question: each review run through `agy-review.sh` passes `--settings` with outside access off, and the saved
  setting stays unchanged.

## Evidence

The run table, the sealed answer key's hash and the log lines are in way-of-working `SOURCES.md`, 1q.

A cost the agent found after the owner's relayed choice, and put to the owner before the reply:
the runner took 375 and 506 seconds live, where Pi's reviews took 81 to 268 seconds when they did not rerun the check. A review round gets longer.

## Alternatives considered

Keep the order as it was, which does not answer the owner's request. Use the prompt that
forbids all tools: it caught the contradiction with an unchanged file only in part, in each of four runs.

## Recorded words

From [the answers file](2026-11-22-antigravity-first-answers.md), 13:43:05 UTC, received directly:

> My email is now private.
> Ship antigravity FIRST

The file also holds the question this answered, in full, and the earlier words with how each reached the agent.
