# Sources

This file lists every source the ontology skill draws on: what the skill took from each, the version or date used, and how to check for a newer one. Agents do not read it. All text in the skill is our own wording, except short quotations marked as such.

Last full review: 2026-10-22. Check the sources below every three months, and whenever a W3C specification publishes a new version. The property-graph sources (n10s, Neo4j, the guideline) follow the `ontology-to-lpg` skill's review schedule.

## 1. The method as practised

- **What it is:** the written method and decision records of a private build of a downstream refining enterprise's process ontology (2026). The build ran Steps 0 to 12 over several modules, released them as versioned packages, and projected them into Neo4j.
- **Version used:** the method as it stood on 2026-10-22.
- **What the skill took:** the step sequence and its gates; the ten policies; the source policies; the eleven promotion rules, the predicate review method and the source-correction backlog; the quality bar and the soundness checks; organizations, roles and RACI; plans and runs; integration of measures and other overlays; SHACL testing; versioning and release packages; the governance rules on decisions, delegation, checks and privacy.
- **Scripts taken on 2026-10-24:** `check_shapes.py`, `check_code_lists.py`, `check_packages.py` and `run_regression.py` generalise that build's whole-graph gate, controlled-value test, release-package test and competency-question runner. They read their files, and the schemes to leave out, from the command line. On that build's released packages they gave the same results as its own tests that day, as recorded in the pull request that added them.
- **Added on 2026-10-24 at the ontology owner's request:** every release's changelog states its known gaps (`release.md`, rule 18), so the gaps a build knows about travel with the release instead of staying in the build's notes.
- **What the skill left out:** every project-specific decision, identifier, namespace, count and internal name, and the history of how each rule was learned. The skill keeps each rule's reason and drops the incident behind it.
- **Licence:** the ontology owner's own work, used with permission.
- **How to check for updates:** ask the ontology owner whether the method has changed since 2026-10-22.

## 2. Ontology-to-LPG Conversion Playbook

- **What it is:** the guideline for mapping an OWL and SKOS ontology into a Neo4j labelled property graph. Version 2.2 (October 2026) was in the enterprise-people-graph repository; since 2026-10-23 the guideline is the `ontology-to-lpg` skill in this repository (version 2.3), whose `SOURCES.md` lists its sources.
- **What the skill took:** when to project and the Rule 4 choice, in `references/lpg-projection.md`, which points to `ontology-to-lpg` for the method.
- **Licence:** the ontology owner's own work, used with permission.
- **How to check for updates:** follow `ontology-to-lpg`'s `SOURCES.md`.

## 3. Juha Korpela, *Building Semantics with Conceptual Models* (Common Sense Data, 2026)

- **What the skill took:** the conceptual-modelling rules in `references/foundations.md`: model the business, not the storage; entities and relationships before attributes; singular nouns; a definition for every entity; relationships as verbs; subtypes only where the business tells kinds apart; declare, don't suggest.
- **Licence:** a published book. Nothing is quoted.

## 4. W3C specifications and other standards

| Source | Version and date | Used in | What the skill took |
|---|---|---|---|
| RDF 1.1 Concepts and Abstract Syntax, https://www.w3.org/TR/rdf11-concepts/ | W3C Recommendation, 25 February 2014 | `foundations.md`, policy 5 | Language-tagged and plain literals are different terms. |
| RDF Schema 1.1, https://www.w3.org/TR/rdf-schema/ | W3C Recommendation, 25 February 2014 | `domain-model.md`, rule 6 | §3.1 and §3.2: several `rdfs:domain` or `rdfs:range` statements mean "all of the classes". Quoted. |
| SKOS Reference, https://www.w3.org/TR/skos-reference/ | W3C Recommendation, 18 August 2009 | `identity-taxonomy.md`, Step 3; `domain-model.md`, rule 1 | The SKOS model; integrity condition S14 (one `skos:prefLabel` per language tag); §1.3: concepts are individuals, classes are classes, and a SKOS-aware system must tell them apart (quoted). |
| SKOS Primer, https://www.w3.org/TR/skos-primer/ | W3C Working Group Note, 18 August 2009 | `domain-model.md`, rules 1 and 3 | §5.2, "SKOS Concepts and OWL Classes": SKOS concepts are OWL individuals; OWL DL users keep concepts and classes formally distinct and bridge them with an annotation property (quoted). |
| OWL 2 Document Overview (Second Edition), https://www.w3.org/TR/owl2-overview/ | W3C Recommendation, 11 December 2012 | `domain-model.md` | The OWL 2 document set. |
| OWL 2 Primer (Second Edition), https://www.w3.org/TR/owl2-primer/ | W3C Recommendation, 11 December 2012 | `domain-model.md`, rules 5 and 7; `identity-taxonomy.md`, Step 3, rule 1 | §2, "What is OWL 2?": the open-world assumption (quoted); §4.2: a subclass axiom lets a reasoner infer membership in the parent (quoted); §4.3: disjointness must be stated explicitly (quoted); §8.1: annotations are not part of the logical meaning (quoted); §8.3: one name, one property kind in OWL 2 DL (paraphrased). |
| SHACL, https://www.w3.org/TR/shacl/ | W3C Recommendation, 20 July 2017 | `shacl.md`, `domain-model.md`, templates | Shapes, cardinality, `sh:in` (§4.8.3, quoted), `sh:pattern` (§4.4.3). |
| SPARQL 1.1 Query Language, https://www.w3.org/TR/sparql11-query/ | W3C Recommendation, 21 March 2013 | `shacl.md`, rule 17; `regression.md` | §17.4.3.14 `REGEX`; competency questions as queries. |
| XPath and XQuery Functions and Operators 3.1, https://www.w3.org/TR/xpath-functions-31/ | W3C Recommendation, 21 March 2017 | `shacl.md`, rule 17 | §5.6.3 `fn:matches` searches the string. Quoted. |
| The Organization Ontology (ORG), https://www.w3.org/TR/vocab-org/ | W3C Recommendation, 16 January 2014 | `organization.md` | `org:Role`, `org:Membership`, `org:subOrganizationOf` (quoted), sites and units. |
| PROV-O, https://www.w3.org/TR/prov-o/ | W3C Recommendation, 30 April 2013 | `provenance.md` | Qualified association and `prov:hadPlan` from a run to its definition. |
| P-Plan, http://purl.org/net/p-plan# (a community ontology, not a W3C specification) | ontology version 1.2, modified 2013-05-17; documentation release 17 September 2013 | `provenance.md` | Plans and steps, left unused while the taxonomy is a naming hierarchy. Quoted. |
| The RDF Data Cube Vocabulary, https://www.w3.org/TR/vocab-data-cube/ | W3C Recommendation, 16 January 2014; read 2026-10-24 | `integration.md`, rules 29 to 31 | `qb:concept` links a component property to the `skos:Concept` it represents (§6.1, §12.9); a data structure definition, its dimensions, measures and attributes; integrity constraints IC-4, IC-5 and IC-19. Paraphrased. |
| DCAT Version 3, https://www.w3.org/TR/vocab-dcat-3/ | W3C Recommendation, 22 August 2024 | `release.md`, `integration.md` | Dataset and distribution records for release packages; a data product concept linked by `rdfs:seeAlso` to the catalog record of a dataset that realizes it, never typed or SKOS-matched as one. |
| DCMI Metadata Terms, https://www.dublincore.org/specifications/dublin-core/dcmi-terms/ | 2020-01-20 | `quality.md`, point 8; templates | `dcterms:creator`, `dcterms:dateAccepted`, `dcterms:source`, `dcterms:references`, `dcterms:rights`. |
| ISO 704:2022, *Terminology work: Principles and methods* | 2022 | `quality.md`, point 1 | The intensional definition (genus and difference). Not quoted. |
| qSKOS, "Quality Issues", https://github.com/cmader/qSKOS/wiki/Quality-Issues; Mader, Haslhofer and Isaac, "Finding Quality Issues in SKOS Vocabularies", TPDL 2012, https://arxiv.org/abs/1206.1339 | wiki page last edited 8 February 2022 (33 revisions); qSKOS v2.0.4, commit `082a7c66f1`, 1 June 2024; read 2026-10-24 | `quality.md`, "The qSKOS issues"; `scripts/check_taxonomy.py` | The 29 issues and each one's definition, paraphrased; the v2.0.4 query behind each check (its inverse pairs, the language literals it counts, the labels it compares, its exact-match chains), and the deliberate differences the table names. |
| BCP 47: RFC 5646, *Tags for Identifying Languages*, https://www.rfc-editor.org/rfc/rfc5646 | September 2009 | `scripts/check_taxonomy.py`, `lang-tag` | §2.1, the syntax of a well-formed tag (grandfathered tags included). qSKOS cites RFC 3066, which RFC 5646 replaced. |
| Linked Open Vocabularies (LOV), https://lov.linkeddata.es/; Vandenbussche, Atemezing, Poveda-Villalón and Vatant, "Linked Open Vocabularies (LOV): a gateway to reusable semantic vocabularies on the Web", *Semantic Web* 8(3), 2017, https://doi.org/10.3233/SW-160213 | Site and API documentation page (`/dataset/api`) read 2026-10-24; that day its SPARQL endpoint (`/dataset/lov/sparql`) and REST API (`/dataset/lov/api/v2/...`) answered with an HTML page instead of results, so neither is verified | `external-ontologies.md`, "The registries to search" | What LOV catalogs and its search interfaces. |
| BARTOC, Basic Register of Thesauri, Ontologies & Classifications, https://bartoc.org/about | About page read 2026-10-24; the JSKOS API at https://bartoc.org/api/ answered that day | same section | What it registers (any KOS, any subject, language and format); run by the Verbundzentrale des GBV since 2020; keyword and advanced search. |
| Open Knowledge Graphs, https://openknowledgegraphs.com/ | Read 2026-10-24: 3,217 resources listed, "sourced from Wikidata", "daily-refreshed" (its page description) | same section | What it lists and how to filter it. Its page metadata (schema.org JSON-LD) names the publisher, Steve Hedden, an MIT licence for the site and CC0 for the data; source at https://github.com/SteveHedden/open-knowledge-graphs. |
| DBpedia Archivo, https://archivo.dbpedia.org/; Frey, Streitmatter, Götz, Hellmann and Arndt, "DBpedia Archivo: A Web-Scale Interface for Ontology Archiving under Consumer-Oriented Aspects", SEMANTiCS 2020, LNCS 12378, https://svn.aksw.org/papers/2020/semantics_archivo/public.pdf; code https://github.com/dbpedia/archivo | Paper (2020) and repository README (latest commit `e8ad81b`, 2024-08-26) read 2026-10-24; the site did not answer from this machine that day | same section | Archiving of ontology versions several times a day (the paper), the star rating (README, "Star Rating"), the `/info` and `/list` pages, and `download?o=<IRI>&f=<ttl|owl|nt>` for the latest version (README, "Accessing an Ontology"). |
| ANSI/NISO Z39.19-2005 (R2010), *Guidelines for the Construction, Format, and Management of Monolingual Controlled Vocabularies*, https://www.niso.org/publications/ansiniso-z3919-2005-r2010 (free PDF from NISO) | 2005, reaffirmed May 2010 (DOI 10.3789/ansi.niso.z39.19-2005R2010); read in full 2026-10-24 | `quality.md`, "The vocabulary standards behind these rules" | Quoted: §4.1 the definition requirement and its note; §6.2.1 (a) to (c) compounds and qualifiers; §6.2.2 and §6.2.2.1 scope notes and reciprocal scope notes; §6.5.1 plural count nouns and §6.5.1.1 the warrant exception; §6.6.3.1, §6.6.3.2.1 and §6.6.3.2.2 abbreviations; §8.3 and §8.3.1 hierarchical and generic relationships; §8.3.4 polyhierarchy; §11.3.1.2 and §11.3.2.2 history notes. Also `identity-taxonomy.md`, Step 3, rule 8 (abbreviations). |
| ISO 25964-1:2011, *Information and documentation — Thesauri and interoperability with other vocabularies — Part 1: Thesauri for information retrieval*, https://www.iso.org/standard/53657.html | Published 2011-08, last reviewed and confirmed 2022; revision under way (ISO project 86713); catalogue record read 2026-10-24 | `quality.md`, same section | Named as Z39.19's international counterpart only. The text is paywalled and was not read; no rule claims to follow its clauses. |
| ISO 25964-2:2013, *Part 2: Interoperability with other vocabularies*, https://www.iso.org/standard/53658.html | Published 2013-03, last reviewed and confirmed 2023; revision under way (ISO project 92117); catalogue record read 2026-10-24 | `quality.md`, same section | Named as the counterpart for mappings between vocabularies only. Text not read; no rule claims to follow its clauses. |
| SSSOM, Simple Standard for Sharing Ontology Mappings, https://mapping-commons.github.io/sssom/ (data model, SSSOM/TSV format, the `mapping_justification` and `confidence` slots) | Version 1.0 (`sssom-schema` 1.0.0, PyPI, 2024-08-09); 1.1 in alpha (v1.1.0a5, 2026-05-22); the site's pages are built from the development branch; read 2026-10-24, and the `mapping_justification` pattern read at tags v1.0.0 and v1.1.0a5 and on the development branch 2026-10-25 | `external-ontologies.md`, rules 9 to 12; `scripts/check_sssom.py`; `templates/mappings.sssom.tsv` | The four required mapping slots and the literal-mapping exception; `mapping_set_id` and `license` required on a set; CURIEs in SSSOM/TSV with every prefix declared or built in, and the eight built-in prefixes; `confidence` from 0 to 1; the nine SEMAPV justifications of v1.0.0's pattern and the four v1.1.0a5 adds; the development branch's seven further values (LLM-based matching among them) are in no release and are refused; `sssom_version`, when stated, must be 1.1; any predicate is accepted, of which the common SKOS ones are listed. "There can be no mapping without some form of justification" is paraphrased from the model page. |
| Widoco, https://github.com/dgarijo/Widoco | 1.4.25 (released 2024-06-30), the jar built for JDK 17, run on OpenJDK 24 on 2026-10-24; 1.4.26 was released 2026-10-23 and is not yet used | `release.md`, rules 24 to 27; `scripts/build_docs.py` | `-ontFile`, `-outFolder`, `-rewriteAll`, `-noPlaceHolderText`, `-lang`; it writes `index-<lang>.html`, sections, and the ontology in four serialisations. Run on the worked test package and on one real package as a trial. |
| Tim Berners-Lee, "Cool URIs don't change", https://www.w3.org/Provider/Style/URI | W3C, 1998 | `identity-taxonomy.md`, Step 2, rule 2 | Keep information that changes out of identifiers. |

**How to check for updates:** open each W3C link and compare the "Latest published version" with the date above; read the errata page linked from it. For DCMI Metadata Terms, compare the date at the top of the page.

## 5. n10s: its source code, and behaviour observed in October 2026

The two `sh:pattern` and `sh:in` facts in `references/shacl.md` (rules 17 and 18) rest on the n10s source at tag 2025.06.1 (commit `6a5846b`), `src/main/java/n10s/validation/SHACLValidator.java`, https://github.com/neo4j-labs/neosemantics/blob/2025.06.1/src/main/java/n10s/validation/SHACLValidator.java:

- Lines 1408 to 1417: `sh:pattern` compiles to Cypher `toString(x) =~ params.theRegex`; Cypher's `=~` matches the whole string.
- Lines 1044 to 1048: a literal `sh:in` list is read as a list of strings; line 471 stores it as `params.put("theInLiterals", valueLiteralList)`; line 1359 tests `val in params.theInLiterals`.

The other n10s facts (the constraints it cannot run, SHORTEN against MAP mode) moved with the projection method to the `ontology-to-lpg` skill; its `SOURCES.md`, section 3, cites them.

Status facts that change over time, checked 2026-10-22:

- RDF 1.2 Concepts is a W3C Candidate Recommendation Snapshot, 7 April 2026: https://www.w3.org/TR/rdf12-concepts/
- rdflib RDF 1.2 support: https://github.com/RDFLib/rdflib/issues/3524 (all stages open).
- Apache Jena: full RDF 1.2 syntax and SPARQL 1.2 from 6.1.0 (5.4.0 to 6.0.x was an experimental preview), per https://github.com/apache/jena/blob/main/CHANGES.txt.
- Eclipse RDF4J: RDF 1.2 from 6.0.0, https://rdf4j.org/release-notes/6.0.0/
- n10s: https://github.com/neo4j-labs/neosemantics. The skill cites the implementation at tag 2025.06.1, commit `6a5846b` (29 May 2026), which runs on Neo4j 2025.06.2 and has no RDF 1.2 support. The default branch's latest commit is `d5cfd2a` (9 October 2026, "Add Neo4j Labs disclaimer"), checked 2026-10-23.

**How to check for updates:** `gh api repos/neo4j-labs/neosemantics/releases --jq '.[0] | "\(.tag_name) \(.published_at)"'`; re-run the pass-and-fail test in `shacl.md`, rule 16, on any new n10s release before relying on it; recheck the RDF 1.2 and library links above.

## 6. Outside sources: Going Meta and the Neo4j ontology skill

Read on 2026-10-22: the slides and code of nine Going Meta sessions in https://github.com/jbarrasa/goingmeta (YouTube titles, descriptions and chapters; no video or transcript), and every file of the Neo4j ontology agent skill.

| Source | Date | What it contains |
|---|---|---|
| Going Meta `session39`, "Ontology Creation with the Neo4j MCP Server" | 7 October 2025 | An agent designs a graph model; a script converts Mermaid to OWL and silently drops edges with properties and gives a shared property two domains. |
| Going Meta `session41`, "Ontologies, LLMs, Property Graphs - Do we really have a Jaguar Problem?" | 9 December 2025 | An LLM given an ontology still produced triples that break it; reasoning belongs in a reasoner ("This is Dangerous!!!", PDF p11). |
| Going Meta `session42`, "Evaluating the Quality of Ontologies" | 6 January 2026 | Four families of quality metrics, Cypher for structural ones, an LLM competency-question scorer checked in Neo4j. |
| Going Meta `session44`, "Validating Neo4j Graphs with SHACL" | 3 March 2026 | SHACL against a property graph through tools that compile shapes to Cypher; inspect the compiled query. |
| Going Meta `session45`, S03E07 "Agent Skills For Creating and Using Ontologies" | 7 April 2026 | An ontology-builder skill: input buckets, a requirement gate, an evidence gate, genus-and-difference definitions, a requirements YAML file whose first question needs an area it puts out of scope. |
| Going Meta `session46`, "The Graph Behind the Graph: Tracing Ontology Design Decisions" | 5 May 2026 (YouTube 12 May) | The session45 skill run with every modelling choice written to agent memory. |
| Going Meta `session48`, "Actionable Knowledge For Agents With Context Graphs" (William Lyon) | 7 July 2026 | A constrained model writes only from supplied source references and a worker re-checks every claim (PDF p54); drift and staleness checks. |
| Going Meta `session49`, "Unwrapping OKF" | 4 August 2026 | Trust tiers, lifecycle and staleness; "an LLM never touches it" for structure (PDF p13). |
| `neo4j-contrib/neo4j-skills`, `neo4j-ontology-skill` 1.0.1, https://github.com/neo4j-contrib/neo4j-skills/tree/39247b9c4ab20062aefd1cfe83c040167ef9ee83/neo4j-ontology-skill | commit `39247b9`, 21 October 2026; MIT licence | A skill that writes property-graph schema documents and must not report done while its validator exits non-zero; it names what it does not do. Its validator falls back to a moving schema alias when the named version cannot be fetched. |

**Proposals adopted, and where:**

| Proposal | Where in the skill |
|---|---|
| Name each thin input and stop for the owner; keep requirements machine-readable with a conflict check (session45) | `governance.md`, rules 1 and 2; `templates/requirements.yaml`; `scripts/check_requirements.py` |
| Trace every element to a competency question and list what was left out (session45) | `regression.md`, rules 1 and 2; `domain-model.md`, rule 8; `templates/competency-questions.md` |
| Genus-and-difference definitions (session45) | `quality.md`, point 1, "thing" form |
| Two domains mean "both" (session39's converter output) | `domain-model.md`, rule 6 |
| State the skill's boundary; keep validation blocking; pin the validated version (Neo4j skill) | `SKILL.md` scope line; `governance.md`, rules 16, 17 and 27 |
| Structure from deterministic code; model-written text only from supplied sources, re-checked (sessions 41, 48, 49) | `governance.md`, rules 18 and 19 |
| Test how the target engine runs each constraint; anchor every pattern (session44, with our own n10s observation) | `shacl.md`, rules 16 to 18 |

**Proposals not adopted, and why:**

| Proposal | Why not (yet) |
|---|---|
| Check that cited sources still exist and still say what was cited; a stale-after date on facts (sessions 48, 49) | A check that fetches sources makes the check script depend on the network and on other sites' uptime. Open item. |
| Make the decision trace queryable by projecting decision records into the graph with PROV-O (sessions 46, 48) | Records stay as reviewed Markdown; `provenance.md`, rule 10 covers assertions about mappings only. Open item. |
| A quality scorecard of structural metrics and a one-purpose coherence check per module (sessions 42, 48) | Advisory metrics; no evidence yet that they catch a defect the gates miss. Open item. |
| Serve the projection's consumers: a serve or do-not-serve view, a derived trust tier, stub nodes for unresolved references, a schema string for text-to-Cypher (session49) | Belongs with a consumer of the graph; `integration.md`, rule 27 keeps the consumer rules. Open item. |
| Extraction artifacts: a GraphRAG schema export, `skos:example` values, a plain-English rendering of the ontology (sessions 41, 45) | The skill builds no extraction pipeline. |
| Mutually disjoint top classes, and a three-level depth cap (session45) | Declined on purpose: `foundations.md`, conceptual modelling, rule 6 allows disjointness only where the business guarantees it, and a process hierarchy can be deeper. |
| "Absent means none" against empty values (Neo4j skill) | Covered in part by closed shapes; not written as its own rule. |

**How to check for updates:** `gh api "repos/jbarrasa/goingmeta/commits?since=2026-10-22T00:00:00Z" --jq '.[] | "\(.sha[0:12]) \(.commit.message|split("\n")[0])"'` and `gh api "repos/neo4j-contrib/neo4j-skills/commits?path=neo4j-ontology-skill&since=2026-10-21T00:00:00Z" --jq '.[] | "\(.sha[0:12]) \(.commit.message|split("\n")[0])"'`.
