# Sources

What the way-of-working skill was built from. Agents do not read this file.

Last review: 2026-10-07.

## 1. The enterprise-performance-model ontology build (2026-10-05 and 06)

- **Link:** https://github.com/aadehamid/enterprise-performance-model, PRs #199 to #221 (merged) and #222 (open when this was written).
- **What we took:** every rule, from the review rounds that taught it. Examples: the decision-record and attribution rules (#199, #212); claiming only what has landed (#216); counting from structure, not text search (#208, #216); primary sources with full-support versions (enterprise-people-graph #1); a rule change reaching every dependent section (enterprise-people-graph #1, #216); the shared tool and check script (#217 to #221); review standards holding only judgement rules (#222, open when this was written).
- **What we left out:** everything specific to that project (its decisions, figures and file names), except as the worked example named in `README.md`.

## 2. mattpocock-skills (marketplace `mattpocock`, v1.3.1)

- **What we took:** the retro loop (`retro`), decision interviews (`grill-with-docs`, `grilling`), the rules for writing documents agents read (`writing-for-agents`), and the shape of a PR body (`pr`) — the smallest view that makes the point, evidence before and after, and merge danger as a one-way or two-way door. That shape is adapted into `references/changing.md`, not adopted as a template: `changing.md` already owns what a PR body says, and a second authority for one rule is what rule 6 forbids. The `pr` skill credits Humanlayer's `show-me`.
- **How to check for updates:** `claude plugin update mattpocock-skills@mattpocock`.

## 3. clear-writing (this repo)

- **What we took:** the rule that prose for people follows clear-writing. This skill points to it.
