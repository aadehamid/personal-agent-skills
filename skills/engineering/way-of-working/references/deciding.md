# Deciding

Read this before recording a decision or running a decision interview.

## Interview with docs

For a plan or design with open questions, run the grill-with-docs interview (the owner types `/grill-with-docs`; it is hidden from model invocation). Ask in rounds: every question whose prerequisites are settled, numbered, each with a recommended answer. Facts are the agent's job: look them up, do not ask the owner. Decisions are the owner's.

## Decision records

- One record per decision, in the project's decision folder, with: context, decision, alternatives considered, the owner's recorded words (quoted), evidence, status (Proposed / Decided / Superseded) and date.
- The index of records and each record's status agree. A check script enforces this where the project has one.
- A decision the agent inferred from a request, rather than one the owner stated, is **Proposed** until the owner confirms it in words.
- Amend, don't rewrite: a later decision that changes an earlier one names it ("amended by NNNN"), and the earlier record gets a dated note.

## Writing a record

A record's Decision section says only what the owner said. A sentence an agent adds there becomes a claim the owner never made, and reviewers will find it.

- **Quote the question in full,** and the recommendation that came with it. Strip Markdown from the quotes, and say so, rather than shortening them.
- **When the owner accepted a recommendation,** the Decision section quotes that recommendation, plus the text of the option it chose. Nothing else goes there.
- **When the owner answered in their own words,** the Decision restates only those words.
- **Anything the agent adds** (background, an interpretation, a plan for a later change) goes in Context or Evidence, written as the agent's, never as the owner's.
- **A detail the owner did not address stays open.** Say "not decided" rather than carry it over from the question.

Where the project's check script reads decision records, have it compare each quoted recommendation in the Decision section with the same quote under the owner's words, character for character. That catches a paraphrase mechanically.

## When a decision lands

Search every earlier record and project document for what the new decision settles: statements that call it open, undecided, proposed, deferred to a later round or planned for a later change. Update each in the same pull request, pointing to the new record. An approved record left saying "still open" stays in force beside the decision that closed it.

## Conventions to confirm per owner

Ask once and record in memory: whether a skipped question means agreement, and which interview skill to use. Never assume either.

## Done when

The record exists, quotes the owner's words, says nothing the owner did not, matches its index entry, and any record it amends carries a dated note pointing to it. No earlier record still calls the decided question open.
