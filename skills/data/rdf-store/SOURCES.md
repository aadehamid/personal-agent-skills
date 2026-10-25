# Sources

This file lists every source the rdf-store skill draws on: what the skill took from each, the version or date used, and how to check for a newer one. Agents do not read it. All text in the skill is our own wording.

Last full review: 2026-10-24. Check the sources below every three months, and whenever pyoxigraph, Jena Fuseki, the Databricks SQL connector or a W3C specification below publishes a new version.

## 1. The owner's decision to split the skill

- **What it is:** the owner's instruction of 2026-10-24, recorded in the store-tests handoff: "record it in the handoff as the first piece of step 2. I like the idea of splitting it from the projection skill", answering "should we have a skill that loads .ttl files to any typical triple store, using Jena as default. The skill should alos be able to load .ttl to databrick in a way that there is no loss of data and we go from Databrick to .ttl and back without losing data." Also, on Databricks: "there must be options to use both Databrick Free and Databrick Enterprise edition".
- **What the skill took:** its scope (any SPARQL 1.1 store with Jena as the default, and Databricks both editions), the round trip as the test, and the plain Delta triple table the owner chose over OntoBricks for the lossless store.

## 2. W3C specifications

| Source | Version and date | Used in | What the skill took |
|---|---|---|---|
| RDF Dataset Canonicalization (RDFC-1.0), https://www.w3.org/TR/rdf-canon/ | W3C Recommendation, 21 May 2024; read 2026-10-24 | `references/no-loss.md`; `rdfstore.py` | The canonical form of a dataset, blank nodes included, as the no-loss proof; the canonical N-Quads form of each quad, sorted, as the text that is hashed. |
| RDF 1.1 N-Quads, https://www.w3.org/TR/n-quads/ | W3C Recommendation, 25 February 2014; read 2026-10-24 | `references/no-loss.md`, `stores.md` | N-Quads as the exchange format, since its fourth term carries the graph; the Delta table's columns. RDF 1.2 N-Quads (https://www.w3.org/TR/rdf12-n-quads/) is a Working Draft of 23 October 2026; its triple terms and directional literals are not stored. |
| SPARQL 1.1 Graph Store HTTP Protocol, https://www.w3.org/TR/sparql11-http-rdf-update/ | W3C Recommendation, 21 March 2013; read 2026-10-24 | `references/stores.md`; `FusekiStore` | PUT, GET and DELETE of a named graph with indirect identification (`?graph=<IRI>`), and `?default` for the default graph. |
| SPARQL 1.1 Update, https://www.w3.org/TR/sparql11-update/ | W3C Recommendation, 21 March 2013; read 2026-10-25 | `references/stores.md`; `FusekiStore.publish` | One update request for the whole dataset, because "Each request SHOULD be treated atomically by a SPARQL 1.1 Update service" (quoted). |
| RDF 1.1 Concepts and Abstract Syntax, section 3.5, https://www.w3.org/TR/rdf11-concepts/#section-skolemization | W3C Recommendation, 25 February 2014; read 2026-10-24 | `references/no-loss.md`; `skolemize` | Skolem IRIs under `/.well-known/genid/`. |

## 3. pyoxigraph

- **What it is:** Python bindings of Oxigraph, an RDF library and store in Rust. https://pypi.org/project/pyoxigraph/
- **Version used:** 0.5.13, published to PyPI 2026-10-22; read 2026-10-24.
- **What the skill took:** parsing and writing Turtle, N-Triples and N-Quads, and `Dataset.canonicalize(CanonicalizationAlgorithm.RDFC_1_0)`. Chosen because it is maintained (a release two days before), implements RDFC-1.0 by name, and is one wheel with no system dependencies. On 2026-10-24 its output matched the W3C test suite's expected results (https://w3c.github.io/rdf-canon/tests/) for rdfc10 tests 002 (no blank nodes), 016, 017 and 044 (blank nodes); test 001 is an empty dataset. The three blank-node cases are pinned byte for byte in `scripts/testdata/rdfc10-cases.json` and run in the tests. rdflib 7.6.0's `to_canonical_graph` is not RDFC-1.0; PyLD 3.3.0 implements the older URDNA2015 for JSON-LD.
- **How to check for updates:** `curl -s https://pypi.org/pypi/pyoxigraph/json | python3 -c 'import json,sys; print(json.load(sys.stdin)["info"]["version"])'`.

## 4. Apache Jena Fuseki

- **What it is:** Jena's SPARQL server. `docker/fuseki/Dockerfile` builds 6.2.0 from Jena's `jena-fuseki-docker` package and server jar on Maven Central, each checked against a pinned SHA-256; its build steps match `ontology-to-lpg`'s copy (the opening comments differ), which records the pins' sources in its `SOURCES.md`.
- **Version used:** 6.2.0; run 2026-10-24 in Docker 29.8.2.
- **What the skill took:** the default store, with an in-memory dataset `/ds` and its `/data` and `/query` endpoints.

## 5. The Databricks SQL connector and Delta

- **What it is:** `databricks-sql-connector` on PyPI, the Python DB API driver for Databricks SQL warehouses. https://pypi.org/project/databricks-sql-connector/
- **Version used:** 4.8.0, the version uv resolved on 2026-10-24, against a Databricks SQL warehouse at version 2026.39.
- **What the skill took:** `sql.connect(server_hostname, http_path, access_token)` from this machine, so Free Edition's outbound limits do not apply; `CREATE OR REPLACE TABLE ... USING DELTA`; `FROM VALUES` with `unbase64` and `decode` to keep data text out of the SQL. Without `pyarrow` the connector warns that Arrow fetches are off; the plain fetch read 36,575 rows in a few seconds.
- **How to check for updates:** the connector's PyPI page and its changelog in https://github.com/databricks/databricks-sql-python.
