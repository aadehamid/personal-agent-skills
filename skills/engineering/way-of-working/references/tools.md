# Locate helper skills

Search for `SKILL.md` in the host's installed skill roots first. Exclude virtual
environments, dependency directories, and caches from content searches. If a
helper is absent there, search plugin caches for that helper's `SKILL.md`.
A plugin file that can be read is not necessarily installed in the host's catalog.
Report that distinction; install or link it only within the user's authorization.

## Herdr

Herdr is the terminal multiplexer the independent review prefers (`before-push.md`).
Install and verify it once per machine:

- **Binary.** Install from the herdr repo's install instructions
  (`https://github.com/herdrdev/herdr`). Verify with `command -v herdr` and
  `herdr --version`.
- **Skill.** Link the `herdr` skill into the shared skill root and every agent's
  skills folder, the same way other skills are linked. The skill lives at
  `skills/herdr/SKILL.md` in the herdr repo. It is what tells an agent how to
  drive Herdr; without it, the review recipe has no instructions to follow.
- **Server.** Start the Herdr server and confirm it is running with `herdr status`.
  The review commands need a live server. The server starts when Herdr launches;
  if `herdr status` reports it not running, start it per the herdr docs.
- **Agent integration.** For an agent to be recognized and controlled inside a
  Herdr pane, install its integration with `herdr integration install <name>`
  (for example `hermes`, `codex`, `claude`). This gives session-resume after a
  server restart and reliable lifecycle state.
