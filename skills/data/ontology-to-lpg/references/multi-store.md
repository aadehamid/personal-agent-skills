# Multi-store: one source, several stores, nothing lost

Read it when the same released ontology must live in triple stores and in Neo4j or Aura, and you must prove each copy holds exactly the source. It is the plan the skill's owner decided on 2026-10-23. Hops 1, 4 and 5 run with this skill's scripts, and hops 2 and 3 (skolemize, Jena Fuseki and the Databricks store, each with a no-loss round trip) with the `rdf-store` skill's. Hop 6, the rebuild, runs with `run_projection.py` (`run-config.md`), which also runs every other hop from one run configuration.

## The flow

| Hop | What happens | The check | Status |
|---|---|---|---|
| 1. Source | The released packages and their data files are the master copy (`inputs.md`, rule 1). | `check_projection_rules.py` and `validate_data.py` pass (SKILL.md steps 2 and 3). | Built |
| 2. Skolemize | Replace every blank node with a Skolem IRI once, before any load, and keep that file beside the release as the derived copy every store reads; the release stays the master copy. | The skolemized file has no blank node, and a second run writes the same bytes; its Skolem IRIs come from RDFC-1.0 labels, so they depend only on the graph. | Built in the `rdf-store` skill (`rdfstore.py skolemize`) |
| 3. Triple stores | Load the skolemized files into each store, one named graph per file. Any SPARQL 1.1 store through add-on J. Databricks through add-on K: a Delta table in Unity Catalog with the columns `subject`, `predicate`, `object`, `object_kind`, `datatype`, `lang`, `graph` (`object_kind` says whether the object is an IRI, a blank node or a literal; `rdf-store`'s `references/stores.md` has the table). | The `rdf-store` round trip: export everything the store holds and compare it with the source by RDFC-1.0 hash; equal hashes mean zero lost and zero added. Counts per graph and per predicate are a quick look (`triplestore.py` adds the three-way counts against the n10s export). | Built in the `rdf-store` skill; on 2026-10-24 a multi-module ontology's 33 graphs (36,575 quads) round-tripped with equal hashes through Jena Fuseki 6.2.0 and a Databricks Delta table |
| 4. Local Neo4j | Project with n10s: SKILL.md steps 4 to 6. | `check-report` passes: what n10s compiled, one fail case per row, the round trip and two equal hashes (`pipeline.md`, rules 13 to 17). | Built |
| 5. Aura or any Neo4j | Copy the verified graph with add-on I. | The target's graph hash equals the local one and the report's. | Built; run against a local second Neo4j and Aura Free |
| 6. Rebuild | Delete the local Neo4j and the Aura data. Rebuild both, taking a store's export (for example the Databricks Delta table) as the source of hops 4 and 5. | The rebuilt graph's hash equals the hash from hop 4, and its round trip against the original source files loses and adds nothing. That proves source → store → Neo4j and Aura loses nothing. | Built: `run_projection.py`, step `rebuild` (`run-config.md`); first run on 2026-10-25 from a Databricks Delta table, with equal hashes locally and on Aura Free |

## What each store holds: the projection policy

A released package has three graphs: `<module>.ttl` (the content), `shapes.ttl` (the rules) and `catalog.ttl` (the DCAT release record). The stores treat them differently, because they do different work.

| Store | Content (`<module>.ttl`) | Rules (`shapes.ttl`) | Release record (`catalog.ttl`) |
|---|---|---|---|
| Triple store (Jena) and Delta table | All, one named graph | All, one named graph | All, one named graph |
| Neo4j, local and Aura | All, with no selection | Not nodes. They validate the release: pySHACL before the load, n10s in the graph at the load | Not in full: one `:ModuleRelease` node per module (add-on M) |

- **All the content, always.** Do not project part of a module. The round trip's proof of 0 lost and 0 added compares the graph with the files, so a selective projection would lose that proof. A consumer that needs less of the graph filters it with labels or module tags (add-on F).
- **The rules run; they are not data.** Shapes loaded as nodes would mix the rules with the things they describe, and the hash and the round trip would have to read around them. n10s keeps its compiled form of them in its own configuration, outside `:Resource`.
- **One record per release, not the catalog.** A reader of the graph needs to know which release it holds and whether it passed. The rest of the catalog stays in the triple stores and the files.
- **One local Neo4j and one standing triple store.** Keep one local graph, in one form, and copy that form to Aura: two local graphs in two forms give two sets of counts, and no reader can tell which is right. Set `keep_neo4j` and `keep_jena` (`run-config.md`), so one run leaves both loaded and proven.

## The data flow, box by box

The data-flow diagram predates the `rdf-store` split of 2026-10-24: its Databricks box still says "(planned)", and its Fuseki arrow says "counts per predicate" where the store is now compared by RDFC-1.0 hash. The validation-path diagram is current. The text below gives the current state.

The diagram is `diagrams/data-flow.png` (source `diagrams/data-flow.eraser`; the editable `diagrams/data-flow.excalidraw` comes from `diagrams/make_data_flow.py`). Its groups, left to right, and every arrow:

**Sources** (grey, three boxes: "Source documents", "Industry and peer sources", "Reference process model"). They stand for the sources the ontology is built from, whatever the domain. Arrows into "W3C stack": the source material crosses into the ontology build; the `ontology` skill cites every fact it takes. Nothing here is checked by this skill.

**Ontology build (ontology skill, Steps 1-11)** (blue). "W3C stack: RDF, OWL, SKOS, SHACL, PROV-O, DCAT" → "check.sh, pySHACL, competency questions (SPARQL)" → "Released packages + DCAT catalog (git tags)". These are the `ontology` skill's steps; its gates prove each release before this skill reads it. The released packages are the master copy (hop 1 above).

**Released packages → "Skolemize blank nodes (stable IRIs)"** (yellow). What crosses: every released data file. What happens: hop 2. The check: no blank node left, and a second run writes the same bytes. Built in the `rdf-store` skill (`rdfstore.py skolemize`).

**Skolemize → Triple stores** (purple), two arrows:
- "load, export back, compare" into "Apache Jena Fuseki, Graph Store Protocol, one named graph per package": the `rdf-store` skill publishes the graphs in one SPARQL Update request (`--update`, advised) or, without it, with one non-atomic `PUT` per graph, exports everything the store holds and compares it with the files by RDFC-1.0 hash. Built; `triplestore.py` (add-on J) adds the counts against the n10s export.
- "triple for triple" into "Databricks: Delta triple table in Unity Catalog (planned)": add-on K, with the two boxes under it, "Free Edition: transfers run from your machine" and "Enterprise: your machine, or a job in the workspace", whose arrows point at the table because both modes write the same table (see "Databricks: two modes" below). Built in the `rdf-store` skill, with the same round trip; the diagram's "(planned)" label predates it.

**Skolemize → ontology-to-lpg skill** (orange): "Check: design rules, data shapes, refusals" → "Reason: ROBOT + ELK, once, upstream" → "Serialise: loadable.nt + inferred.nt (check-serialised)". What crosses: the released data files, or the skolemized copies hop 2 writes with the `rdf-store` skill when a consumer needs stable IRIs for blank nodes; both are built. They are SKILL.md steps 2 to 4, checks V1 to V5 below.

**Serialise → Neo4j, local (Docker + n10s)** (green): "n10s load (SHORTEN, fixed order)" → "Gate: n10s listShapes() readback, one fail case per compiled constraint, round trip, determinism hash". What crosses: `loadable.nt`, `inferred.nt`, `merged.ttl` and the import-safe shapes, copied into the import folder by `load_verify.py`. The checks are V6 to V12 below. Built.

**Jena ⇢ Gate, "three-way counts (--projection-report): files, store, Neo4j"** (dashed): `triplestore.py --projection-report <projection-report.json>` compares the store's per-predicate counts with the files' and with the report's `export_predicate_counts` (check V14). Built.

**Gate → Neo4j Aura, "validated graph"**: "Copy over the driver; hash must match the local graph" → "GRAPH TYPE: schema enforced by the database". `copy_graph.py` (add-on I) copies the graph that passed V12 (check V13); `build.py graph-type --output graph-type.cypher` (add-on H) writes the statement applied after it (G1 to G4). Built; run on Aura Free.

**Databricks ⇢ Rebuild test ⇢ Check** (dashed, red group): "Empty local Neo4j and Aura, rebuild both from the Databricks export, compare with the released files: no loss end to end". What crosses: the store's export, written by `rdf-store`'s `export` as N-Quads and, with `--ttl-dir`, one Turtle file per graph, which re-enters the skill at "Check" and runs the whole path again; the check is hop 6, built as `run_projection.py`'s `rebuild` step.

**Released packages ⇢ Later: Unity Catalog** (dashed): "OntoBricks (Databricks Labs): link Unity Catalog tables and metric views (the KPIs) to the business processes in the ontology". What crosses: the released ontology, as OntoBricks' domain ontology. No no-loss check applies: OntoBricks builds instances from tables, not from the release. Later, not part of this skill.

## The validation path, V1 to V14, and GRAPH TYPE, G1 to G4

The diagram is `diagrams/validation-path.png` (source `diagrams/validation-path.eraser`; `diagrams/validation-path.excalidraw` from `diagrams/make_validation_path.py`). Each check must pass before the next runs, in the order of the tables (the order SKILL.md steps 2 to 6 run them). The rules named here hold the detail; this section is the map. "Stops" means the command exits 1 (2 on bad input) and you go no further; from V6 to V12 it also means no report: `load_verify.py` writes `projection-report.json` only when every check passed (V12).

**Before the load (on the files)**

| # | Checks | Without it | Command, record | Rule |
|---|---|---|---|---|
| V1 | Design rules: one kind and one range per predicate (Rule 1), a cardinality shape (Rule 2), one fixed prefix per namespace, pins, rule-gap exceptions | an unmappable predicate loads as a guess, an unknown namespace gets an invented `ns0` prefix | `check_projection_rules.py`; stops | `design-rules.md`, rules 1 to 3; `inputs.md`, rules 1 to 6; `pipeline.md`, rule 1 |
| V2 | Full SHACL with pySHACL and SHACL-AF over the released (asserted) data, before reasoning: 0 violations; values that cannot round-trip are refused | the graph would hold data the shapes reject, and the in-graph check (V8) runs only part of the shapes | `validate_data.py <data>...`; stops | `pipeline.md`, rules 1 and 3 |
| V3 | Reason once with ROBOT and ELK; keep only real inferences (IRI-to-IRI `rdf:type` and `rdfs:subClassOf`, no OWL API declarations) | Neo4j does no reasoning, so inferences would be missing, or declarations would load as facts | `robot reason`, `build.py inferred` | `pipeline.md`, rules 4 and 6 |
| V4 | After serialising: `check-serialised` (one triple per line and nothing else, byte order, no repeats, nothing in `inferred.nt` already asserted), then full SHACL again over `loadable.nt` and `inferred.nt` together, 0 violations | an unsorted or commented file breaks the fingerprint and the diffs; an inference can break a shape | `build.py check-serialised`, then `validate_data.py loadable.nt inferred.nt`; stops | `pipeline.md`, rules 2 and 5 |
| V5 | Manifest, written after V4 passed (SKILL.md step 4): SHA-256 of every input and shape file, the input and shapes fingerprints | a report could outlive the inputs it checked | `build.py manifest [--verify]`; `projection-manifest.json` | `running.md`, rule 3 |

**In the local Neo4j (Docker + n10s)**, all in one `load_verify.py` run:

| # | Checks | Without it | Report field | Rule |
|---|---|---|---|---|
| V6 | Load in a fixed order; `onto.import` and both `rdf.import` calls return `OK`; the shapes import returns as many rows as `listShapes()` | a partial import would pass | `shapes_import_rows`, `in_graph_shape_constraints` | `pipeline.md`, rules 8 to 11 |
| V7 | Engine readback: `listShapes()` against the shapes file; every constraint n10s did not compile is listed. It does not stop the run: V2 already checked every constraint | silence from a constraint n10s never compiled would look like a pass | `compiled`, `not_compiled`, `prediction_differences`, `left_out_before_import` | `pipeline.md`, rule 13 |
| V8 | n10s `validate()`: 0 violations | the graph could differ from what V2 passed | `shacl_violations_in_graph` | `pipeline.md`, rule 15 |
| V9 | One fail case per compiled constraint, passing only on the right node, path and component; a committed mutant is caught, then restored to 0 violations | a check that cannot fire looks the same as a pass | `fail_cases`, `mutant`, `in_graph_mutant_violations` | `pipeline.md`, rules 14 and 15 |
| V10 | Round trip: export back to RDF, schema rows left out, 0 triples lost, 0 added | a value changed or dropped by the load would go unseen | `roundtrip_lost`, `roundtrip_added`, `export_predicate_counts` | `pipeline.md`, rule 16 |
| V11 | Determinism: a sorted and a shuffled load give one graph hash | the result could depend on load order | `determinism_hash_sorted`, `determinism_hash_shuffled` | `pipeline.md`, rule 17 |
| V12 | The report is written only when V6 to V11 all passed; `check-report` then requires fingerprints that match the manifest (V5) and rechecks the report itself: `passed: true`, the numbers, equal hashes, a non-empty `compiled` list (missing or empty fails) with a passing or no-op case for every row, and the mutant | a failed or stale run could be committed as a pass | `passed`; `build.py check-report` | `running.md`, rules 3 and 5 |

**Delivery**

| # | Checks | Without it | Command, record | Rule |
|---|---|---|---|---|
| V13 | Aura copy: the Aura hash equals the local hash and the report's `determinism_hash_sorted` | a copy that dropped or changed anything would go unseen | `copy_graph.py --report <projection-report.json>`; stops before touching the target unless the report earns its pass and the target is not the source database (same `db.info()` id) (it rechecks every field `check-report` checks except the fingerprints) and its hash matches the source; prints both hashes | `add-ons.md`, I |
| V14 | Triple store: counts per graph and per predicate (files against store); the three-way check (files, store, the report's export) runs only with `--projection-report <projection-report.json>` | a store that lost triples would go unseen | `triplestore.py --projection-report <projection-report.json>`; its report, written only when every count matched (else `<report>.failed`, exit 1) | `add-ons.md`, J |

**GRAPH TYPE on Aura** (Enterprise or Aura; Community refuses it)

| # | What | Rule |
|---|---|---|
| G1 | `build.py graph-type --output graph-type.cypher` writes one `CYPHER 25 ALTER CURRENT GRAPH TYPE SET` statement from the `sh:targetClass` shapes and the data (list types follow the load's multivalued list; no empty node type), with what it leaves out as quoted `// left out:` comments | `add-ons.md`, H |
| G2 | Apply it after V13, on the copied graph, and confirm with `SHOW CURRENT GRAPH TYPE`. The data passed V6 to V13, so a refusal means the statement is wrong, not the data (two such defects were found this way) | `add-ons.md`, H, "Applying it" |
| G3 | Probe: a write that breaks the type must fail with `Neo.ClientError.Schema.ConstraintValidationFailed`; run it in a transaction you roll back | `add-ons.md`, H, "Applying it" |
| G4 | From then on the database rejects bad writes from applications, where n10s cannot run | `add-ons.md`, H |

It covers labels, property types, `NOT NULL` (when `sh:minCount` is at least 1, list or scalar), lists (exactly the load's multivalued properties) and relationship endpoints. It leaves out relationship counts, `sh:in`, `sh:pattern`, ranges and lengths, which have no `GRAPH TYPE` form. Coverage depends on `sh:targetClass` shapes: a shape that targets by node or by SHACL-SPARQL gives no element type (on one multi-module test ontology, 35 node and 46 relationship element types). It guards later writes; the n10s gate (V6 to V12) stays the proof that the projection is right.

## Why each step is there

- **Skolemize first.** Blank nodes have no identity outside one file: "Blank nodes do not have identifiers in the RDF abstract syntax" (RDF 1.1 Concepts, §3.5, https://www.w3.org/TR/rdf11-concepts/#section-skolemization). Each store would relabel them, so no consumer could point at one. (The `rdf-store` round trip still compares stores that hold blank nodes, through RDFC-1.0 canonicalization.) §3.5 allows systems to "replace some or all of the blank nodes in an RDF graph with IRIs" (quoted), and says Skolem IRIs meant to be recognised outside the system "SHOULD use a well-known IRI ... with the registered name genid", a path starting `/.well-known/genid/` (quoted). Mint them under a base you document, such as `https://id.example.org/.well-known/genid/`, from a hash of the graph IRI and the blank node's RDFC-1.0 label, as `rdf-store`'s `skolemize` does, so a rerun mints the same IRIs. Design rule 3 (`design-rules.md`) already keeps blank nodes out of the data; the files still hold them in OWL axioms and RDF lists, and those are what skolemizing fixes for the stores. A Skolem IRI minted from the node's RDFC-1.0 label is not an IRI "generated per run", which rule 3 forbids: the same input always gives the same IRI.
- **Export back, not only count.** Matching counts can hide a changed value; the RDFC-1.0 hash of the export against the source's cannot (`rdf-store`).
- **Neo4j stays the projection.** The triple stores hold the same triples as the source; Neo4j holds the projection that n10s, the shapes and the round trip verified. The rebuild of hop 6 tests that a store's copy is a valid source for the projection.

## Databricks: two modes for add-on K

The `rdf-store` skill builds add-on K (its `references/stores.md`); this section keeps the reasoning behind its two modes.

Add-on K must run on both editions. The no-loss checks are the same in both; only where the transfer runs differs.

- **Free Edition.** It is serverless only, with "One SQL warehouse, limited to a 2X-Small cluster size", and "outbound internet access is restricted to a limited set of trusted domains" (quoted from Databricks Free Edition limitations, https://docs.databricks.com/aws/en/getting-started/free-edition-limitations, read 2026-10-23). So every transfer runs from your machine: write and read the Delta table over the Databricks SQL connector (`rdf-store`), export it locally as N-Quads and Turtle, and load Neo4j or Aura from there. Never push from a notebook to Aura. *2026-10-29:* outbound access to Aura is not always blocked. In a real project a one-time Free Edition serverless job, with the `neo4j` 5.28.1 driver and the Aura login in a Databricks secret scope written from the local credentials file without printing it, resolved Aura's host, opened port 7687 and ran a Bolt query that counted the ontology's nodes. Treat that as a connection test, not a load path: a graph written from the workspace skips the local n10s gate, so the rule above stands for loads.
- **Enterprise (paid) workspaces.** The same machine-driven path works. The load, or the rebuild of hop 6, may also run inside the workspace, as a job or a notebook, when the workspace's network rules allow the destination: a serverless network policy is either full access or restricted to listed destinations (Databricks, "What is serverless egress control?", https://docs.databricks.com/aws/en/security/network/serverless-network-security/network-policies, read 2026-10-23). Check that Aura's host is allowed before you plan an in-workspace copy. A graph written to Aura from the workspace skips the local n10s gate, so it counts only when its hash equals the hash of hop 4. Classic compute's egress depends on the workspace's own network setup; this is not verified here.

- **No built-in triple store.** Add-on K is a plain Delta table, written and read with SQL, and checked like any store in hop 3.
- **OntoBricks is a later tool, not the store.** OntoBricks (Databricks Labs, https://github.com/databrickslabs/ontobricks, read at commit `97b27c7`) works per domain: an ontology, R2RML mappings from Unity Catalog tables, and a graph it materialises from those tables. It builds instances only from the tables through the mappings, so it cannot hold the released files triple for triple. Use it later to link Unity Catalog data and metric views to the ontology.

## Sharing a store with data that is not the ontology

A project may want other graphs beside the projection in the same Neo4j or Aura database, such as a technical graph of its own pipeline (tables, steps, checks) that links to the ontology's measures and systems by IRI. Keep the projection's numbers untouched:

- **Its own label, never `:Resource`.** The graph hash reads `:Resource` nodes and the edges between them (`pipeline.md`, rule 17), and the round trip exports `:Resource` nodes and the edges out of them (`load_verify.py`). Give every other node a label of its own and no `:Resource` label, and start every edge at one of its nodes, so no edge leaves an ontology node for it and neither number can see it. Then loading it moves none of those numbers: in a real project (2026-10-29) the graph hash, 4,193 nodes and the relationship counts were the same before and after a 134-node technical graph was loaded beside the ontology.
- **Pin the exact queries, not a pattern.** Test that the functions computing the counts, the hash and the round trip send exactly the `:Resource`-only Cypher you expect: run them against a fake session that records each query and compare the strings. A regex scan of every query in the projection code looked like a stronger check but kept missing reads (a path variable, a label disjunction, parentheses inside a string literal); the project replaced it with the exact pin and claimed only what the pin covers.
- **A reload wipes it.** `load_verify.py` starts each load with `MATCH (n) DETACH DELETE n`, and `copy_graph.py --replace` empties the target first, so reload the other graph after every projection reload or copy.
- **Build it from the project's files.** SPARQL Anything (https://sparql-anything.cc/, v1.3.0) turns SQL files, run commands, JSON and CSV into RDF with SPARQL queries kept beside the code, so the technical graph, or a decision trail written as PROV-O, comes from what the project already holds. If you type its records as `prov:Activity`, see the ontology playbook's PROV-O note on run shapes.

## Keeping the stores in step

The released Turtle is the master copy, held in Git where there is Git; every store is a copy that can fall behind it. Three kinds of copy need keeping in step, each by its own check: the ontology's triples in each store, a graph kept beside them, and files a release reads from outside Git.

### The ontology's triples in each store

Once several stores hold the projection, each can fall behind the newest release. In a real project (2026-10-29) this took these parts:

- **A marker per store.** Each store records the release set it was loaded from (the catalog's datasets and the projection's input fingerprint): a node with its own label in Neo4j and Aura, never `:Resource`, and a row in a table beside the triple table. The marker is written only after the store is checked against the repository: the pipeline's graph must give the committed report's hash and counts, the other Neo4j stores must hold the projection's nodes and relationships, the triple table must hold every module's newest release.
- **A standing triple store needs no marker.** Its named graphs are version IRIs, so the store itself says which releases it holds: compare its graph names and each graph's triple count with the release files. That puts nothing extra in the store, so a later export compares equal to the files without an exclusion. A Fuseki with an in-memory dataset (the default here) empties on restart, and the check then reads empty; reload it with `run_projection.py --only jena`.
- **A drift check** compares each marker with the main branch's newest catalog and each store's live count with its marker, and reports each store as current, behind, changed, unmarked or unreachable (with the error's name). It exits non-zero unless every store is current.
- **A sync** reloads only what is not current, with the existing pipeline and driver rather than new loaders: local stores by default, cloud stores on request. It then reloads anything else the store held (see the section above) and marks what it reloaded.
- **A workflow on release tags** reloads the cloud stores, and stays inactive until its logins exist as repository secrets: its first step checks them and every later step runs only if that check found them all. GitHub says "Secrets cannot be directly referenced in if: conditionals" and gives a job-level environment variable, tested in `if`, as its way round that (GitHub, "Using secrets in GitHub Actions", https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets, read 2026-10-29); a first step whose output later steps test is another way, and the one the real project used. Pin the checkout of any repository it runs code from.
- **A release step when nothing schedules it.** Where no workflow runs the drift check, it is a written step of every release, and the `ontology` skill's `references/release.md`, "Keeping copies in step", says when it runs and which release the sync loads.

### A graph kept beside the triples

A graph that is not the ontology's triples, such as a technical or lineage graph (the section above) or a logical data model loaded as its own subgraph apart from the `:Resource` nodes, is loaded from its own files, so the release set cannot say whether it is current. Check it against those files:

- **Its own marker, written with the load.** A node with its own label records a SHA-256 digest of the files the graph was loaded from (each file's name and hash, sorted). Write it in the same transaction as the load, so a marker never describes a load that failed.
- **A content fingerprint, not only counts.** The check computes a fingerprint of what the store holds (each node's labels and key properties, each edge's type and the keys at its two ends, sorted, then hashed) and the same fingerprint from the files. A hand edit that leaves the counts unchanged then reads as changed.
- **A copy refreshed only from a matching source.** A copy of the graph in another store, such as a lakehouse table read from Neo4j, is refreshed from its source store only when that source's fingerprint matches the files; otherwise reload the source first. A copy taken from a drifted source would carry the drift with a fresh date.
- **The previous graph or none, never part of one.** Each load deletes the old graph and writes the new one, marker included, in one transaction, or loads beside it under a staging label and swaps once the load is complete. A failed load then leaves the graph that was there before.

### Files a release reads from outside Git

A file kept outside Git, such as an export a client keeps private, has no store marker: its path relative to its folder and its SHA-256, in the release's input record (`release-inputs.json`), are the record. The rules are the `ontology` skill's (`references/release.md`, "Inputs kept outside Git").
