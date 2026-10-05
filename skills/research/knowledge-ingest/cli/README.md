# kb

Read-only validation for knowledge-ingest bundles, so agents stop writing their own
checks. `kb --help` lists the commands; the skill's SKILL.md says when to run them.

## Install / run

```bash
uv tool install --editable <skill>/cli   # puts `kb` on PATH; code edits apply immediately
uv run --project <skill>/cli kb --help   # or run without installing
```

Config is the project's `knowledge-ingest.config.json`, found via `--config`, `$KB_CONFIG`,
the current directory or a parent, or `~/.config/kb/config.json` (usually a symlink to the
project's file). Keys kb reads: `bundles[].name/path/shape`, `bundles[].uncited_ok`
(`{file: reason}`), `validator`, `sync_simulator`.

## Rules for changes

- **Read-only.** No command edits or deletes. Fixes stay with the agent, so any agent can
  run any command safely.
- **Every check earns its place.** Add one when a real ingest or review hit the failure, and
  add a test that reproduces it in `tests/test_kb.py`. Name the test after the bug.
- **Fail closed.** Anything that could not be checked is a failure, never a pass: a
  missing validator, unpaired quote marks, malformed simulator output, an unresolvable
  reference. A clean result must mean "checked and fine".
- **Exit codes:** 0 clean (warnings allowed), 1 failures, 2 usage/config error. With
  `--json`, stdout is always `{"status": "clean"|"fail"|"error", "reports": [...]}`,
  errors included.
- **`kb quotes` matching:** each source is searched on its own, visible body only (no
  frontmatter, hidden HTML, comments or image alt text). Only real markdown and real
  HTML tags are removed, so `vector<int>` stays text. Fragments match on token
  boundaries, in order, and each needs at least 3 word characters. Changed punctuation
  is DRIFT.
- **Parsing:** frontmatter is parsed with PyYAML. Invalid YAML or invalid UTF-8 is a
  failure. Relative paths in the config resolve from the config file's folder.
- **Recurring low-severity patterns** are reported once per bundle with the full list in
  `--json` `details`, so they do not bury real failures.
- **Project-specific logic stays in the project.** Sync behaviour is reached through the
  config's `sync_simulator` command, not reimplemented here.

## Layout

| Module | Command |
|---|---|
| `checks.py` | `kb check`: structural Gate A |
| `quotes.py` | `kb quotes`: quotations verbatim in the page's sources |
| `coverage.py` | `kb coverage`: Raw files no page cites |
| `dupes.py` | `kb dupes`: same-URL Raw files |
| `urls.py` | URL identity (`norm()`), shared with `../scripts/url_identity.py` |
| `citers.py` | `kb citers`: exact citing lines for one Raw file |
| `syncsim.py` | `kb sync-sim`: runs the project's simulator |
| `vault.py` | frontmatter, pages, exact citation matching |

## Tests

```bash
cd <skill>/cli && uv run --group dev pytest -q
```
