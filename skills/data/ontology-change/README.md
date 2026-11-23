# ontology-change

An agent skill that takes a filled change form for a released ontology and drives it through the release's own commands to a checked, committed release: check the form, turn it into a proposal, show the plan and get a yes, apply it, run the release's check, load and check the stores, and give people the new forms.

It gives no command of its own. Every command comes from the release's guides, `HANDOUT.md` and the sections of `HOW-TO-UPDATE.md` it or the skill names; the release's doc test runs or checks their command blocks. The skill adds the order, the yes before an apply, and plain-word answers to a refusal. A few words it relies on, such as a check ending "not complete", come from what the commands print, which the guides show only in part.

This README is for people. Agents read `SKILL.md`.

## Files

| Path | Who reads it | What it does |
|---|---|---|
| `SKILL.md` | the agent | The steps, the cases before them, the refusal procedure and the rules. |
| `README.md` | you | This page. |
| `SOURCES.md` | you | Where the skill comes from, and when to check it again. |
| `upstream/` | you | Local snapshots of the release's three guides, for the update check in `SOURCES.md`. Not tracked. |

## Status

- Written on 2026-11-22 for KPI Store 1.2 (decision: `docs/decisions/2026-11-22-ontology-change-skill.md`). A copy in the release's `skills/` folder is planned for 1.2 and has not landed.
- Rehearsed on 2026-11-22 by fresh agents (Sonnet) on scratch copies of the release (branch `feat/handout` at b3b1924), with a KPI form routed to a domain activation and a process map request. Two runs proposed the three forms in one run, stopped for the yes, and applied them in the printed order, each ending on its `Done.` line with its own commit. A third run, on the text after review, stopped for the yes although the person's request said "go ahead"; a fourth, with no form, named the KPI intake form and its signers and stopped. The last wording fixes (the exact step for the form check, the intake README sections for a form with no answers yet, and the question about a form that looks wrong) came from the third and fourth runs and were not rehearsed again.
- Not rehearsed: steps 6 and 7 (the rehearsal machine has no stores), a single form, a new module, a refusal, a settings change and an upgrade.
