# Sources

This file lists what the ontology-change skill draws on. Agents do not read it.

## 1. The owner's decision

- **What it is:** `docs/decisions/2026-11-22-ontology-change-skill.md` in the personal-agent-skills repository, with the owner's words and the recommendation they answered in its answers file. The owner answered "yes, add the skill to 1.2", then set where it lives: "We probably should also update the master personal agent report. That's the personal agent skill repo, and then we copy from there to this release".
- **What the skill took:** its scope (a filled form to a released, loaded change), the rule that it gives no command of its own, the yes before an apply, and the master here with a copy in the release.

## 2. The release's guides

- **What it is:** `HANDOUT.md`, "Running and changing your ontology", and `HOW-TO-UPDATE.md`, in the KPI Store release repository, as they stood at b3b1924 on 2026-11-22, the head of the handout's pull request, which merged into `kpi-store/1.2` as 7c98cbd on 2026-11-23; the three files are the same on both commits. The release's doc test runs or checks their command blocks.
- **Also:** `kpi-intake/README.md` in the same release, for who does what in a KPI interview, the routes and the workbook check.
- **What the skill took:** the order of the steps, the headings it names, and the lines it expects.
- **Snapshots:** `upstream/HANDOUT.md`, `upstream/HOW-TO-UPDATE.md` and `upstream/kpi-intake-README.md` hold the three files at b3b1924 (local only, not tracked).
- **Recreate the snapshots** (a fresh clone has none), from a clone of the release repository in `<clone>`:
  `git -C <clone> show b3b1924:HANDOUT.md > upstream/HANDOUT.md`, `git -C <clone> show b3b1924:HOW-TO-UPDATE.md > upstream/HOW-TO-UPDATE.md` and `git -C <clone> show b3b1924:kpi-intake/README.md > upstream/kpi-intake-README.md`, run in this skill's folder after `mkdir -p upstream`.
- **How to check for an update:** with a newer release checked out in `<release>`, run `diff upstream/HANDOUT.md <release>/HANDOUT.md`, `diff upstream/HOW-TO-UPDATE.md <release>/HOW-TO-UPDATE.md` and `diff upstream/kpi-intake-README.md <release>/kpi-intake/README.md`. Read every changed heading the skill names, every changed line it expects (a check's "Result: not complete" line, the apply's `Done.` line and the line after it, "No store needs loading"), and any change to the routes of "Propose a KPI with the forms it waits on". Change the skill to match, rehearse it, then copy the new files into `upstream/` and put the new commit here. Check at each release of the guides.
