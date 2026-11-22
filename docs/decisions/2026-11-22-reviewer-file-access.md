# Reviewers read the repository and what they are handed

Status: Decided  
Date: 2026-11-22

## Context

This is the agent's account. On 2026-11-22 a Pi review of pull request 104 spent over 7 minutes in a `find` over
the owner's Documents, Desktop, Downloads and Dropbox project folders, looking for evidence the review request
said was missing. The agent stopped it before Pi received the file names. The same review, told to stay inside
its clone, took 57 seconds. The owner then asked what happens when Pi needs a file from outside the repository,
and whether the rule should apply to all agents.

## Decision

The owner said, at 13:50:45 UTC:

> Working agents should have access to files and folders outside if the repo

The owner said, at 13:51:20 UTC:

> Yes

That "Yes" accepted the agent's recommendation of 13:50:50. These are the agent's words, quoted in full with bold
and code markers removed:

> Agreed. Working agents keep their access to files and folders outside the repo, with no new rule and no need to ask you first. I've dropped that half of the proposal.
>
> That leaves reviewers only. Pi, Kimi, Codex and Cursor CLI would read the repo, their skill and scratch files, and whatever the working agent attaches with --attach. The working agent can attach a file from anywhere, so a reviewer can still get an outside file when it needs one.
>
> Shall I build that reviewers-only version after Antigravity ships? A "yes" is enough.

## Implementation choices

These are the agent's choices, not the owner's words.

- Antigravity is covered too. The question named four reviewers because `agy-review.sh` had not merged yet. It
  merged in pull request 105 before this change started. The agent told the owner at 13:51:47 that it would
  include it, as the answers file records.
- One helper, `review-evidence.sh`, does the copying. The two sentences of the rule are repeated in the five
  scripts, with a test that fails when they differ, because sourcing a shared library broke tests when it was
  tried (issue 85).
- A folder holding a link or a special file is refused, so a copy cannot lead back out to what nobody attached.
- Evidence is removed when the script knows the review ended. Where a reviewer may still be running, it is kept
  and its path printed.
- In Rex, an earlier run's report does not stand in for a run that has attached evidence.
- (Note, 2026-11-22: [Antigravity reviews are locked per run](2026-11-22-antigravity-lock.md) proposes to enforce
  part of it for Antigravity: not web search. For the other reviewers the next point still holds.)
- The rule is an instruction. No sandbox enforces it, and agy's `allowNonWorkspaceAccess` setting stays the
  owner's open question ([the Antigravity record](2026-11-22-antigravity-first.md)).
- The Codex plugin path has no script, so the working agent puts the rule in that request itself.

## Evidence

The stall and the rerun are in the thread of pull request 104 and in way-of-working `SOURCES.md`, 1r.

## Alternatives considered

- Keep reviewers inside the clone with no way to attach a file. The owner's first question showed the gap.
- Limit working agents too. The agent proposed it at 13:49:10, and the owner answered at 13:50:45 that working
  agents should have access outside the repo.
- Enforce the rule with an operating-system sandbox. It is a larger change, left until a reviewer strays again.

## Recorded words

From [the answers file](2026-11-22-reviewer-file-access-answers.md), 13:50:45 and 13:51:20 UTC:

> Working agents should have access to files and folders outside if the repo

> Yes
