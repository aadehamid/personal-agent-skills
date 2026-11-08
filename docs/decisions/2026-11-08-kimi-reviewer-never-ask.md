# The Kimi reviewer runs with --auto (Never Ask)

Status: Decided  
Date: 2026-11-08

## Context

Running an independent review in `aadehamid/enterprise-people-graph` with the
`way-of-working` reviewer order blocked on Kimi's read-approval prompts; each
stop waited on the owner and the run then exceeded its wait. The owner asked:

> kimi is asking for approval. can we open it to give it auto approval next time

The words are also recorded in that repository's decision record EPG-DEC-0001
(amendment of 2026-11-08).

## Decision

The Kimi reviewer launches with `--auto` (Never Ask) in all three hosts
(`herdr-review.sh`, `hc-review.sh`, `rex-review.sh`). The hash in each
reviewer's label and agent name carries the mode, so a live `-y` reviewer can
never be reused by the updated script. The reviewer prompt in every host says:
approval prompts are answered automatically, do not stop to ask the owner, do
not use blocking question tools, and record whatever would have been asked as
an explicit `Open questions` section in the report. The `ce-code-review`
skill's no-blocking-prompts rule says the same (installed copy,
`~/.agents/skills/ce-code-review/SKILL.md`).

## Recorded words

From the owner's session message of 2026-11-08, quoted verbatim:

> Option one is okay.

Option one is the recommended answer to the mode-contract question the first
review round of the `--auto` change raised: Never Ask answers genuine
questions too, and the review continues with the question recorded in the
report instead of stalling. Judgement calls still reach the owner through the
PR body and the report's open-questions section, the way the
`way-of-working` flow already works.

## Consequences

- A review never stops on approval prompts; a genuinely blocked review fails
  closed with the answer-then-continue instruction, as it does today.
- Herdr's tail now treats a blocked outcome like Rex and hc do: no report and
  no skill-report fallback after a block, exit 1 (first review round finding
  #3 of PR #99).
- The hc readiness classifier rejects a choice list above the input line the
  way Rex does, so a setup dialog never receives the prompt (first review
  round, agent-native finding).
- The label hash carries the launch mode, so a pre-change reviewer is never
  reused (finding #4 of PR #99).
- The runner does not pin a Kimi version; flag semantics are verified against
  the installed Kimi.
