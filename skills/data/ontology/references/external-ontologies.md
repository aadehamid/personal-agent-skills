# Surveying and reusing public ontologies

Serves Step 0, and the external mappings applied at later steps (Steps 5 and 7). Read it at Step 0, when applying a mapping, and whenever the user asks whether an existing ontology, vocabulary or code list covers part of the scope.

## Where to look

1. Sector standards bodies: code lists and data-exchange standards (product codes, item identifiers, circulation protocols).
2. Published domain ontologies: GitHub, ontology portals, and the registries below.
3. Registries and authority files: legal entities and their ownership (for example GLEIF Level 2), places, standard identifiers.
4. W3C and community vocabularies: ORG, PROV-O, P-Plan, DCAT, OWL-Time, QUDT, SOSA/SSN.

Search the web for the domain plus "ontology", "OWL", "vocabulary" and "code list".

### The registries to search

Search all four core registries for the domain's main nouns and record each search in the registry-search table of `templates/survey-register.md`: the registry, the date, the query terms, and the hits by name, or "no hits". Each hit worth assessing then gets its own row in the survey table. A registry's listing is a lead; assess the source itself (below).

**Offline.** When a registry cannot be reached, record its row as "not run (offline)" with the date and the query terms you would use, and list the search as an open item (`governance.md`, rule 14). The "Done when" below is then not met, so Step 0 stays open with that reason, and Step 1 may start: the survey changes nothing a later step builds on, because a mapping found later is applied at its own step (rule 1) and a gap is a finding either way (rule 8). Run each open search at the first connection, fill its row, and close the step then. When the build's own network blocks a registry that the internet can reach, the search may run on another machine, such as the owner's computer; note where it ran beside the registry's name in the row.

| Registry | What it holds | How to search it |
|---|---|---|
| Linked Open Vocabularies (LOV), https://lov.linkeddata.es/ | Reusable RDF vocabularies with curated metadata: versions, who maintains them, and which vocabularies reuse which | The REST API: `https://lov.linkeddata.es/dataset/api/v2/vocabulary/search?q=<term>` for vocabularies and `.../api/v2/term/search?q=<term>` for terms (last checked 2026-11-27). The older documented path `/dataset/lov/api` returned 404 that day, and the vocabulary search page showed no results for 7 of 8 terms the API found, so record the API search |
| BARTOC, https://bartoc.org/ | Knowledge organization systems of every kind (thesauri, classifications, subject headings, ontologies), any subject and language | `https://bartoc.org/api/voc/suggest?search=<term>&limit=100` (last checked 2026-11-24). `/api/voc?search=` ignored the term that day: every query returned the same list |
| Open Knowledge Graphs, https://openknowledgegraphs.com/ | Ontologies, vocabularies, taxonomies, data standards and semantic software, drawn from Wikidata and refreshed daily | The site's search runs in the browser; the API `https://api.openknowledgegraphs.com/ontologies?q=<term>&limit=100` answers (last checked 2026-11-24, when it reported a text-only mode with its semantic search paused; note it beside the registry's name in the row when it says so) |
| DBpedia Archivo, https://archivo.dbpedia.org/ | Archived versions of web ontologies, checked for new versions several times a day, each with a star rating for retrievability and quality tests | It has no keyword search: filter its full list of ontologies by name and IRI (last checked 2026-11-24, when the root URL led to the list). Its `/info` page lists every archived version with its tests; `https://archivo.dbpedia.org/download?o=<ontology IRI>&f=<ttl, owl or nt>` fetches the latest archived version in that format (owl when `f` is left out) |

*Why these four:* LOV and Archivo cover RDF vocabularies, BARTOC covers thesauri and classifications that never became RDF, and Open Knowledge Graphs adds standards and tools. Cite the Archivo version you read, from its `/info` page, when the publisher's own copy can change under the same IRI (rule 7). A star rating says the file loads and passes Archivo's tests; it says nothing about fit or licence.

**Before you search a registry, test its endpoint with two different terms.** An error (a 404, a 5xx or an HTML error page), or the same results for both terms, means the endpoint has moved or broken: find the current one on the registry's own site and note it beside the registry's name in the row, and do not record the failed search as "no hits". When no working endpoint can be found, the search is not run, as under "Offline" above. *Why:* a broken endpoint returns nothing or the same list for every term, which reads as a search with no hits.

**Check each hit against the term before you count it.** Drop a match on part of another word ("art" inside "chart") and a match on only one word of a multi-word query ("data and metadata" matching "and"). Keep a match on another form of the term: a plural, or a label written in CamelCase or with hyphens or underscores ("DataCatalog" for "data catalog"). *Why:* a registry's raw count includes the false matches and overstates what exists, and a strict string match would drop the real ones.

**Also search each of these that fits the domain,** and record it in the same table:

| Registry | What it holds | Fits |
|---|---|---|
| Research Data Alliance Metadata Standards Catalog, https://rdamsc.bath.ac.uk/ | Metadata standards. It replaced the RDA Metadata Standards Directory, which says the catalog superseded it and that the directory is no longer maintained (checked 2026-11-27) | Any domain that publishes datasets |
| BioPortal, https://bioportal.bioontology.org/, and other installations of OntoPortal, https://ontoportal.org/ | Ontologies loaded into a portal, with search and mappings between them | A domain its listed ontologies touch: check BioPortal's list first, and OntoPortal's list of its other installations |
| W3C SKOS Datasets wiki, https://www.w3.org/2001/sw/wiki/SKOS/Datasets | A community list of thesauri and classifications published in SKOS | Any domain; the page was last edited on 3 July 2018 (checked 2026-11-27), so check each entry's own site for a current version |

**Cite each resource from its publisher's own copy, never from what a registry, an aggregator or a catalogue says about it.** An archived copy, such as an Archivo version, may pin the exact file you read, beside the publisher's citation, with its version and date (rule 7). *Why:* a listing can be stale or wrong about version and licence, and only the publisher's copy is authoritative.

## Common vocabularies to check where they fit

Some vocabularies recur across industries. Check each one whose topic your scope touches, and give it a row in the survey register with its treatment; one your scope does not touch needs no row. Read each one's licence at its publisher before you map to it (rule 4). The ones marked **map by code only** are not published as RDF, or their terms restrict copying: map to them by identifier (rule 3, and "Choose one treatment" below), and never import them.

| Topic | Vocabulary | Publisher | Licence, as published (read it again before use) |
|---|---|---|---|
| Statistics | SDMX (Statistical Data and Metadata eXchange), ISO 17369 | The SDMX sponsor organisations, https://sdmx.org/ | sdmx.org states no licence for the standard, and its footer reads "All rights reserved" (read 2026-11-27). Confirm its terms with the publisher before you map to it. **Map by code only** |
| Financial reporting | IFRS Accounting Taxonomy | IFRS Foundation, https://www.ifrs.org/issued-standards/ifrs-taxonomy/ | Free for professional use (preparing, auditing or advising on reports); a licence is needed for commercial use, such as building it into software for others (the taxonomy page, read 2026-11-27). Read its licensing terms and conditions, https://www.ifrs.org/content/dam/ifrs/about-us/legal-and-governance/legal-docs/taxonomy/taxonomy-terms-and-conditions.pdf, before any commercial use, mapping included. **Map by code only** |
| Products and services | UNSPSC (United Nations Standard Products and Services Code) | United Nations Development Programme (UNDP), which owns it, https://www.undp.org/unspsc | UNDP calls it an open standard, and the current version can be downloaded at no cost (read 2026-11-27). Not published as RDF: **map by code only** |
| Products | GS1 Global Product Classification (GPC) | GS1, https://www.gs1.org/standards/gpc | The GPC page states no terms (read 2026-11-27): read GS1's terms before use. **Map by code only** |
| Skills and occupations | ESCO (European Skills, Competences, Qualifications and Occupations) | European Commission, https://esco.ec.europa.eu/ | Free to download in all 28 ESCO languages; the download page states no licence (read 2026-11-27), so read the Commission's legal notice, https://commission.europa.eu/legal-notice_en, before you map to it |
| Data catalogues | DCAT-AP (DCAT Application Profile for data portals in Europe), version 3.0.1 | SEMIC, Interoperable Europe, European Commission, https://semiceu.github.io/DCAT-AP/ | CC BY 4.0 (read 2026-11-27) |
| Tabular data | CSV on the Web (CSVW): the Metadata Vocabulary for Tabular Data, namespace `http://www.w3.org/ns/csvw#`, and the Model for Tabular Data and Metadata on the Web | W3C, https://www.w3.org/TR/tabular-metadata/ and https://www.w3.org/TR/tabular-data-model/ (both Recommendations, 17 December 2015) | A W3C vocabulary: use it by IRI (rule 2) |

*Why:* these topics (statistics, financial reporting, products, skills, catalogues, tables) turn up in many domains, and a survey that searches only the domain's own words misses them. Two are European (ESCO and DCAT-AP); look for the national or sector equivalent where your scope lies elsewhere.

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

**Map by code only** is a limit on Map, not a fourth treatment: the external code goes on your node as an identifier with `rdfs:seeAlso` to its record (rule 3), and none of the source's terms, labels or structure is copied in. Use it for a source that is not published as RDF, or whose terms restrict copying.

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

Each of the four core registries in "The registries to search", and each further registry there that fits the domain, has a row in the register's registry-search table with its query terms and its hits or "no hits"; each common vocabulary whose topic the scope touches has a row in the survey table; every surveyed source has a recorded treatment and, unless it is ignored, its licence, version and target step; every gap is recorded as a finding, and every applied mapping is a row in a mapping set that passes `scripts/check_sssom.py`.
