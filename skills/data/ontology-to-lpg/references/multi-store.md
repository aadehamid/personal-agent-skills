# Multi-store: one source, several stores, nothing lost

Read it when the same released ontology must live in triple stores and in Neo4j or Aura, and you must prove each copy holds exactly the source. It is the plan the skill's owner decided on 2026-10-23. Hops 1, 4 and 5, and the counts of hop 3 (add-on J, which loads the released files as they are until hop 2 exists), can be run with this skill's scripts today. Hop 2 (skolemize), hop 3's export diff and Databricks store (add-on K), and hop 6 (the rebuild) are planned, not built.

## The flow

| Hop | What happens | The check | Status |
|---|---|---|---|
| 1. Source | The released packages and their data files are the master copy (`inputs.md`, rule 1). | `check_projection_rules.py` and `validate_data.py` pass (SKILL.md steps 2 and 3). | Built |
| 2. Skolemize | Replace every blank node with a Skolem IRI once, before any load, and keep that file beside the release as the derived copy every store reads; the release stays the master copy. | The skolemized file has no blank node and the same number of triples; a reverse map from Skolem IRI to blank node turns it back into a graph isomorphic to the original (rdflib `to_isomorphic`). | Planned: no script yet |
| 3. Triple stores | Load the skolemized files into each store, one named graph per file. Any SPARQL 1.1 store through add-on J. Databricks through add-on K: a Delta table in Unity Catalog with the columns `subject`, `predicate`, `object`, `datatype`, `lang`, `graph`. | Counts per graph and per predicate equal the files' (`triplestore.py`). Then export each store back to N-Triples and diff it with the source: zero lost, zero added. | J built and tested on Jena Fuseki 6.2.0 (counts only, on the library and a multi-module ontology, loading the unskolemized files; the export diff is planned). K planned |
| 4. Local Neo4j | Project with n10s: SKILL.md steps 4 to 6. | `check-report` passes: what n10s compiled, one fail case per row, the round trip and two equal hashes (`pipeline.md`, rules 13 to 17). | Built |
| 5. Aura or any Neo4j | Copy the verified graph with add-on I. | The target's graph hash equals the local one and the report's. | Built; run against a local second Neo4j and Aura Free |
| 6. Rebuild | Delete the local Neo4j and the Aura data. Rebuild both, taking a store's export (for example the Databricks Delta table) as the source of hops 4 and 5. | The rebuilt graph's hash equals the hash from hop 4, and its round trip against the original source files loses and adds nothing. That proves source → store → Neo4j and Aura loses nothing. | Planned |

## The data flow, box by box

The diagram is `diagrams/data-flow.png` (source `diagrams/data-flow.eraser`; the editable `diagrams/data-flow.excalidraw` comes from `diagrams/make_data_flow.py`). Its groups, left to right, and every arrow:

**Sources** (grey, three boxes: "Source documents", "Industry and peer sources", "Reference process model"). They stand for the sources the ontology is built from, whatever the domain. Arrows into "W3C stack": the source material crosses into the ontology build; the `ontology` skill cites every fact it takes. Nothing here is checked by this skill.

**Ontology build (ontology skill, Steps 1-11)** (blue). "W3C stack: RDF, OWL, SKOS, SHACL, PROV-O, DCAT" → "check.sh, pySHACL, competency questions (SPARQL)" → "Released packages + DCAT catalog (git tags)". These are the `ontology` skill's steps; its gates prove each release before this skill reads it. The released packages are the master copy (hop 1 above).

**Released packages → "Skolemize blank nodes (stable IRIs)"** (yellow). What crosses: every released data file. What happens: hop 2. The check: no blank node left, same triple count, the reverse map gives an isomorphic graph. Planned: no script yet.

**Skolemize → Triple stores** (purple), two arrows:
- "load, export back, compare" into "Apache Jena Fuseki, Graph Store Protocol, one named graph per package": `triplestore.py` (add-on J) replaces each named graph with `PUT`; the check is the per-graph and per-predicate counts against the files, then the export diff of hop 3. Counts built; the export diff planned.
- "triple for triple" into "Databricks: Delta triple table in Unity Catalog (planned)": add-on K, with the two boxes under it, "Free Edition: transfers run from your machine" and "Enterprise: your machine, or a job in the workspace", whose arrows point at the table because both modes write the same table (see "Databricks: two modes" below). Planned.

**Skolemize → ontology-to-lpg skill** (orange): "Check: design rules, data shapes, refusals" → "Reason: ROBOT + ELK, once, upstream" → "Serialise: loadable.nt + inferred.nt (check-serialised)". These are SKILL.md steps 2 to 4, checks V1 to V5 below. Built.

**Serialise → Neo4j, local (Docker + n10s)** (green): "n10s load (SHORTEN, fixed order)" → "Gate: n10s listShapes() readback, one fail case per compiled constraint, round trip, determinism hash". What crosses: `loadable.nt`, `inferred.nt`, `merged.ttl` and the import-safe shapes, copied into the import folder by `load_verify.py`. The checks are V6 to V12 below. Built.

**Jena ⇢ Gate, "three-way counts: files, store, Neo4j"** (dashed): `triplestore.py --projection-report` compares the store's per-predicate counts with the files' and with the report's `export_predicate_counts` (check V14). Built.

**Gate → Neo4j Aura, "validated graph"**: "Copy over the driver; hash must match the local graph" → "GRAPH TYPE: schema enforced by the database". `copy_graph.py` (add-on I) copies the graph that passed V12 (check V13); `build.py graph-type` (add-on H) emits the statement applied after it (G1 to G4). Built; run on Aura Free.

**Databricks ⇢ Rebuild test ⇢ Check** (dashed, red group): "Empty local Neo4j and Aura, rebuild both from the Databricks export, compare with the released files: no loss end to end". What crosses: the store's export as N-Triples, which re-enters the skill at "Check" and runs the whole path again; the check is hop 6. Planned.

**Released packages ⇢ Later: Unity Catalog** (dashed): "OntoBricks (Databricks Labs): link Unity Catalog tables and metric views (the KPIs) to the business processes in the ontology". What crosses: the released ontology, as OntoBricks' domain ontology. No no-loss check applies: OntoBricks builds instances from tables, not from the release. Later, not part of this skill.

## The validation path, V1 to V14, and GRAPH TYPE, G1 to G4

The diagram is `diagrams/validation-path.png` (source `diagrams/validation-path.eraser`; `diagrams/validation-path.excalidraw` from `diagrams/make_validation_path.py`). Each check must pass before the next runs. The rules named here hold the detail; this section is the map. "Stops" means the command exits 1 (2 on bad input) and you go no further; from V6 to V12 it also means no report: `load_verify.py` writes `projection-report.json` only when every check passed (V12).

**Before the load (on the files)**

| # | Checks | Without it | Command, record | Rule |
|---|---|---|---|---|
| V1 | Design rules: one kind and one range per predicate (Rule 1), a cardinality shape (Rule 2), one fixed prefix per namespace, pins, rule-gap exceptions | an unmappable predicate loads as a guess, an unknown namespace gets an invented `ns0` prefix | `check_projection_rules.py`; stops | `design-rules.md`, rules 1 to 3; `inputs.md`, rules 1 to 6; `pipeline.md`, rule 1 |
| V2 | Full SHACL with pySHACL and SHACL-AF: the data, then asserted plus inferred together, 0 violations; values that cannot round-trip are refused | the graph would hold data the shapes reject, and the in-graph check (V8) runs only part of the shapes | `validate_data.py`; stops | `pipeline.md`, rules 1 to 3 |
| V3 | Reason once with ROBOT and ELK; keep only real inferences (IRI-to-IRI `rdf:type` and `rdfs:subClassOf`, no OWL API declarations) | Neo4j does no reasoning, so inferences would be missing, or declarations would load as facts | `robot reason`, `build.py inferred` | `pipeline.md`, rules 4 and 6 |
| V4 | `check-serialised`: one triple per line and nothing else, byte order, no repeats, nothing in `inferred.nt` already asserted | an unsorted or commented file breaks the fingerprint and the diffs | `build.py check-serialised`; stops | `pipeline.md`, rule 5 |
| V5 | Manifest: SHA-256 of every input and shape file, the input and shapes fingerprints | a report could outlive the inputs it checked | `build.py manifest [--verify]`; `projection-manifest.json` | `running.md`, rule 3 |

**In the local Neo4j (Docker + n10s)**, all in one `load_verify.py` run:

| # | Checks | Without it | Report field | Rule |
|---|---|---|---|---|
| V6 | Load in a fixed order; `onto.import` and both `rdf.import` calls return `OK`; the shapes import returns as many rows as `listShapes()` | a partial import would pass | `shapes_import_rows`, `in_graph_shape_constraints` | `pipeline.md`, rules 8 to 11 |
| V7 | Engine readback: `listShapes()` against the shapes file; every constraint n10s did not compile is listed. It does not stop the run: V2 already checked every constraint | silence from a constraint n10s never compiled would look like a pass | `compiled`, `not_compiled`, `prediction_differences`, `left_out_before_import` | `pipeline.md`, rule 13 |
| V8 | n10s `validate()`: 0 violations | the graph could differ from what V2 passed | `shacl_violations_in_graph` | `pipeline.md`, rule 15 |
| V9 | One fail case per compiled constraint, passing only on the right node, path and component; a committed mutant is caught, then restored to 0 violations | a check that cannot fire looks the same as a pass | `fail_cases`, `mutant`, `in_graph_mutant_violations` | `pipeline.md`, rules 14 and 15 |
| V10 | Round trip: export back to RDF, schema rows left out, 0 triples lost, 0 added | a value changed or dropped by the load would go unseen | `roundtrip_lost`, `roundtrip_added`, `export_predicate_counts` | `pipeline.md`, rule 16 |
| V11 | Determinism: a sorted and a shuffled load give one graph hash | the result could depend on load order | `determinism_hash_sorted`, `determinism_hash_shuffled` | `pipeline.md`, rule 17 |
| V12 | The report is written only when V6 to V11 all passed; `check-report` then requires `passed: true` and fingerprints that match the manifest (V5) | a failed or stale run could be committed as a pass | `passed`; `build.py check-report` | `running.md`, rules 3 and 5 |

**Delivery**

| # | Checks | Without it | Command, record | Rule |
|---|---|---|---|---|
| V13 | Aura copy: the Aura hash equals the local hash and the report's `determinism_hash_sorted` | a copy that dropped or changed anything would go unseen | `copy_graph.py --report`; stops before touching the target unless the report passed and its hash matches the source; prints both hashes | `add-ons.md`, I |
| V14 | Triple store: counts per graph, per predicate, and three-way (files, store, the report's export) | a store that lost triples would go unseen | `triplestore.py`; its report, written only when every count matched (else `<report>.failed`, exit 1) | `add-ons.md`, J |

**GRAPH TYPE on Aura** (Enterprise or Aura; Community refuses it)

| # | What | Rule |
|---|---|---|
| G1 | `build.py graph-type` prints one `ALTER CURRENT GRAPH TYPE SET` statement from the `sh:targetClass` shapes and the data (list types follow the load's multivalued list; no empty node type), with what it leaves out as `// left out:` comments | `add-ons.md`, H |
| G2 | Apply it after V13, on the copied graph, and confirm with `SHOW CURRENT GRAPH TYPE`; the data already passed V6 to V13, so it is accepted | `add-ons.md`, H |
| G3 | Probe: a write that breaks the type must fail with `Neo.ClientError.Schema.ConstraintValidationFailed`; roll it back | `add-ons.md`, H |
| G4 | From then on the database rejects bad writes from applications, where n10s cannot run | `add-ons.md`, H |

It covers labels, property types, `NOT NULL` (from `sh:minCount 1` with `sh:maxCount 1`), lists and relationship endpoints. It leaves out relationship counts, `sh:in`, `sh:pattern`, ranges and lengths, which have no `GRAPH TYPE` form. Coverage depends on `sh:targetClass` shapes: a shape that targets by node or by SHACL-SPARQL gives no element type (on one multi-module test ontology, 35 node and 46 relationship element types). It guards later writes; the n10s gate (V6 to V12) stays the proof that the projection is right.

## Why each step is there

- **Skolemize first.** Blank nodes have no identity outside one file: "Blank nodes do not have identifiers in the RDF abstract syntax" (RDF 1.1 Concepts, §3.5, https://www.w3.org/TR/rdf11-concepts/#section-skolemization). Each store would relabel them, and the stores could then be compared only by graph isomorphism, not triple by triple. §3.5 allows systems to "replace some or all of the blank nodes in an RDF graph with IRIs" (quoted), and says Skolem IRIs meant to be recognised outside the system "SHOULD use a well-known IRI ... with the registered name genid", a path starting `/.well-known/genid/` (quoted). Mint them under a base you document, such as `https://id.example.org/.well-known/genid/`, from a stable hash of the blank node's own triples, so a rerun mints the same IRIs. Design rule 3 (`design-rules.md`) already keeps blank nodes out of the data; the files still hold them in OWL axioms and RDF lists, and those are what skolemizing fixes for the stores. A Skolem IRI minted from the node's triples is not an IRI "generated per run", which rule 3 forbids: the same input always gives the same IRI.
- **Export back, not only count.** Matching counts can hide a changed value; a diff of the export against the source cannot.
- **Neo4j stays the projection.** The triple stores hold the same triples as the source; Neo4j holds the projection that n10s, the shapes and the round trip verified. The rebuild of hop 6 tests that a store's copy is a valid source for the projection.

## Databricks: two modes for add-on K

Add-on K must run on both editions. The no-loss checks are the same in both; only where the transfer runs differs.

- **Free Edition.** It is serverless only, with "One SQL warehouse, limited to a 2X-Small cluster size", and "outbound internet access is restricted to a limited set of trusted domains" (quoted from Databricks Free Edition limitations, https://docs.databricks.com/aws/en/getting-started/free-edition-limitations, read 2026-10-23). So every transfer runs from your machine: write and read the Delta table over the Databricks SQL connector, write N-Triples locally, and load Neo4j or Aura from there. Never push from a notebook to Aura.
- **Enterprise (paid) workspaces.** The same machine-driven path works. The load, or the rebuild of hop 6, may also run inside the workspace, as a job or a notebook, when the workspace's network rules allow the destination: a serverless network policy is either full access or restricted to listed destinations (Databricks, "What is serverless egress control?", https://docs.databricks.com/aws/en/security/network/serverless-network-security/network-policies, read 2026-10-23). Check that Aura's host is allowed before you plan an in-workspace copy. A graph written to Aura from the workspace skips the local n10s gate, so it counts only when its hash equals the hash of hop 4. Classic compute's egress depends on the workspace's own network setup; this is not verified here.

- **No built-in triple store.** Add-on K is a plain Delta table, written and read with SQL, and checked like any store in hop 3.
- **OntoBricks is a later tool, not the store.** OntoBricks (Databricks Labs, https://github.com/databrickslabs/ontobricks, read at commit `97b27c7`) works per domain: an ontology, R2RML mappings from Unity Catalog tables, and a graph it materialises from those tables. It builds instances only from the tables through the mappings, so it cannot hold the released files triple for triple. Use it later to link Unity Catalog data and metric views to the ontology.
