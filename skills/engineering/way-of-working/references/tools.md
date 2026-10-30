# Locate helper skills

Search for `SKILL.md` in the host's installed skill roots first. Exclude virtual
environments, dependency directories, and caches from content searches. If a
helper is absent there, search plugin caches for that helper's `SKILL.md`.
A plugin file that can be read is not necessarily installed in the host's catalog.
Report that distinction; install or link it only within the user's authorization.

## Herdr

Herdr TUI (the `herdr` CLI) is the terminal multiplexer the independent review prefers
(`before-push.md`); Rex and the Herdr app, below, are the other hosts.
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

## Rex

Rex (Superlogical, beta) is the second host for the independent review. Inside a Rex
pane (`REX_SESSION` set) and outside Herdr, `herdr-review.sh` hands off to
`rex-review.sh` (`before-push.md`, "In Rex").

- **App and CLI.** The macOS app is open to beta testers
  (`https://www.superlogical.com/rex/docs/installation`). The app ships the `rex` CLI
  and puts it on the path of its own panes. Verify with `rex whoami --json` from a Rex pane.
- **Skill.** `rex skill setup` installs a `rex` skill stub that runs `rex __internal skill`,
  the guide for the installed version.
- **What it cannot tell.** Rex shows the status a program reports with OSC 7501
  (`https://www.superlogical.com/rex/docs/build/program-status`). On 2026-10-24 Claude Code
  reported one; Kimi Code 2.3.1, the Cursor agent CLI 2026.10.22 and Codex CLI 0.164.0 did
  not. So `rex-review.sh` reads the reviewer's state from the pane's process and the bottom
  of its screen, and a reported status, when one appears, comes first.

## Herdr app (hc)

The Herdr app is the third host for the independent review. It runs on herdr-core, whose CLI
is `hc`, and is a separate program from Herdr TUI: the two share no terminals (herdr.dev FAQ,
"How is it different from Herdr TUI?", 2026-10-29). In an hc terminal (`HC_TERMINAL_ID` set)
outside Herdr TUI and Rex, `herdr-review.sh` hands off to `hc-review.sh` (`before-push.md`,
"In the Herdr app").

- **App and CLI.** Install from `https://herdr.dev/download/`. Verify with `command -v hc`
  and `hc server status`.
- **Guides.** `hc --skill` prints the current manual for driving agents with `hc`;
  `~/.config/herdr-app/AGENTS.md` covers the window itself (layouts, keys, mods).
- **What it tells.** `hc get <t>` gives a status only for a program that reports one with
  OSC 7501. On 2026-10-29 Codex CLI 0.166.0 reported one and the Cursor agent CLI
  2026.10.22 did not; Kimi Code was not checked. `hc-review.sh` reads a reviewer that reports
  none from its screen.
