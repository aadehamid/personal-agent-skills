# relate-project-memory

Gives a repository one long-term memory that every coding agent shares: Claude Code, Codex, Cursor, Gemini CLI, Kimi, Pi and the rest. The memory is a Relate graph. Agents read it at session start and save decisions, corrections and findings through one script, `scripts/memory.sh`, which validates every save, writes it in one transaction, and keeps the history of each corrected fact.

An installer does the mechanical part and keeps projects current. The skill tells the agent how to adapt the rest to the project and take the change through the project's own rules.

This README is for people. Agents read `SKILL.md` and the files it points to.

## Files

| Path | Read by | What it does |
|---|---|---|
| `SKILL.md` | agent | Steps to set up memory in a new project or update an existing one, and the hazards met on the first two projects. |
| `scripts/install.py` | agent runs it | Installs, updates (`--update`) or checks (`--check`) the setup in a repository. It replaces the files the skill owns and never overwrites the project's own files. |
| `scripts/test_install.py` | `scripts/check.sh` | Tests for the installer. The last test installs into a fresh repository and runs the installed memory tests there. |
| `templates/memory.sh` | installed | The memory command: `remember`, `recall`, `about`, `history`, `asof`, `slots`, `brief`, `check`, `init`, `path`. |
| `templates/memory/schema.cypher` | installed | Constraints and indexes for `Entity`, `Episode` and `Fact`. |
| `templates/memory/remember.cypher` | installed | Writes one episode in a transaction, with the id guards and supersession. |
| `templates/test_memory.py` | installed | 41 tests of `memory.sh`. Eight of them run without Relate, so CI runs them too. |
| `templates/project-memory-SKILL.md` | installed once | The project's own `project-memory` skill, with an `ADAPT` marker for the project's boundaries. |
| `SOURCES.md` | you | Where the design came from. |
| `README.md` | you | This file. |

## Set up on a machine

Each machine needs `relate` (`curl -sSfL https://relatedb.ai/install.sh | bash`) and `python3` 3.11 or later. The store lives in each project's git-ignored `.relate-memory/` folder. Dropbox syncs it between machines, so agents should save from one machine at a time; the script stops if Dropbox leaves conflicted copies.

## Status

- Built from three setups on 2026-11-27: Pearland Petroleum Corporation (ADR-0058), tar-twin-frozen-worklist-demo (D17, PRs #17 and #18), and this skill's templates, which add the follow-ups Pi raised on tar-twin PR #17: a closed fact's range never ends before it starts, and slots and keys must be lowercase.
- `asof` comes from the cookbook recipe "Know what an agent believed, and when" (<https://relatedb.ai/cookbook/bitemporal-decisions/index.md>).
- Open: the Dropbox conflict scan matches only the English `conflicted copy` file name. There is no vector recall, because the agents share no embedding model.
