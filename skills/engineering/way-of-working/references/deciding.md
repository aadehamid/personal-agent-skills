# Deciding

Read this before recording a decision or running a decision interview.

## Interview with docs

For a plan or design with open questions, run the grill-with-docs interview (the owner types `/grill-with-docs`; it is hidden from model invocation). Ask in rounds: every question whose prerequisites are settled, numbered, each with a recommended answer. Facts are the agent's job: look them up, do not ask the owner. Decisions are the owner's.

## Decision records

- One record per decision, in the project's decision folder, with: context, decision, alternatives considered, the owner's recorded words (quoted), evidence, status (Proposed / Decided / Superseded) and date.
- The index of records and each record's status agree. A check script enforces this where the project has one.
- A decision the agent inferred from a request, rather than one the owner stated, is **Proposed** until the owner confirms it in words.
- Amend, don't rewrite: a later decision that changes an earlier one names it ("amended by NNNN"), and the earlier record gets a dated note.

## Conventions to confirm per owner

Ask once and record in memory: whether a skipped question means agreement, and which interview skill to use. Never assume either.

## Done when

The record exists, quotes the owner's words, matches its index entry, and any record it amends carries a dated note pointing to it.
