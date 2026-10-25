---
name: rdf-store
description: >-
  Gated method for loading RDF releases (Turtle, N-Triples, N-Quads) into a triple store and proving by a round trip that nothing was lost. Use when loading an ontology or any RDF dataset into Apache Jena Fuseki or another SPARQL 1.1 store; storing RDF in Databricks as a Delta table and reading it back; exporting a store's copy to N-Quads or Turtle; skolemizing blank nodes before a load; comparing two RDF datasets for loss with RDF Dataset Canonicalization (RDFC-1.0); or checking that a store, an export or a migration kept every triple, literal, datatype, language tag and named graph.
---

# RDF store

Load releases into a store in **gated** steps; each step ends on its "Done when" gate. The release files are the master copy: a store holds a copy that must come back **isomorphic**, and the round trip is the proof.

Scope: RDF files into a store and back out. Building the ontology belongs to the `ontology` skill; projecting it into a labelled property graph (Neo4j, Aura) belongs to `ontology-to-lpg`, whose multi-store plan uses this skill for its triple-store hops.

The script is `scripts/rdfstore.py`; run it with `uv run --no-project --with pyoxigraph python3 scripts/rdfstore.py <command>` (add `--with databricks-sql-connector` for Databricks). Its docstring lists every command and option; it refuses an option a command does not take, before touching any file or store.

## The steps

1. **Name the graphs.** Read `references/no-loss.md`, "Graphs".
   Done when: `rdfstore.py pack --out <dataset.nq> [--graph FILE=IRI]... <file>...` exits 0, so every file has one graph name, no two files share one, and no quad sits in the default graph.
2. **Skolemize, when a consumer needs stable IRIs for blank nodes** (a property graph, an index, a link from elsewhere). Read `references/no-loss.md`, "Skolemization". The hash proof works with blank nodes, so a store-only round trip may skip this step.
   Done when: `rdfstore.py skolemize --authority <https://your-host> --out <dir> <file>...` wrote every file, the output holds no `_:` label, and a second run writes byte-identical files.
3. **Start the store.** Read `references/stores.md` for the store you use: Jena Fuseki from `docker/compose.yaml` by default, any store that speaks the SPARQL 1.1 Graph Store Protocol, or a Databricks Delta table (Free or Enterprise).
   Done when: the store answers (Fuseki's `/$/ping`; for Databricks, a `SELECT 1` over the env file's warehouse), and the store holds nothing you have not loaded yourself: the round trip exports everything, so a leftover graph fails it.
4. **Round trip.** `rdfstore.py roundtrip --store fuseki|databricks <store options> --report <report.json> <file>...` publishes the dataset, exports everything the store holds, and compares. With Fuseki, pass `--update` so the whole dataset goes in one request; with Databricks, the rows go through a staging table that replaces the live one only when its copy matches.
   Done when: it exits 0 and prints `PASS the store's copy has the same RDFC-1.0 hash`; the report's `hashes_equal` is true. Equal counts without equal hashes are a fail: counts miss a changed value.
5. **Read a failure.** On exit 1 with a report, read its `diff` (quads missing from and extra in the store's copy, with their numbers in `missing` and `extra`) and `graph_counts`; read `references/no-loss.md`, "Reading a diff", before you change anything. Exit 1 with `FAIL a store request or write failed` leaves no report: read the message, and reload the store before trusting it.
   Done when: you can name the cause of every missing and extra quad, fixed it in the load or the store, and step 4 passes.
6. **Export a copy, when a consumer needs one** (a rebuild of another store, a Turtle file per graph). `rdfstore.py export --store ... --out <dataset.nq> [--ttl-dir <dir>]`. `--out` must be a new file and `--ttl-dir` an empty or new folder; the outputs are written all together or not at all.
   Done when: `rdfstore.py compare <packed release.nq> <dataset.nq>` exits 0.

## Rules that apply at every step

- **The hash is the proof; counts are a quick look.** `references/no-loss.md`, "The proof".
- **Export everything the store holds,** never only what you loaded, so a leftover graph shows as extra.
- **Never print a credential.** Store credentials live in an env file outside the repository; the script reads them and removes them from every message it prints.
- **A store's copy is disposable.** Rebuild it from the release files; never fix a release by editing its copy in a store.

## Files

- `scripts/rdfstore.py`: `skolemize`, `pack`, `roundtrip`, `export` and `compare`; exit 0 on a pass, 1 on a failed check or request, 2 on bad input (found before any store is touched).
- `scripts/test_rdf_store.py`: the tests (no Docker or Databricks needed), run by the repository's check script; live tests run when `RDF_STORE_LIVE_FUSEKI` or `RDF_STORE_LIVE_DATABRICKS` is set. `scripts/testdata/` holds W3C RDFC-1.0 test cases.
- `docker/compose.yaml` and `docker/fuseki/Dockerfile`: Jena Fuseki 6.2.0 built from pinned, checksummed parts.
- `references/no-loss.md`: graphs, skolemization, the proof and reading a diff.
- `references/stores.md`: Fuseki and other Graph Store Protocol stores, and the Databricks Delta table.
