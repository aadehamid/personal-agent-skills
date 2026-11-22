# Personal agent skills

My own skills for Claude Code and other agents. Each skill is a folder with a `SKILL.md`, filed under a category.

## Home Repo

This repository is also my Home Repo: the place I start an agent session when a
task spans more than one repo. `AGENTS.md` holds an "Other Repos" section that
maps each repo to its local path, with a "clone from <remote> if missing"
fallback, so an agent started here can reach any of them without duplicating
skills or steering.

Start a session here for cross-repo work, or when I want the full shared context
in one place. For work in a single repo, start in that repo as usual. The
skills install globally, so this repo is a map and a shared home, not a daily
requirement.

## Skills

| Category | Skill | What it does |
|---|---|---|
| engineering | [way-of-working](skills/engineering/way-of-working/SKILL.md) | Hamid's engineering standard for agent work on any repo: recorded decisions, PRs for every change, checks before every push, shared deterministic tools and guardrails, and a retro loop that improves the standard. |
| engineering | [night-run](skills/engineering/night-run/SKILL.md) | Lets an agent work through a goal while you are away. You approve a written brief before you leave; the agent ships each item through the pull-request loop, logs each decision it makes for you, and ends with a morning summary. |
| planning | [project-discovery](skills/planning/project-discovery/SKILL.md) | Turns an idea or existing project into a tailored documentation package, with guided discovery, reference assessment, interactive or batch drafting, approval tracking, and review. |
| writing | [clear-writing](skills/writing/clear-writing/SKILL.md) | Writes and edits plain, clear prose for people. Uses a subset of ASD-STE100, an anti-AI-tell pattern list, a re-pitch mode for messages that did not land, and a calibrate mode that tunes the rules from past sessions. |
| writing | [unslop](skills/writing/unslop/SKILL.md) | Alias: catches calls to unslop (for example from pstack) and routes them to clear-writing. |
| writing | [wait-what](skills/writing/wait-what/SKILL.md) | Type `/wait-what` when Claude's last message did not make sense. Runs clear-writing's re-pitch mode. |
| data | [ontology](skills/data/ontology/SKILL.md) | Builds a business ontology from scratch in gated steps (W3C stack), reuses public ontologies by mapping, and hands the result to ontology-to-lpg for a Neo4j projection. |
| data | [ontology-visualization](skills/data/ontology-visualization/SKILL.md) | Builds and maintains readable ontology viewers across domains, with a playbook for source fidelity, layers, connections, usability and updates after each release. |
| data | [ontology-to-lpg](skills/data/ontology-to-lpg/SKILL.md) | Projects a W3C ontology into a Neo4j property graph in gated steps: design rules, released inputs with listed gaps, check, reason, load with n10s, and a verify step that proves the graph is a complete, repeatable copy; then a review of the loaded graph against Neo4j's modeling anti-patterns, and the shapes as a Data Modeling MCP model for Arrows and Mermaid. `run_projection.py` runs it all, with the copy to Aura, Jena and Databricks round trips and a rebuild from any store, from one run configuration, for released packages or plain RDF files. |
| data | [rdf-store](skills/data/rdf-store/SKILL.md) | Loads RDF releases into Jena Fuseki, any SPARQL 1.1 store or a Databricks Delta table, one named graph per file, and proves nothing was lost by a round trip compared with RDF Dataset Canonicalization (RDFC-1.0). |
| data | [ontology-change](skills/data/ontology-change/SKILL.md) | Takes a filled change form for a released ontology through the release's own commands to a checked, committed and loaded release, with the plan shown and a yes before each apply. It holds no command: every command comes from the release's handout. |
| research | [knowledge-ingest](skills/research/knowledge-ingest/SKILL.md) | Turns saved sources into a linked knowledge base (Obsidian vault or wiki), one article or a backlog of hundreds, and resumes where the last session stopped. Every claim must trace to a source; a mechanical gate (the `kb` CLI) and an independent review catch what the author misses. |

Installed from elsewhere, not stored here:

| Skill | Install | What it does |
|---|---|---|
| retro | `npx skills add mattpocock/skills --skill retro -g` | Reviews a session and ranks improvements to the agent environment. |
| writing-for-agents | `npx skills add mattpocock/skills --skill writing-for-agents -g` | Writing documents an agent reads: skills, CLAUDE.md, AGENTS.md. Clear-writing hands those to it. |

## Layout

```
skills/<category>/<skill-name>/
  SKILL.md        required. The only file agents load by default.
  README.md       required. For people: what each file does, plus a Status section with open items. Agents never read it.
  SOURCES.md      required if the skill draws on outside work: what was taken, versions, how to check for updates.
  upstream/       local-only snapshots of those sources (gitignored), so an update check is a diff.
  references/     docs the skill reads when needed
  scripts/        code the skill runs
  cli/            a command-line tool the skill uses (Python package with pyproject.toml), installed by --tools
  evals/          test prompts, inputs, and grader
config/           snippets to install outside the repo, such as the CLAUDE.md line
workspaces/       eval run outputs (not tracked)
```

Category names are short and lowercase: `writing`, `coding`, `data`, `engineering`, `ops`, `research`. Add a new one when no existing category fits.

## Install on a machine

```bash
git clone https://github.com/aadehamid/personal-agent-skills.git
cd personal-agent-skills
./scripts/link-skills.sh --global --tools
npx skills add mattpocock/skills --skill writing-for-agents --skill retro -g
./scripts/update-pstack.sh   # optional: pstack from cursor/plugins, without its unslop
```

Configure the pre-push hook following the conditions and command in
[AGENTS.md](AGENTS.md).

Check that `retro/SKILL.md` and `writing-for-agents/SKILL.md` exist in both
`~/.agents/skills` and your agent's skill directory. A Claude plugin cache alone
does not make a skill discoverable in Codex. On this machine, both were installed
from `mattpocock/skills` revision `b0618bc436ad893b3c5e84e55fba86586d34a404`
and linked into Codex's skills directory. New sessions may need to refresh their
skill catalog.

`--tools` installs each skill's command-line tool with `uv tool install --editable` (needs [uv](https://docs.astral.sh/uv/)). Today that is `kb`, the validation CLI for knowledge-ingest. A skill that needs per-project setup says so in the "Set up on a machine" section of its README.

`--global` adds `config/global-snippet.md` to every agent's global instruction file — Claude's `~/.claude/CLAUDE.md`, Codex's `~/.codex/AGENTS.md`, and any other agent root that holds a `CLAUDE.md`, `AGENTS.md`, `GEMINI.md` or `.goosehints`. That tells each agent to load clear-writing whenever it writes prose, and way-of-working before changing a repo. Without it, agents rarely load the skills on their own. The script does not add the sections twice. `--claude-md` is kept as an alias.

The snippet's third section is for pstack's poteto-mode. It points agents at `~/.agents/poteto-mode-split.md`, which `--global` links to `config/poteto-mode-split.md`. That file sets the workflow from deciding to shipping, sized to the change, and says which work poteto-mode leads and which belongs to clear-writing, way-of-working and night-run. Cursor keeps its global rules in its settings, so the script cannot reach it. Paste the poteto-mode section under Cursor Settings › Rules, or keep it in `~/.cursor/rules/`, where pstack puts its own rules.

To pick up work on another machine, also read the "Status" section in each skill's README. It lists the open items. To check sources for updates, first rebuild the local `upstream/` snapshots as described in that skill's `SOURCES.md`.

The script symlinks each skill into `~/.agents/skills/`, then into the skills folder of every agent on the machine. It finds agent folders by looking for existing links into `~/.agents/skills`, which is how `npx skills add -g` installs skills. `~/.claude/skills` is always included. Re-run it after you add a skill or install a new agent. Use `--dry-run` to see what it would change.

`update-pstack.sh` clones or pulls `cursor/plugins` into `~/Projects/cursor-plugins` and links pstack's skills into `~/.agents/skills`, `~/.claude/skills` and, when Hermes is installed, `~/.hermes/skills`, leaving out pstack's unslop (the alias here replaces it). It leaves alone any file, folder or link it did not create. It also links pstack's subagents into `~/.claude/agents`, and points any Cursor pstack plugin's unslop at the alias. Re-run it to update pstack. To keep the old `update-pstack` command, run `ln -s "$PWD/scripts/update-pstack.sh" ~/.local/bin/update-pstack`.

## Add a skill

1. Create `skills/<category>/<skill-name>/SKILL.md`.
2. Add a `README.md` next to it with a table of every file: its path, who reads it (agent or you), and what it does. Use [clear-writing's README](skills/writing/clear-writing/README.md) as the model. Do not link to the README from `SKILL.md`, or agents will start to read it.
3. If the skill draws on outside sources, add `SOURCES.md` and local `upstream/` snapshots. Use clear-writing's as the model. Restate outside material in your own words and link to it. Do not commit third-party text unless its license allows it.
4. Run `./scripts/link-skills.sh`.
5. Add a row to the table above.
