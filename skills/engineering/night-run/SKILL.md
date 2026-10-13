---
name: night-run
description: >-
  Runs a long stretch of repository work while the owner is away: a written brief the owner approves, decisions made under the owner's delegation and logged, every change shipped through the project's pull-request loop with independent and PR reviewers, and a morning log that leaves nothing waiting on the owner. Use when the owner says they are leaving the agent to work unsupervised, overnight, or until a goal is done.
---

# Night run

The owner is away, so the agent works through the goal alone. **Nothing waits on the owner**: the agent decides what the evidence settles, ships through the normal pull-request loop, and records every choice where the owner will read it in the morning. The owner's standing rules still hold; this skill adds what changes when no one is there to answer.

## Steps

1. **Load the standards.** Load `way-of-working` and `clear-writing` if they are installed, and read the project's agent instruction file (`AGENTS.md`, `CLAUDE.md` or its equivalent), review standards and check script. Where the project has its own rule, it wins. Done when you can name the project's check command, its default branch, its decision-record format, and how a pull request gets merged.

2. **Write the brief, and get the owner's yes.** Fill [`references/brief.md`](references/brief.md) with the owner while they are still here. Quote their exact words for the permission, the goal and the delegation. Show the brief to the owner and start only after they approve it. If the owner leaves before approving it, do not start the run: save the draft brief and the open question where they will see it first. **Nothing waits on the owner** applies once the run has started. Save the brief next to the log. Done when every field in the template has a value, and the owner has approved the brief in their own words.

3. **Record the delegation first.** If the project keeps decision records, record the owner's delegation as one, in its own pull request, before the first decision that relies on it. Done when that record is merged, or the project has no decision records and the brief holds the quote.

4. **Work the queue.** Take the next item in the brief's order and ship it through the loop in [`references/loop.md`](references/loop.md). Read [`references/hazards.md`](references/hazards.md) before the first rebase, the first test run inside a worktree, and the first reviewer you start. Keep at most one open pull request per concern. The queue serves one goal, so starting the next item while a pull request waits for review is not unrelated work: keep watching that pull request and finish it first when it needs you. Add a log entry each time an item ships, stalls or changes plan. Done when every item in the queue is merged, deferred with a logged reason, or blocked under a stop condition.

5. **Decide, and log the decision.** When a question comes up, settle it from the evidence in the brief's evidence order, then record it as described in the loop reference. Mark each one as made under the delegation, so the owner can reverse it. Done when each decision appears in two places: where its question lives, and in the log.

6. **Stop only on a stop condition.** The brief lists them. The defaults are a question the evidence cannot settle, and any action that is irreversible outside the repository: spending money, publishing, deleting remote data, or rewriting the history of the default branch or another protected branch. Rebasing your own unmerged branch and pushing it with `--force-with-lease` is normal work, not a stop. So is deleting a merged branch you opened with way-of-working's `after-merge.sh`, which deletes only when every commit on the branch is on the default branch; when it refuses, that is a stop. Any other delete of remote data, such as another person's branch, a tag or a package, stays a stop. When you hit one, log the question with your recommendation, then move to the next item that does not depend on it. Done when every item in the brief's order appears in the log as merged, deferred with a reason, or blocked with its question and recommendation.

7. **Close the run.** Write the summary at the end of the log from [`references/brief.md`](references/brief.md#morning-summary), update the project's open-items list if it keeps one, then clean up: end every reviewer session you started, delete merged branches you opened with `after-merge.sh` (a refusal is a stop, logged for the owner), remove worktrees, and stop the jobs and local services you started. Report the summary to the owner. Done when the summary lists every merged pull request, every decision made for the owner, and every question waiting on them, and nothing you started is still running.

**Done when** the goal in the brief is met or every remaining item is blocked by a logged stop condition, and the morning summary is written.
