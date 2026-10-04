# Bootstrapping a new bundle

Scaffolding a bundle needs before its first ingest, so that early pages have somewhere to
link. Skipping it produces orphan summaries with nothing to cross-reference.

## Choose the shape first

**concept** — index, overview, log, stub entity/concept pages, curriculum stages.
**catalog** — index, overview, log. Nothing else.

Catalog is right when the corpus is dated ephemera: releases, announcements, pricing,
industry news. A concept wiki over that goes stale faster than it can be written.

Diagnostic when unsure — term-frequency the corpus. If the top terms are all borrowed
from *other* subjects, the corpus talks about other domains rather than having one. That
is a feed. Build it catalog-shaped and write down why, so the missing layer reads as a
decision rather than an oversight.

## Stubs come from the corpus, not a template

Count terms across the bundle's own sources and stub only what the corpus actually
discusses, with the frequency as evidence. A cloned term list from a sibling bundle
produces stubs nobody ever fills — they make the graph look like coverage it does not
have, and they clutter every later lint pass.

Roughly 6–12 stubs per bundle is enough to give the first ingest somewhere to link.

## Curriculum stages are per-bundle

Stage titles from another subject are worse than no stages. "Hardware Track" means nothing
in a fine-tuning curriculum. Write the progression this subject actually has.

## Adapt, do not clone, the schema file

If copying a sibling bundle's schema, strip every term, example and stage scope belonging
to that sibling and substitute this domain's own. A clone is a starting point; left
unadapted it silently teaches the next agent the wrong vocabulary.
