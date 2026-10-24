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
| H. A `GRAPH TYPE` | The target runs Neo4j Enterprise 2026.02 or later and should reject data outside the model | `build.py graph-type` (see below) |
| I. Copy to Aura or another Neo4j | The graph must live where n10s cannot run | `copy_graph.py` (see below) |
| J. A triple store | SPARQL consumers need the same data | `triplestore.py` (see below) |
| K. Databricks (planned, not built) | The data must also live in Unity Catalog | A Delta table `(subject, predicate, object, datatype, lang, graph)` checked like J. Free Edition: loaded and read from your machine over the Databricks SQL connector. Enterprise: the same, or inside the workspace when its network rules allow the destination. See `multi-store.md` |

## H. A `GRAPH TYPE` from the shapes

In the validation map (`multi-store.md`) this is G1 to G4.

`build.py graph-type --config <config> --shapes <shapes>... <data>...` prints one `CYPHER 25 ALTER CURRENT GRAPH TYPE SET { ... }` statement. The Cypher manual marks the statement "Cypher 25 only", Enterprise Edition, introduced in Neo4j 2026.02 (https://neo4j.com/docs/cypher-manual/current/schema/graph-types/set-graph-types/; the element syntax is at https://neo4j.com/docs/cypher-manual/current/schema/syntax/). It emits:

- one node element type per `sh:targetClass` that has at least one typed property, `(:Label => {prop :: TYPE ...})`, with a typed property for each property shape on a value whose `sh:datatype` maps to a Cypher type (`design-rules.md`, the XSD table). The property is `LIST<TYPE NOT NULL>` exactly when the load stores it as an array, which is the load script's own multivalued list (`pipeline.md`, rule 10: global per predicate, so `sh:maxCount 1` on one class does not make it a scalar where another class or the data makes it a list), and a scalar otherwise; that is why the command reads the data files. It is `NOT NULL` when `sh:minCount` is at least 1, list or scalar (Aura Free accepted `LIST<STRING NOT NULL> NOT NULL`). A target with no typed property gets no node element type: Aura rejects an empty one (`(:Label =>)` and `=> {}` were both syntax errors on 2026-10-23), while a relationship endpoint may name a label that has no element type of its own;
- one relationship element type per predicate whose property shapes name one `sh:class`, `(:Source)-[:TYPE =>]->(:Target)`.

When two property shapes on one target map the same key differently, the first (by shape IRI) is kept and the other listed; a property shape with both `sh:datatype` and `sh:class` is typed as a property and its relationship listed.

It leaves out, and lists as `// left out:` comments: relationship counts, `sh:in`, `sh:pattern`, `sh:nodeKind`, ranges and lengths (no `GRAPH TYPE` form), property shapes with no mappable datatype or class, and paths that are not a predicate. Labels and types are the SHORTEN names, backtick-quoted. On `neo4j:2026.06` Community (2026.06.0, 2026-10-23), the library statement passed the parser and was refused with `51N27 'ALTER CURRENT GRAPH TYPE SET' is not supported in community edition`, while a misspelt type (`STRNG`) was refused as a syntax error; On Aura Free on 2026-10-23, on one multi-module test ontology, the statement held 35 node and 46 relationship element types after the two fixes above (no empty node types; list types from the load's multivalued list). It was accepted (`SHOW CURRENT GRAPH TYPE` returned it), a write with an integer where the type declared a string was rejected with `Neo.ClientError.Schema.ConstraintValidationFailed`, and `ALTER CURRENT GRAPH TYPE SET {}` cleared it. Coverage depends on `sh:targetClass` shapes: a shape that targets with `sh:targetNode` or SHACL-SPARQL gives no element type. Apply it after the load and the verify step, never instead of them: the n10s shapes and the round trip stay the gate. The Neo4j skill `neo4j-cypher-skill`, `references/graph-type.md`, has the full syntax.

## I. Copy to Aura or another Neo4j

n10s does not run on Aura: "neosemantics is only available for Neo4j self-hosted (CE and EE) and is not available in Aura" (https://neo4j.com/labs/neosemantics/, "Availability & Installation"). So build and verify locally (steps 5 and 6), then copy the verified graph with plain Cypher:

```bash
NEO4J_PASSWORD="$PASSWORD" uv run --no-project --with rdflib --with neo4j python3 copy_graph.py \
  --source "bolt://127.0.0.1:$PORT" --target-env <target.env> \
  --report projection-report.json [--replace] [--batch 1000]
```

Run it after `check-report` passed and before the local container is removed (`running.md`, rule 5, step 3). `<target.env>` holds `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` and optionally `NEO4J_DATABASE`, the format of an Aura credentials file; the script never prints the password. It refuses a target that holds any node unless `--replace` is given, which deletes everything there first, in batches. It copies every `:Resource` node with its labels and properties (the `n4sch__` schema nodes included) and every relationship between two `:Resource` nodes, in `UNWIND` batches with dynamic labels and types, after creating the uniqueness constraint on `:Resource(uri)`; it leaves out n10s's configuration nodes (`_GraphConfig`, `_NsPrefDef`, `_n10sValidatorConfig`). `--report` is required: the script reads it before touching either database and stops (exit 2) unless it says `passed: true` with equal sorted and shuffled hashes; it then stops (exit 1), before it writes or deletes anything on the target, unless the source's graph hash equals the report's `determinism_hash_sorted`. So `--replace` can only ever install the verified graph. After the copy it hashes the target as `load_verify.py` does (`pipeline.md`, rule 17) and fails unless it equals the source's. A failure during the copy can leave a partial graph on the target; the script says so, and a rerun with `--replace` replaces it. On 2026-10-23 it copied the library graph (38 nodes, 87 relationships) and a real multi-module ontology (3,925 nodes, 20,015 relationships) to a second local `neo4j:2025.06.2` with equal hashes. On Aura Free (server version `5.27-aura`, Enterprise, Cypher 5 and 25), the same run on the multi-module ontology rebuilt and verified the graph locally, copied 3,925 nodes and 20,015 relationships, and the Aura hash equalled the local and report hash.

rdflib-neo4j (https://neo4j.com/labs/rdflib-neo4j/) is the Neo4j Labs alternative: an RDFLib store backed by Neo4j, "a client-side alternative to Neosemantics for cloud-native Neo4j deployments". It loads RDF from the client but does not run the in-graph SHACL, the round trip or the hash of steps 5 and 6, so this skill copies a graph those steps verified instead.

## J. The same files in a triple store

`triplestore.py` loads the validated inputs into any SPARQL 1.1 store and checks that nothing was lost. It speaks only W3C protocols: the SPARQL 1.1 Graph Store HTTP Protocol (https://www.w3.org/TR/sparql11-http-rdf-update/) to replace each named graph with `PUT` (`?graph=<IRI>`), and the SPARQL 1.1 Protocol to count. There is no store-specific code.

```bash
uv run --no-project --with rdflib python3 triplestore.py --gsp <graph store URL> --query <SPARQL URL> \
  [--env <store.env>] [--graph-base <IRI>] --inferred inferred.nt \
  [--projection-report projection-report.json] [--cq <question.rq>]... --report triplestore-report.json <data.ttl>...
```

- **Graphs:** one named graph per input file: the `owl:versionIRI` of its one `owl:Ontology`, else that ontology's IRI, else `<graph-base><file name>`; `inferred.nt` goes to `<graph-base>inferred`. The default base is `urn:lpg-projection:graph:`; pick one under your own domain for anything shared.
- **Credentials:** `--env` names a file that may set `SPARQL_GSP`, `SPARQL_QUERY`, `SPARQL_USER` and `SPARQL_PASSWORD` (HTTP Basic); flags win. The password is never printed.
- **Counts:** a count is the number of distinct triples; blank nodes count as triples, without matching labels. Per graph, `COUNT(*)` must equal the file's triples; per predicate, the distinct triples over all the loaded graphs must equal the files' together; with `--projection-report`, they must also equal the report's `export_predicate_counts`, the n10s export with the schema rows left out (n10s's configuration nodes are never exported). That is the three-way check: files, store and graph.
- **The report is fail-closed:** the report named by `--report`, and its `.failed` file, are deleted before anything else; the report is written, by a rename, only when every count matched. A mismatch writes the details to `<report>.failed`; a failed request writes nothing. `--projection-report` must say `passed: true`.
- **Competency questions:** each `--cq` SPARQL `SELECT` runs over the loaded graphs (as `default-graph-uri` parameters) and its row count goes into the report.

Start the store with the skill's compose file: from `docker/`, `docker compose --profile fuseki up -d --build` builds Fuseki 6.2.0 from `docker/fuseki/Dockerfile` (which fetches `jena-fuseki-docker-6.2.0.zip` and the server jar, checks each against a pinned SHA-256, and builds as Jena's own Dockerfile does on base images pinned by digest; `--build` keeps a stale local `lpg-fuseki:6.2.0` from being used) and serves an in-memory `/ds` on `127.0.0.1:13030` (`LPG_FUSEKI_PORT` changes it): `--gsp http://127.0.0.1:13030/ds --query http://127.0.0.1:13030/ds/query`. Remove it with `docker compose --profile fuseki down -v`.

It exits 0 when every count matches, 1 on a mismatch or a failed request, 2 on bad input. Tested on 2026-10-23 against Apache Jena Fuseki 6.2.0 in Docker, bound to `127.0.0.1`: Jena publishes no prebuilt image, and its Fuseki Docker page (https://jena.apache.org/documentation/fuseki2/fuseki-docker.html) builds one from the `jena-fuseki-docker` package. The test built it from `jena-fuseki-docker-6.2.0.zip` (SHA-256 `7a2dbc918a02adaba2a398c7cebf64c85a42d9a6717ade814acc14ca27d71c66`, checked against Maven Central's SHA-1) with `docker build --build-arg JENA_VERSION=6.2.0` and ran it with `--mem /ds`; `docker/fuseki/Dockerfile` now does the same in one build. The library files loaded as two graphs (100 and 1 triples), all three counts matched, a competency question returned 3 rows, and a changed export count failed the run. On a multi-module ontology, Fuseki loaded 12 named graphs and the per-graph, per-predicate and three-way counts matched for all 176 predicates. Fuseki 6.2.0 refused a `urn:x-` graph name as a relative IRI, which is why the default base has no `x-` namespace. Remove it afterwards with `docker compose --profile fuseki down -v` (or `docker rm -f -v` for a container started by hand). The counts are checked today; exporting the store back to N-Triples and diffing it with the source (`multi-store.md`, hop 3) is planned.

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
