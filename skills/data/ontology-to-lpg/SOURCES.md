# Sources

This file lists every source the ontology-to-lpg skill draws on: what the skill took from each, the version or date used, and how to check for a newer one. Agents do not read it. All text in the skill is our own wording, except short quotations marked as such.

Last full review: 2026-10-23. Check the sources below every three months, and whenever n10s, Neo4j, ROBOT or a W3C specification below publishes a new version.

## 1. The Ontology-to-LPG Conversion Playbook, version 2.2, and its learning guide

- **What it is:** Hamid Adesokan's guideline for converting a W3C ontology into a Neo4j labelled property graph, with a companion learning guide. Folder `guideline_to_map_ontology_to_LPG/` of https://github.com/aadehamid/enterprise-people-graph: `Ontology_to_LPG_Conversion_Playbook.md` and `Ontology_Skills_for_LPG_Mapping.md`.
- **Version used:** v2.2, commit `8ce9ada` (merge of PR #3, 14 October 2026), read 2026-10-23 from the repository's `main`.
- **What the skill took:** everything, rewritten. The scope table, the mental model, design rules 1 to 5 with options 4a and 4b, the five-step pipeline including the 4b flatten queries and the post-load Cypher, the scale table, add-ons A to G, the XSD to Cypher table, the checklist (now the "Done when" gates) and the anti-patterns go to `references/design-rules.md`, `pipeline.md`, `running.md` and `add-ons.md`. The learning guide goes to `references/learning-path.md`. Its examples are replaced by the library example.
- **What changed:** this skill is version 2.3 of the guideline; `references/versions.md` lists what it adds. The guideline folder is now superseded by this skill, by the owner's decision of 2026-10-23.
- **Licence:** the author's own work, used with permission. The repository has no licence file.
- **How to check for updates:** none expected; changes now land here. To compare with the old text: `gh api "repos/aadehamid/enterprise-people-graph/commits?path=guideline_to_map_ontology_to_LPG&per_page=3" --jq '.[] | "\(.sha[0:7]) \(.commit.message|split("\n")[0])"'`.

## 2. The method as practised

- **What it is:** the projection pipeline, tests and decision records of a private, multi-module enterprise ontology build that projected every one of its released packages into Neo4j in October 2026, with Neo4j 2025.06.2, n10s 2025.06.1 and ROBOT 1.9.10.
- **Version used:** the pipeline and its records as they stood on 2026-10-23.
- **What the skill took:** projecting released packages at their newest versions, pinned by hand and checked against the release folder, with each package's own shapes; applying Rules 1 and 2 to every owned namespace with fixed prefixes; the release-exceptions list that fails on a stale entry; counting an inverse link as a qualified-relation end, with exactly one such link per node; the n10s findings on `sh:pattern` and literal `sh:in` lists; the deliberate mutant; the manifest and the report with input and shape fingerprints; the CI and workstation split; container clean-up. `scripts/check_projection_rules.py` and `scripts/in_graph_shapes.py` are new, general versions of checks in that pipeline.
- **What the skill left out:** every module name, namespace, identifier, count, system and decision number, and the history of how each rule was learned. The skill keeps each rule's reason and drops the incident behind it.
- **Licence:** the ontology owner's own work, used with permission.
- **How to check for updates:** ask the ontology owner whether the projection method has changed since 2026-10-23.

## 3. n10s (neosemantics)

| Source | Version and date | Used in | What the skill took |
|---|---|---|---|
| Release 2025.06.1, https://github.com/neo4j-labs/neosemantics/releases/tag/2025.06.1 | published 2026-06-16; tag points at commit `6a5846b` | `pipeline.md`; `running.md`, rule 2 | The jar built for Neo4j 2025.06 (`neosemantics-2025.06.1.jar`). Its SHA-256, `4c461087...b3e` in full in `running.md`, is the `digest` GitHub records for the release asset (`gh api repos/neo4j-labs/neosemantics/releases/tags/2025.06.1 --jq '.assets[].digest'`), and matched a downloaded copy on 2026-10-23. |
| `SHACLValidator.java` at tag 2025.06.1, https://github.com/neo4j-labs/neosemantics/blob/2025.06.1/src/main/java/n10s/validation/SHACLValidator.java | read 2026-10-23 | `pipeline.md`, rule 13; `scripts/in_graph_shapes.py` | Lines 59 to 123 (`PROP_CONSTRAINT_QUERY`): the shapes n10s reads; line 73 follows `sh:node?/sh:property` one hop from the targeted shape, and the implicit class target (line 89) reads `a rdfs:Class`, so an `owl:Class` shape without `sh:targetClass` is not applied; it reads `sh:path`, `sh:inversePath`, `sh:class`, `sh:nodeKind`, `sh:datatype`, counts, ranges, lengths, `sh:hasValue`, `sh:in`, `sh:disjoint`, `sh:pattern` and `sh:targetClass` (or a node shape that is a class), and never `sh:and`, `sh:or` or `sh:xone`. Lines 1408 to 1417: `sh:pattern` compiles to Cypher `toString(x) =~ params.theRegex` (lines 1411 and 1412). Lines 1044 to 1048: a literal `sh:in` list is read as a list of strings (`inLiterals`); line 471 stores it as `params.put("theInLiterals", valueLiteralList)`; line 1359 tests `val in params.theInLiterals`. Lines 1030 to 1036: a literal `sh:hasValue` is stored as split strings; line 1300 tests it against the property's values. Lines 1191 to 1209 (`getDatatypeCastExpressionSuff`): only `xsd:boolean`, `xsd:string`, `xsd:integer`, `xsd:float`, `xsd:decimal`, `xsd:date`, `xsd:dateTime`, the GeoSPARQL WKT literal and `xsd:anyURI` are accepted; any other `sh:datatype` throws (line 1209). |
| `UriUtils.java` and `NsPrefixMap.java` at tag 2025.06.1, `src/main/java/n10s/utils/` | read 2026-10-23 | `design-rules.md`, rule 3 | `UriUtils.java` lines 47 to 52: a SHORTEN name is the namespace's prefix, the separator and the local name. `NsPrefixMap.java` line 105: an unknown namespace gets a generated `ns` prefix. |
| Mapping reference, https://neo4j.com/labs/neosemantics/4.0/mapping/ | read 2026-10-23 | `design-rules.md`, rule 5; `pipeline.md`, rule 9 | Mappings apply with `handleVocabUris: 'MAP'`, and in MAP mode "all non-mapped vocabulary elements ... will get the default treatment they get when the 'IGNORE' option is selected" (quoted). |
| Issue #237, https://github.com/neo4j-labs/neosemantics/issues/237, and PR #361, https://github.com/neo4j-labs/neosemantics/pull/361 | issue open since 2021-11-09; PR opened 2026-05-09, open; both checked 2026-10-23 | `design-rules.md`, rule 5 | SHACL does not validate with `handleVocabUris` set to MAP; the proposed fix is not merged. |
| Behaviour observed in the runs of section 2, October 2026 | n10s 2025.06.1 on Neo4j 2025.06.2 | `pipeline.md`, rules 9 and 13 | In MAP mode the shapes import failed with "The graph is not namespace aware"; n10s rejects `sh:datatype rdf:langString` and does not support `sh:not`, `sh:languageIn`, `sh:node` on a property shape, `sh:targetSubjectsOf` or `sh:targetObjectsOf`; a shape with a SPARQL target never runs; an unanchored `"\S"` failed every value longer than one character; a loaded `true` did not match `sh:in (true)`; an `sh:in` list of IRIs ran correctly. |
| A second run, 2026-10-23, with `load_verify.py` on the library templates | the same versions; image digest `sha256:0347fe5b1126dd328cc68a54449c2cf83636e348e2da1547abf62b2dbfad67f2` | `pipeline.md`, rules 11, 14 to 17; `running.md`, rules 2 and 5 | Every check passed: 30 shapes rows and 30 listed, 0 violations, eight generated fail cases with the components in rule 14's table, the mutant caught and restored, 0 lost and 0 added with 70 schema rows left out, equal hashes. The image copied its bundled `apoc-2025.06.2-core.jar` into the plugins folder as `apoc.jar` (SHA-256 `4df40cea...80fb`, in full in `running.md`) and changed the folder's owner; a plugins folder made by `mktemp -d` (mode 700) made the container exit until it was opened with `chmod 755`. Two other test runs, one of them on a private multi-module ontology, found that a read-only plugins mount fails; that a tagged string holding a newline exports as `xsd:string` `"text@en"` with no `literalLang`; and that n10s ignores `sh:lessThanOrEquals` (absent from `listShapes()`, and a forced violation reported nothing) while `sh:disjoint` runs but is not listed. |
| A run of this skill's scripts on the library templates, 2026-10-23 | n10s 2025.06.1 and APOC on `neo4j:2025.06.2`, ROBOT 1.9.10 | `pipeline.md`, rules 4, 10, 11, 14, 16 and 17 | ROBOT with `--include-indirect true` inferred `W-0043 rdf:type lib:Work`, which `build.py inferred` kept as the only inferred triple; without the flag nothing was inferred. The generated load script loaded without error; the shapes import returned 30 rows, equal to `listShapes()`; zero violations in the graph; each fail case in rule 14's table reported the component named (an inverse-path count included); with schema rows (70 of them) excluded, the round trip lost and added nothing; after emptying the database as rule 17 says, the sorted and shuffled loads gave equal hashes while the export returned 189 and 187 rows. A separate end-to-end run on the same versions found that sorting every list property also sorted `_n10sValidatorConfig` and broke `listShapes()` (`StreamCorruptedException`), and that the export returns a tagged literal's text with `literalLang` set. |

**How to check for updates:** `gh api repos/neo4j-labs/neosemantics/releases --jq '.[0] | "\(.tag_name) \(.published_at)"'` and `gh api repos/neo4j-labs/neosemantics/pulls/361 --jq '"\(.state) \(.merged_at)"'`. On a new release, re-run the pass and fail tests of `pipeline.md`, rule 14, before changing the drop list in `scripts/in_graph_shapes.py`.

## 4. Neo4j, Cypher and APOC

| Source | Version and date | Used in | What the skill took |
|---|---|---|---|
| Neo4j 2025.06.2, https://github.com/neo4j/neo4j (tag `2025.06.2`, "Release 2025.06.2") | tagged 2025-07-11 | `pipeline.md`; `running.md` | The tested database version; the Docker image installs APOC through `NEO4J_PLUGINS`. |
| Cypher Manual, "String operators", https://neo4j.com/docs/cypher-manual/current/expressions/predicates/string-operators/ | Cypher 25 manual, read 2026-10-23 | `pipeline.md`, rule 13 | `=~` takes a Java regular expression; the manual's examples prefix `.*` to match the end of a string (`n.email =~ '.*\\.se'`), because `=~` matches the whole string. |
| APOC, https://neo4j.com/docs/apoc/current/ | bundled with the neo4j:2025.06.2 image | `pipeline.md`, rules 10 and 12 | `apoc.coll.sort`, `apoc.merge.relationship`, `apoc.map.removeKeys`. |

**How to check for updates:** compare the Neo4j version n10s's newest release is built for with the pinned one.

## 5. ROBOT and ELK

| Source | Version and date | Used in | What the skill took |
|---|---|---|---|
| ROBOT v1.9.10, https://github.com/ontodev/robot/releases/tag/v1.9.10 | published 2026-02-18 | `pipeline.md`, rule 4; `running.md`, rule 2 | The tested reasoner wrapper. The SHA-256 of `robot.jar` in `running.md` is the release asset's GitHub `digest`, and matched a downloaded copy on 2026-10-23. |
| ROBOT `reason`, https://robot.obolibrary.org/reason | read 2026-10-23 | `pipeline.md`, rule 4 | ELK is the default reasoner; by default only inferred subclass axioms are asserted, and `--axiom-generators` adds others such as `ClassAssertion`; by default only direct axioms are generated (`--include-indirect false`); an incoherent ontology fails the step. |
| ROBOT Getting Started, https://robot.obolibrary.org/ | read 2026-10-23 | `running.md`, rule 1 | "make sure you have Java 11 or later installed" (quoted). |

**How to check for updates:** `gh api repos/ontodev/robot/releases --jq '.[0] | "\(.tag_name) \(.published_at)"'`.

## 6. W3C specifications and RDF tooling

| Source | Version and date | Used in | What the skill took |
|---|---|---|---|
| RDF 1.2 Concepts, https://www.w3.org/TR/rdf12-concepts/ | W3C Candidate Recommendation Snapshot, 7 April 2026 (checked 2026-10-23) | `design-rules.md`, rule 4 | Triple terms, `rdf:reifies`, triple terms only as objects; the status. |
| RDF 1.2 Turtle and Primer, https://www.w3.org/TR/rdf12-turtle/, https://www.w3.org/TR/rdf12-primer/ | the RDF 1.2 document set, as the guideline cites it | `design-rules.md`, rule 4; `learning-path.md` | The `~ reifier` and `{| |}` annotation syntax. |
| RDF 1.1 Concepts, https://www.w3.org/TR/rdf11-concepts/ | W3C Recommendation, 25 February 2014 | `pipeline.md`, rule 16 | A plain literal is an `xsd:string` literal. |
| SHACL, https://www.w3.org/TR/shacl/ | W3C Recommendation, 20 July 2017 | `design-rules.md`, rule 2; `pipeline.md`, rule 13 | Cardinality, `sh:in` (§4.8.3), `sh:pattern` (§4.4.3) defined through SPARQL `REGEX`. |
| SPARQL 1.1 Query, https://www.w3.org/TR/sparql11-query/ | W3C Recommendation, 21 March 2013 | `pipeline.md`, rule 13 | §17.4.3.14: `REGEX` invokes XPath `fn:matches`. |
| XPath and XQuery Functions and Operators 3.1, https://www.w3.org/TR/xpath-functions-31/ | W3C Recommendation, 21 March 2017 | `pipeline.md`, rule 13 | §5.6.3: `fn:matches` returns true "if $input or some substring of $input matches" the pattern (quoted), so SHACL searches. |
| ORG, https://www.w3.org/TR/vocab-org/, and PROV-O, https://www.w3.org/TR/prov-o/ | W3C Recommendations, 16 January 2014 and 30 April 2013 | `design-rules.md`, rule 4 | The qualified-relation pattern (`org:Membership`, `org:hasMembership`, `prov:qualifiedAssociation`). |
| OWL 2 Profiles, https://www.w3.org/TR/owl2-profiles/ | W3C Recommendation (Second Edition), 11 December 2012 | `design-rules.md`, OWL profile | The EL profile. |
| Apache Jena, https://github.com/apache/jena/blob/main/CHANGES.txt | 6.1.0, tagged 2026-05-03 | `design-rules.md`, rule 4; `pipeline.md` | "This version of Jena has support for RDF 1.2 syntax, input and output" (quoted, 6.1.0); 5.4.0 introduced "a preview of RDF 1.2 support. This work is *experimental*" (quoted). |
| Eclipse RDF4J 6.0.0 release notes, https://rdf4j.org/release-notes/6.0.0/ | GitHub release published 2026-08-10 | `design-rules.md`, rule 4 | "broad support for the current RDF 1.2 and SPARQL 1.2 specifications" (quoted). |
| RDF4J `URIUtil.getLocalNameIndex`, https://rdf4j.org/javadoc/3.7.7/org/eclipse/rdf4j/model/util/URIUtil.html | javadoc 3.7.7, read 2026-10-23 | `scripts/check_projection_rules.py` | An IRI's local name starts after the first `#`, else the last `/`, else the last `:`. n10s uses this split (`UriUtils.java`, section 3). |
| rdflib RDF 1.2 tracking, https://github.com/RDFLib/rdflib/issues/3524 | open, checked 2026-10-23 | `design-rules.md`, rule 4 | rdflib, and so pySHACL, do not read RDF 1.2 yet. |
| rdflib `compare`, https://rdflib.readthedocs.io/en/stable/apidocs/rdflib.compare/ | stable docs | `pipeline.md`, rule 16 | `to_isomorphic` and `graph_diff` for the round trip. |

**How to check for updates:** open each W3C link and compare the latest published version with the date above. For RDF 1.2, a move to Recommendation, and rdflib issue #3524 closing, are the two events that could make option 4b practical for a Python pipeline.

The learning guide's reading list (`references/learning-path.md`) names further books, courses and W3C documents; the skill takes no fact from them.
