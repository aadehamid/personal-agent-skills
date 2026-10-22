# way-of-working

Hamid's engineering standard for working with coding agents on any project. It covers how decisions get recorded, how changes move through pull requests, what gets checked before every push, which guardrails a project needs, and how the standard improves after each project. Every rule in it exists because skipping it cost a review round on a real project; `SOURCES.md` lists which. The skill itself names no project: its rules and examples are meant to hold anywhere.

This README is for people. Agents read `SKILL.md` and the files it points to.

## Files

| Path | Read by | What it does |
|---|---|---|
| `SKILL.md` | agent, every run | The session-start list, the eight rules, and the pointers to each reference. Its description makes agents load it when starting on a project, setting up guardrails, recording a decision, preparing a PR or running a retro. |
| `references/deciding.md` | agent, before a decision | Decision interviews (grill-with-docs), decision records, Proposed vs Decided, amendments. |
| `references/changing.md` | agent, before a PR | The PR flow, watching PRs, cross-repo changes, rules that save review rounds. |
| `references/before-push.md` | agent, before every push | The five checks, the independent-review command and how to handle its findings, plus proving a new check fails. |
| `references/guardrails.md` | agent, when a project lacks them | The order to build the guardrails in, the shared deterministic tool, the one check script run by CI and a pre-push hook, and the split between mechanical rules and judgement rules. |
| `references/documents.md` | agent, when writing project docs | One place per meaning, method vs record, moving approved text, handover notes. |
| `references/tools.md` | agent, when locating helper skills | Focused search of installed roots, then plugin caches if needed. |
| `references/improving.md` | agent, after a costly session | The retro loop and where each lesson goes. |
| `scripts/herdr-review.sh` | agent, before a push | Runs the independent review in a Herdr pane, waits, and prints the report and its file path. |
| `scripts/pi-review.sh` | agent, before a push or as the PR reviewer | Runs Pi through Ollama in a fresh clone, as the independent reviewer (a report file) or the PR reviewer (a MERGE or HOLD comment). Inside Herdr it runs in its own tab. |
| `scripts/watch-pr.sh` | agent, while a PR is open | Polls a pull request every 30 seconds and exits on its first new event: a merge or close, a review or comment of any kind, or a finished check. |
| `scripts/merge-on-verdict.sh` | agent, when it may merge on the PR reviewer's verdict | Waits for the review bot's MERGE or HOLD on a given head and for the required check, then merges with `--match-head-commit` only on MERGE plus a passed check. |
| `scripts/after-merge.sh` | agent, after a merge | Syncs `main`, moves open pull requests based on the merged branch to `main`, and deletes the branch on both sides, only if all its commits are in `main`. |
| `scripts/test_herdr_review.py`, `scripts/test_pi_review.py`, `scripts/test_pr_scripts.py` | the repo's `scripts/check.sh` | Run the five scripts against fake `herdr`, `gh` and `ollama` commands and real throwaway git repositories. |
| `SOURCES.md` | you | Where each rule came from. |
| `README.md` | you | This file. |

## Adopting it on a new project

The order is in `references/guardrails.md` under "A project with nothing yet". That is the authoritative version, for you and for agents alike; this file does not repeat it, because two copies of a procedure drift.

After the first heavy session, run a retro and put each lesson in one place (`references/improving.md`). A lesson that holds only for one project goes in that project's own files, never in this skill.

## Status

Started 2026-10-06 from one project.

- **No evals yet.** Write test prompts before tuning: starting a new repo, preparing a PR with a figure in it, and recording a decision from a vague request.
- **Narrow evidence so far.** The lessons come from a few Python and Markdown repositories. Expect changes as other kinds of project use it.
- **A review gate between the stages.** The skill gives the implementing agent the command to run an independent review, and tells it to reproduce each finding and re-review after fixing. It is still the agent's job to run it: a hook that refuses to push without one is not built yet.
