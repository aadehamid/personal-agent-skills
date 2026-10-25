# Stores

## Jena Fuseki, and any Graph Store Protocol store

Jena Fuseki is the default store. From `docker/`, `docker compose -p <project> up -d --build` builds Fuseki 6.2.0 from the pinned, checksummed package and jar (the Dockerfile says how), with an in-memory dataset `/ds`; `docker compose -p <project> down -v` removes it. `RDF_FUSEKI_PORT` sets the port (default 13031). The endpoints:

- Graph Store Protocol: `http://127.0.0.1:<port>/ds/data`
- SPARQL query: `http://127.0.0.1:<port>/ds/query`
- SPARQL update: `http://127.0.0.1:<port>/ds/update`

`roundtrip --store fuseki --gsp <data URL> --query <query URL> --update <update URL>` works with any store that implements the SPARQL 1.1 Graph Store HTTP Protocol (indirect graph identification, `?graph=<IRI>`), the SPARQL 1.1 Protocol and SPARQL 1.1 Update.

- **Publishing.** With `--update`, the whole dataset goes in one SPARQL Update request (`DROP SILENT GRAPH` then `INSERT DATA` per graph). SPARQL 1.1 Update says "Each request SHOULD be treated atomically": a SHOULD, not a guarantee. A store that applies it that way leaves itself as it was when the request fails; one that does not can be left with some graphs dropped. Without `--update`, each graph is replaced by its own HTTP PUT, and a failure part way leaves some graphs new and some old. Either failure stops the run with exit 1, never a pass; reload the store before you trust it. This skill has not tested a failure part way through a live Fuseki update.
- **Blank nodes stay in one graph.** Each graph travels as its own document, so a blank node that occurs in two graphs cannot survive the trip; the run refuses such a dataset (exit 2) before any request. Skolemize it, or keep each blank node in one graph.
- **Exporting.** The script lists the store's named graphs with a SPARQL query, reads each back with HTTP GET as N-Triples, and reads the default graph with `?default`. Each graph is a separate document, so its blank nodes are standardized apart from every other graph's.

An in-memory dataset starts empty on every restart, which makes "nothing you have not loaded" (SKILL.md, step 3) a restart away.

The `ontology-to-lpg` skill keeps a copy of `docker/fuseki/Dockerfile` for its own count checks. The two differ only in their opening comments; a test fails when their build steps differ, so update both together.

## Databricks: a Delta triple table

`roundtrip --store databricks --env <file> [--table <name>]` writes the dataset to a Delta table in Unity Catalog and reads it back, from this machine over the Databricks SQL connector. The env file, outside any repository, holds `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `DATABRICKS_HTTP_PATH` (the SQL warehouse's), `DATABRICKS_CATALOG` and `DATABRICKS_SCHEMA`. The schema must exist. The run touches two tables: `<table>` (default `rdf_quads`) and a staging table of its own, `<table>__staging_<random>`, so two runs on one table never verify or promote each other's rows.

- **Staging, then one replace.** The rows go into the run's staging table, which the script exports and compares first. Only a staging copy with the same hash replaces `<table>`, in one `CREATE OR REPLACE TABLE <table> AS SELECT * FROM <staging>`, a single Delta transaction; the staging table is dropped whatever happens, and the live table is read back and compared again, since that is what consumers see. When two runs target one table, the last to replace it wins. A failure or a mismatch before the replace leaves the previous `<table>` as it was (the report says `"published": false`).
- **Unsupported terms are refused first.** RDF 1.2 triple terms and literals with a base direction stop the run with exit 2 before any statement runs.
- **The token** is removed from every message the script prints and from the report, including the connector's own errors and any data value that holds it; errors about the env file name the setting, never its value.

The table is N-Quads as columns:

| Column | Holds |
|---|---|
| `subject` | an IRI, or `_:label` for a blank node (an IRI always has a scheme, which cannot start with `_`) |
| `predicate` | an IRI |
| `object` | the IRI, `_:label` for a blank node, or the literal's lexical form |
| `object_kind` | `iri`, `bnode` or `literal`: the same text can be any of the three, so the kind has its own column |
| `datatype` | a literal's datatype IRI; NULL for a language-tagged literal and for an IRI or blank node |
| `lang` | a literal's language tag, else NULL |
| `graph` | the named graph's IRI; NULL for the default graph |

Every value travels base64-encoded inside the INSERT and is decoded in SQL (`decode(unbase64(...), 'UTF-8')`), so no text from the data is ever read as SQL, whatever quotes or backslashes it holds. Rows go in batches of 2,000 per statement.

**Both editions.** Free Edition gives one small serverless SQL warehouse and limits outbound internet to trusted domains, so every transfer runs from this machine; never push from a notebook to an outside service. Enterprise runs the same path; a job in the workspace can do the same work where its network policy allows the destination, and its result counts only when its hash equals this script's.

The table is a store, not a reasoner or a SPARQL endpoint: query it with SQL, or `export` it to N-Quads (and Turtle, one file per graph) to rebuild a triple store or a property graph.
