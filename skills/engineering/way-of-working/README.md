# way-of-working

Hamid's engineering standard for working with coding agents. It covers how decisions get recorded, how changes move through pull requests, what gets checked before every push, which guardrails a project needs, and how the standard improves after each project. It came out of the enterprise-performance-model ontology build on 2026-10-05 and 06. Every rule in it exists because skipping it cost a review round there.

This README is for people. Agents read `SKILL.md` and the files it points to.

## Files

| Path | Read by | What it does |
|---|---|---|
| `SKILL.md` | agent, every run | The session-start list, the eight rules, and the pointers to each reference. Its description makes agents load it when starting on a project, setting up guardrails, recording a decision, preparing a PR or running a retro. |
| `references/deciding.md` | agent, before a decision | Decision interviews (grill-with-docs), decision records, Proposed vs Decided, amendments. |
| `references/changing.md` | agent, before a PR | The PR flow, watching PRs, cross-repo changes, rules that save review rounds. |
| `references/before-push.md` | agent, before every push | The five checks, the independent-review command and how to handle its findings, plus proving a new check fails. |
| `references/guardrails.md` | agent, when a project lacks them | The order to build the guardrails in on a repository that has none, the shared deterministic tool, the one check script run by CI and a pre-push hook, and the split between mechanical rules and judgement rules. |
| `references/documents.md` | agent, when writing project docs | One place per meaning, method vs record, moving approved text, handover notes. |
| `references/improving.md` | agent, after a costly session | The retro loop and where each lesson goes. |
| `SOURCES.md` | you | Where each rule came from. |
| `README.md` | you | This file. |

## Adopting it on a new project

The order is in `references/guardrails.md` under "A project with nothing yet". That is the authoritative version, for you and for agents alike; this file does not repeat it, because two copies of a procedure drift. In short: `AGENTS.md`, then the check script with CI and the pre-push hook, then the shared tool, then a review standards file, then decision records — one pull request each, and agree with your agents how a skipped question is read before the decision records go in.

After the first heavy session, run a retro and put each lesson in one place (`references/improving.md`).

The enterprise-performance-model repo is the worked example. See `scripts/epm_facts.py`, `scripts/check.sh`, `.github/workflows/checks.yml` and `business_architecture/domain/decisions/`. Its `REVIEW_STANDARDS.md` is in enterprise-performance-model PR #222, open when this was written.

## Status

Started 2026-10-06 from one project.

- **No evals yet.** Write test prompts before tuning: starting a new repo, preparing a PR with a figure in it, and recording a decision from a vague request.
- **One project's lessons.** Expect changes after the first project that isn't an ontology build. The guardrail examples come from a Python and Markdown repo.
- **A review gate between the stages.** The skill gives the implementing agent the command to run an independent review, and tells it to reproduce each finding and re-review after fixing. It is still the agent's job to run it: a hook that refuses to push without one is not built yet.
