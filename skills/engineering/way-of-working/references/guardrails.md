# Guardrails

Read this when a project lacks a shared tool, a check script, CI or a review standards file, or when you are about to write a one-off script to count or classify something.

## A project with nothing yet

A repository with no `AGENTS.md`, no check script and no CI is not a reason to work without them. It is the case this skill exists for, and building them is the first work on such a repository. One concern per pull request, in this order:

Start at the first step you do not find, not at step 1. A repository that already has `AGENTS.md` resumes at step 2, and only the steps still missing are the work. **The order is not finished until every step exists**: a session that lands one of them has not discharged it, and the next session picks up at the first step still missing.

1. **`AGENTS.md`.** The project's working rules and pointers. Keep it short: it points at other files rather than restating them. Start from the session-start list in `SKILL.md`, keep what applies, drop what does not, and add what this project needs.
2. **`scripts/check.sh`, CI and the pre-push hook.** One script running every mechanical gate, called by both CI and the hook, so a local run and a CI run cannot differ. The sections below have the detail and the conditions for installing the hook. **The hook's install line goes into the `AGENTS.md` you wrote at step 1** — the project's own file, so a fresh clone of that project can wire the hook. It never goes into this skill: the install line names one project's path, and every other repository loads this skill.
3. **The shared tool** for the figures the project's documents quote, with its tests.
4. **A review standards file.** Near-empty at first. It grows from findings a reviewer actually made, each with the incident that taught it.
5. **Decision records.** A folder with an index, and agreement with the owner on how a skipped question is read (`references/deciding.md`).

**The first pull request is the exception.** Rule 3 and `before-push.md` require the check script to pass before every push, and on a bare repository there is not one yet — an agent that treats this as absolute cannot push at all. Until step 2 lands, the check before a push is the project's own build and test command; if the project has none, say so in the pull request body rather than implying one ran. Nothing else about the flow changes: one concern, a pull request, the owner merges.

The check script starts with the gates the project already has. It gains the shared tool's consistency checks when step 3 lands, not before — the tool does not exist yet, and a check script that names a missing tool fails on its own first run.

Say what you are about to do and why before the first of these lands. An owner who did not ask for a check script is owed the reason, and may have one already.

The work you were asked to do is not lost by this: it waits behind the guardrails, and lands on a repository where every later change is checked.

## Shared, deterministic tools

Every agent that writes its own counting script counts differently, and each difference becomes a wrong figure in a document. Build one tool in the repo instead, and make every agent use it.

- **What it answers:** the figures documents quote, one item's status, the rows in one work item, a repo-wide search that also matches text split across lines, and consistency checks such as decision records against their index.
- **How it computes:** run the project's existing scripts as they are (in a temporary copy if they write files) rather than reimplementing their logic. Define each population once, in code, from the source file's structure.
- **What it prints:** the files it read and the commit, so a PR body can quote the line; `--json` for agents.
- **How it is trusted:** tests that pin today's figures, tests that break the input on purpose (reformatting, citations, wrapped lists) and expect the same answer, and a test that the tool never writes to the repo.

Before writing any script to count or classify, check whether the shared tool already answers the question. If it does not, extend the tool, not a private script.

## One check script, run everywhere

- One script runs every mechanical check: the project's gates, all tests, the shared tool's consistency checks, and a test that published figures in documents match the tool.
- It fails if the checks change the working tree. Comparing content hashes is not enough by itself: a guard built that way passed every ordinary run while missing four changes — an untracked file rewritten (names were recorded, not contents), a file named `-` (a bare `-` operand is read as standard input even after `--`), a dropped executable bit, and an index change. Snapshot four things and fail on any difference, each pinned to what it has to observe:
  - **Contents.** Open each non-ignored path, tracked or untracked, and hash the bytes read. Do not hand the path to a hasher that may read standard input: `sha256sum -- -` hashes empty input, so an untracked file named `-` can be rewritten with the snapshot unchanged.
  - **Filesystem entry, not the file behind it.** An untracked script that loses its execute bit changes neither its contents nor git's status. A symlink retargeted to a different path holding the same bytes changes neither, because opening it follows the link. Snapshot the entry type, the permission bits, and for a symlink the link text itself — `readlink` on the link, not a read through it.
  - **Index blobs.** `git status` records a change *category*, not a blob id: a staged blob can be replaced while the porcelain letter is already `MM`. Snapshot the blob id and mode of every index entry (`git ls-files -s`).
  - **git's own view of status**, which covers renames and staging the four above do not name directly.

  A read that fails **aborts the comparison**. Skipping the path drops it from both snapshots, so they match, and a check that rewrote a file the guard could not read still passes. A language where reads raise gives that for free; in a shell the status must be taken from the read itself, because a pipeline's status is its last command's, not the failing one's.
- CI runs it on every PR. A pre-push hook runs it locally. **Give the hook a way to be installed** — a `scripts/bootstrap.sh` that sets `core.hooksPath` and installs anything the checks need, or, if the project prefers fewer files, the one-line `git config` command written into the project's `AGENTS.md`. Either way say where it is, and put it in the session-start steps of the project's `AGENTS.md` (step 2 of the order above): a hook nobody installs is a hook that never runs, and a fresh clone is exactly where that happens.
- Set up the hook only in the simple case, where all of these hold: `git config core.hooksPath` prints nothing; `ls "$(git rev-parse --git-path hooks)"` shows only `*.sample` files; no tool installs hooks (Git LFS, pre-commit); and `git worktree list` shows one worktree. In any other case, change no hook configuration: report what you found and ask the owner how to wire the check in, because an existing or shared hook setup can serve other worktrees or repositories.
- In the simple case: add `scripts/hooks/pre-push` that runs the check script, track it as executable (`git update-index --chmod=+x scripts/hooks/pre-push`; `git ls-files -s` shows `100755`), and set `git config core.hooksPath scripts/hooks`. Git silently skips a missing or non-executable hook, so a successful push proves nothing.
- Prove the hook runs: `git hook run pre-push` (Git 2.36 or later) must print the check script's output and exit 0. Then make one check fail on purpose and confirm `git hook run pre-push` exits non-zero; restore it.
- Pin CI actions to tags that exist (check with `gh api repos/<owner>/<repo>/git/ref/tags/<tag>`).

## Mechanical rules in code, judgement in a review file

Classify each rule. A rule a script can check (a figure, a status match, a required section, a file pattern) goes in the check script. A rule that needs judgement (a claim matches its record, a change landed, the right population was counted) goes in a short review standards file the reviewer reads, each rule with the incident that taught it. The review file references the instruction file's requirements; it does not restate them.

## Done when

The project has the shared tool with tests, the check script running in CI and the hook, and a review standards file holding only judgement rules.
