# Sources

This file lists what the ontology-change skill draws on. Agents do not read it.

## 1. The owner's decision

- **What it is:** the owner's answer of 2026-11-22, "yes, add the skill to 1.2", to a recommendation for a thin skill that drives the ontology update from a filled form, pointing to the release's handout and holding no rules of its own. The same day the owner set where it lives: "We probably should also update the master personal agent report. That's the personal agent skill repo, and then we copy from there to this release".
- **What the skill took:** its scope (a filled form to a released, loaded change), the rule that the handout is the only source for commands, the yes before an apply, and the master here with a copy in the release.

## 2. The release's handout

- **What it is:** `HANDOUT.md`, "Running and changing your ontology", in the KPI Store release repository (branch `kpi-store/1.2`), with the guide `HOW-TO-UPDATE.md` it names. The release's doc test runs or checks their command blocks.
- **What the skill took:** the order of the steps and the headings it names. Check for changes whenever the release renames or reorders a handout section: the release's test of the skill's copy fails when a heading the skill names is gone.
