# Independent review

## Why a different instance

The agent that wrote a page cannot see what it invented, because the invented part felt
like knowing. This is not a discipline problem — it is a visibility problem, and the only
reliable fix is a reader who has the sources but not the memory of writing.

A different model family is better still: it shares fewer of the author's blind spots.

## The brief

```
You are the REVIEWER for a knowledge-base ingest. REPORT-ONLY: report findings, do NOT
edit any file. All paths are absolute; read them yourself.

## Schema you check against
<bundle>/CLAUDE.md   (or the project's schema file)

## The sources ingested — the ONLY permitted evidence
<absolute path per source>

## Files created or edited
<explicit list>

## Check priorities, in order
1. FACTUAL ACCURACY / NO INVENTION — every claim, number and name must trace to one of
   the sources above. Outside knowledge counts as invention however true it is.
2. SCOPE — out-of-scope material belongs in an aside, not a new page.
3. SCHEMA — frontmatter fields, provenance objects, relative links, dates, trust stamps.
4. GRAPH — no orphans; index entries present and sensible.
5. CONSISTENCY — back-references match reality; the log's touched list is accurate;
   curriculum markers correct.
6. VOICE — concision, no emojis, no broken markdown.

## Attack these specifically
<the claims you are least sure of, named>

## Output
Findings tagged HIGH / MEDIUM / LOW with file and line, then one verdict:
ship / ship-with-fixes / needs-rework.
```

The "attack these specifically" section is where the review earns its cost. Reviewers
reliably catch what they are pointed at. Name the number you transcribed and did not
re-check, the synthesis you are not sure is in the source, the mechanism you might have
supplied from your own knowledge.

## Resolving findings

The author owns resolution, not the reviewer.

1. **Verify each finding against the source before applying it.** Reviewers produce false
   positives, and deleting accurate content to satisfy one is a real loss. If a finding is
   wrong, document the override with the evidence rather than silently ignoring it.
2. Apply every HIGH and MEDIUM. LOW is optional.
3. Re-run the mechanical check on the changed files.
4. Record in the log: which reviewer, the verdict, the finding counts, and what the
   findings actually were. "Reviewed, 8 findings applied" is worth little to a future
   reader; naming the failures is worth a lot.
5. Archive the brief and the findings.

Two reviews of well-intentioned work returned `needs-rework` with eight valid findings
each. Treat that as the expected outcome. A review that finds nothing is more likely a
review that was not given the sources.
