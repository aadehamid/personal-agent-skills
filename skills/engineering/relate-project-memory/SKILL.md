---
name: relate-project-memory
description: >-
  Sets up or updates shared long-term memory in a repository: one Relate graph that every coding agent (Claude Code, Codex, Cursor, Gemini, Kimi, Pi) reads and saves through scripts/memory.sh. Use when asked to give a project memory, set up Relate memory for all agents, or bring an existing memory setup up to date.
---

# Relate project memory

`scripts/install.py` does the mechanical work. It copies the files this skill owns into the project and keeps them current: `scripts/memory.sh`, the Cypher files and `test_memory.py`. It creates the project's own files once: the `project-memory` skill, its Claude link, the Claude `SessionStart` hook, Gemini's `AGENTS.md` setting and the `.gitignore` lines. Your work is the part a script cannot do: adapting the project's text and taking the change through the project's own rules.

The project's rules win. Read its `AGENTS.md`, its decision records, its check script and its review rules before you change anything, and ship through its pull-request process.

## Prerequisites

`relate --version` runs, and `python3 --version` is 3.11 or later. If relate is missing: `curl -sSfL https://relatedb.ai/install.sh | bash`.

## Set up a new project

1. **Branch** from current `main`, as the project's rules say.
2. **Write the checks first if the project asks for that.** Run step 3's command with `--dry-run` added to see the files, then copy only `templates/test_memory.py` into the tests folder with `cp` and run it, so the PR can show it failing before the code exists. The installer accepts that copy in step 3, because it matches the template.
3. **Install:**

   ```bash
   python3 <this skill>/scripts/install.py <repo> --decision-ref "<D17 or ADR-0058>" --decision-records "<\`docs/decisions.md\`>"
   ```

   `--decision-ref` names the decision record you write in step 5. `--decision-records` says where the project keeps decisions. The tests go in `tests/` when that folder exists, otherwise `scripts/`; `--tests-dir` overrides.
4. **Adapt the project skill** at `.agents/skills/project-memory/SKILL.md`. Replace its `<!-- ADAPT ... -->` comment with the project's own boundaries from its `AGENTS.md`: restricted data, names that stay out, synthetic-data rules, date conventions. Keep the rest.
5. **Record the decision** the way the project records decisions, quoting the owner's request word for word. State the choices: one script for every save, the git-ignored `.relate-memory/` store at the main checkout's root, full-text recall, and Dropbox use from one machine at a time when the repo lives in Dropbox.
6. **Point `AGENTS.md` at it.** Add one line or session-start step: read memory with `scripts/memory.sh brief` at session start, save decisions, corrections and findings before finishing, and read `.agents/skills/project-memory/SKILL.md` before the first save.
7. **Wire the tests into the check script** if it does not already find `test_memory.py`. They run with `unittest` or `pytest`. Most CI runners have no `relate`, so 29 of the 37 tests skip there. The eight validation, path and help tests still run.
8. **Prove it.** Run, in order:
   - `python3 <this skill>/scripts/install.py <repo> --check` exits 0.
   - The project's check script passes.
   - Save a first memory that records the setup: a `handoff` episode with today's date and time, your agent's name and the branch, in the shape of the project skill's example. Write your own ids and text; the example's are placeholders. If Codex is installed, save it from inside Codex's sandbox, which proves a sandboxed agent can write the real store:

     ```bash
     cd <repo> && codex sandbox -P :workspace -c x=1 -C . -- scripts/memory.sh remember <episode.json>
     ```

9. **Ship** through the project's PR process.

Done when `install.py --check` exits 0, the project's checks pass, the first memory is saved, and the PR has merged.

## Update an existing project

1. Branch, then run `install.py <repo> --update`. It replaces the tool-owned files and never touches the project's own files. To add a project file that is missing, such as the Gemini setting, run a plain install afterwards; it adds only what is missing.
2. Compare the project skill with `templates/project-memory-SKILL.md` and port what changed in the template: new rules, commands or limits. Keep the project's adapted sections.
3. A setup from before this skill may use another environment variable for the store path, such as `PPC_MEMORY_DB`. The script now reads `PROJECT_MEMORY_DB`. Search the project for the old name and update every mention.
4. Run `install.py <repo> --check`, then the project's checks, and ship through its PR process.

Done when `install.py --check` exits 0, the project's checks pass, and the PR has merged.

## Hazards

- **Keep the store out of `.git`.** Codex's workspace sandbox blocks every write inside `.git`, so a store there can be read but never saved.
- **Link the skill file, not its folder.** Some repositories' tree guards reject folder symlinks. The installer already links the file.
- **Pinned counts move.** A project that pins its number of decisions or files in tests needs those tests updated with the new decision record.
- **Project text rules apply.** Some projects ban em and en dashes or check links in markdown. Run their doc checks on the adapted skill.
- **Change the templates here, not in a project.** A fix made in a project's `scripts/memory.sh` is lost on the next `--update`, and `--check` reports the file as out of date.
