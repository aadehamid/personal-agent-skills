---
name: way-of-working
description: >-
  Hamid's engineering standard for agent work on any repository: how decisions are recorded, how every change goes through a pull request, the checks that run before every push, the shared tools and guardrails that replace one-off scripts, and the retro loop that improves the standard. Use when starting or onboarding to a project, setting up a repo's guardrails (check script, CI, pre-push hook, review standards), recording a decision, preparing or fixing a pull request, or running a retrospective.
---

# Way of working

The owner decides; the agent supplies evidence, options and a recommendation, and does the work through pull requests that a reviewer merges or holds. Every rule below exists because skipping it cost a review round.

## First, find the project's own versions

Read the project's `AGENTS.md`, its review standards file, its check script, and its decision records. Where the project has its own rule, it wins over this skill. Where it lacks one, propose adding it, using the references below.

## Session start

Do this before any other work in a repository. Reading the project's files comes first, then bringing the repository up to the standard.

1. **Read the project's files** — `AGENTS.md`, its review standards file, its check script, its decision records. **When any of the four is missing, build it before doing anything else**, in the order `references/guardrails.md` gives under "A project with nothing yet", starting at the first step you do not find. A repository with none of them is the case that order exists for, and one missing a single file is the same order, resumed.
2. **Run the check script** — the one script called by CI and by the pre-push hook. Land it before other work, because every later change depends on it.
3. **Check the hook is wired and working.** `git config core.hooksPath` should point at the tracked hook and the hook should be executable, but that proves nothing on its own: an executable hook that does nothing passes it, and git skips a missing or non-executable hook without a word. Run the verification in `references/guardrails.md` — `git hook run pre-push` exits 0, and exits non-zero when a check is deliberately broken. Wire it if it is not, under the conditions in that same reference. A shared or existing hook setup serves other work, so report what you found and ask instead of overwriting it.
4. **Check for open pull requests** — yours and anyone's. Watch each one until it merges, before starting unrelated work. The mechanism and cadence are in `references/changing.md`.
5. **Match the reader.** Prose for people follows clear-writing; documents for agents follow writing-for-agents.

When a step cannot be done — no permission to change CI, a shared hook setup, another owner's pull request — say what you found and ask. Do not skip it silently.

## The rules

1. **On the record.** Nothing is Decided or Approved without the owner's recorded words, quoted in a decision record. A merge decides nothing. A skipped question in a decision round means "agreed with the recommendation" only if the owner has said so. Read `references/deciding.md` before recording a decision or running a decision interview.
2. **Every change is a pull request.** One concern per PR. A reviewer merges or holds; fix holds on the same branch. Watch open PRs and finish them before starting unrelated work. Read `references/changing.md` before opening a PR.
3. **Check before every push**, the first push and every review fix alike. Read `references/before-push.md` before you push.
4. **Shared, deterministic tools.** Figures, row status and repo-wide searches come from one tested tool in the repo, never from a script an agent writes for the occasion or from memory. Mechanical rules run in one check script, in CI and a pre-push hook. Read `references/guardrails.md` when a project lacks them or when you are about to write a one-off counting script.
5. **Claim only what has landed.** A document states as done only what is merged; anything in an open PR is pending, with its number.
6. **One source of truth per rule.** A rule lives in one place; other documents point to it. Instruction files hold pointers, not detail. Read `references/documents.md` when writing or restructuring project documents.
7. **Write for the reader.** Prose for people follows the clear-writing skill; documents for agents follow writing-for-agents.
8. **Improve the standard.** After a session with repeated review rounds, run a retro and put each lesson in exactly one place. Read `references/improving.md`.

Done when: the work is merged through PRs that passed the check script and an independent review, every decision it relies on is recorded with the owner's words, and nothing it claims is still pending.
