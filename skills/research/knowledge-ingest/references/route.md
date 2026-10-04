# Routing a URL list into subject areas

Given a list of URLs (or freshly fetched sources) with no home yet: decide which bundle
each belongs to, and whether any new bundle is justified.

The output is a proposal for a human, not a fait accompli. Route everything, then present
the assignment and the genuine judgement calls before writing to any `urls.txt`.

## Step 1 — Check what already exists

Before deciding anything, read the bundles that already exist and what they hold. Two
failures come from skipping this:

- Proposing a "new" subject that an existing bundle already covers.
- Adding a source the corpus already has under a different URL.

For the second, normalise before comparing. The same article lives at many URLs: host
moves, `/short-courses/` renamed to `/courses/`, repo renames, docs-tree restructures,
`youtube.com/live/<id>` versus `?v=<id>`. A naive comparison once reported 123 sources
missing when the true figure was 64 — nearly half the answer was noise, and acting on it
would have duplicated three dozen sources. `scripts/url_identity.py` carries the alias
handling; extend its table when you confirm a new alias, and **verify each alias on both
sides before adding it**. A wrong alias silently hides a genuinely new source, which is
worse than a duplicate because nothing will ever surface it again.

## Step 2 — Route by reading, never by keyword

Regex classification does not work here and should not be attempted. A first-match
classifier built for exactly this task sent Unsloth to inference, nanoGPT to fine-tuning,
and backpropagation to transformers — because no pattern separates "quantization for
serving" from "quantization during fine-tuning".

Read the title and enough of the captured content to know what the source is about. Mark
each assignment with a confidence, and treat the low-confidence ones as the list you
discuss rather than the list you quietly commit.

## Step 3 — Make new subjects earn their place

The default is an existing bundle. A new subject has to justify itself against three
tests, and failing any one of them means routing into what already exists:

**Does an existing bundle already cover this?** Not "is there a perfect bundle" — is there
one where this material would be at home and would make that bundle better? Splitting a
domain across two thin bundles is worse than one substantial one.

**Is there enough of it to sustain a bundle?** A handful of sources does not make a
subject; it makes a cluster inside an existing one. Bundles carry real cost — scaffolding,
stub pages, a curriculum, a notebook, ongoing maintenance — and a bundle nobody fills is
worse than no bundle, because it looks like coverage.

**Is it a domain, or a feed?** Term-frequency the candidate. If its top terms are all
borrowed from other subjects, it talks *about* other domains rather than having one of its
own. That is a feed: build it catalog-shaped, or do not build it at all.

## Step 4 — Name the subject from the corpus, not the request

The name people give a list is what they meant to collect, not what they collected. A list
called `llm-inference-optimization-urls.txt` turned out to be more fine-tuning than
inference. A subject provisionally called `rag-retrieval` had OCR appearing 595 times
against 138 for the next term — it was a document-AI bundle with retrieval attached, and
renaming it cost minutes then and would have cost a wiki and a notebook later.

Check the name against the term frequencies before the bundle accumulates anything.

## Step 5 — Drop what has no content, with reasons

Auth walls, login pages, site homepages, dead links, and pages the corpus already holds at
a pinned permalink. Write the reason next to each drop. A dropped URL with no reason
recorded gets rediscovered and re-argued every time someone re-runs the comparison.

Keep two things that look droppable but are not: sources whose `<title>` is useless
(`Medium`, `Google Colab`) but whose content is real — repair the title from the URL slug
instead; and links that are recoverable by rewriting (a Colab GitHub URL to its raw form).

## Step 6 — Present, then write

Give the human: the assignment table, the count per subject, any proposed new subjects with
the argument for why they earned their place, the drops with reasons, and the genuine
judgement calls — the sources that could sit in two bundles, and the ones whose subject you
are unsure of.

Only after that, append to each `urls.txt` under a dated comment header, and validate that
every line parses: no empty URL field, no missing fields, and no `|` inside a title, since
that is the field delimiter.
