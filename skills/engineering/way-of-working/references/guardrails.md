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
- Before you set `core.hooksPath`, look for hooks it would disable: run `git config core.hooksPath` and list `.git/hooks` without the `.sample` files, and check for tools that install hooks (Git LFS, pre-commit). If none exist, point `core.hooksPath` at a tracked `scripts/hooks` folder. If some do, call the check script from the existing pre-push hook instead. Then push once to confirm both the old hooks and the check run.
- Pin CI actions to tags that exist (check with `gh api repos/<owner>/<repo>/git/ref/tags/<tag>`).

## Mechanical rules in code, judgement in a review file

Classify each rule. A rule a script can check (a figure, a status match, a required section, a file pattern) goes in the check script. A rule that needs judgement (a claim matches its record, a change landed, the right population was counted) goes in a short review standards file the reviewer reads, each rule with the incident that taught it. The review file references the instruction file's requirements; it does not restate them.

## Done when

The project has the shared tool with tests, the check script running in CI and the hook, and a review standards file holding only judgement rules.
