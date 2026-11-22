# Make the check and review flow faster with no drop in quality

Status: Decided  
Date: 2026-11-22

## Context

This is the agent's account. The owner asked where the time went on pull requests #101 and #102, and the
agent suggested four fixes.

## Decision

The owner asked for the four suggested fixes to be worked, and said that done is when the pull request flow
is optimized, with a substantial reduction on code review and without a single drop in quality, and that
quality is the most important thing.

## Implementation choices

These are the agent's choices, made under that request. They are not the owner's words.

- Suggestions 1 and 2 became one change. The tests already stubbed their sleeps, so a poll-interval setting
  would save nothing. The ten script suites run in parallel instead, with a guard that fails a file with no
  tests, as the old runner did.
- Suggestion 3 applies to Pi only, which reviews in its own clone. With Kimi, Codex and the Cursor agent CLI,
  which share the working tree, the check runs first. Pi is told not to repeat the whole check, and may run
  any test it needs.
- Suggestion 4 is not done. The setting is the owner's to change, and GitHub refuses branch protection on this
  repository while it is private, as it normally is (see the two readings under Evidence).

## Evidence

Wall times the working agent measured around each script run on the owner's Mac, 2026-11-22 (UTC):

| Commit reviewed | check.sh | Pi review | Pi reran the check | How they ran |
|---|---|---|---|---|
| e2d58ce (the change of #101) | 380 s | 433 s | yes | one after the other |
| e7d9ccd (#102, round 1) | 360 s | 112 s | no | one after the other |
| 44acd09 (#102, round 2) | 349 s | 81 s | no | side by side |
| 94f21c0 (#102, the fix for its hold) | 379 s | 442 s | yes | side by side |
| d4aec1e (this change, round 1) | 99 s | 168 s | no | side by side |

The commits are the local ones the agent tested, some of which were rebuilt from patches and never pushed.

Branch protection, read twice with `gh api repos/aadehamid/personal-agent-skills/branches/main/protection`:

- 2026-11-22 04:39 UTC, repository private: HTTP 403, "Upgrade to GitHub Pro or make this repository public to
  enable this feature."
- 2026-11-22 05:28 UTC, repository public for this pull request's CI: HTTP 404, "Branch not protected". The
  refusal was gone and no protection was set. The agent did not try to set any.

## Alternatives considered

Cutting or skipping tests for documentation-only changes would be faster still. It lowers coverage, so it was
not taken.

## Recorded words

From [the answers file](2026-11-22-faster-checks-answers.md):

> let us work the suggestion s below.

> work the plan. Done is when  PR flow is optimized and we have substantinal reduction on code review without a single drop in quality. Quality is the most important thing.

The first quote is the opening sentence of its message. The answers file holds both messages in full.
