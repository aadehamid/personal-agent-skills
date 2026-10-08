# Changing

Read this before opening a pull request.

## The flow

1. Branch from the current main.
2. Make one concern's change. A follow-up fix found while working goes in its own PR unless it is the same concern.
3. Run the checks in `before-push.md`.
4. Open the PR. Its body carries what "What the body says" below lists. That section is the one place that says what a body holds.
5. Watch the PR until it merges. See "Watching a pull request" below.
6. After merge, sync main, delete the branch, and move to the next item.

## What the body says

The body carries these:

- **What changed, and why.** The shape of the change in a line or two, then the problem it answers.
- **What the checks found, including the independent review.** Which findings it raised, and what became of each.
- **Any judgement call the reviewer should weigh.** Which findings you fixed and which you answered, with the reasoning the reviewer needs to weigh the answer. This one is prose, and prose stays.
- **The shared tool's commit line for every figure.** Quoted, so the reader can re-run it.

Three things make that readable.

- **The smallest view that makes the point.** A diff sketch, a call tree, a file tree or a short table says more than paragraphs, because the reader is checking a shape rather than reading an argument. Pick the one that answers the question they have, and leave the other views out.
- **Evidence, before and after.** Not "verified" — the output. The failing run and the passing run, or the command and what it printed. Evidence the reader can re-run beats a claim they must trust, and it is the difference between a reviewer checking your work and taking your word.
- **Merge danger.** A one-way door or a two-way one? A change that is cheap to revert is lower risk, and the owner deciding whether to merge needs to know which this is. Add the blast radius in a word or two: what it touches, and who will notice.

This shape is adapted from the `pr` skill in `mattpocock-skills` (itself from Humanlayer's `show-me`). Its template is not adopted wholesale: this section already owns what a PR body contains, and a second copy of one rule is what rule 6 forbids.

## Watching a pull request

Watch every pull request you open, and every one already open when you start, until it merges or the owner closes it. A pull request nobody watches sits on a review finding for hours.

- **Poll every five minutes** on a recurring timer, and report **only when something changes** — a new review, a comment, a check result, a merge state. Silence is the normal case; do not narrate an unchanged poll.
- **Bound review output.** Use `gh api --jq` to select the reviewed commit, creation time, state, and relevant body text. Omit decorative HTML footers. Keep unresolved findings from earlier commits available until fixed or answered. Retrieve source text needed to judge a finding even when it is from an older round.
- **On a HOLD**, fix on the same branch, run the check script again, run the independent review again (`before-push.md`), and reply on the PR saying what changed.
- **A review against an older commit is not the current verdict.** Read the commit the review names before acting on it.
- **On merge**, sync main, delete the branch, and stop the timer.
- **Delete only the branch you just merged.** A merged pull request does not prove the branch is merged: a squash merge breaks commit ancestry, and commits pushed after the merge stay on the branch. Check the live remote rather than a cached ref, and delete under a lease so a concurrent push aborts the delete:

  ```sh
  git fetch origin <branch> main &&
  sha="$(git rev-parse origin/<branch>)" &&
  git merge-base --is-ancestor "$sha" origin/main &&
  git push origin --delete <branch> --force-with-lease="<branch>:$sha" &&
  git branch -d <branch>
  ```

  Run it as one `&&` chain, so the first failure stops the rest: a bare sequence would carry on to the delete after the ancestry check said no. Fetch `main` as well as the branch, or the check compares against a stale `main`. Everything after the fetch uses the captured `sha`, never `origin/<branch>` again — re-reading a mutable ref between the check and the delete is how a branch verified as merged ends up leased at a commit that is not. The last line is `-d`, never `-D`: it refuses an unmerged branch.

  Without the lease, a push landing after the check takes that work with it. With it, the delete is rejected instead (`stale info`, exit 1).
- **A branch someone else opened is theirs to delete**, even after its pull request merges. Ask.

## Rules that save review rounds

- **Claim only what has landed.** Work in an open PR, in this repo or another, is pending; say so with its number.
- **Cross-repo changes go in step.** When a change spans repositories, open one PR per repo and say in each which other PR it depends on.
- **A review comment against an older commit is not the current verdict.** Check the review's commit before acting on it.
- **When an automated reviewer is new to a repo**, it runs on the next event; push or comment to trigger it rather than waiting.
- **Resolve a conflict by writing the file, then reading it back.** A resolution made by a scripted find-and-replace keeps whatever its pattern did not match, which is how a conflict marker reaches a commit: the script reports success because its own pattern matched. Read the resolved file for markers, and for the lines you meant to keep, before you stage it. Fixing the file and reading it again is the repair. Staging a resolution does not record it; the commit does, whichever command makes it — `git commit` itself, or any of git's `--continue` verbs — and `git rerere` records one without a commit at all. An abort undoes only an operation still in progress, and it measures that from a checkpoint the operation, not you, controls. `git cherry-pick --abort` and `git am --abort` compare HEAD with it; when a `git commit` moved HEAD past it they decline to rewind and tear the operation down anyway (`warning: You seem to have moved HEAD. Not rewinding, check your HEAD!`, `Not rewinding to ORIG_HEAD`), leaving the commit on the branch with the rest of the queue gone and nothing to resume. Resume *instead* and the checkpoint follows HEAD — cherry-pick records it when the next pick runs, `git am` on any move to the next patch, `--skip` as much as `--continue` — so the abort after that conflict is allowed and rewinds the whole operation past the commit. Repair by resetting the branch to a commit you name, not by aborting. Measured on two-commit sequences whose first pick or patch conflicted: cherry-pick, commit the resolution, `--abort` → the warning, HEAD on the commit, `.git/sequencer` removed; the same commit, `--continue` to the next conflict, `--abort` → HEAD back at the start. `git am`, commit the resolution, `--skip` (which the `No changes - did you forget to use 'git add'?` message suggests, after `--continue` exits 128 on the now-clean index) → the checkpoint moves from the start up to that commit, and the next `--abort` puts HEAD back at the start with the resolution gone. Where the commit finishes the operation there is nothing left to abort (`no cherry-pick or revert in progress`, `no rebase in progress` after a `--continue` that completes a rebase). `git rebase --abort` rewinds regardless: after a `git commit` inside the rebase it put the branch back where it started. With `rerere` on, an abort keeps the resolution it recorded, and a retry can come back with those lines already in the file: measured, after a rebase was aborted at its second conflict, the next `git rebase` laid the wrong resolution down in place of a fresh conflict with markers.

## Done when

The PR is merged, its review findings were fixed or answered on the PR, and the local clone is back on main.
