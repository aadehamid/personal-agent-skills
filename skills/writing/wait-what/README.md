# wait-what

Type `/wait-what` when Claude's last message did not make sense to you. Claude explains the same content again: context first, then the point in short sentences, in your project's own terms, ending with what you need to decide or do.

This README is for people. Agents do not read it.

## Files

| Path | Read by | What it does |
|---|---|---|
| `SKILL.md` | agent, only when you type `/wait-what` | Hands off to the re-pitch mode of clear-writing, with a short fallback if clear-writing is not installed. `disable-model-invocation: true` means the agent never loads it on its own, so its description costs no context. |
| `README.md` | you | This file. |

You do not need the command. Saying "wait what" or "I don't follow" also triggers re-pitch mode through clear-writing. The command is the guaranteed path.

## Sources

Adapted from Matt Pocock's `wait-what` skill (MIT license): https://github.com/mattpocock/skills/tree/main/skills/productivity/wait-what, commit `d80fa0f4ebe0`. The re-pitch steps themselves live in `../clear-writing/SKILL.md`. See `../clear-writing/SOURCES.md` for what was adopted.
