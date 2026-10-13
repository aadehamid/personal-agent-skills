# night-run

Lets an agent work through a goal while you are away, such as overnight. Before you leave, you and the agent write a brief: your permission, the goal, the order of work, how decisions get made, and which reviewers to use. The agent then ships each item through your normal pull-request loop. It decides what the evidence settles and logs each decision for you to read in the morning, so nothing waits on you.

The skill works for any agent that reads `SKILL.md` files, on any project. The project's own rules always win over it. The reviewers, check command and log path come from the brief, so the skill names no project and no model.

This README is for people. Agents read `SKILL.md` and the files it points to.

## Files

| Path | Read by | What it does |
|---|---|---|
| `SKILL.md` | agent, every run | The seven steps of a run, from loading the standards to the morning summary. Its description makes agents load it when you say you are leaving them to work alone. |
| `references/brief.md` | agent, at the start and end | The brief template, the log entry types, and the morning summary template. |
| `references/loop.md` | agent, for each item | How one item ships: branch, check, independent review, PR review, merge. Also how decisions get recorded, and what to do when a tool stalls. |
| `references/hazards.md` | agent, before the first rebase, worktree test or reviewer | The git, reviewer and record-keeping mistakes that cost time on a real run. |
| `SOURCES.md` | you | Where each rule came from. |
| `README.md` | you | This file. |

## Using it

Tell the agent you are leaving it to work alone. In agents that run skills as commands, such as Claude Code, you can also type `/night-run`. Stay until the brief is written and you have approved it. In the morning, read the summary at the end of the log first.

The skill relies on `way-of-working` for the pull-request loop and on `clear-writing` for the log. Both are in this repository.

## Status

- Built from one run, so far: the 2026-10-13 run on Engineering_Drawing_to_Graph (see `SOURCES.md`). After the next run, check whether the hazards list still matches what went wrong.
