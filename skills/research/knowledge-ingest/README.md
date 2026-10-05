# knowledge-ingest

A skill that turns saved sources (articles, papers, transcripts) into a linked
knowledge base: an Obsidian vault, a wiki, or any "bundle" of pages. It works on one
article or a backlog of hundreds, and it can pick up where the last session stopped. The
skill holds the method and the quality gates. Each project holds its own paths and
conventions in one config file.

The method is built around four ways this work goes wrong without anyone noticing, and
two gates that catch them:

- **Gate A** is mechanical. The `kb` CLI in `cli/` checks it.
- **Gate B** is an independent review by a second agent, ideally a different model family.

This README is for people. Agents do not read it. They read `SKILL.md` and the files it
points to.

## Files

| Path | Read by | What it does |
|---|---|---|
| `SKILL.md` | agent, every run | The skill itself. The frontmatter `description` decides when it triggers. The body has the four invariants (every claim traces to a source, keep hedges, record disagreements, verify before acting), the two gates, how the work scales by batch size, the known traps, and when to stop and ask. |
| `references/ingest.md` | agent, ingest mode | The full batch procedure (cluster selection, ledger, both gates) and the page templates. |
| `references/review.md` | agent, Gate B | How to brief an independent reviewer: sources marked as the only permitted evidence, file list, the claims to attack first, and how to resolve findings. |
| `references/route.md` | agent, route mode | Sorting a URL list into subjects, and the test a new subject must pass before it gets its own bundle. |
| `references/bootstrap.md` | agent, bootstrap mode | Setting up a new bundle: concept or catalog shape, and stub pages taken from the corpus's own terms. |
| `references/audit.md` | agent, audit mode | Checking whether an existing bundle can be trusted: sample for fidelity and report an error rate. |
| `cli/` | agent, through the `kb` command | The `kb` validation CLI (Python, Typer). Read-only. Subcommands: `check` (Gate A), `quotes` (every quotation verbatim in its sources), `coverage` (unprocessed sources), `dupes` (duplicate sources), `citers` (who cites a file), `sync-sim` (would the project's sync recreate a deleted file). `cli/README.md` has the rules for changing it. |
| `cli/tests/test_kb.py` | you, when changing `kb` | 96 regression tests. Most reproduce a real bug from validating a live corpus, and the test names say which. |
| `scripts/check_ingest.py` | agent, legacy | Old entry point for Gate A. It now forwards to `kb check`. |
| `scripts/url_identity.py` | agent, route mode | Compares an external list of saved links against a corpus inventory, treating the same article under different URLs as one. It imports its URL rules from `cli/kb/urls.py`. |
| `evals/evals.json` | you, when testing | Six test prompts with expected behavior. Three should use the skill: starting a 40-file backlog, resuming yesterday's ingest, and auditing a vault. Three should not: summarising one paper, bulk-fetching URLs, and answering a question from existing notes. |
| `README.md` | you | This file. |

No `SOURCES.md`: the skill is built from running a real ingest pipeline (about 900
sources across nine vaults, each batch independently reviewed), not from outside text.

## Set up a new machine

The skill alone installs in two commands. To continue the knowledge-management work
on another machine, it also needs the project repo and the vaults. Nothing in these
steps depends on your username or on where your home folder is.

1. Install [uv](https://docs.astral.sh/uv/), Python 3 and git.
2. Clone this repo and run its install script with both options. It links
   knowledge-ingest (and the other skills) into every agent on the machine, installs
   `kb`, and adds the clear-writing pointer to `~/.claude/CLAUDE.md`.

   ```bash
   git clone https://github.com/aadehamid/personal-agent-skills.git
   cd personal-agent-skills
   ./scripts/link-skills.sh --claude-md --tools
   ```

3. Get the project repo, which holds the config, the schema validator, the sync
   simulator, the runbook and the ledger. Dropbox syncs it to
   `~/Dropbox/1_PROJECTS/knowledge-management`, or clone
   `https://github.com/aadehamid/knowledge-management`.
4. Get the vaults. They are not in git. They live in `~/Documents/Knowledge Management`,
   which iCloud Drive syncs to any Mac signed into the same Apple ID with "Desktop &
   Documents" turned on. If you keep them somewhere else, add
   `export KB_VAULT_ROOT="/path/to/your/vaults"` to your shell profile. `kb` and the
   project's sync scripts all read that variable.
5. Point `kb` at the project config, so it works from any folder:

   ```bash
   mkdir -p ~/.config/kb
   ln -sfn ~/Dropbox/1_PROJECTS/knowledge-management/knowledge-ingest.config.json ~/.config/kb/config.json
   ```

6. Install the Codex plugin in Claude Code (`/plugin`, then openai-codex) and log in.
   The independent review runs through the project's `scripts/codex_review.sh`, which
   finds whichever plugin version is installed.
7. Run `kb bundles`. Every vault should show a path that exists. A vault marked
   MISSING means step 4 is not done or `KB_VAULT_ROOT` points at the wrong folder.
8. Run `kb coverage` to see what is left to process, then ask any agent to "pick up
   where we left off".

The daily sync (git pull, then copy new sources into the vaults) runs from a launchd
job on the original machine. It is optional. To run it on another Mac, copy
`~/Library/LaunchAgents/com.hamid.knowledge-sync.plist` from the original machine, change
the script path in it to where `scripts/pull_and_sync.sh` lives on the new one, and
load it with `launchctl load`.

## Config reference

Each project has one `knowledge-ingest.config.json` in its root. The skill reads it
for paths and conventions. Without one, the skill asks for paths and offers to write it.

```json
{
  "vault_root": "~/Documents/Knowledge Management",
  "bundles": [
    {"name": "My Vault", "path": "My Vault", "sources": "sources/my-vault", "shape": "concept",
     "uncited_ok": {"some-raw-file.md": "why it is deliberately not cited"}}
  ],
  "validator": "scripts/validate_bundle.py",
  "reviewer": {"kind": "codex", "cmd": "scripts/codex_review.sh"},
  "ledger": "path/to/INGEST-LEDGER.md",
  "runbook": "path/to/INGEST-RUNBOOK.md",
  "sync_simulator": "python3 scripts/simulate_sync.py"
}
```

Paths follow three rules, so a config works unchanged on any machine:

- A bundle `path` that is relative resolves against the vault root. The vault root is
  `$KB_VAULT_ROOT` when that variable is set, and the config's `vault_root` otherwise.
- Every other relative path (`validator`, `ledger`, `runbook`) resolves from the
  config file's folder.
- `~` and environment variables such as `$HOME` expand everywhere. An undefined
  variable is an error, so a typo never resolves to the wrong folder.

Only `bundles` is required. `kb check` fails without a `validator`, which is any
script that takes a bundle path and exits non-zero on a schema failure. A
`sync_simulator` is needed only if a sync job can recreate files you delete.
`cli/kb/syncsim.py` describes the JSON it must print. `kb` finds the config through
`--config`, then `$KB_CONFIG`, then the current folder and its parents, then
`~/.config/kb/config.json`.

## Common tasks

**Pick up where you left off.** In any agent, say "where did we leave off" or "process
the rest of the backlog". The skill reads the config, the runbook and the ledger, and
recomputes what is unprocessed with `kb coverage`.

**Add a check to `kb`.** Add it under `cli/kb/` with a test in `cli/tests/test_kb.py`
that reproduces the failure. Keep every command read-only and fail-closed: anything it
could not check is a failure, never a pass. See `cli/README.md`.

**Run the tests.**

```bash
cd skills/research/knowledge-ingest/cli && uv run --group dev pytest -q
```

## Status

Last updated 2026-10-04.

- **`kb` went through four Codex review rounds on 2026-10-04.** The first three
  returned needs-rework (16, then 11 partial plus regressions, then 13 findings). The
  fourth, after publishing, returned ship-with-fixes with 8 remaining paths. All were
  fixed, each with a regression test. If a later review finds more, add each finding
  as a test first.
- **Citation rule.** `kb` counts a source as cited only when a page's link or
  `sources[].resource` resolves, from the page's own folder, to the file in that vault's
  `Raw/`, or when the page uses the `[source: <file>]` marker. Bare mentions, links into
  another vault, and anything inside code, comments, hidden HTML or strikethrough do
  not count. On the corpus it was built against, this gave the same result as the
  earlier pattern rule, minus its false positives.
- **No trigger eval.** `evals/evals.json` tests behavior, not triggering. If the skill
  fires on the wrong requests, or misses casual ones like "work through the backlog",
  add a trigger set and tune the description with skill-creator.
- **Validator and sync simulator are per project.** The ones used so far
  (`test_okf_bundle.py`, `simulate_sync.py`) live in the knowledge-management repo, not
  here, because they encode that project's schema and sync rules.
