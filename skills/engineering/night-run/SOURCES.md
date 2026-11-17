# Sources

What the night-run skill was built from. Agents do not read this file.

Last review: 2026-11-17.

## 1. The Engineering_Drawing_to_Graph night run (2026-10-13)

- **Link:** https://github.com/aadehamid/Engineering_Drawing_to_Graph, PRs #23 to #30, and the run's morning log.
- **What we took:** the brief (permission, goal, order, delegation, reviewers, stop conditions), which the owner approved before leaving. Recording the delegation as a decision record before the first decision that used it (DEC-048, PR #24). Logging each delegated decision where its question lives and in the morning log (DEC-049 to DEC-052). The hazards in `references/hazards.md` under "Git state", "Reviewers" and "Your own records": a manual test run in a worktree wrote `core.worktree` and a test identity into the shared git config, and four commits on `main` got the wrong author; an amend during a rebase conflict rewrote a merge commit on `main`; a rebase assumed a branch had merged and left conflict markers; a PR description quoted hashes from before a rebase; a reviewer could not write its report to the macOS temporary folder; a stuck reviewer session (a Herdr tab); a database container killed for memory while three reviewers ran; an incident first blamed on the wrong tool, then corrected.
- **Also from the session that built this skill (same day):** a review script edited while a running review still used it crashed that review partway, so `hazards.md` warns against it.
- **What we left out:** that project's decisions, reviewers and models. The brief supplies those for each run.

## 2. way-of-working (this repo)

- **What we took:** the pull-request loop, the checks before every push, the independent review with full first rounds and focused later rounds, and claiming only what has merged. This skill points to it.

## 3. A release-packaging run on a private repository (2026-11-11 to 2026-11-15)

- **Where:** the owner's private release repository, pull requests #3 to #34 on its release branch, and the run's night log and retro input in the owner's handoff folder. The retro ran on 2026-11-17 at the owner's request ("Can we do a /retro now", "implement the highest priorpity ones").
- **What we took:** done lines, after the close was refused twice because the goal's exceptions were kept outside the goal, and once more over a goal sentence stricter than the owner's talk about it. The proof kit, after test stores and rehearsal data were removed before the close was accepted and had to be rebuilt. The Target field and the tracer bullet, after faults of the target operating system appeared only after four builds. The hazards under "Long runs and proofs": the disk filled three times, a three-hour proof run looked idle behind a buffered log, a proof script's `python -m` command did nothing and ended 0, and a check nested in the document test hid a release-blocking fault.
- **How to check:** the retro input lists each event with its log entry time and pull request.
- **What we left out:** that project's names, data and client.
