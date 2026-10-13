# The loop for one item

Each item in the queue runs this loop. It is the project's own pull-request loop (way-of-working's `changing.md` and `before-push.md`, where installed), with the changes that matter when no one is watching.

1. **Branch.** Make one branch per concern, in its own worktree, so a reviewer reading one branch never sees another's changes. If an item builds on an unmerged branch, stack it on that branch and log the stack. Stacked branches merge in order, and each one is rebased onto `main` after the one below it merges.
2. **Build.** Do the work. Write tests that pin values by hand, not values computed by the code under test.
3. **Check.** Run the check command before every push, the first push and every fix alike.
4. **Independent review.** Start the brief's independent reviewer on the branch, as a background job the harness reports back on. Read its report from the report file named in the brief. Round 1 reviews the full diff. Every later round reviews only the fix commits, and says which findings each fix closes. Fix every finding or answer it in the PR description. A reviewer that has finished but left no report has not reviewed.
5. **Open the pull request.** Use the project's PR format. Name the decisions the PR relies on, and mark the ones made under the delegation.
6. **PR review.** Start the brief's PR reviewer. Fix a hold on the same branch. Then run the check, give the fix a focused independent review, push, and ask the PR reviewer again.
7. **Merge.** Merge only when the brief's merge rule holds. Record the merge on the PR, then clean up the branch and worktree. Log the merge.

## Decisions

- **Record each decision where its question lives:** a decision record, the document that asked, or the PR. Quote the evidence that settles it.
- **Mark it as delegated.** Each record says it was made under the owner's delegation, and names the delegation record.
- **Keep the owner's words separate from yours.** Quote only words the owner typed as theirs. Your reasoning goes in the context or evidence section.
- **Log it.** Add a `Decided` entry with a pointer to where the decision is recorded.

## When a tool stalls

- **A reviewer stops responding, or a queued prompt never starts.** Close its tab and start it again on the same commit. If it stalls a second time, switch to another reviewer of the same role, and log the switch.
- **The PR reviewer named in the brief is down.** Use the stand-in the brief names. If the brief names none, keep the PR open, log it, and move to the next item.
- **An item depends on another open pull request.** Log the dependency and move to the next item. Come back after that PR merges.
- **A local service dies**, for example a container killed for memory. Restart it, rerun the step that used it, and log it. Run fewer reviewers at once if it happens again.
