# rdf-store

An agent skill for loading RDF releases into a triple store and proving that nothing was lost. The agent loads each release file as its own named graph, exports everything the store holds, and compares the two sides by their RDF Dataset Canonicalization (RDFC-1.0) hash. Equal hashes mean every triple, literal, datatype, language tag and graph came back, and nothing was added.

It supports two stores: Apache Jena Fuseki (or any store that speaks the SPARQL 1.1 Graph Store Protocol), and a Delta table in Databricks, on Free Edition or Enterprise. The skill was split out of `ontology-to-lpg` on 2026-10-24, so the projection skill keeps Neo4j and Aura and this one keeps the triple stores.

This README is for people. Agents read `SKILL.md` and the files it points to.

## How to use it

1. Start Fuseki: from `docker/`, run `docker compose -p trial up -d --build`.
2. Round-trip your releases:

   ```sh
   uv run --no-project --with pyoxigraph python3 scripts/rdfstore.py roundtrip --store fuseki \
     --gsp http://127.0.0.1:13031/ds/data --query http://127.0.0.1:13031/ds/query \
     --report report.json <release>.ttl ...
   ```

   It prints `PASS` and exits 0 when the store's copy has the same hash, or prints a diff and exits 1.

3. For Databricks, put the workspace address, token, warehouse path, catalog and schema in an env file outside any repository, and run the same command with `--store databricks --env <file>` (and `--with databricks-sql-connector`).

## Tested on

On 2026-10-24 the 33 graphs of an 11-module enterprise ontology's newest releases (36,575 quads, 1,995 of them with blank nodes) round-tripped with equal hashes through Fuseki 6.2.0 in Docker and through a Delta table on a Databricks serverless SQL warehouse. The Databricks load took 72 seconds. The skolemized copy round-tripped through Fuseki too.

## Files

- `SKILL.md`: the steps the agent follows.
- `scripts/rdfstore.py` and `scripts/test_rdf_store.py`: the tool and its tests.
- `docker/`: Jena Fuseki built from pinned parts.
- `references/`: the proof and the stores.
- `SOURCES.md`: every source, with its version and date.
