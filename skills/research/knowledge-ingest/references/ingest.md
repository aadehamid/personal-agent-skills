# The ingest loop in detail

## Choosing a batch

Find sources nothing cites yet:

```python
from pathlib import Path
B = Path("<bundle>")
cited = "".join(p.read_text(encoding="utf-8", errors="ignore")
                for p in (B / "Wiki").rglob("*.md"))
for r in sorted((B / "Raw").glob("*.md")):
    if r.name not in cited:
        print(len(r.read_text(encoding="utf-8", errors="ignore").split()), r.name)
```

Take 8–12 on one topic. The word counts matter: a batch of 200-word shells produces a
batch of thin pages, and it is better to know that before writing than after.

## Page types

| Type | Where | When |
|---|---|---|
| summary | `Wiki/summaries/<slug>.md` | one per source, or one per group of closely-related sources |
| concept | `Wiki/concepts/<Name>.md` | a mechanism or idea |
| entity | `Wiki/entities/<Name>.md` | a named thing — a library, model, tool |
| paper | `Wiki/papers/<Title>.md` | the source is an academic paper |

Folding several thin sources into one summary is usually right — three tool READMEs that
each say little make one good page and three bad ones. Say in the page that it covers
several sources, and cite them all.

Fill existing stub pages before creating new ones.

## Frontmatter

```yaml
---
type: summary
title: Some Title
tags: [topic, subtopic]
sources:
  - id: <source-file-stem, truncated>
    resource: ../../Raw/<source-file>.md
    title: "Source title"
updated: 2026-08-30
description: one sentence, lower case, no trailing period
generated: { by: "agent:<model-id>", at: "2026-08-30T14:22:05Z" }
---
```

Three things that break files if ignored:

- **Quote any value containing `:`**. An unquoted colon makes YAML read the value as a
  mapping and the file fails to parse.
- **`resource:` is relative to the page's own directory.** Two levels down needs `../../`.
  Wrong depth means broken provenance that no link checker in the body will catch.
- **`at:` is the real clock**, from `date -u +%Y-%m-%dT%H:%M:%SZ`. A rounded guess that
  lands after the file's own mtime is a stamp that lies, which is worse than none.

Links between pages are relative markdown with percent-encoded spaces:
`[Reward Model](../concepts/Reward%20Model.md)`.

## Wiring

Four things, all required, none of them optional-feeling in a way that survives review:

**Index** — every new page listed under its section. A page missing from the index is an
orphan.

**Back-references** — each source's frontmatter lists the pages citing it. This must hold
in *both* directions; the checker verifies both.

**Curriculum stage** — place each source in a stage. When a stage goes from empty to
populated, remove its skeleton marker, add a line naming how many sources it now holds,
and bump `updated`.

**Log** — one entry, under today's date heading, newest first, one heading per date. Say
what was ingested, what was created, and any judgement call you made. The log is what a
future agent reads to understand why the bundle looks the way it does.

## Writing

Read the source, then write from what you read. The gap where invention creeps in is the
sentence you write while thinking about the topic rather than looking at the text.

Signals you are drifting:
- You are explaining background the source assumed rather than stated.
- You reached for a number you remember rather than one you just read.
- You are smoothing two sources into one story.

All three produce pages that read better than the honest version and are worth less.

## Quote splicing and verification (learned the hard way, 2026-09-12)

When a quote is assembled programmatically, splice it with an **inclusive** helper —
`src[i:j+len(end_anchor)]`, never `src[i:j]` — or the final phrase silently vanishes
("...LLVM backend" without "takes over."). And when replacing a mangled quote, assert the
full corrupted span is consumed; a partial replace leaves the old sentence tail
appended to the new one ("...This is not a bug. by default. This is not a bug.").

Angle-bracket tags (<think>) inside a quote are eaten by some display layers between
the agent and the file — the agent *writes* them, sees them swallowed, and can't tell
the file is now wrong. Verify quote fidelity **byte-level via hex comparison against
the Raw file**, never by re-reading rendered output. And never write "quotes verified
byte-identical" into the log before the independent reviewer confirms it — that claim
is exactly what a reviewer falsifies first.

Use `kb quotes <page>` rather than an ad-hoc regex. A hand-rolled `"..."` regex produces
false positives: the page's own frontmatter `description`/stamps, connective prose between
two adjacent quotes (`"quote A" connective "quote B"` read as one span), and mis-pairing
after a short quote is skipped. It also produces false negatives when link or emphasis
markup sits inside the source text. `kb quotes` handles all of these and reports a paragraph
with unbalanced quote marks instead of guessing.

## Raw immutability: the mechanical-repair exception (2026-10-05)

Raw prose, quotes, and facts never change. Paths and frontmatter can be repaired. The
test: would the edit survive if the source text were read aloud? Path repairs would;
prose rewrites would not. The two legitimate repairs — image path absolutization
(HTTP-HEAD-verified against the source domain, `*[figure not recovered]*` notes for
figures gone from the live site) and frontmatter maintenance — are procedures, and the
vault-maintenance skill owns them. Log path repairs in the bundle's `Wiki/log.md`.

## Quote drift at scale (2026-10-05)

One batch of subagent-written summaries produced ~90 `kb quotes` failures — drift is
not a rare typo, it is what batch-written pages do. The failure modes (hard-wrapped
quotes, ellipsis joins, case and trailing-punctuation drift, paraphrase quoted as
fact) and the per-failure repair procedure live in the vault-maintenance skill. The
lesson that generalizes: after repair, re-run `kb quotes` on every touched page, and
treat the repair regexes as their own hazard — escape the quote text, test the
pattern on one known instance before a bulk `re.subn`, and count replacements
against the flagged failures.

## Stamp hygiene on touched pages (Codex review, 2026-09-12)

Every page touched by an ingest — including one-line cross-ref additions to Learning
Path stages and old summaries — takes the current `updated` date and a fresh ingest
stamp (`generated:` for the ingesting agent; on a page with an existing `generated:`,
add `verified:` for this ingest instead of overwriting the original authorship). A
touched page with stale metadata is a MEDIUM finding every time.

Batch writers (subagents writing a dozen pages at once) systematically forget the
stamps. Do not rely on the brief alone: after every batch write, run a bulk stamp pass
over the touched pages — parse the frontmatter, add the missing stamp (`generated:`,
or `verified:` where `generated:` already exists) — before running Gate A. The
check-fix-recheck cycle costs more than the pass.
