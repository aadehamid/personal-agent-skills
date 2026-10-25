# Add-ons and anti-patterns

Read it when a consumer asks for something the core pipeline does not give (superclass labels, split language keys, exact decimals, units, provenance, business keys, a `GRAPH TYPE`, the graph in Aura, the same data in a triple store or in Databricks), or when reviewing a projection.

## Add-ons (adopt only when needed, and record each)

| Add-on | Use when | What to add |
|---|---|---|
| A. Superclass labels | `MATCH (:lib__Item)` should find copies without walking the hierarchy | The reason step with `--include-indirect true` already loads every inferred superclass as a label (`pipeline.md`, rule 4); adopt this add-on only to leave out upper-ontology roots |
| B. Language policy | Labels in several languages | `lpg:langPolicy "splitKeys"`, giving `label_en`, `label_fr` |
| C. Exact decimals | Fines, fees, anything computed with exact arithmetic | `lpg:cypherType "STRING"` on `xsd:decimal` properties |
| D. Known exclusions | OWL axioms you will not project | List them in `exclusions.nt`; the round-trip diff ignores them |
| E. Units | Quantities with units | QUDT value and unit pattern, not custom datatypes |
| F. Named graphs and provenance | Several sources or versions | Load each graph separately; tag nodes and relationships with `graph` |
| G. Business keys | Consumers MERGE on a key such as a barcode | `lpg:keyProperty true`, giving an extra uniqueness constraint |
| H. A `GRAPH TYPE` | The target runs Neo4j Enterprise 2026.02 or later and should reject data outside the model | `build.py graph-type --output graph-type.cypher` (see below) |
| I. Copy to Aura or another Neo4j | The graph must live where n10s cannot run | `copy_graph.py` (see below) |
| J. A triple store | SPARQL consumers need the same data | The `rdf-store` skill loads the files and proves the round trip; `triplestore.py` (see below) adds the counts against the n10s export |
| K. Databricks | The data must also live in Unity Catalog | The `rdf-store` skill: a Delta table of quads, loaded and read from your machine over the Databricks SQL connector on Free Edition or Enterprise, with the same round trip. See `multi-store.md` |
| L. A Data Modeling MCP model | Reviewers want an Arrows drawing or a Mermaid diagram of the graph | `build.py data-model` (see below) |

## H. A `GRAPH TYPE` from the shapes

In the validation map (`multi-store.md`) this is G1 to G4.

`build.py graph-type --config <config> --shapes <shapes>... --output graph-type.cypher <data>...` writes one `CYPHER 25 ALTER CURRENT GRAPH TYPE SET { ... }` statement to the file, each left-out item as a quoted `// left out:` comment, and prints only the quoted file name and counts. It stops (exit 2) when the shapes give no element type at all. The Cypher manual marks the statement "Cypher 25 only", Enterprise Edition, introduced in Neo4j 2026.02 (https://neo4j.com/docs/cypher-manual/current/schema/graph-types/set-graph-types/; the element syntax is at https://neo4j.com/docs/cypher-manual/current/schema/syntax/). It emits:

- one node element type per `sh:targetClass` that has at least one typed property, `(:Label => {prop :: TYPE ...})`, with a typed property for each property shape on a value whose `sh:datatype` maps to a Cypher type (`design-rules.md`, the XSD table). The property is `LIST<TYPE NOT NULL>` exactly when the load stores it as an array, which is the load script's own multivalued list (`pipeline.md`, rule 10: global per predicate, so `sh:maxCount 1` on one class does not make it a scalar where another class or the data makes it a list), and a scalar otherwise; that is why the command reads the data files. It is `NOT NULL` when `sh:minCount` is at least 1, list or scalar (Aura Free accepted `LIST<STRING NOT NULL> NOT NULL`). A target with no typed property gets no node element type: Aura rejects an empty one (`(:Label =>)` and `=> {}` were both syntax errors on 2026-10-23), while a relationship endpoint may name a label that has no element type of its own;
- one relationship element type per predicate whose property shapes name one `sh:class`, `(:Source)-[:TYPE =>]->(:Target)`.

When two property shapes on one target map the same key differently, the first (by shape IRI) is kept and the other listed; a property shape with both `sh:datatype` and `sh:class` is typed as a property and its relationship listed.

It leaves out, and lists as `// left out:` comments: relationship counts, `sh:in`, `sh:pattern`, `sh:nodeKind`, ranges and lengths (no `GRAPH TYPE` form), property shapes with no mappable datatype or class, and paths that are not a predicate. Labels and types are the SHORTEN names, backtick-quoted. On `neo4j:2026.06` Community (2026.06.0, 2026-10-23), the library statement passed the parser and was refused with `51N27 'ALTER CURRENT GRAPH TYPE SET' is not supported in community edition`, while a misspelt type (`STRNG`) was refused as a syntax error; On Aura Free on 2026-10-23, on one multi-module test ontology, the statement held 35 node and 46 relationship element types after the two fixes above (no empty node types; list types from the load's multivalued list). It was accepted (`SHOW CURRENT GRAPH TYPE` returned it), a write with an integer where the type declared a string was rejected with `Neo.ClientError.Schema.ConstraintValidationFailed`, and `ALTER CURRENT GRAPH TYPE SET {}` cleared it. Coverage depends on `sh:targetClass` shapes: a shape that targets with `sh:targetNode` or SHACL-SPARQL gives no element type. Apply it after the load and the verify step, never instead of them: the n10s shapes and the round trip stay the gate.

**Applying it** (G2 to G4 in `multi-store.md`): after the copy of add-on I (V13), run the file's statement on the target as one statement (with `cypher-shell -f graph-type.cypher`, or a driver), then `CYPHER 25 SHOW CURRENT GRAPH TYPE` must return it. Then probe: in a transaction, write a value that breaks one declared property type (for example an integer where the type says `STRING`); the write must fail with `Neo.ClientError.Schema.ConstraintValidationFailed`; roll the transaction back. A refused statement means the statement is wrong, not the data, which passed V6 to V13. From then on the database refuses such writes from any application, where n10s cannot run. `CYPHER 25 ALTER CURRENT GRAPH TYPE SET {}` clears it. The Neo4j skill `neo4j-cypher-skill`, `references/graph-type.md`, has the full syntax.

## I. Copy to Aura or another Neo4j

n10s does not run on Aura: "neosemantics is only available for Neo4j self-hosted (CE and EE) and is not available in Aura" (https://neo4j.com/labs/neosemantics/, "Availability & Installation"). So build and verify locally (steps 5 and 6), then copy the verified graph with plain Cypher:

```bash
NEO4J_PASSWORD="$PASSWORD" uv run --no-project --with rdflib --with neo4j python3 copy_graph.py \
  --source "bolt://127.0.0.1:$PORT" --target-env <target.env> \
  --report projection-report.json [--replace] [--batch 1000] [--query-timeout 120]
```

Run it after `check-report` passed and before the local container is removed (`running.md`, rule 5, step 3). `<target.env>` holds `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` and optionally `NEO4J_DATABASE`, the format of an Aura credentials file; the script never prints the password. It refuses a target that holds any node unless `--replace` is given, which deletes everything there first, in batches. It copies every `:Resource` node with its labels and properties (the `n4sch__` schema nodes included) and every relationship between two `:Resource` nodes, in `UNWIND` batches with dynamic labels and types, after creating the uniqueness constraint on `:Resource(uri)`; it leaves out n10s's configuration nodes (`_GraphConfig`, `_NsPrefDef`, `_n10sValidatorConfig`). `--report` is required: the script reads it before touching either database and stops (exit 2) unless the report earns its pass, which it rechecks rather than trusting `passed` (every field `check-report` checks except the fingerprints: the numbers, equal hashes, compiled rows each with a passing case, the mutant); it also stops on an unknown flag (such as the old `--expect-hash`); and before it writes or deletes anything it asks both servers for their database id (`CALL db.info()`) and stops (exit 1) when they are the same database, whatever URI, host alias or scheme reached it; it then stops (exit 1), before it writes or deletes anything on the target, unless the source's graph hash equals the report's `determinism_hash_sorted`. So `--replace` can only ever install the verified graph. After the copy it hashes the target as `load_verify.py` does (`pipeline.md`, rule 17) and fails unless it equals the source's. A failure during the copy can leave a partial graph on the target; the script says so, and a rerun with `--replace` replaces it. Since the graph hash writes a date (or any non-JSON value) with its type, a report written before that change for a graph holding such values no longer matches: rerun `load_verify.py` to write a current report before copying. On 2026-10-23 it copied the library graph (38 nodes, 87 relationships) and a real multi-module ontology (3,925 nodes, 20,015 relationships) to a second local `neo4j:2025.06.2` with equal hashes. On Aura Free (server version `5.27-aura`, Enterprise, Cypher 5 and 25), the same run on the multi-module ontology rebuilt and verified the graph locally, copied 3,925 nodes and 20,015 relationships, and the Aura hash equalled the local and report hash.

rdflib-neo4j (https://neo4j.com/labs/rdflib-neo4j/) is the Neo4j Labs alternative: an RDFLib store backed by Neo4j, "a client-side alternative to Neosemantics for cloud-native Neo4j deployments". It loads RDF from the client but does not run the in-graph SHACL, the round trip or the hash of steps 5 and 6, so this skill copies a graph those steps verified instead.

## J. The same files in a triple store

Loading a store and proving that nothing was lost (an export of everything the store holds, compared with the source by its RDFC-1.0 hash) is the `rdf-store` skill, split out of this one on 2026-10-24; use it for every triple store and for Databricks. What stays here is `triplestore.py`, the count check that ties a store to the projection: its three-way counts compare the files, the store and the n10s export.

`triplestore.py` loads the validated inputs into any SPARQL 1.1 store and checks per-graph and per-predicate counts, and with a projection report the three-way counts. It speaks only W3C protocols: the SPARQL 1.1 Graph Store HTTP Protocol (https://www.w3.org/TR/sparql11-http-rdf-update/) to replace each named graph with `PUT` (`?graph=<IRI>`), and the SPARQL 1.1 Protocol to count. There is no store-specific code.

```bash
uv run --no-project --with rdflib python3 triplestore.py --gsp <graph store URL> --query <SPARQL URL> \
  [--env <store.env>] [--graph-base <IRI>] --inferred inferred.nt \
  [--projection-report projection-report.json] [--cq <question.rq>]... --report triplestore-report.json <data.ttl>...
```

- **Graphs:** one named graph per input file: the `owl:versionIRI` of its one `owl:Ontology`, else that ontology's IRI, else `<graph-base><file name>`; `inferred.nt` goes to `<graph-base>inferred`. The default base is `urn:lpg-projection:graph:`; pick one under your own domain for anything shared.
- **Credentials:** `--env` names a file that may set `SPARQL_GSP`, `SPARQL_QUERY`, `SPARQL_USER` and `SPARQL_PASSWORD` (HTTP Basic); flags win. The password is never printed. The report stores the endpoints redacted (`shell.redact`: all userinfo before `@` and the value of a credential-like query key such as `token` or `sig` become `***`). Every error, in setup or in a request, prints a fixed context and the exception's type (and an HTTP status), never its text, and a refusal holds no text the user supplied (no path, value or unknown option; an unverified projection report gets a count of failed checks, which `build.py check-report` lists), because any of them can carry a URL or a credential (`shell.error_line`, `shell.Refusal`).
- **Counts:** a count is the number of distinct triples; blank nodes count as triples, without matching labels. Per graph, `COUNT(*)` must equal the file's triples; per predicate, the distinct triples over all the loaded graphs must equal the files' together; with `--projection-report`, they must also equal the report's `export_predicate_counts`, the n10s export with the schema rows left out (n10s's configuration nodes are never exported). That is the three-way check: files, store and graph.
- **The projection report is rechecked:** `--projection-report` must earn its pass (the same recheck as add-on I), not only say `passed: true`.
- **The report is fail-closed:** the report named by `--report`, and its `.failed` file, are deleted before anything else; the report is written, by a rename, only when every count matched. A mismatch writes the details to `<report>.failed`; a failed request writes nothing. 
- **Competency questions:** each `--cq` SPARQL `SELECT` runs over the loaded graphs (as `default-graph-uri` parameters) and its row count goes into the report.

Start the store with the skill's compose file: from `docker/`, `docker compose -p <project> --profile fuseki up -d --build` builds Fuseki 6.2.0 from `docker/fuseki/Dockerfile` (which fetches `jena-fuseki-docker-6.2.0.zip` and the server jar, checks each against a pinned SHA-256, and builds as Jena's own Dockerfile does on base images pinned by digest; `--build` keeps a stale local `lpg-fuseki:6.2.0` from being used) and serves an in-memory `/ds` on `127.0.0.1:13030` (`LPG_FUSEKI_PORT` changes it): `--gsp http://127.0.0.1:13030/ds --query http://127.0.0.1:13030/ds/query`. Remove it with `docker compose -p <project> --profile fuseki down -v`, with the same `-p` (running.md uses `-p "$CONTAINER"` for the projection stack; use it here too when Fuseki runs beside Neo4j).

It exits 0 when every count matches, 1 on a mismatch or a failed request, 2 on bad input. Tested on 2026-10-23 against Apache Jena Fuseki 6.2.0 in Docker, bound to `127.0.0.1`: Jena publishes no prebuilt image, and its Fuseki Docker page (https://jena.apache.org/documentation/fuseki2/fuseki-docker.html) builds one from the `jena-fuseki-docker` package. The test built it from `jena-fuseki-docker-6.2.0.zip` (SHA-256 `7a2dbc918a02adaba2a398c7cebf64c85a42d9a6717ade814acc14ca27d71c66`, checked against Maven Central's SHA-1) with `docker build --build-arg JENA_VERSION=6.2.0` and ran it with `--mem /ds`; `docker/fuseki/Dockerfile` now does the same in one build. The library files loaded as two graphs (100 and 1 triples), all three counts matched, a competency question returned 3 rows, and a changed export count failed the run. On a multi-module ontology, Fuseki loaded 12 named graphs and the per-graph, per-predicate and three-way counts matched for all 176 predicates. Fuseki 6.2.0 refused a `urn:x-` graph name as a relative IRI, which is why the default base has no `x-` namespace. Remove it afterwards with `docker compose -p <project> --profile fuseki down -v` (or `docker rm -f -v` for a container started by hand). The export and the comparison with the source (`multi-store.md`, hop 3) are the `rdf-store` skill's round trip.

## L. The graph as a Data Modeling MCP model

`build.py data-model --config <config> --shapes <shapes>... --output data-model.json <data>...` writes the shapes' element types (`build.element_types`, the mapping add-on H also reads) as a `DataModel` of the Neo4j Data Modeling MCP server, `mcp-neo4j-data-modeling` 0.8.2 (https://github.com/neo4j-contrib/mcp-neo4j, `servers/mcp-neo4j-data-modeling`, `data_model.py` at commit `0eaf613e0f`). One node per label a shape targets or a relationship reaches, keyed on `uri`; one property per typed key, with a list typed `LIST` and its element type in the description; one relationship per source, key and target, every label pair kept. Labels and types are the SHORTEN names. It holds more than the `GRAPH TYPE`: a label with no typed property and a relationship type used between several label pairs stay in the model, and add-on H drops both. `metadata.left_out` lists what the shapes give no typed form; `metadata.not_in_graph_type` lists what the model holds and a `GRAPH TYPE` cannot; add-on H's comments are exactly the two lists together. Before it writes, the command checks the model against that server's `DataModel` under strict validation (`build.data_model_problems`; `test_modeling.py` checks it against the pinned package on every case) and exits 1 on a problem.

Give the file's JSON to the server's tools: `validate_data_model` (it accepted the library model on 2026-10-24), then `get_mermaid_config_str` or `export_to_arrows_json` for Arrows.app. Leave out its `export_to_pydantic_models`: in 0.8.2 it writes each SHORTEN name into a Python declaration as it is, so a name with a hyphen (legal in an IRI) gives code that does not parse, and it makes every property a required field, so an instance without an optional property (`sh:minCount 0`) is refused (both found on the library model in the review of 2026-10-25). The ontology stays the source: regenerate the file after each release, and never edit the model to change the graph. Two of the server's tools stay unused. Its OWL import and export are lossy by its own README ("OWL Classes become Nodes, ObjectProperties become Relationships, and DatatypeProperties become Node properties"), and on 2026-10-24 `load_from_owl_turtle` rejected a released SKOS module whose object property has `rdfs:domain skos:Concept`, because that file does not declare `skos:Concept` an `owl:Class`. Its GraphRAG schema export is skipped, because this skill builds no extraction pipeline.

## Reviewing the loaded graph

`model_review.py` checks a loaded graph (after step 6, or on the copy of add-on I) against the anti-patterns of Neo4j's `neo4j-modeling-skill` 1.0.7 that a projection keeps, with that skill's severities (ERROR a correctness failure, WARNING a performance or extensibility risk, INFO a style point):

```bash
NEO4J_PASSWORD="$PASSWORD" uv run --no-project --with rdflib --with neo4j python3 model_review.py \
  --uri "bolt://127.0.0.1:$PORT" [--report model-review.json]
uv run --no-project --with rdflib --with neo4j python3 model_review.py --env <target.env> [--report ...]
```

- **ERROR** `missing-key-constraint`: no uniqueness or node-key constraint on `:Resource(uri)` (`--key-label`, `--key-property` for another key). n10s MERGEs on `uri`, and without the constraint it creates duplicates without a word.
- **WARNING** `generic-label` and `generic-type`: a label whose local name is Entity, Node or Thing, or a relationship type whose local name is RELATED_TO, HAS or CONNECTED_TO, in any case and with or without `_` or `-`. The fix belongs in the ontology: a more specific class or property.
- **WARNING** `supernode`: a node with more than `--max-degree` relationships (default 100,000, the skill's limit). **WARNING** `supernode-candidate`: a node at `--factor` (10) times the median degree of one of its labels and at least `--min-degree` (50). Degree counts both directions. Concept schemes and widely used code-list values land here by design: read them against the ontology, and keep them as nodes (`design-rules.md`, "Where this skill departs from neo4j-modeling-skill").
- **INFO** `reciprocal-type`, a local heuristic and not one of the skill's rules: one relationship type used from label A to B and from B to A. In a projection it usually means the ontology states one property in both directions where it meant a property and its inverse; the skill asks only that direction carry meaning.

Only domain labels count: n10s's own (Resource, the configuration labels, `n4sch__*`) are left out before every degree rule, and a node with none is not reviewed. The medians, offenders and reciprocal pairs are computed in Cypher, so only label statistics and at most `--limit` offenders (default 100) come back; the output says when the limit was reached. Every statement carries a server-side timeout, `--query-timeout` seconds (default 120). It exits 1 when it finds an ERROR, 0 otherwise, and 2 on bad input, a failed or timed-out query, or a report it could not write (the report is written by a rename, so an earlier one survives a failed write). No password or credential-bearing URI is printed: every error prints a fixed context and the exception's type, never its text (`shell.error_line`); the same holds for `copy_graph.py`, `load_verify.py` and `triplestore.py`. Fix an ERROR before the graph is used; read every WARNING against the ontology, which stays the master copy.

## Anti-patterns

Each is a way the projection passes while being wrong.

- Relying on n10s defaults: overwrite for multivalued properties, invented `ns0` prefixes.
- Loading shapes the engine cannot run, and reading its silence as a pass.
- Loading the reasoner's OWL API declarations as inferences.
- Blank-node qualified-relation nodes or reifiers: the node or relationship then has no stable identity.
- Merging two reifiers of one triple into one relationship.
- Cypher written by hand rather than generated from the ontology.
- Projecting working source files instead of released packages.
- An exception list that is never checked for stale entries.
- Expecting Neo4j to do OWL reasoning.
- Treating Neo4j as the master copy instead of the Turtle files.
- Trusting a shapes file to say what the engine checks: read back `listShapes()` and test every row (`pipeline.md`, rules 13 and 14).
