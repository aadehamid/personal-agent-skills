# ontology-change

An agent skill that takes a filled change form for a released ontology and drives it through the release's own commands to a checked, committed release: check the form, turn it into a proposal, show the plan and get a yes, apply it, run the release's check, load and check the stores, and give people the new forms.

It holds no command. Every command and expected line comes from the release's handout, `HANDOUT.md`, which the release's own test runs, so the skill cannot drift from the commands. The skill adds the order, the yes before an apply, and plain-word answers to a refusal.

This README is for people. Agents read `SKILL.md`.

## Files

- `SKILL.md`: the steps the agent follows.
- `SOURCES.md`: where the skill comes from.

## Status

- First written on 2026-11-22 for KPI Store 1.2, which ships a copy in its `skills/` folder. The copy and this master are the same files.
- Tested by a fresh agent that followed it on the release's rehearsal forms; the result is in the pull request that added it.
