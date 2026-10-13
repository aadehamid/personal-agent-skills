# The loop for one item

Each item in the queue runs this loop. It is the project's own pull-request loop (way-of-working's `changing.md` and `before-push.md`, where installed), with the changes that matter when no one is watching.

1. **Branch.** Make one branch per concern, in its own worktree, so a reviewer reading one branch never sees another's changes. If an item builds on an unmerged branch, stack it on that branch and log the stack. Stacked branches merge in order. After the one below merges, fetch, rebase the next one onto the default branch, run the check, and push it with `git push --force-with-lease`.
2. **Build.** Do the work. Write tests that pin values by hand, not values computed by the code under test.
3. **Check.** Run the check command before every push, the first push and every fix alike.
4. **Independent review.** Start the brief's independent reviewer on the branch, and wait until its report file exists or the reviewer exits with an error. If your agent can run a long command in the background and be told when it ends, use that, so you are free in the meantime. Read the report from the report file named in the brief. Round 1 reviews the full diff. Every later round reviews only the fix commits, and says which findings each fix closes. Fix every finding or answer it in the PR description. A reviewer that has finished but left no report has not reviewed.
5. **Open the pull request.** Use the project's PR format. Name the decisions the PR relies on, and mark the ones made under the delegation.
6. **PR review.** Start the brief's PR reviewer. Fix a hold on the same branch. Then run the check, give the fix a focused independent review, push, and ask the PR reviewer again.
7. **Watch and merge.** Watch the pull request until the PR reviewer and CI have both answered for the latest push. Merge only when the brief's merge rule holds. Record the merge on the PR, then clean up the branch and worktree, and end the reviewer sessions for that branch. Log the merge.

## Decisions

- **Record each decision where its question lives:** a decision record, the document that asked, or the PR. Quote the evidence that settles it.
- **Mark it as delegated.** Each record says it was made under the owner's delegation, and names the delegation record.
- **Keep the owner's words separate from yours.** Quote only words the owner typed as theirs. Your reasoning goes in the context or evidence section.
- **Log it.** Add a `Decided` entry with a pointer to where the decision is recorded.

## When a tool stalls

- **A reviewer stops responding, or a queued prompt never starts.** End its session and start a new one on the same commit. If it stalls a second time, switch to another reviewer of the same role, and log the switch.
- **The PR reviewer has not answered a push within the brief's wait.** Start the brief's stand-in on the same commit. Its verdict counts for the merge rule. Log the switch, and use the stand-in for every later push until the PR reviewer answers again. If the brief names no stand-in, keep the PR open, log it, and move to the next item.
- **An item depends on another open pull request.** Log the dependency and move to the next item. Come back after that PR merges.
- **A local service dies**, for example a container killed for memory. Restart it, rerun the step that used it, and log it. Run fewer reviewers at once if it happens again.
