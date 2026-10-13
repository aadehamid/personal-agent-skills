# Hazards

Each of these cost time on a real unsupervised run. Read this file before the first rebase, the first test run inside a worktree, and the first reviewer you start.

## Git state

- **Clear `GIT_*` before running tests by hand inside a worktree.** A pre-push hook sets `GIT_DIR`. A test that makes a temporary repository with that variable set writes into the real one: a commit lands on your branch, and `git init` writes `core.worktree` and `user.*` into the shared `.git/config`. Run tests with `env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE`, and make the project's own tests clear these variables themselves.
- **After any test run you started by hand, read `git config --local --list`.** It should hold no `core.worktree` and no `user.name` or `user.email` you did not set. A stray identity silently changes the author of every later commit.
- **Check the author before each push:** `git log --format='%h %an <%ae>' origin/main..`. Fix a wrong author on an unpushed branch with `git rebase --exec 'git commit --amend --no-edit --reset-author' origin/main`. Commits already on `main` stay as they are; ask the owner in the morning summary.
- **During a rebase conflict, resolve the files and run `git rebase --continue`.** Leave `git commit --amend` until the rebase has finished: during a conflict it can rewrite a commit that is already on `main`.
- **Rebase onto what `main` contains now.** Read `git log origin/main` first, rather than assuming another branch has merged. After a rebase, run `git diff --check origin/main` and search for `<<<<<<<` before you push.
- **If a rebase goes wrong, reset to the branch tip you had before** (`git reflog`) and redo it. Nothing pushed means nothing lost.
- **After a rebase, update the commit hashes the PR description quotes.**

## Reviewers

- **Give each reviewer a report file the writer can read.** A sandboxed reviewer may be unable to write to the system temporary folder, so use a path under `/tmp`. Tell the reviewer the exact path in the prompt.
- **Run a PR reviewer in a disposable clone, never in a working tree you are using.** A reviewer that checks out the PR branch changes the files under your feet.
- **Close a reviewer's tab when its PR merges.** Old tabs keep their agent and model. A later run can reuse a stale tab and get the wrong reviewer.
- **Several reviewers at once use a lot of memory.** Local services, such as a database container, can be killed. Watch for that and restart them.

## Your own records

- **Blame a tool only after you have checked your own actions.** If an earlier log entry named the wrong cause, add a `CORRECTION` entry that names the real one.
- **Claim only what has merged.** In the log and the summary, work in an open PR is pending, with its number.
