# Stores

## Jena Fuseki, and any Graph Store Protocol store

Jena Fuseki is the default store. From `docker/`, `docker compose -p <project> up -d --build` builds Fuseki 6.2.0 from the pinned, checksummed package and jar (the Dockerfile says how), with an in-memory dataset `/ds`; `docker compose -p <project> down -v` removes it. `RDF_FUSEKI_PORT` sets the port (default 13031). The endpoints:

- Graph Store Protocol: `http://127.0.0.1:<port>/ds/data`
- SPARQL query: `http://127.0.0.1:<port>/ds/query`

`roundtrip --store fuseki --gsp <data URL> --query <query URL>` works with any store that implements the SPARQL 1.1 Graph Store HTTP Protocol (indirect graph identification, `?graph=<IRI>`) and the SPARQL 1.1 Protocol. It replaces each graph with HTTP PUT (N-Triples), lists the store's named graphs with a SPARQL query, reads each back with HTTP GET, and reads the default graph with `?default`.

An in-memory dataset starts empty on every restart, which makes "nothing you have not loaded" (SKILL.md, step 3) a restart away.

The `ontology-to-lpg` skill keeps an identical copy of `docker/fuseki/Dockerfile` for its own count checks; a test here fails when the two differ, so update both together.

## Databricks: a Delta triple table

`roundtrip --store databricks --env <file> [--table <name>]` writes the dataset to a Delta table in Unity Catalog and reads it back, from this machine over the Databricks SQL connector. The env file, outside any repository, holds `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `DATABRICKS_HTTP_PATH` (the SQL warehouse's), `DATABRICKS_CATALOG` and `DATABRICKS_SCHEMA`. The schema must exist; the run replaces the one table it names (default `rdf_quads`) and touches nothing else.

The table is N-Quads as columns:

| Column | Holds |
|---|---|
| `subject` | an IRI, or `_:label` for a blank node (an IRI always has a scheme, which cannot start with `_`) |
| `predicate` | an IRI |
| `object` | the IRI, the blank-node label or the literal's lexical form |
| `object_kind` | `iri`, `bnode` or `literal`: the same text can be any of the three, so the kind has its own column |
| `datatype` | a literal's datatype IRI; NULL for a language-tagged literal and for an IRI or blank node |
| `lang` | a literal's language tag, else NULL |
| `graph` | the named graph's IRI; NULL for the default graph |

Every value travels base64-encoded inside the INSERT and is decoded in SQL (`decode(unbase64(...), 'UTF-8')`), so no text from the data is ever read as SQL, whatever quotes or backslashes it holds. Rows go in batches of 2,000 per statement.

Not stored: RDF 1.2 triple terms and literals with a base direction. The script stops with exit 2 on either, rather than storing them wrong.

**Both editions.** Free Edition gives one small serverless SQL warehouse and limits outbound internet to trusted domains, so every transfer runs from this machine; never push from a notebook to an outside service. Enterprise runs the same path; a job in the workspace can do the same work where its network policy allows the destination, and its result counts only when its hash equals this script's.

The table is a store, not a reasoner or a SPARQL endpoint: query it with SQL, or rebuild a triple store or a property graph from its export.
