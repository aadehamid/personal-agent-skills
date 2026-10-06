# unslop (alias)

A one-file alias. Some skills you use, mainly pstack's (`poteto-mode`, `technical-writing`, `teach` and others), tell the agent to run the unslop skill. You replaced unslop with clear-writing, so this alias catches those calls and hands them to clear-writing.

This README is for people. Agents do not read it.

## Files

| Path | Read by | What it does |
|---|---|---|
| `SKILL.md` | agent, when a skill or prompt calls unslop | Tells the agent to load clear-writing and use Edit or Write mode. Maps "unslop rule N" to the same number in clear-writing's AI-tells list. |
| `README.md` | you | This file. |

## Status

Added 2026-10-06.

- **pstack's own unslop must stay unlinked.** `scripts/update-pstack.sh` excludes it. If pstack's unslop is linked again, the two skills share a name.
- **File-path links still reach pstack's copy.** A few pstack skills link straight to `../unslop/SKILL.md`. An agent that follows that link reads pstack's original file in the clone, not this alias. That's rare and harmless, since clear-writing covers the same rules.
- **Cursor's pstack plugin has its own unslop.** `scripts/update-pstack.sh` points each cached copy at this alias and backs up the original. Re-run it after Cursor updates the plugin, since each version is a new cache folder.
