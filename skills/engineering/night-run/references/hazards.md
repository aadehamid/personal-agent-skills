# Hazards

Each of these cost time on a real unsupervised run. Read this file before the first rebase, the first test run inside a worktree, and the first reviewer you start.

## Git state

- **Clear `GIT_*` before running tests by hand inside a worktree.** A pre-push hook sets `GIT_DIR`. A test that makes a temporary repository with that variable set writes into the real one: a commit lands on your branch, and `git init` writes `core.worktree` and `user.*` into the shared `.git/config`. Run tests with `env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE`, and make the project's own tests clear these variables themselves.
- **After any test run you started by hand, read `git config --local --list`.** It should hold no `core.worktree` and no `user.name` or `user.email` you did not set. A stray identity silently changes the author of every later commit.
- **Check the author before each push.** In these commands, `<remote>` and `<default>` are the brief's remote and default branch. Run `git fetch <remote>`, then `git log --format='%h %an <%ae>' <remote>/<default>..`. To fix a wrong author on an unmerged branch, first remove the bad identity: `git config --local --unset user.name`, the same for `user.email`, and unset any `GIT_AUTHOR_*` or `GIT_COMMITTER_*` variable. Confirm that `git var GIT_AUTHOR_IDENT` shows the right person. Only then run `git rebase --exec 'git commit --amend --no-edit --reset-author' <remote>/<default>`, and push with `--force-with-lease`. Commits already on the default branch stay as they are; ask the owner in the morning summary.
- **A stacked PR closes when its base branch is deleted.** On enterprise-performance-model #328, a pull request whose base branch `after-merge.sh` deleted with `git push --delete` was closed, not moved to the default branch. Way-of-working's `after-merge.sh` now moves each open PR based on the branch before it deletes the branch.
- **During a rebase conflict, resolve the files and run `git rebase --continue`.** Leave `git commit --amend` until the rebase has finished: during a conflict it can rewrite a commit that is already on the default branch.
- **Fetch, then rebase onto what the default branch contains now.** Run `git fetch <remote>` first: `<remote>/<default>` is stale until you do. Then read `git log <remote>/<default>`, rather than assuming another branch has merged. After a rebase, run `git diff --check <remote>/<default>` and search for `<<<<<<<` before you push.
- **If a rebase goes wrong, reset to the branch tip you had before** (`git reflog`) and redo it. Nothing pushed means nothing lost.
- **After a rebase, update the commit hashes the PR description quotes**, in the opened PRs and the queued bodies alike, including the line that quotes the head. Map old to new by commit subject only within each branch's own range: fixes carried across a stack share a subject, and a repo-wide map sends them all to one commit.

## Reviewers

- **Give each reviewer a report file the writer can read.** A sandboxed reviewer may be unable to write to the system temporary folder, so use a path under `/tmp`. Tell the reviewer the exact path in the prompt.
- **Run a PR reviewer in a disposable clone, never in a working tree you are using.** A reviewer that checks out the PR branch changes the files under your feet.
- **Keep the machine awake for the whole run.** A reviewer that runs as a local agent stalls while the machine sleeps, and its script reports a timeout or an agent that never started. On macOS, start the session under `caffeinate -i`, or ask the owner to turn sleep off before they leave.
- **End a reviewer's session when its PR merges.** An old session, such as a terminal tab or pane, keeps its agent and model. A later run can reuse it and get the wrong reviewer.
- **Several reviewers at once use a lot of memory.** Local services, such as a database container, can be killed. Watch for that and restart them.

## Your own tools

- **Leave a script alone while a running job uses it.** Bash reads a script as it runs, so an edit can break a job that is still running it. Copy the script first, or wait for the job to end.

## Your own records

- **Blame a tool only after you have checked your own actions.** If an earlier log entry named the wrong cause, add a `CORRECTION` entry that names the real one.
- **Claim only what has merged** (way-of-working rule 5). In the log, work in an open PR is pending, with its number.
