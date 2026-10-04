# Sources

This file lists every source clear-writing was built from: what we took, what we left out, and the exact version we used. It also says how to check each source for updates. Agents do not read this file.

The `upstream/` folder holds a snapshot of each source as we used it, so an update check is a `diff`. The snapshots are third-party text, so they stay on your machine: git ignores `upstream/`, and the public repo has only the links, versions, and hashes below. If you clone the repo on a new machine, rebuild the snapshots from the pinned versions before you run a check:

```bash
mkdir -p upstream
gh api "repos/cursor/plugins/contents/pstack/skills/unslop/SKILL.md?ref=70b2dc8b4b85" --jq .content \
  | base64 -d > upstream/cursor-unslop-SKILL.md
```

For the two X posts, ask Claude to save each post's text from its link into `upstream/karpathy-post.md` and `upstream/kunchen-post.md`. The Anthropic unslop has no public URL. To rebuild it, turn it on in claude.ai for a moment and copy it from `~/.claude/skills/synced/*/unslop/SKILL.md`.

Last full review: 2026-10-03. Suggested cadence: every three months, or when one of the authors posts about a change.

## 1. Cursor unslop (cursor/plugins)

- **Link:** https://www.skills.sh/cursor/plugins/unslop. The file is `pstack/skills/unslop/SKILL.md` in https://github.com/cursor/plugins.
- **Version used:** commit `70b2dc8b4b85` (2026-09-23). Snapshot: `upstream/cursor-unslop-SKILL.md`.
- **What we took:** the ideas behind rule 32 (mannered prose), rule 33 (over-compression), the flat ban on em dashes (rule 13), and the convention that rule numbers are stable ids. All are rewritten in our own words. These are in `references/ai-tells.md` and in the AI-tells list in `SKILL.md`.
- **What we left out:** this fork drops rules 1, 2, 4, 6, and 21 and the "Adding soul" section. We kept them from the Anthropic version (source 2). It also sets `disable-model-invocation: true`, so it runs only when the user calls it by name. We want clear-writing to trigger on its own.
- **License:** the repo has no license file, so its text is all rights reserved. This repo does not include that text: `ai-tells.md` restates the ideas in new words, and the snapshot stays local. Check again if the upstream repo adds a license.
- **Check for updates:**

  ```bash
  gh api "repos/cursor/plugins/commits?path=pstack/skills/unslop/SKILL.md&since=2026-10-03T00:00:00Z" \
    --jq '.[] | "\(.sha[0:12]) \(.commit.committer.date) \(.commit.message|split("\n")[0])"'
  gh api repos/cursor/plugins/contents/pstack/skills/unslop/SKILL.md --jq .content | base64 -d \
    | diff upstream/cursor-unslop-SKILL.md -
  ```

  Also look at the rest of `pstack/skills/`. Commit `e8d856f0273b` ("density and mannered-prose pass across the skills") changed several sibling skills, and those may hold other writing principles.

## 2. Anthropic directory unslop

- **Link:** the unslop skill in the claude.ai skills directory. It syncs to `~/.claude/skills/synced/<id>/unslop/SKILL.md` when it is turned on. We know of no public URL.
- **Version used:** the synced copy as of 2026-10-03 (sha256 starts `9206242eaf7c`). Snapshot: `upstream/anthropic-unslop-SKILL.md`.
- **What we took:** the ideas behind rules 1 to 31, rewritten in our own words with our own examples (`references/ai-tells.md`). The "Adding soul" section became the voice rules in `SKILL.md`. The self-audit step became step 4 of the edit process.
- **What we left out:** "Let some mess in" was reworded as "Do not over-structure", because a calibrated skill should not add errors on purpose.
- **Status:** on 2026-10-03 it was removed from the synced skills folder (moved to `~/.claude/skills/.trash/`), so it no longer competes with clear-writing for triggers.
- **Check for updates:** open it in the claude.ai skills directory, or turn it on for a moment so it syncs, then run:

  ```bash
  diff upstream/anthropic-unslop-SKILL.md ~/.claude/skills/synced/*/unslop/SKILL.md
  ```

  Turn it off again afterwards.

## 3. Andrej Karpathy on ASD-STE100

- **Link:** https://x.com/karpathy/status/2105819303471976479 (2026-10-02). Snapshot: `upstream/karpathy-post.md`.
- **What we took:** the core idea of using ASD-STE100 to make model output easier to read, at "about 80% of the way" to the full spec. This shaped the 12 STE rules in `SKILL.md`, and the "Rules left out" section of `references/ste-rules.md`.
- **What we left out:** his format ladder (diagram, then HTML page, then explainer video). It is about output format, not prose, and other skills (diagram-design, artifact-design) cover it. Revisit this if you want clear-writing to suggest a diagram when prose is the wrong format.
- **Check for updates:** look for follow-up posts or replies from @karpathy on the same topic.

## 4. Kun Chen on picking an STE subset

- **Link:** https://x.com/kunchenguid/status/2105931853815296295 (2026-10-02). Snapshot: `upstream/kunchen-post.md`.
- **What we took:** the full STE ruleset is too strict, so pick a subset based on your own transcripts. This became calibrate mode (`references/calibrate.md`, `scripts/sample_transcripts.py`, `calibration.md`). A reply by @alexgreensh, saying that full STE hurt knowledge work, is the reason for the register table in `SKILL.md`.
- **What we changed:** his prompt writes the rules to a user-level AGENTS.md. We write them to `calibration.md` inside the skill, and add a CLAUDE.md summary only if the user agrees.
- **Check for updates:** look for follow-ups from @kunchenguid, and for the open-source output styles that @alexgreensh mentions in the replies. They may have benchmark results worth comparing against.

## 5. ASD-STE100 specification

- **Link:** https://www.asd-ste100.org (official site; the spec is free on request).
- **Version used:** none directly. The 12 rules in `SKILL.md` were written from general knowledge of the spec's writing rules, not copied from a specific issue. No snapshot.
- **Check for updates:** see whether a new issue of the spec has been published. If you get a copy, compare its writing rules against `references/ste-rules.md`. This is the most likely place to find a rule we missed.

## 6. Matt Pocock, wait-what

- **Link:** https://github.com/mattpocock/skills/tree/main/skills/productivity/wait-what. License: MIT.
- **Version used:** commit `d80fa0f4ebe0` (2026-09-17). Snapshot: `upstream/mattpocock-wait-what-SKILL.md`.
- **What we took:** the re-pitch idea. When a message does not land, explain it again with context first, in STE, in the project's own terms. This became re-pitch mode in `SKILL.md` and the user-invoked `../wait-what` skill. His pointer to `GLOSSARY.md` and `GLOSSARY-MAP.md` became the term order in STE rule 3.
- **What we added:** a fixed shape for the re-pitch (context, point, terms, decision), a completion criterion, and the rule that a re-pitch is shorter than the original and takes a new angle.
- **Check for updates:**

  ```bash
  gh api "repos/mattpocock/skills/commits?path=skills/productivity/wait-what&since=2026-10-03T00:00:00Z" --jq '.[] | "\(.sha[0:12]) \(.commit.message|split("\n")[0])"'
  ```

## 7. Matt Pocock, writing-for-agents

- **Link:** https://github.com/mattpocock/skills/tree/main/skills/productivity/writing-for-agents. License: MIT.
- **Version used:** commit `d80fa0f4ebe0` (2026-09-17). Snapshots: `upstream/mattpocock-writing-for-agents-SKILL.md` and `upstream/mattpocock-writing-for-agents-SKILL-MECHANICS.md`.
- **How we use it:** installed as its own skill with `npx skills add mattpocock/skills --skill writing-for-agents -g`, not merged into clear-writing. Clear-writing hands documents that an agent reads (skills, CLAUDE.md, AGENTS.md) to it. `npx skills update` keeps it current, so it needs no update check here.
- **What we applied to clear-writing itself:**
  - *Negation primes the banned behaviour.* SKILL.md now states targets ("plain words", "periods and commas for separation"). The lists of banned words and patterns moved to `references/ai-tells.md`, which the agent reads only for the final check.
  - *Completion criteria.* Write, Edit, and Re-pitch modes each end with a "Done when" line that can be checked.
  - *Branch test for disclosure.* The ai-tells check runs only for deliverables and edits, not for every chat reply.
  - *One trigger per branch.* The description gained one trigger for re-pitch and lost the stale unslop mention.
- **Not yet applied:** a no-op pruning pass. Rules that the model already follows (calibration found rules 4 and 7 neutral) could be cut. Use the evals to test each cut before you make it.

## Review log

| Date | Sources checked | Result |
|---|---|---|
| 2026-10-03 | Matt Pocock (6, 7) | Added re-pitch mode, the /wait-what command, the project-terms order in rule 3, positive targets, and completion criteria. Installed writing-for-agents as its own skill. |
| 2026-10-03 | all | First version built. Adopted Cursor rules 32 and 33 and the flat em dash ban. Fixed the credit for rules 1 to 31, which came from the Anthropic version and not the Cursor one. |

## How to run a review

1. Run the "check for updates" step for each source above.
2. For each change, decide: adopt, adapt, or skip. Write the reason in this file under that source.
3. Copy the new upstream text over its snapshot in `upstream/`, and update the version and date.
4. If you changed `SKILL.md` or the references, rerun the evals (see `README.md`).
5. Add a row to the review log, then commit.

You can also ask Claude: "review the clear-writing sources for updates". Claude reads this file and follows the steps.
