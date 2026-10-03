# Personal agent skills

My own skills for Claude Code and other agents. Each skill is a folder with a `SKILL.md`, filed under a category.

## Skills

| Category | Skill | What it does |
|---|---|---|
| writing | [clear-writing](skills/writing/clear-writing/SKILL.md) | Writes and edits plain, clear prose. Uses a subset of ASD-STE100, the unslop anti-AI-tell rules, and a calibrate mode that tunes the rules from past sessions. |

## Layout

```
skills/<category>/<skill-name>/
  SKILL.md        required. The only file agents load by default.
  README.md       required. For people: what each file does. Agents never read it.
  SOURCES.md      required if the skill draws on outside work: what was taken, versions, how to check for updates.
  upstream/       local-only snapshots of those sources (gitignored), so an update check is a diff.
  references/     docs the skill reads when needed
  scripts/        code the skill runs
  evals/          test prompts, inputs, and grader
workspaces/       eval run outputs (not tracked)
```

Category names are short and lowercase: `writing`, `coding`, `data`, `ops`, `research`. Add a new one when no existing category fits.

## Install on a machine

```bash
git clone https://github.com/aadehamid/personal-agent-skills.git
cd personal-agent-skills
./scripts/link-skills.sh
```

The script symlinks each skill into `~/.agents/skills/`, then into the skills folder of every agent on the machine. It finds agent folders by looking for existing links into `~/.agents/skills`, which is how `npx skills add -g` installs skills. `~/.claude/skills` is always included. Re-run it after you add a skill or install a new agent. Use `--dry-run` to see what it would change.

## Add a skill

1. Create `skills/<category>/<skill-name>/SKILL.md`.
2. Add a `README.md` next to it with a table of every file: its path, who reads it (agent or you), and what it does. Use [clear-writing's README](skills/writing/clear-writing/README.md) as the model. Do not link to the README from `SKILL.md`, or agents will start to read it.
3. If the skill draws on outside sources, add `SOURCES.md` and local `upstream/` snapshots. Use clear-writing's as the model. Restate outside material in your own words and link to it. Do not commit third-party text unless its license allows it.
4. Run `./scripts/link-skills.sh`.
5. Add a row to the table above.
