# Auditing an existing bundle

For when the question is "can I trust what is already here?" rather than "what is next?".

## Run the mechanical check first

`kb check <bundle>` gives structure: schema, links, reference reciprocity, stamps, index
coverage, log ordering. `kb coverage`, `kb dupes` and `kb quotes <page>` add backlog,
duplicate sources and quote fidelity. Quote fidelity on a sample of pages is a cheap first
fidelity signal before the manual sample below.

Report what it says precisely. It does not check whether claims are in their sources, and
a reader who takes "Clean" as "accurate" has been misled by the report rather than the
tool.

## Then sample for fidelity

Full re-review of a large bundle is rarely affordable; a sample gives an error *rate*,
which is usually the actual question.

- Take 3–5 pages per bundle, weighted toward pages written without a review gate.
- For each, gather the sources its frontmatter cites.
- Send page plus sources to an independent reviewer, report-only, asking specifically
  whether every claim traces to the cited sources.

Report the rate, not just the findings. "4 of 20 sampled pages carried an unsourced claim"
tells someone what to do; a list of four findings does not.

## What to look for by hand

- **Pages built on near-empty sources.** A page citing a 14-word source cannot be saying
  much that came from it. Check word counts of cited sources.
- **Confident mechanism claims.** These are where outside knowledge enters.
- **Absent hedges.** If a page states a research finding flatly, check the source for
  "likely", "suggests", or a scoping condition.
- **Reviewer attribution in the log.** A log with no reviewer named is a bundle whose
  fidelity has never been checked by anything but its author. That is worth reporting
  plainly, whatever the structural checks say.
