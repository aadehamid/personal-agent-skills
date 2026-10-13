# Sources

What the night-run skill was built from. Agents do not read this file.

Last review: 2026-10-13.

## 1. The Engineering_Drawing_to_Graph night run (2026-10-13)

- **Link:** https://github.com/aadehamid/Engineering_Drawing_to_Graph, PRs #23 to #30, and the run's morning log.
- **What we took:** the brief (permission, goal, order, delegation, reviewers, stop conditions), which the owner approved before leaving. Recording the delegation as a decision record before the first decision that used it (DEC-048, PR #24). Logging each delegated decision where its question lives and in the morning log (DEC-049 to DEC-052). Every hazard in `references/hazards.md`: a manual test run in a worktree wrote `core.worktree` and a test identity into the shared git config, and four commits on `main` got the wrong author; an amend during a rebase conflict rewrote a merge commit on `main`; a rebase assumed a branch had merged and left conflict markers; a PR description quoted hashes from before a rebase; a reviewer could not write its report to the macOS temporary folder; a stuck reviewer session (a Herdr tab); a database container killed for memory while three reviewers ran; an incident first blamed on the wrong tool, then corrected.
- **Also from the session that built this skill (same day):** a review script edited while a running review still used it crashed that review partway, so `hazards.md` warns against it.
- **What we left out:** that project's decisions, reviewers and models. The brief supplies those for each run.

## 2. way-of-working (this repo)

- **What we took:** the pull-request loop, the checks before every push, the independent review with full first rounds and focused later rounds, and claiming only what has merged. This skill points to it.
