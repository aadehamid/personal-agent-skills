# Guardrails

Read this when a project lacks a shared tool, a check script, CI or a review standards file, or when you are about to write a one-off script to count or classify something.

## Shared, deterministic tools

Every agent that writes its own counting script counts differently, and each difference becomes a wrong figure in a document. Build one tool in the repo instead, and make every agent use it.

- **What it answers:** the figures documents quote, one item's status, the rows in one work item, a repo-wide search that also matches text split across lines, and consistency checks such as decision records against their index.
- **How it computes:** run the project's existing scripts as they are (in a temporary copy if they write files) rather than reimplementing their logic. Define each population once, in code, from the source file's structure.
- **What it prints:** the files it read and the commit, so a PR body can quote the line; `--json` for agents.
- **How it is trusted:** tests that pin today's figures, tests that break the input on purpose (reformatting, citations, wrapped lists) and expect the same answer, and a test that the tool never writes to the repo.

Before writing any script to count or classify, check whether the shared tool already answers the question. If it does not, extend the tool, not a private script.

## One check script, run everywhere

- One script runs every mechanical check: the project's gates, all tests, the shared tool's consistency checks, and a test that published figures in documents match the tool.
- It fails if the checks change the working tree (compare content hashes before and after, in a language where any read error raises).
- CI runs it on every PR. A pre-push hook runs it locally; agent bootstrap scripts set the hook up.
- Set up the hook only in the simple case, where all of these hold: `git config core.hooksPath` prints nothing; `ls "$(git rev-parse --git-path hooks)"` shows only `*.sample` files; no tool installs hooks (Git LFS, pre-commit); and `git worktree list` shows one worktree. In any other case, change no hook configuration: report what you found and ask the owner how to wire the check in, because an existing or shared hook setup can serve other worktrees or repositories.
- In the simple case: add `scripts/hooks/pre-push` that runs the check script, track it as executable (`git update-index --chmod=+x scripts/hooks/pre-push`; `git ls-files -s` shows `100755`), and set `git config core.hooksPath scripts/hooks`. Git silently skips a missing or non-executable hook, so a successful push proves nothing.
- Prove the hook runs: `git hook run pre-push` (Git 2.36 or later) must print the check script's output and exit 0. Then make one check fail on purpose and confirm `git hook run pre-push` exits non-zero; restore it.
- Pin CI actions to tags that exist (check with `gh api repos/<owner>/<repo>/git/ref/tags/<tag>`).

## Mechanical rules in code, judgement in a review file

Classify each rule. A rule a script can check (a figure, a status match, a required section, a file pattern) goes in the check script. A rule that needs judgement (a claim matches its record, a change landed, the right population was counted) goes in a short review standards file the reviewer reads, each rule with the incident that taught it. The review file references the instruction file's requirements; it does not restate them.

## Done when

The project has the shared tool with tests, the check script running in CI and the hook, and a review standards file holding only judgement rules.
