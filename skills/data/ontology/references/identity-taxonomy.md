# Identity and the SKOS taxonomy

Serves Steps 2 and 3. Read it before you mint any IRI, build or regenerate the concept scheme, or rename a concept.

## Step 2: identity

1. **Slugs and IRIs are identity; labels are presentation.** Never use a label as a join, lookup, access-control or API key. *Why:* labels change and collide; identity must not.
2. **Keep the source's local IDs as `skos:notation` and derive slugs from them.** Mint a slug only where a node has no ID. Reference-framework IDs attach by `dcterms:references` and never replace local IDs. *Why:* the local ID is what the business already uses to find the thing.
3. **Put no version in a term IRI.** Versions live on the ontology header (`release.md`). *Why:* identity must survive a definition change.
4. **Use a persistent base scoped to the organization**, never a person or a project. *Why:* usernames and project names change; the base should change by one redirect.
5. **Give every node something can point at an IRI, including n-ary and qualified-relation nodes. Released data has no blank nodes.** *Why:* a blank node has no stable identity across builds, so a consumer cannot reference it and a property-graph load cannot reproduce it.
6. **Derive minted IRIs from content, never from position.** Build an assignment's IRI from its ends plus a short hash of the source string (`.../assignment/lend-item--accountable--circulation-lead--3f9a1c20`), not from its place in a list. *Why:* a source edit that reorders a list must not remint identities.
7. **Settle identity before direction, and direction before meaning.** *Why:* a relationship between two things you cannot identify is a guess.
8. **A label proposes a candidate; it never confirms one.** Resolve a target only on a stable ID or approved contextual evidence; otherwise defer it with the raw phrase, the candidates and a review trigger. *Why:* in practice labels drift during a build and one label can name two concepts in two branches; a label join misresolves both without an error.
9. **Record renames as overlays on the identity map** (current name, prior name, note, scoped alias). After any regeneration of the identity map, restore the overlays before rebuilding the Turtle. *Why:* otherwise the Turtle silently reverts to old labels.
10. **Fix a row's meaning at review time.** If a better reading appears later, hold the row and record the better reading as its reason; corrections reach the source through the source-correction backlog (`promotion.md`). *Why:* re-reading rows silently makes the ledger unreproducible.

## Step 3: the SKOS taxonomy

1. **Use SKOS first, not OWL classes, for the naming hierarchy.** One `skos:ConceptScheme`; `skos:broader`/`skos:narrower` for the hierarchy; `skos:prefLabel`, `skos:altLabel`, `skos:notation`, `skos:definition`. *Why:* turning hierarchy levels into classes asserts disjointness and inherited restrictions that a naming hierarchy does not support.
2. **Give every concept exactly one parent, except the scheme's top concepts (`skos:topConceptOf`), which have none. No cycles. The build fails on either.** *Why:* the parent test and every roll-up query assume a tree.
3. **Slot every new concept into the hierarchy; allow no floating nodes.** *Why:* a floating node escapes the parent test and every scope query.
4. **One `skos:prefLabel` per language per concept, and a language tag on every literal.** *Why:* two preferred labels in one language make the name a coin toss.
5. **Put `skos:definition` on every concept and a scope note on every approved one, to the quality bar in `quality.md`.** *Why:* a concept without a definition means whatever each reader assumes.
6. **Send collected definition text through a human gate.** Reference text informs a definition; never copy it verbatim. *Why:* copied text carries another organization's scope and licence.
7. **Classify by primary purpose, not by location, asset or department.** Write one primary question per domain ("what is the financial position, performance, obligation and exposure?" for Finance) and use it as the placement test for every new concept. *Why:* purpose is stable when the org chart and the systems change.
8. **Add aliases selectively.** `skos:altLabel` is a live search commitment: make a former name an alias only if it is unique, accurate and useful. Keep other former names in a history annotation. *Why:* a stale alias returns the wrong concept to a search.
9. **Split a source field that mixes dimensions.** A field holding "event-driven", "monthly" and "tactical" holds three dimensions (operating mode, cadence, planning level); model three controlled fields, each with its own code list, and record "unspecified" honestly where a value is missing. *Why:* one mixed field cannot be validated or queried by any one dimension.
10. **Keep lifecycle status, governance status and hold status separate.** *Why:* a concept can be a Candidate and on hold at once; one status chain cannot say that.
11. **Give every code-list property its own SKOS scheme**, and check each value against its own list (`shacl.md`). *Why:* a value from the wrong list (a cadence used as an operating mode) passes a check that only asks "is it a concept?".
12. **Mark structural anchors** (grouping nodes that are not work anyone performs) with a concept kind. *Why:* responsibility and run rules must be able to exclude them by a query.
13. **Run the mechanical checks before any review:** labels present, IDs present, hierarchy integrity, no label collisions. *Why:* a reviewer's time goes to meaning, not to typos a script finds.

Deprecation and release headers: `release.md`.
