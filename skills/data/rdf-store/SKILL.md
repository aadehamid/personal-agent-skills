---
name: rdf-store
description: >-
  Gated method for loading RDF releases (Turtle, N-Triples, N-Quads) into a triple store and proving by a round trip that nothing was lost. Use when loading an ontology or any RDF dataset into Apache Jena Fuseki or another SPARQL 1.1 store; storing RDF in Databricks as a Delta table and reading it back; skolemizing blank nodes before a load; comparing two RDF datasets for loss with RDF Dataset Canonicalization (RDFC-1.0); or checking that a store, an export or a migration kept every triple, literal, datatype, language tag and named graph.
---

# RDF store

Load releases into a store in **gated** steps; each step ends on its "Done when" gate. The release files are the master copy: a store holds a copy that must come back **isomorphic**, and the round trip is the proof.

Scope: RDF files into a store and back out. Building the ontology belongs to the `ontology` skill; projecting it into a labelled property graph (Neo4j, Aura) belongs to `ontology-to-lpg`, whose multi-store plan uses this skill for its triple-store hops.

The script is `scripts/rdfstore.py`; run it with `uv run --no-project --with pyoxigraph python3 scripts/rdfstore.py <command>` (add `--with databricks-sql-connector` for Databricks). Its docstring lists every command and option.

## The steps

1. **Name the graphs.** Read `references/no-loss.md`, "Graphs". Each release file is one named graph, named by the owl:versionIRI of its one owl:Ontology; a file without one gets `--graph FILE=IRI`.
   Done when: `rdfstore.py pack --out <dataset.nq> [--graph FILE=IRI]... <file>...` exits 0, so no two files share a graph and every file has a name.
2. **Skolemize, when a consumer needs stable IRIs for blank nodes** (a property graph, an index, a link from elsewhere). Read `references/no-loss.md`, "Skolemization". The hash proof works with blank nodes, so a store-only round trip may skip this step.
   Done when: `rdfstore.py skolemize --authority <https://your-host> --out <dir> <file>...` wrote every file, the output holds no `_:` label, and a second run writes byte-identical files.
3. **Start the store.** Read `references/stores.md` for the store you use: Jena Fuseki from `docker/compose.yaml` by default, any store that speaks the SPARQL 1.1 Graph Store Protocol, or a Databricks Delta table (Free or Enterprise).
   Done when: the store answers (Fuseki's `/$/ping`; for Databricks, a `SELECT 1` over the env file's warehouse), and the graphs or table you will load hold nothing you have not loaded yourself.
4. **Round trip.** `rdfstore.py roundtrip --store fuseki|databricks <store options> --report <report.json> <file>...` clears the graphs it will load, loads them, exports everything the store holds, and compares.
   Done when: it exits 0 and prints `PASS the store's copy has the same RDFC-1.0 hash`; the report's `hashes_equal` is true. Equal counts without equal hashes are a fail: counts miss a changed value.
5. **Read a failure.** On exit 1, read the report's `diff` (quads missing from and extra in the store's copy) and `graph_counts`. Read `references/no-loss.md`, "Reading a diff", before you change anything.
   Done when: you can name the cause of every missing and extra quad (a stale graph from an earlier load, a store that rewrote a literal, a term kind lost in a table), fixed it in the load or the store, and step 4 passes.

## Rules that apply at every step

- **The hash is the proof; counts are a quick look.** `references/no-loss.md`, "The proof".
- **Export everything the store holds,** never only what you loaded, so a leftover graph shows as extra.
- **Never print a credential.** Store credentials live in an env file outside the repository; the script reads them and prints none.
- **A store's copy is disposable.** Rebuild it from the release files; never fix a release by editing its copy in a store.

## Files

- `scripts/rdfstore.py`: `skolemize`, `pack`, `roundtrip` and `compare`; exit 0 on a pass, 1 on a failed check or request, 2 on bad input.
- `scripts/test_rdf_store.py`: the tests (no Docker or Databricks needed), run by the repository's check script; live tests run when `RDF_STORE_LIVE_FUSEKI` or `RDF_STORE_LIVE_DATABRICKS` is set.
- `docker/compose.yaml` and `docker/fuseki/Dockerfile`: Jena Fuseki 6.2.0 built from pinned, checksummed parts.
- `references/no-loss.md`: graphs, skolemization, the proof and reading a diff.
- `references/stores.md`: Fuseki and other Graph Store Protocol stores, and the Databricks Delta table.
