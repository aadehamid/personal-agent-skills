# Sources

What the way-of-working skill was built from. Agents do not read this file.

Last review: 2026-10-13.

## 1. The enterprise-performance-model ontology build (2026-10-05 and 06)

- **Link:** https://github.com/aadehamid/enterprise-performance-model, PRs #199 to #221 (merged) and #222 (open when this was written).
- **What we took:** every rule, from the review rounds that taught it. Examples: the decision-record and attribution rules (#199, #212); claiming only what has landed (#216); counting from structure, not text search (#208, #216); primary sources with full-support versions (enterprise-people-graph #1); a rule change reaching every dependent section (enterprise-people-graph #1, #216); the shared tool and check script (#217 to #221); review standards holding only judgement rules (#222, open when this was written).
- **What we left out:** everything specific to that project (its decisions, figures and file names). This file is the only place in the skill that names it.

## 1b. The Engineering_Drawing_to_Graph design package (2026-10-11 and 12)

- **Link:** https://github.com/aadehamid/Engineering_Drawing_to_Graph, PRs #12 to #21.
- **What we took:** writing a decision record as quotes, not paraphrase, and updating earlier records a new decision settles (#13 held three times and ran five review rounds; #15 held once). The two-round review cap and the 30-second watch, which the owner set during that session. Comparing every fact of a fixture with its document and pinning the document text (#21, two rounds). The watch and after-merge scripts, which replace a loop and a delete chain retyped for every pull request.
- **What we left out:** that project's decisions, documents and checks. Its own decision-record check stays in that repository.

## 1c. The night run and the night-run skill (2026-10-13)

- **Link:** https://github.com/aadehamid/Engineering_Drawing_to_Graph PRs #23 to #30, and https://github.com/aadehamid/personal-agent-skills PR #24.
- **What we took:** the "Who reviews" table, which the owner set on 2026-10-13 after the Cursor bot stopped answering for a night: Pi through Ollama stood in as PR reviewer while the Cursor agent CLI gave the independent review. The 8-minute wait and the rule to leave a pull request alone until its reviewer answers, both the owner's. Pi in a fresh clone, after a reviewer that shared a working tree was suspected of changing its files, and in its own Herdr tab, so the owner can watch.

## 1d. The GATE-001 and GATE-003 decisions (2026-10-13)

- **Link:** https://github.com/aadehamid/Engineering_Drawing_to_Graph PRs #32 and #33.
- **What we took:** three lessons from #33, where a check that the owner's quoted answer renders as plain text took nine independent-review rounds and four bot holds. Stating a check on a class of input against the renderer's output and generating the class in its test. Confirming a test run finished before reading its result, after a test run that never started read as zero failures through `grep -c`. Confirming a pull request is still open before pushing to it, after the bot merged #32 while fixes for it were still being written.

## 2. mattpocock-skills (marketplace `mattpocock`, v1.3.1)

- **What we took:** the retro loop (`retro`), decision interviews (`grill-with-docs`, `grilling`), the rules for writing documents agents read (`writing-for-agents`), and the shape of a PR body (`pr`) — the smallest view that makes the point, evidence before and after, and merge danger as a one-way or two-way door. That shape is adapted into `references/changing.md`, not adopted as a template: `changing.md` already owns what a PR body says, and a second authority for one rule is what rule 6 forbids. The `pr` skill credits Humanlayer's `show-me`.
- **How to check for updates:** `claude plugin update mattpocock-skills@mattpocock`.

## 3. clear-writing (this repo)

- **What we took:** the rule that prose for people follows clear-writing. This skill points to it.
