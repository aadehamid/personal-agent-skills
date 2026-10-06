# Changing

Read this before opening a pull request.

## The flow

1. Branch from the current main.
2. Make one concern's change. A follow-up fix found while working goes in its own PR unless it is the same concern.
3. Run the checks in `before-push.md`.
4. Open the PR. The body says what changed, why, what the checks found (including the independent review), and any judgement call the reviewer should weigh. Quote the shared tool's commit line for every figure.
5. Watch the PR (a background poller that wakes the agent on a new review, comment or merge). On a HOLD, fix on the same branch, run the checks again, reply on the PR with what changed.
6. After merge, sync main, delete the branch, and move to the next item.

## Rules that save review rounds

- **Claim only what has landed.** Work in an open PR, in this repo or another, is pending; say so with its number.
- **Cross-repo changes go in step.** When a change spans repositories, open one PR per repo and say in each which other PR it depends on.
- **A review comment against an older commit is not the current verdict.** Check the review's commit before acting on it.
- **When an automated reviewer is new to a repo**, it runs on the next event; push or comment to trigger it rather than waiting.

## Done when

The PR is merged, its review findings were fixed or answered on the PR, and the local clone is back on main.
