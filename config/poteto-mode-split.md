# Running poteto-mode with the user's own skills

poteto-mode leads how you think, design, debug and build. The user's skills set the rules that work runs inside. Where this file and poteto-mode disagree, this file wins. A repository's own instructions (`AGENTS.md`, `CLAUDE.md`, `REVIEW_STANDARDS.md` and the like) win over both.

## poteto-mode leads the thinking and building

- The playbooks Investigation, Bug fix, Perf issue, Hillclimb, Runtime forensics, Trace forensics, Feature, Refactoring, Prototype, Visual parity and Eval.
- The routed skills `how`, `why`, `interrogate`, `architect`, `arena`, `swarm` and `reflect`, the `principle-*` skills, and the Subagents rules.
- The content rules in Writing the reply: name the principles that shaped each decision, label every claim measured, inferred or guess, and link only what you produced or read.

## clear-writing owns every piece of prose

Each prose trigger in poteto-mode (the `unslop` trigger, the `technical-writing` trigger and the style rules in Writing the reply) means: load clear-writing and follow it. That covers replies, docs, READMEs, PR titles and bodies, and commit messages. `/unslop` already routes to clear-writing. clear-writing replaces `/technical-writing`.

## way-of-working owns the pull request loop

When a playbook reaches a pull request (Opening a PR, Babysit, Shipping, Autopilot-full, Autopilot-stack, or the PR step at the end of any playbook), switch to way-of-working and the repository's rules for that whole stretch:

- the checks that run before every push, and the sweep;
- the independent reviewer and the PR reviewer the repository names, with its round limits;
- the merge rule: merge on the PR reviewer's verdict for the current head, as the repository defines it;
- stack depth: the repository's limit, or three unmerged stacked branches when it sets none, opening each stacked PR once its base has merged.

A pstack PASS or FAIL verifier may run as extra evidence for the PR body. The repository's PR reviewer gives the merge verdict. Keep poteto-mode's bottom-up landing and its patch-id re-check of old verdicts, since both fit inside the merge rule.

## night-run owns unattended work

Autonomous run, Orchestrate, Autopilot-full and Autopilot-stack, and any task the user steps away from ("going to bed", "run until done"), run under night-run: a brief the user approves, decisions logged under the user's delegation, every change through the pull request loop above, and a morning log. The show-me-your-work trail feeds that log. Never block on the human applies inside the brief. The gates named by night-run, way-of-working and the repository are operator-named gates, so they still need the operator.

## Substitutes for Cursor-only pieces

- `/deslop` from `cursor-team-kit`: use `ce-simplify-code`.
- `control-ui`: drive the browser with `chrome-devtools-axi`. `control-cli`: use the `run` skill.
- A Cursor cloud agent as verifier: a reviewer on a different model, as way-of-working names.
- Model slugs and `/setup-pstack` apply in Cursor only. Elsewhere, spawn subagents with the harness's own tool (`subagent_type: "poteto-agent"` in Claude Code) on the model the harness picks.
