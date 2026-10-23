<!-- Copy this file when you record one decision. Rules: references/governance.md, "Decisions" and "Delegation"; where the way-of-working skill is installed, its references/deciding.md is the home of the record rules this template carries. Delete every comment before you commit. -->

# <PREFIX>-<NNNN>: <the decision, as one sentence>

<!-- Example title: "LIB-0007: A loan is a class with a borrower, a copy and a due date" -->

| Field | Value |
|---|---|
| Status | <Proposed / Decided (the owner, YYYY-MM-DD) / Decided (delegated under <PREFIX>-<NNNN>) / Superseded by <PREFIX>-<NNNN>> |
| Date | <YYYY-MM-DD; add the decided date if it differs from the proposed date> |
| Source | <the session or comment where the owner answered; the answers file's path> |

<!-- While the owner has not answered, or answered "not yet": Status is "Proposed. ASSUMED, not yet answered (Q<n>)", the Decision section says "Not decided", and Consequences lists the work done on the assumption and how to undo it (governance.md, rule 3). -->

## Question

<The question as asked, in full, and the recommendation that came with it, quoted. Markdown stripped from the quotes, and this line says so.>

## Context

<What was open and why it mattered now, with the evidence each statement rests on. The agent's words.>

## Decision

**The owner's decision:** <When the owner accepted the recommendation: that recommendation, quoted, plus the text of the option it chose. When the owner answered in their own words: only those words. Nothing else.>

<!-- Under a delegation, write "None for this choice; delegated under <record>." in place of the line above. -->

**What follows (the agent, <carrying out that decision / under <PREFIX>-<NNNN>>):**

1. <Each consequence the agent adds: names, rules, files to change. Say which record any item rests on.>

<!-- A detail the owner did not address is "not decided"; do not carry it over from the question. -->

## Alternatives considered

- **<Option>.** Not chosen: <the reason, from the owner's words or the evidence>.

## The owner's recorded words

Saved in `<path to the answers file>`: "<verbatim quote>".

<!-- The check script compares each quoted span here with the answers file, and each quoted recommendation in the Decision section with the same quote here. Under a delegation, quote the delegation's own words and say "The owner can reverse any item." -->

## Evidence

- <Source, with its tier (foundations.md, policy 3), item or line, and date. Figures quote the command and commit that computed them.>

## Consequences

- <What changes for later work, which records or documents now point here, and what each open item waits on and whom (governance.md, rule 14). An earlier record this one amends gets a dated note pointing here.>
