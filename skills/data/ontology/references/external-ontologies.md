# Surveying and reusing public ontologies

Serves Step 0, and the external mappings applied at later steps (Steps 5 and 7). Read it at Step 0, when applying a mapping, and whenever the user asks whether an existing ontology, vocabulary or code list covers part of the scope.

## Where to look

1. Sector standards bodies: code lists and data-exchange standards (product codes, item identifiers, circulation protocols).
2. Published domain ontologies: GitHub, ontology portals, and the registries below.
3. Registries and authority files: legal entities and their ownership (for example GLEIF Level 2), places, standard identifiers.
4. W3C and community vocabularies: ORG, PROV-O, P-Plan, DCAT, OWL-Time, QUDT, SOSA/SSN.

Search the web for the domain plus "ontology", "OWL", "vocabulary" and "code list".

### The registries to search

Search all four for the domain's main nouns and record each search in the registry-search table of `templates/survey-register.md`: the registry, the date, the query terms, and the hits by name, or "no hits". Each hit worth assessing then gets its own row in the survey table. A registry's listing is a lead; assess the source itself (below).

**Offline.** When a registry cannot be reached, record its row as "not run (offline)" with the date and the query terms you would use, and list the search as an open item (`governance.md`, rule 14). The "Done when" below is then not met, so Step 0 stays open with that reason, and Step 1 may start: the survey changes nothing a later step builds on, because a mapping found later is applied at its own step (rule 1) and a gap is a finding either way (rule 8). Run each open search at the first connection, fill its row, and close the step then.

| Registry | What it holds | How to search it |
|---|---|---|
| Linked Open Vocabularies (LOV), https://lov.linkeddata.es/ | Reusable RDF vocabularies with curated metadata: versions, who maintains them, and which vocabularies reuse which | The vocabulary search and the term search on the site: this is the search to record. LOV also documents a SPARQL endpoint and a REST API (`/dataset/lov/api`) and offers a dump to download; on 2026-10-24 the endpoint and the API answered with an HTML page instead of results, so they are not verified, and a downloaded dump is data to query yourself, not a search of the registry |
| BARTOC, https://bartoc.org/ | Knowledge organization systems of every kind (thesauri, classifications, subject headings, ontologies), any subject and language | Keyword search, or search by KOS type and subject; a JSKOS API at `https://bartoc.org/api/` |
| Open Knowledge Graphs, https://openknowledgegraphs.com/ | Ontologies, vocabularies, taxonomies, data standards and semantic software, drawn from Wikidata and refreshed daily | A search box, with filters by category and type |
| DBpedia Archivo, https://archivo.dbpedia.org/ | Archived versions of web ontologies, checked for new versions several times a day, each with a star rating for retrievability and quality tests | Its ontology list and `/info` page, which lists every archived version with its tests; `https://archivo.dbpedia.org/download?o=<ontology IRI>&f=<ttl, owl or nt>` fetches the latest archived version in that format (owl when `f` is left out) |

*Why these four:* LOV and Archivo cover RDF vocabularies, BARTOC covers thesauri and classifications that never became RDF, and Open Knowledge Graphs adds standards and tools. Cite the Archivo version you read, from its `/info` page, when the publisher's own copy can change under the same IRI (rule 7). A star rating says the file loads and passes Archivo's tests; it says nothing about fit or licence.

## Assess each candidate

| Point | Question |
|---|---|
| Scope fit | Which of your competency questions or concepts does it cover? |
| Licence | May you link to it, copy terms, redistribute? Read the licence or end-user agreement itself, not a summary. |
| Maintenance | Date and version IRI of the last release; who maintains it? |
| Upper ontology | Does it pull in BFO or another foundation you would also have to adopt? |
| Size | How much of it would you never use? |

## Choose one treatment

- **Map (the default):** keep your own term and add `skos:exactMatch` (same meaning) or `skos:closeMatch` (near enough for retrieval). *Why:* you gain the source's authority without its structure; importing usually brings an upper ontology or a large model you must keep consistent, and the extra structure answers none of your competency questions.
- **Import:** only a small, stable, openly licensed source you would otherwise rebuild term for term.
- **Ignore:** record why. *Why:* nobody repeats the search.

## Rules

1. **Record every source in a register:** coverage, licence, version, treatment, and the step where you apply it. Apply each mapping at its step, not all at once. *Why:* a mapping needs the local concept it points from, which a later step builds.
2. **Use W3C vocabularies by IRI**, without importing them (`org:Role`, `prov:Activity`). *Why:* consumers read them with no mapping, and the import brings nothing a question needs.
3. **Map a registry by identifier:** the registry ID as an identifier on your node, with `rdfs:seeAlso` to its record. Where the registry lacks the relation you model, say so in a note. *Why:* the identifier is checkable, and the note stops a reader expecting a registry relation that does not exist.
4. **Check what a standard's licence allows before you map to it.** Pointing to a code by its identifier uses a standard without changing it; copying its code lists into the ontology may need its legends, or be forbidden. *Why:* many sector standards license use but not modification or derived works.
5. **Map only between things of the same kind.** A business process is not a BFO-typed class of logistics process, facility or shipment; a SKOS match between them claims a meaning match no source checks. Park such a mapping with a trigger (a concept layer of the matching kind, or a consumer that needs the external terms). *Why:* a cross-kind match is read as equivalence.
6. **Park a mapping that has no local concept to point from yet,** with a trigger naming the concept or module that will bring it. *Why:* a mapping without a local end cannot be stated.
7. **Cite each mapped source with its version or version IRI and the date you checked it.** *Why:* external ontologies change, and a mapping is correct only against the version you read.
8. **Record a gap as a finding when nothing covers an area; never stretch a neighbouring ontology to fill it.** *Why:* public ontologies often cover one part of a sector well and leave the rest bare, and a stretched mapping misleads.

## Record mappings as SSSOM

Keep every mapping to another vocabulary as a row in an SSSOM/TSV file (Simple Standard for Sharing Ontology Mappings, `SOURCES.md`), beside the module it maps from, and emit the `skos:*Match` triples from that file. Start from `templates/mappings.sssom.tsv`.

9. **One row per mapping, with its justification and who made it:** `subject_id`, `predicate_id`, `object_id` and `mapping_justification` on every row, `author_id` as a role, `confidence` from 0 to 1, and a `comment` that says what tells the two terms apart when the match is not exact; `scripts/check_sssom.py` fails a non-exact match without one. *Why:* a mapping without its justification and confidence reads as certain, and SSSOM posits there can be no mapping without a justification.
10. **Use the SKOS mapping relations and `rdfs:seeAlso` only.** `owl:equivalentClass` and `owl:sameAs` import the other ontology's logic, which "map, don't import" rules out; `scripts/check_sssom.py` refuses them unless `--allow-predicate` names one, and that needs a decision record. Record a rejected candidate as a row with `predicate_modifier: Not`, so nobody proposes it again.
11. **Say how each mapping was found:** `semapv:ManualMappingCuration` for a person's judgement; a matcher's justification (`semapv:LexicalMatching`, or with `sssom_version: 1.1` a value such as `semapv:StructuralMatching`) for a candidate a tool proposed, then `semapv:MappingReview` once a person has checked it. A candidate a language model proposed has no released justification of its own yet (the development branch's `semapv:LLMBasedMatching` is in no release), so record it as `semapv:UnspecifiedMatching` with the model named in `mapping_tool`. *Why:* a tool's candidate is not a decision; the human gate in `quality.md` applies to mappings too.
12. **Pin the other vocabulary's version** in `object_source_version`, in the metadata block or on every row (rule 7; the check fails a set that states it in neither), and run `scripts/check_sssom.py` on every `*.sssom.tsv` the project keeps from its check script; `templates/check.sh`, section 2b, has the lines.

## Done when

Every registry in "The registries to search" has a row in the register's registry-search table with its query terms and its hits or "no hits", every surveyed source has a recorded treatment, licence, version and target step, every gap is recorded as a finding, and every applied mapping is a row in a mapping set that passes `scripts/check_sssom.py`.
