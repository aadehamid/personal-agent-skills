# clear-writing

A skill that makes Claude write plain, clear prose with no AI tells. It also edits text you give it. It combines a subset of ASD-STE100 (Simplified Technical English), the 33 unslop rules, and a calibration file built from your own sessions.

This README is for people. Agents do not read it. They read `SKILL.md` and the files it points to.

## Files

| Path | Read by | What it does |
|---|---|---|
| `SKILL.md` | agent, every run | The skill itself. The frontmatter `description` decides when the skill triggers. The body picks the mode (write, edit, re-pitch, calibrate) and the register (instruct, explain, persuade), lists the 12 STE rules and the plain-style targets, and ends each mode with a "Done when" check. |
| `calibration.md` | agent, every run | Your personal rule weights: which rules to emphasize or relax, plus rules added from your sessions. Calibrate mode writes it. It overrides `SKILL.md` where they conflict. |
| `references/ste-rules.md` | agent, when needed | Before/after examples for each of the 12 STE rules. It also lists the STE rules this skill leaves out, and why. |
| `references/ai-tells.md` | agent, final check only | The full 33-pattern list: rules 1 to 31 from the Anthropic unslop, rules 32 and 33 from the Cursor fork. Rule numbers match both versions. |
| `references/calibrate.md` | agent, calibrate mode only | Step-by-step instructions for calibrate mode and the template for `calibration.md`. |
| `scripts/sample_transcripts.py` | agent, calibrate mode only | Samples recent Claude Code sessions from `~/.claude/projects/` and prints only your prompts and Claude's prose. It skips tool calls, thinking, subagents, and the live session. |
| `evals/evals.json` | you, when testing | The four test prompts (manager explainer, LinkedIn post, 3am runbook, re-pitch) and the checks for each one. |
| `evals/inputs/` | you, when testing | The input files the test prompts use, including a dense message for the re-pitch test. |
| `evals/trigger-eval.json` | you, when tuning | The 20 prompts (10 should trigger, 10 near-misses) used to tune the frontmatter description. |
| `evals/grade.py` | you, when testing | Scores test outputs against the checks: em dashes, AI vocabulary, emoji, warning order, preserved facts, and so on. Writes `grading.json` for each run. |
| `SOURCES.md` | you | Every source this skill was built from: what we took, what we left out, the version used, and how to check for updates. Has a review log. |
| `upstream/` | you, local only | Snapshots of each source as we used it, so an update check is a `diff`. Git ignores this folder because it holds third-party text. |
| `README.md` | you | This file. |

## Common tasks

**Recalibrate after more sessions.** In Claude Code, say "calibrate my writing rules". The skill rewrites `calibration.md`. Review the diff, then commit it.

**Change a rule.** Edit the rule list in `SKILL.md`. If the change affects the examples, update `references/ste-rules.md` too. Then rerun the tests (below) to check that nothing got worse.

**Rerun the tests.** Ask Claude to "rerun the clear-writing evals with skill-creator". Results go to `workspaces/clear-writing/iteration-N/` at the repo root. That folder is not tracked in git. To grade a run by hand:

```bash
python3 evals/grade.py ../../../workspaces/clear-writing/iteration-N
```

**Check the sources for updates.** Follow "How to run a review" in `SOURCES.md`, or ask Claude to "review the clear-writing sources for updates".

**Tune when it triggers.** Use skill-creator's description optimizer with `evals/trigger-eval.json`. Run it with `env -u ANTHROPIC_API_KEY`, and unlink `~/.claude/skills/clear-writing` during the run so the test counts the right skill.

## Status

Last updated 2026-10-03 (iteration 2: re-pitch mode, positive targets, completion criteria; preferred over the previous version in all 4 tests).

- **Calibration is thin.** `calibration.md` came from only 3 sessions, so most rules are marked tentative. Run calibrate mode again on a machine with more sessions: pull first, say "calibrate my writing rules", review the diff, then commit and push. Calibrate mode merges with the existing file, so the results from each machine add up.
- **CLAUDE.md summary is on hold.** After the next calibration, decide whether to add a three-to-five-line summary of the calibrated rules to `~/.claude/CLAUDE.md`. This is separate from the one-line pointer that `link-skills.sh --claude-md` installs.
- **Triggering.** The description was tuned on 2026-10-03 (held-out score 5/8, up from 4/8). The CLAUDE.md pointer does most of the work. Retune only if the skill starts to trigger on the wrong requests.

## Sources

See `SOURCES.md`.
