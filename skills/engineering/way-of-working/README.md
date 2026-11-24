# way-of-working

Hamid's engineering standard for working with coding agents on any project. It covers how decisions get recorded, how changes move through pull requests, what gets checked before every push, which guardrails a project needs, and how the standard improves after each project. Every rule in it exists because skipping it cost a review round on a real project; `SOURCES.md` lists which. The skill itself names no project: its rules and examples are meant to hold anywhere.

This README is for people. Agents read `SKILL.md` and the files it points to.

## Files

| Path | Read by | What it does |
|---|---|---|
| `SKILL.md` | agent, every run | The session-start list, the eight rules, and the pointers to each reference. Its description makes agents load it when starting on a project, setting up guardrails, recording a decision, preparing a PR or running a retro. |
| `references/deciding.md` | agent, before a decision | Decision interviews (grill-with-docs), decision records, Proposed vs Decided, amendments. |
| `references/changing.md` | agent, before a PR | The PR flow, watching PRs, cross-repo changes, rules that save review rounds. |
| `references/before-push.md` | agent, before every push | The six checks, the independent-review command and how to handle its findings, plus proving a new check fails. |
| `references/guardrails.md` | agent, when a project lacks them | The order to build the guardrails in, the shared deterministic tool, the one check script run by CI and a pre-push hook, and the split between mechanical rules and judgement rules. |
| `references/documents.md` | agent, when writing project docs | One place per meaning, method vs record, moving approved text, handover notes. |
| `references/tools.md` | agent, when locating helper skills | Focused search of installed roots, then plugin caches if needed. |
| `references/improving.md` | agent, after a costly session | The retro loop and where each lesson goes. |
| `scripts/herdr-review.sh` | agent, before a push | Runs the independent review in a Herdr pane, waits, and prints the report and its file path. Inside Rex and outside Herdr, or with `--host rex`, it hands the same arguments to `rex-review.sh`; in a Herdr app terminal outside both, or with `--host hc`, to `hc-review.sh`. |
| `scripts/rex-review.sh` | agent, before a push, through `herdr-review.sh` | Runs the same review in a Rex pane: a split beside the agent's pane, or a new tab when that window already holds two. It reads the reviewer's state from the pane's process and screen, because the reviewer CLIs report no status to Rex. |
| `scripts/hc-review.sh` | agent, before a push, through `herdr-review.sh` | Runs the same review in a child terminal of the Herdr app (herdr-core's `hc`). It reads a reported status first and falls back to the screen; it ends and removes the reviewer's terminal after a report. |
| `scripts/review-evidence.sh` | the review scripts, for `--attach` | Copies the outside files and folders a review was handed into one folder with a `MANIFEST.txt`, so the reviewer reads a fixed copy. It refuses a missing path and a folder holding a link or special file. |
| `scripts/agy-review.sh` | agent, before a push | Runs Antigravity (`agy`) as the independent reviewer in a fresh clone, where it can read files and cannot run commands, under a per-run lock that leaves web search as the known gap. It counts a review only when agy exits 0 and the first line is READY or FIX, because agy also exits 0 with no review. |
| `scripts/pi-review.sh` | agent, before a push or as the PR reviewer | Runs Pi through Ollama in a fresh clone, as the independent reviewer (a report file) or the PR reviewer (a MERGE or HOLD comment). Inside Herdr it runs in its own tab. |
| `scripts/watch-pr.sh` | agent, while a PR is open | Polls a pull request every 30 seconds and exits on its first new event: a merge or close, a review or comment of any kind, or a finished check. |
| `scripts/merge-on-verdict.sh` | agent, when it may merge on the PR reviewer's verdict | Waits for the review bot's MERGE or HOLD on a given head and for the required check, then merges with `--match-head-commit` only on MERGE plus a passed check. |
| `scripts/stop-cursor-review.sh` | agent, when the Cursor bot is not available | Cancels the bot's run on a pull request's head through Cursor's Cloud Agents API, found through the bot's check run, and labels the pull request `review-takeover` so the bot's automation can skip it. Exit 3 says what it could not do, and the stand-in starts anyway; exit 4 says the pull request moved to a new head, and it stops and labels nothing. |
| `scripts/guard-check-running.py` | Claude Code, as a `PreToolUse` hook | Refuses an edit inside the folder of a running `scripts/check.sh`, so a check is never broken or emptied by an edit made during it. `references/guardrails.md` says how to wire it. |
| `scripts/after-merge.sh` | agent, after a merge | Syncs `main`, moves open pull requests based on the merged branch to `main`, and deletes the branch on both sides, only if all its commits are in `main`. |
| `scripts/test_herdr_review.py`, `scripts/test_rex_review.py`, `scripts/test_hc_review.py`, `scripts/test_pi_review.py`, `scripts/test_agy_review.py`, `scripts/test_review_evidence.py`, `scripts/test_pr_scripts.py`, `scripts/test_stop_cursor_review.py`, `scripts/test_guard_check_running.py` | the repo's `scripts/check.sh` | Run the eleven scripts against fake `herdr`, `rex`, `hc`, `gh`, `curl`, `ollama` and `agy` commands, real throwaway git repositories, and a real running check script. |
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
