# Changing

Read this before opening a pull request.

## The flow

1. Branch from the current main.
2. Make one concern's change. A follow-up fix found while working goes in its own PR unless it is the same concern.
3. **Refine the code before review.** Run the `ce-simplify-code` skill on the change. It launches three parallel reviewers (code-reuse, code-quality, efficiency), applies worthwhile findings while preserving behavior, verifies with typecheck/lint/tests, and summarizes. This is the pass that makes the diff reviewable — do it before the checks below, so the independent review reads the code you intend to ship, not a first draft. Skip it only when the change is documentation, generated or vendored files, or mechanical churn with no substantive code (the skill's own preflight decides).
4. Run the checks in `before-push.md`.
5. Open the PR. Its body carries what "What the body says" below lists. That section is the one place that says what a body holds.
6. Watch the PR until it merges. See "Watching a pull request" below.
7. After merge, run `~/.agents/skills/way-of-working/scripts/after-merge.sh <branch>` and move to the next item.

**When a PR must merge one way, make it the only way the repository allows.** A file that pins one of the PR's own commits breaks under a squash or rebase merge, which give that commit a new SHA. A warning in the PR body is not enough: a PR that carried one at the top was squash-merged anyway, and a follow-up PR had to re-pin. Ask the owner to untick "Allow squash merging" and "Allow rebase merging" in the repository settings, so the default merge button is the right one.

## Who reviews

Each pull request gets two reviews: the independent review before each push (`before-push.md`), and the PR review, which gives the merge verdict. The scripts are in `~/.agents/skills/way-of-working/scripts/`. Whether the Cursor bot is available decides which tool does which:

| Cursor bot | Independent review | PR review |
|---|---|---|
| Available | Pi: `pi-review.sh --role independent` | The Cursor bot |
| Not available | The Cursor agent CLI: `herdr-review.sh --kind cursor` | Pi: `pi-review.sh --role pr` |

1. **Before the pull request opens, pick the row from the repository's most recent pull request.** Use the row that held on its last push. For a repository's first pull request, use the "Available" row. On the "Not available" row, Pi is the PR reviewer from the first push: start it on every push without waiting for the bot, and read any answer from the bot as a comment.
2. **After each push, check the bot at 8 and 30 minutes.** `watch-pr.sh` does not wake on a check that only starts, so check yourself: `gh pr checks <number>` lists the bot's check (named "Cursor Automation" on this owner's repositories) for the head commit once it has started. The bot is not available if its check has not started 8 minutes after the push, or if it has not posted a verdict 30 minutes after the push.
3. **When the bot is not available, start Pi as the PR reviewer yourself:** `pi-review.sh --role pr --pr <number> --head <commit>`, with `--since <commit>` after the first round. Nothing starts it for you. Its MERGE or HOLD comment is the answer you wait for on that push. If the script exits 1, run it once more; if it fails again, log it and leave the pull request open.
4. **A switch lasts for the rest of the pull request.** From then on Pi gives the verdict on every push, and the Cursor agent CLI gives the independent review. A later answer from the bot is read as a comment, not as the verdict.
5. **The two reviews of the merged commit come from different tools.** Its independent review and its merge verdict must not both come from Pi, or both from Cursor. When the row changes after an independent review ran, run the new row's independent reviewer on the head commit at once, and fix or answer its findings. Check again before you merge.

The project or the owner can name other reviewers; the same rules then apply to the ones they name. If Pi cannot run on this machine, use `herdr-review.sh`'s default reviewer, Codex, wherever the table names Pi for the independent review, and tell the owner.

`pi-review.sh` runs Pi in a fresh clone under `/tmp`, never in the working tree, because a reviewer that checks out a commit changes the files under your feet. As the independent reviewer it can review a commit that is not pushed yet; it writes a report whose first line is READY or FIX, and posts nothing. As the PR reviewer it posts one comment whose first line is MERGE or HOLD, whose second line is `Reviewed commit: <sha>`, and whose last line is a mark unique to the run; the script fails unless a comment with that mark, that first line and that commit appears on the PR. A comment that names a commit other than the head is a verdict on that older commit. `--verify "<claims>"` names what to check, as for `herdr-review.sh`. Inside Herdr, Pi runs in its own tab, `pi-<role>-<repo>`, so the owner can watch; the tab closes only when every check passed. As the PR reviewer it refuses a `--head` that is not the pull request's head, and fails if the head moved while Pi reviewed. Pi gets an hour, then the script stops it and exits 1. It stops the whole process group, because `ollama launch` runs Pi as a child and does not pass the signal on; inside Herdr, that is the tab's foreground group. A passed run removes its clone; a failed one keeps the clone and its log to read. It needs Ollama and Pi installed (`ollama launch pi`). `scripts/test_pi_review.py` covers each case.

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

- **While the Cursor bot is the PR reviewer, check it 8 and 30 minutes after each push**, as "Who reviews" says, because `watch-pr.sh` wakes on neither mark. If it is not available, start Pi as the PR reviewer yourself.
- **Run `~/.agents/skills/way-of-working/scripts/watch-pr.sh <number>`** from the repository as a background job the harness reports back on. It polls every 30 seconds and exits on the first new event: a merge or close, a new review, conversation comment or inline review comment, or a check that finishes, including a rerun that finishes with the same result. A check that only starts or reruns wakes nothing. It exits at once if the pull request has already merged. When it exits, read what changed, act, and start it again unless the pull request is merged or closed. Report only changes; silence is the normal case.
- **Bound review output.** Use `gh api --jq` to select the reviewed commit, creation time, state, and relevant body text. Omit decorative HTML footers. Keep unresolved findings from earlier commits available until fixed or answered. Retrieve source text needed to judge a finding even when it is from an older round.
- **After each push, leave the pull request alone until its reviewer answers**, with a hold or a merge. Make no other push, force-push, rebase or edit to its description in the meantime: a change that lands while the reviewer reads makes its verdict name a commit that is no longer the head, and the round is wasted. Work on something else while you wait. If the reviewer is not available (see "Who reviews"), Pi's verdict on the same commit is the answer you wait for. A problem you find while waiting is fixed after the answer: with the hold's findings, or, after a MERGE, as a new push that starts a new round before you merge.
- **On a HOLD**, fix on the same branch, run the check script again, run the independent review again, within its round limit (`before-push.md`), and reply on the PR saying what changed.
- **A review against an older commit is not the current verdict.** Read the commit the review names before acting on it.
- **On merge, run `~/.agents/skills/way-of-working/scripts/after-merge.sh <branch>`.** It syncs `main`, then deletes the branch locally and on the remote only if every commit on it is in `main`. A squash or rebase merge, or a commit pushed after the merge, leaves work outside `main`, and the script then deletes nothing. It reads the live remote and deletes under a lease on the commit it checked, so a push landing after the check makes the delete fail rather than lose that work. If the branch vanishes mid-run, because a review bot deleted it on merge, a failed fetch or delete counts as done only when git's error says the ref is missing and the live remote then lists no such branch. The script trusts the remote to list every branch; on a server that hides refs, a hidden branch looks deleted. It reads and deletes through the remote's one push URL, and stops if there are several, deleting nothing. Locally it uses `git branch -d`, which refuses an unmerged branch. `scripts/test_pr_scripts.py` covers a squash merge, a late push, an unpushed local commit, a remote branch already deleted, one deleted before the fetch or before the delete, a failed remote lookup, a fetch that wrongly reports the ref missing, a refused delete of a hidden ref, several push URLs, a push racing the delete and a commit racing `branch -d`.
- **Delete only a branch you opened.** A branch someone else opened is theirs to delete, even after its pull request merges. Ask.

## Rules that save review rounds

- **Claim only what has landed.** Work in an open PR, in this repo or another, is pending; say so with its number.
- **Cross-repo changes go in step.** When a change spans repositories, open one PR per repo and say in each which other PR it depends on.
- **A review comment against an older commit is not the current verdict.** Check the review's commit before acting on it.
- **When an automated reviewer is new to a repo**, it runs on the next event; push or comment to trigger it rather than waiting.
- **Resolve a conflict by writing the file, then reading it back.** A resolution made by a scripted find-and-replace keeps whatever its pattern did not match, which is how a conflict marker reaches a commit: the script reports success because its own pattern matched. Read the resolved file for markers, and for the lines you meant to keep, before you stage it. Fixing the file and reading it again is the repair. Staging a resolution does not record it; the commit does, whichever command makes it — `git commit` itself, or any of git's `--continue` verbs — and `git rerere` records one without a commit at all. An abort undoes only an operation still in progress, and it measures that from a checkpoint the operation, not you, controls. `git cherry-pick --abort` and `git am --abort` compare HEAD with it; when a `git commit` moved HEAD past it they decline to rewind and tear the operation down anyway (`warning: You seem to have moved HEAD. Not rewinding, check your HEAD!`, `Not rewinding to ORIG_HEAD`), leaving the commit on the branch with the rest of the queue gone and nothing to resume. Resume *instead* and the checkpoint follows HEAD — cherry-pick records it when the next pick runs, `git am` on any move to the next patch, `--skip` as much as `--continue` — so the abort after that conflict is allowed and rewinds the whole operation past the commit. Repair by resetting the branch to a commit you name, not by aborting. Measured on two-commit sequences whose first pick or patch conflicted: cherry-pick, commit the resolution, `--abort` → the warning, HEAD on the commit, `.git/sequencer` removed; the same commit, `--continue` to the next conflict, `--abort` → HEAD back at the start. `git am`, commit the resolution, `--skip` (which the `No changes - did you forget to use 'git add'?` message suggests, after `--continue` exits 128 on the now-clean index) → the checkpoint moves from the start up to that commit, and the next `--abort` puts HEAD back at the start with the resolution gone. Where the commit finishes the operation there is nothing left to abort (`no cherry-pick or revert in progress`, `no rebase in progress` after a `--continue` that completes a rebase). `git rebase --abort` rewinds regardless: after a `git commit` inside the rebase it put the branch back where it started. With `rerere` on, an abort keeps the resolution it recorded, and a retry can come back with those lines already in the file: measured, after a rebase was aborted at its second conflict, the next `git rebase` laid the wrong resolution down in place of a fresh conflict with markers.

## Done when

The PR is merged, its review findings were fixed or answered on the PR, and the local clone is back on main.
