# Personal agent skills

My own skills for Claude Code and other agents. Each skill is a folder with a `SKILL.md`, filed under a category.

## Skills

| Category | Skill | What it does |
|---|---|---|
| writing | [clear-writing](skills/writing/clear-writing/SKILL.md) | Writes and edits plain, clear prose for people. Uses a subset of ASD-STE100, an anti-AI-tell pattern list, a re-pitch mode for messages that did not land, and a calibrate mode that tunes the rules from past sessions. |
| writing | [wait-what](skills/writing/wait-what/SKILL.md) | Type `/wait-what` when Claude's last message did not make sense. Runs clear-writing's re-pitch mode. |
| research | [knowledge-ingest](skills/research/knowledge-ingest/SKILL.md) | Turns saved sources into a linked knowledge base (Obsidian vault or wiki), one article or a backlog of hundreds, and resumes where the last session stopped. Every claim must trace to a source; a mechanical gate (the `kb` CLI) and an independent review catch what the author misses. |

Installed from elsewhere, not stored here:

| Skill | Install | What it does |
|---|---|---|
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

Category names are short and lowercase: `writing`, `coding`, `data`, `ops`, `research`. Add a new one when no existing category fits.

## Install on a machine

```bash
git clone https://github.com/aadehamid/personal-agent-skills.git
cd personal-agent-skills
./scripts/link-skills.sh --claude-md --tools
npx skills add mattpocock/skills --skill writing-for-agents -g
```

`--tools` installs each skill's command-line tool with `uv tool install --editable` (needs [uv](https://docs.astral.sh/uv/)). Today that is `kb`, the validation CLI for knowledge-ingest. A skill that needs per-project setup says so in the "Set up on a machine" section of its README.

`--claude-md` adds `config/claude-md-snippet.md` to `~/.claude/CLAUDE.md`. That line tells Claude to load clear-writing whenever it writes prose. Without it, Claude rarely loads the skill on its own. The script does not add the line twice.

To pick up work on another machine, also read the "Status" section in each skill's README. It lists the open items. To check sources for updates, first rebuild the local `upstream/` snapshots as described in that skill's `SOURCES.md`.

The script symlinks each skill into `~/.agents/skills/`, then into the skills folder of every agent on the machine. It finds agent folders by looking for existing links into `~/.agents/skills`, which is how `npx skills add -g` installs skills. `~/.claude/skills` is always included. Re-run it after you add a skill or install a new agent. Use `--dry-run` to see what it would change.

## Add a skill

1. Create `skills/<category>/<skill-name>/SKILL.md`.
2. Add a `README.md` next to it with a table of every file: its path, who reads it (agent or you), and what it does. Use [clear-writing's README](skills/writing/clear-writing/README.md) as the model. Do not link to the README from `SKILL.md`, or agents will start to read it.
3. If the skill draws on outside sources, add `SOURCES.md` and local `upstream/` snapshots. Use clear-writing's as the model. Restate outside material in your own words and link to it. Do not commit third-party text unless its license allows it.
4. Run `./scripts/link-skills.sh`.
5. Add a row to the table above.
