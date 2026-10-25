# Running poteto-mode with the user's own skills

poteto-mode leads how you think, design, debug and build. The user's skills set the rules that work runs inside. Where this file and poteto-mode disagree, this file wins. A repository's own instructions (`AGENTS.md`, `CLAUDE.md`, `REVIEW_STANDARDS.md` and the like) win over both.

## The workflow

Pick the first step in this order. If any question the build depends on is still open, start at step 1, whatever the change's size. Once nothing is open, a change across several files or several sessions goes to step 2, and a typo or a one-file change goes to step 3. Step 1 hands on by the same rule.

Some steps use a skill only the owner can start (`/grill-with-docs`, `/to-spec`, `/to-tickets`, `/wayfinder`, `/retro`). At such a step, ask the owner to type that one command, and say why it is the next step.

1. **Decide.** Test the plan with `grilling`, or ask for `/grill-with-docs` when the repository has docs to check the plan against. When the open questions are too many to settle in one session, ask for `/wayfinder`, which maps them as decision tickets and resolves them one at a time. Keep the plan's terms in the glossary with `domain-modeling`. Record each decision as way-of-working says, with the owner's words quoted. A new project starts here with `project-discovery`. Where the repository keeps its own decision records and glossary, write to those. Done when no question the build depends on is still open.
2. **Plan.** Ask for `/to-spec` to turn the decided change into a spec, then `/to-tickets` to split it into tickets that each name what blocks them. Done when every build ticket is on the tracker with its blocking edges. `/wayfinder`'s decision tickets from step 1 are not build tickets.
3. **Build and ship.** Run each ticket, or the change itself when it started here, through the matching poteto-mode playbook, then through the pull request loop under "way-of-working owns the pull request loop" below. Where there is code to test, `tdd` drives the tests. When the owner is away, night-run works the tickets as its queue, under the brief the owner approved. Done when each pull request is merged.
4. **Improve.** After a session with repeated review rounds, ask for `/retro`, then put each lesson in one place as way-of-working's `references/improving.md` says. Done when each lesson sits in exactly one file.

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
- stacking: one branch per concern, stacked on another branch only when the item builds on that unmerged branch, as night-run's loop says, within any limit the repository sets. This replaces poteto-mode's preference for five narrow stacked PRs.

A pstack PASS or FAIL verifier may run as extra evidence for the PR body. The repository's PR reviewer gives the merge verdict. Keep poteto-mode's bottom-up landing and its patch-id re-check of old verdicts, since both fit inside the merge rule.

## night-run owns unattended work

Autonomous run, Orchestrate, Autopilot-full and Autopilot-stack, and any task the user steps away from ("going to bed", "run until done"), run under night-run: a brief the user approves, decisions logged under the user's delegation, every change through the pull request loop above, and a morning log. The show-me-your-work trail feeds that log. Never block on the human applies inside the brief. The gates named by night-run, way-of-working and the repository are operator-named gates, so they still need the operator.

## Substitutes for Cursor-only pieces

- `/deslop` from `cursor-team-kit`: use `ce-simplify-code`.
- `control-ui`: open the app in a real browser with the browser tool the agent has, such as the `chrome-devtools-axi` command where it is installed, and check what a user would see. `control-cli`: run the CLI yourself in the shell and check its real output, as a user would see it.
- A Cursor cloud agent as verifier: a reviewer on a different model, as way-of-working names.
- Model slugs and `/setup-pstack` apply in Cursor only. Elsewhere, spawn subagents with the harness's own tool (`subagent_type: "poteto-agent"` in Claude Code) on the model the harness picks.
