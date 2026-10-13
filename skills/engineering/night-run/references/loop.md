# The loop for one item

Each item in the queue runs this loop. It is the project's own pull-request loop (way-of-working's `changing.md` and `before-push.md`, where installed), with the changes that matter when no one is watching.

1. **Branch.** Make one branch per concern, in its own worktree, so a reviewer reading one branch never sees another's changes. If an item builds on an unmerged branch, stack it on that branch and log the stack. Stacked branches merge in order. After the one below merges, wait until the next PR's current reviewer has answered its latest push, because a rebase is a push. If that answer is a HOLD, fix the hold on the branch first, as step 6 says, so the rebase never pushes the held diff. Then fetch, rebase it onto the default branch, run the check, give the rebased head a focused independent review (step 4), and push it with `git push --force-with-lease`. The rebased head is a new push: wait for the current reviewer's verdict on it before you merge, whatever its answer was before the rebase.
2. **Build.** Do the work. Write tests that pin values by hand, not values computed by the code under test.
3. **Check.** Run the check command before every push, the first push and every fix alike.
4. **Independent review.** Run the independent reviewer the brief names for this PR, with way-of-working's script for it where one exists: each run writes a new report file and exits non-zero when no report appears. Started any other way, give each run a new report path, wait until the reviewer's process ends, and count the review only if that file exists and is newer than the start. If your agent can run a long command in the background and be told when it ends, use that. Round 1 reviews the full diff. Every later round reviews only the fix commits, and says which findings each fix closes. Fix every finding or answer it in the PR description.
5. **Open the pull request.** Use the project's PR format. Name the decisions the PR relies on, and mark the ones made under the delegation.
6. **PR review.** The PR's current reviewer is the brief's PR reviewer, or its stand-in once the stand-in has taken over (see "When a tool stalls"). After each push, leave the PR alone until that reviewer answers: no push, no force-push and no edit to the description. Fix a hold on the same branch. Then run the check, give the fix a focused independent review, push, and wait for the current reviewer again.
7. **Watch and merge.** Watch the pull request until the current reviewer and CI have both answered for the latest push. A verdict on an older commit is not the current verdict. Merge only when the brief's merge rule holds. Record the merge on the PR, then clean up the branch and worktree, and end the reviewer sessions for that branch. Log the merge.

## Decisions

- **Record each decision where its question lives:** a decision record, the document that asked, or the PR. Quote the evidence that settles it.
- **Mark it as delegated.** Each record says it was made under the owner's delegation, and names the delegation record.
- **Keep the owner's words separate from yours.** Quote only words the owner typed as theirs. Your reasoning goes in the context or evidence section.
- **Log it.** Add a `Decided` entry with a pointer to where the decision is recorded.

## When a tool stalls

- **A reviewer stops responding, or a queued prompt never starts.** End its session and start a new one on the same commit. If it stalls a second time, switch to another reviewer of the same role, and log the switch.
- **The PR reviewer is not available for a push**, by the brief's rules (by default, way-of-working's "Who reviews", with its wait). Start the stand-in on the same commit yourself, and log the switch. The stand-in is the PR's current reviewer for every later push on this PR, and the independent reviewer switches with it, as the brief says. Run the new independent reviewer on the head commit at once, and fix or answer its findings: the merged commit's two reviews must come from different tools. A late answer from the PR reviewer is read as a comment, not as the verdict.
- **An item depends on another open pull request.** Log the dependency and move to the next item. Come back after that PR merges.
- **A local service dies**, for example a container killed for memory. Restart it, rerun the step that used it, and log it. Run fewer reviewers at once if it happens again.
