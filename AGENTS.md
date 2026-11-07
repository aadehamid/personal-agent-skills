# Working in personal-agent-skills

Before writing for a person, load `clear-writing`, including for replies, status
updates and review descriptions. Before changing the repository, load
`way-of-working`. These rules apply to subagents too. The maintained skills are
under `skills/writing/clear-writing/` and `skills/engineering/way-of-working/`.
For agent-facing documents, also use `writing-for-agents` when available.

Start with `README.md` for the layout and skill packaging requirements.
Keep reusable methods independent of a consuming project's decisions and data.
Use `REVIEW_STANDARDS.md` for review and `docs/decisions/README.md` when a change
depends on an owner's decision.

Every change goes through the review and pull-request process in
`way-of-working`. Run `scripts/check.sh` before each push. CI calls the same
script. In a fresh clone, install the tracked pre-push hook with
`git config core.hooksPath scripts/hooks`; preserve an existing shared hook
configuration as that skill requires.

Use `scripts/link-skills.sh --dry-run` to inspect the installation inventory.
Run installation from the maintained checkout after the change lands, so links
do not depend on a temporary worktree. Leave unrelated files and worktrees alone.
