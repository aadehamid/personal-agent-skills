# Changing

Read this before opening a pull request.

## The flow

1. Branch from the current main.
2. Make one concern's change. A follow-up fix found while working goes in its own PR unless it is the same concern.
3. Run the checks in `before-push.md`.
4. Open the PR. The body says what changed, why, what the checks found (including the independent review), and any judgement call the reviewer should weigh. Quote the shared tool's commit line for every figure.
5. Watch the PR until it merges. See "Watching a pull request" below.
6. After merge, sync main, delete the branch, and move to the next item.

## Watching a pull request

Watch every pull request you open, and every one already open when you start, until it merges or the owner closes it. A pull request nobody watches sits on a review finding for hours.

- **Poll every five minutes** on a recurring timer, and report **only when something changes** — a new review, a comment, a check result, a merge state. Silence is the normal case; do not narrate an unchanged poll.
- **On a HOLD**, fix on the same branch, run the check script again, run the independent review again (`before-push.md`), and reply on the PR saying what changed.
- **A review against an older commit is not the current verdict.** Read the commit the review names before acting on it.
- **On merge**, sync main, delete the branch local and remote, and stop the timer.
- **Delete only the branch you just merged**, and check it first: `git log origin/main..origin/<branch>` must print nothing. A merged pull request does not prove the branch is merged — a squash merge breaks commit ancestry, and commits pushed after the merge stay on the branch. A branch someone else opened is theirs to delete, so ask.

## Rules that save review rounds

- **Claim only what has landed.** Work in an open PR, in this repo or another, is pending; say so with its number.
- **Cross-repo changes go in step.** When a change spans repositories, open one PR per repo and say in each which other PR it depends on.
- **A review comment against an older commit is not the current verdict.** Check the review's commit before acting on it.
- **When an automated reviewer is new to a repo**, it runs on the next event; push or comment to trigger it rather than waiting.

## Done when

The PR is merged, its review findings were fixed or answered on the PR, and the local clone is back on main.
