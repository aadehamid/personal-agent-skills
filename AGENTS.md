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
script. Before installing the tracked pre-push hook, follow the conditions in
`skills/engineering/way-of-working/references/guardrails.md`. When those
conditions permit installation, run `git config core.hooksPath scripts/hooks`.

Use `scripts/link-skills.sh --dry-run` to inspect the installation inventory.
Run installation from the maintained checkout after the change lands, so links
do not depend on a temporary worktree. Leave unrelated files and worktrees alone.

## Other Repos

This is the Home Repo: run the agent from here and reach the repos below through
these pointers. If a local path does not exist, clone it from its remote. Use a
`git worktree` when several agents work the same repo at once.

- **downstream_oil_and_gas_ontology_release** (published release output of enterprise-performance-model, EPM 1.0 — read-only, regenerate from EPM): `~/Dropbox/1_PROJECTS/downstream_oil_and_gas_ontology_release`. Clone from `github.com/aadehamid/downstream_oil_and_gas_ontology_release` if missing.
- **enterprise-performance-model** (Enterprise Performance Model — source of truth for the downstream release): `~/Dropbox/1_PROJECTS/Enterprise Performance Model`. Clone from `github.com/aadehamid/enterprise-performance-model` if missing. Read its `AGENTS.md` first.
- **scada_harmonization** (ISA-95 SCADA harmonization → UNS): `~/Dropbox/1_PROJECTS/scada_harmonization`. Clone from `github.com/aadehamid/scada_harmonization` if missing. Read its `AGENTS.md` first.
- **enterprise-people-graph** (LIONG people graph): `~/Dropbox/1_PROJECTS/enterprise-people-graph`. Clone from `github.com/aadehamid/enterprise-people-graph` if missing. Read its `AGENTS.md` first.
- **Engineering_Drawing_to_Graph** (engineering drawing → graph): `~/Dropbox/1_PROJECTS/Engineering_Drawing_to_Graph`. Clone from `github.com/aadehamid/Engineering_Drawing_to_Graph` if missing. Read its `AGENTS.md` first.
- **enterprise-context-engineering** (enterprise context engineering): `~/Dropbox/1_PROJECTS/Enterprise Context Engineering`. Clone from `github.com/aadehamid/enterprise-context-engineering` if missing.
