# Make this repository public for a short time so CI can run

Status: Decided  
Date: 2026-11-22

## Context

This is the agent's account. Runs of GitHub Actions on this private repository
have hit a billing error since at least 2026-11-07 (run 42421360962): "recent
account payments have failed or your spending limit needs to be increased".
Successful runs fall in between. GitHub does not bill standard runners on
public repositories. On 2026-11-22 the owner described a usual way of handling
this, and asked for this switch.

The order of events, in UTC on 2026-11-22: the owner asked for the switch at
03:49:25. Claude made the switch on that request, and the repository read
PUBLIC at 03:50:47. The list of what becomes visible reached the owner in the
thread at about 03:51, after the switch. The owner replied "yes." at 03:52:02.

## Decision

The owner's practice is to make the repository public temporarily and switch
it back to private when done. On 2026-11-22 the owner asked Claude to record
this and make the switch, so as not to be the bottleneck when not watching,
and later replied "yes.".

At 03:55 the owner added that it is okay to flip a private repo public to be
able to run CI without billing issues, and to flip it back to private once a
session is complete, and asked for this as a project instruction.

## Implementation choices

These are the agent's choices, not the owner's words. This record governs
this repository. Before the switch, Claude searched for content that relies on the
repository being private, as `way-of-working` `references/changing.md` asks.
That rule also asks to tell the owner before the change. This time the list
reached the owner only after the switch (see Context). Before a future switch,
Claude posts the list in the thread before switching, without waiting for an
answer. Claude does not switch, and asks the owner, if the search finds a
credential or a record that requires the repository to stay private. While
public, Claude re-runs the blocked CI runs, and switches back to private once the open pull request for this record and its
CI have finished. Claude reads the visibility back after each change.

## Evidence

- Visibility: `gh repo view aadehamid/personal-agent-skills --json visibility`
  returned PRIVATE before the switch and PUBLIC at 2026-11-22 03:50:47 UTC.
- Exposure search, 2026-11-22: a pattern scan for common key formats over every
  branch and pull request ref (599 commits), and a narrower scan of pull
  request, issue and comment text. It found only dummy values in a test file.
  It was not a dedicated secret scanner, and old Actions logs, which also become
  public, were not scanned.
- What a public window shows: the notes about the private
  Engineering_Drawing_to_Graph repository (its name, pull request numbers,
  review lessons and IDs such as LIONG-003), `calibration.md`, which quotes past
  sessions, and the owner's email address in commit metadata.
- CI on `main` after the switch: run 44982381107, attempt 2, passed at
  2026-11-22 03:56:54 UTC.

## Alternatives considered

Fixing billing removes the need, and only the owner can do it. Waiting for the
owner each time makes the owner the bottleneck.

## Recorded words

From [the answers file](2026-11-22-temporary-public-for-ci-answers.md):

> the way i handle this I make the repo public temporarily and then switch back to private when I am done

> csn you record this decision and flip this. I dont want to be the bottle neck in case i am not baby sitting this

> yes.

> done. Also can you make a project instruction that it is okay to flip a private repo public to be able to run CI without billing issues. Once a session is complete that repo can be fliped back to private
