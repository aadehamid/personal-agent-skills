# Documents

Read this when writing or restructuring a project's documents.

## One place per meaning

- Each rule, status or figure has one authoritative place; other documents point to it. Two wordings drift apart, and the drift becomes a review round.
- Instruction files (`AGENTS.md`, `CLAUDE.md`) load into every turn, so they hold pointers and the few rules an agent needs before acting. Move detail into docs and checks, and shrink the instruction file once a check enforces a rule.

## Method and record are separate

- A **method** (playbook, standard) says how to do the work, company-neutral, and changes only when the method improves.
- A **record** (worklog, decision records, backlog) says what happened on this project.
- Project decisions go in the record; the method may cite them as worked examples.

## Moving approved text

When approved text moves between files, move it word for word with a note naming its origin. Rewording approved text needs the owner's recorded decision.

## Handover notes

A handover brief outside the repo goes stale the moment work starts. When it is used, add a note at its top saying when, by which session, and where the outputs live; the repo is ground truth.

## Done when

Every rule you touched has one authoritative wording, every other mention points to it, and the instruction file holds pointers rather than detail.

## Read only the evidence needed

For skill discovery, search for `SKILL.md` in the installed skill roots first.
Exclude virtual environments, dependency directories, and caches from content
searches. Expand to plugin caches only when an installed dependency is missing.

For GitHub review, select the fields needed for the current decision with
`gh api --jq`. Include the reviewed commit, creation time, state, and relevant
body text. Omit decorative HTML footers and read older rounds only when a
current finding depends on them. Bound output before returning it to context;
large transcripts belong in files, with the evidence summarized for the reader.
