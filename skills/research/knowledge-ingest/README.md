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
| `cli/tests/test_kb.py` | you, when changing `kb` | 94 regression tests. Most reproduce a real bug from validating a live corpus, and the test names say which. |
| `scripts/check_ingest.py` | agent, legacy | Old entry point for Gate A. It now forwards to `kb check`. |
| `scripts/url_identity.py` | agent, route mode | Compares an external list of saved links against a corpus inventory, treating the same article under different URLs as one. It imports its URL rules from `cli/kb/urls.py`. |
| `evals/evals.json` | you, when testing | Six test prompts with expected behavior. Three should use the skill: starting a 40-file backlog, resuming yesterday's ingest, and auditing a vault. Three should not: summarising one paper, bulk-fetching URLs, and answering a question from existing notes. |
| `README.md` | you | This file. |

No `SOURCES.md`: the skill is built from running a real ingest pipeline (about 900
sources across nine vaults, each batch independently reviewed), not from outside text.

## Set up on a machine

`./scripts/link-skills.sh --tools` (repo root) links the skill and installs `kb` with
`uv tool install --editable`. Editable means edits under `cli/` take effect without a
reinstall. It needs [uv](https://docs.astral.sh/uv/).

Then, for each project you ingest into:

1. **Write `knowledge-ingest.config.json`** in the project root. Without one, the skill
   asks for paths and offers to write it.

   ```json
   {
     "bundles": [
       {"name": "My Vault", "path": "/path/to/vault", "sources": "sources/my-vault", "shape": "concept",
        "uncited_ok": {"some-raw-file.md": "why it is deliberately not cited"}}
     ],
     "validator": "scripts/validate_bundle.py",
     "reviewer": {"kind": "codex", "cmd": "<command that runs a report-only review>"},
     "ledger": "path/to/INGEST-LEDGER.md",
     "runbook": "path/to/INGEST-RUNBOOK.md",
     "sync_simulator": "python3 scripts/simulate_sync.py"
   }
   ```

   Relative paths resolve from the config file's folder.
   - Required: `bundles`.
   - **`validator`** is required for `kb check` to pass. It is any script that takes a bundle path and exits non-zero on a schema failure. `kb check` fails closed without one.
   - **`sync_simulator`** is needed only if a sync job can recreate files you delete. `cli/kb/syncsim.py` describes the JSON it must print.

2. **Optional: make `kb` work from any directory** by linking that config as the default:
   `mkdir -p ~/.config/kb && ln -sfn /path/to/project/knowledge-ingest.config.json ~/.config/kb/config.json`.
   Otherwise `kb` looks for the config in the current folder and its parents, or in
   `--config` / `$KB_CONFIG`.

3. Run `kb bundles` to confirm it found the config, then `kb coverage` to see what is
   unprocessed.

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
