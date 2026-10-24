---
name: ontology-to-lpg
description: >-
  Gated method for projecting an ontology built on the W3C stack (RDF, RDFS, OWL, SKOS, SHACL) into a Neo4j labelled property graph. Use when loading an OWL, RDF or SKOS ontology into Neo4j or another property graph; configuring or debugging n10s (neosemantics); deciding whether a term becomes a node, a relationship or a property; modelling a relationship that carries its own properties (qualified relations or RDF 1.2 reifiers); validating a projection with SHACL in the graph, a round-trip diff or a determinism check; copying the verified graph to Aura, where n10s does not run; or loading the same data into a SPARQL 1.1 triple store.
---

# Ontology to labelled property graph

Project the ontology in **gated** steps. Each step ends on its "Done when" gate; start the next step only when the gate is met. The Turtle release is the master copy: the graph is a projection that can be rebuilt from it at any time.

Scope: from design rules to a verified, repeatable graph. Building the ontology itself (identity, taxonomy, shapes, releases) belongs to the `ontology` skill, whose Step 1 records the projection policy and whose Step 12 hands over to step 2 here; application Cypher and graph data-modelling advice belong to a graph-database skill.

## First, find where the projection stands

1. Read the project's projection policy (`references/design-rules.md`, "Where the Rule 4 choice is recorded"), configuration, manifest and last report, if they exist.
2. Read the project's own projection method, if it has one. Its rules win where they conflict with this skill. The scripts here implement version 2.3 only and have no switch for older behaviour (no `--include-indirect` reasoning, an `onto.import` of `merged.ttl`, the `xsd:` prefix rule); a project pinned to an earlier version keeps using its own scripts and reads `references/versions.md` for what changed.
3. Name the current step and its open gate before you do any work.

## The steps

Before you work on a step, read the reference it names. The scripts run with `uv run --no-project --with rdflib python3 <script>` (add `--with pyshacl` for `validate_data.py`, `--with neo4j` for `load_verify.py`).

1. **Design rules.** Read `references/design-rules.md`. Apply it before the ontology's first release.
   Done when: a recorded place (the projection policy, `references/design-rules.md`, "Where the Rule 4 choice is recorded") holds the Rule 4 option (4a or 4b) and its reason; for the library example, the template configuration's `rule4_reason` is that record. If no module is released yet, stop here: apply the design rules in the ontology build, and return at step 2 after the first release.
2. **Inputs and rule check.** Read `references/inputs.md`; copy `templates/projection-config.json` and copy the Rule 4 option and reason into it.
   Pass many shape files as repeated `--shapes` options built in an array, which bash and zsh both keep apart (zsh does not split a plain variable). Build it from the configuration's pins, so each module contributes the shapes of its pinned release only, then add the whole-graph shape files: `SHAPES=(); while read -r f; do SHAPES+=(--shapes "$f"); done < <(python3 -c 'import json,sys; [print(f"{sys.argv[2]}/{m}/{v}/shapes.ttl") for m, v in sorted(json.load(open(sys.argv[1]))["packages"].items())]' projection-config.json releases); SHAPES+=(--shapes <whole-graph shapes.ttl>)`, then pass `"${SHAPES[@]}"`. Build the data list the same way with `{m}.ttl`.
   Done when: `check_projection_rules.py --config <config> --shapes <shapes>... --releases <folder> <data>...` exits 0, so every released module is pinned at its newest version; every namespace the data and shapes use for predicates or classes (your own, as `own_namespaces` lists them, and the standard ones) has exactly one prefix; every qualified-relation class is registered with its ends and their shapes; and every listed rule gap has a fix and still occurs. Under Rule 4b the script stops with exit 2: run the checks in Jena or RDF4J, or stop and ask the owner.
3. **Check.** Read `references/pipeline.md`, rules 1 to 3.
   Done when: `validate_data.py --config <config> --shapes <shapes>... <data>...` exits 0: the data conforms to every shape with SHACL-AF on, and no value is refused.
4. **Reason and serialise.** Read `references/pipeline.md`, rules 4 to 7, and `references/running.md`, rule 2 (the ROBOT checksum); use `build.py merge`, ROBOT, `build.py loadable`, `build.py inferred` and, on the first run, `build.py manifest` without `--verify`.
   Done when: `build.py check-serialised --loadable loadable.nt --inferred inferred.nt` exits 0, so both files are in byte order without duplicates and `inferred.nt` holds only IRI-to-IRI `rdf:type` and `rdfs:subClassOf` triples whose object is outside the OWL and RDFS namespaces; `validate_data.py` exits 0 over both files together; `build.py manifest` has recorded the input fingerprint.
5. **Load.** Read `references/running.md`, rules 2 and 5 (pinned jars and the container), then `references/pipeline.md`, rules 8 to 14. One `load_verify.py` run serves steps 5 and 6: it writes the import-safe shapes, copies the four files into the import folder, runs the generated load script, checks each import, reads back what n10s compiled, and goes on to verify.
   Done when: the container runs `neo4j:2025.06.2` bound to `127.0.0.1` with the checked jars; `load_verify.py` got past its load (no `FAIL` about `terminationStatus` or the shapes count) and read back `listShapes()`: the gate is what n10s compiled, not the shapes file. Every compiled row has a case that passed or is a no-op; a row with status `no case` fails the run until `--manual-cases` gives one, and every run reruns every case (`references/pipeline.md`, rules 13 and 14; the order is in `references/running.md`, rule 5).
6. **Verify.** Read `references/pipeline.md`, rules 15 to 17. The same `load_verify.py` run does the mutant, the round trip and the two hashed loads, and writes the report in the shape of `templates/projection-report.json`.
   Done when: `build.py check-report` passes on the report, which is the one gate for steps 5 and 6. `load_verify.py` writes the report only when every check passed (exit 0); exit 1 or 2 leaves no report, so stop and do not run `check-report`. Then remove the container with `docker rm -f -v <container>` (the name `load_verify.py` printed: its `--container`, else `$LPG_CONTAINER`, else `lpg-projection`); remove it the same way if you stop earlier (`references/running.md`, rule 5). The report shows zero violations in the graph and at least one on the deliberate mutant, zero triples lost and zero added in the round trip (schema rows excluded), and equal hashes for the sorted and shuffled loads.
7. **Run it in the repository.** Read `references/running.md`.
   Done when: CI runs the commands of `references/running.md`, rule 1, and `build.py manifest --verify` fails after an input or shape file is edited; `build.py check-report` passes on the committed report; `inferred.nt`, the manifest and the report are committed together from one run; `docker ps -a` lists no projection container, because every run ended with `docker rm -f -v <container>` (the `-v` also removes its anonymous volumes).

For add-ons a consumer asks for (superclass labels, language keys, exact decimals, units, provenance, business keys; copying the verified graph to Aura or another Neo4j without n10s; a Cypher 25 `GRAPH TYPE` from the shapes; loading the same files into any SPARQL 1.1 triple store with count checks) and the anti-patterns to review against, read `references/add-ons.md`. When the user asks what to learn first, or for exercises, read `references/learning-path.md`.

## Related Neo4j skills

Neo4j publishes agent skills in `neo4j-contrib/neo4j-skills` (plugin 1.0.1, commit `39247b9`). None of them covers RDF, SHACL or n10s; use them beside this skill:

- `neo4j-ontology-skill`: Neo4j's own Ontology Graph Specification, a different thing from a W3C ontology;
- `neo4j-cypher-skill`, `references/graph-type.md`: the Cypher 25 `GRAPH TYPE` syntax that add-on H emits;
- `neo4j-modeling-skill`: graph data-modelling advice, background for design rules 1 and 2;
- `neo4j-cli-tools-skill`: `cypher-shell`, `neo4j-admin` and running Neo4j in Docker;
- `neo4j-import-skill`: bulk import with `neo4j-admin database import` at the sizes of `references/running.md`, rule 6, and its post-import checks.

## Rules that apply at every step

- **The Turtle release is the master copy;** never edit the graph to fix the ontology.
- **Generate every statement** (configuration, prefixes, multivalued list, in-graph shapes) from the ontology and the configuration: `references/pipeline.md`, rule 8.
- **Silence is not a pass:** a check counts only once it has been seen to fail (`references/pipeline.md`, rules 14 and 15).
- **A rule gap is listed or fixed, never ignored:** `references/inputs.md`, rule 5.
- **Pin and fingerprint everything a result depends on:** `references/running.md`, rules 2 and 3.

## Templates and scripts

Copy from `templates/`: `projection-config.json` (the configuration), `projection-report.json` (the report's shape; it fails `check-report` until filled), and `library-module.ttl` with `library-shapes.ttl` (a small module that passes every check and gives the reasoner one inference to keep). The scripts in `scripts/`:

- `check_projection_rules.py`: the design rules, package pins, refusals and release exceptions;
- `validate_data.py`: pySHACL with every shape, plus the refusals;
- `build.py`: `merge`, `loadable`, `inferred`, `check-serialised`, `cypher`, `graph-type`, `manifest [--verify]` and `check-report`;
- `in_graph_shapes.py`: the import-safe shapes (only what would break n10s left out, each with its reason) and an advisory prediction of what n10s will compile; it gates nothing;
- `load_verify.py`: the load and verify steps against the container, gated on what `listShapes()` reads back, ending in the report;
- `copy_graph.py`: add-on I, copies the verified graph to another Neo4j and compares graph hashes;
- `triplestore.py`: add-on J, loads the same files into a SPARQL 1.1 store and checks the counts;
- `test_projection.py` and `test_engine_gate.py`: the tests of all of them (the parts that need no database or store), run by the repository's check script (`uv run --no-project --with rdflib --with pyshacl python3 -m unittest test_projection test_engine_gate`).

Exit codes: 2 means bad input for every script. `check_projection_rules.py`, `validate_data.py` and `build.py` exit 0 on a pass and 1 with one line per failure. `load_verify.py` prints a JSON summary and every constraint n10s did not compile, then exits 0 and writes the report only when every check passed, and 1 otherwise; `build.py check-report` passing means steps 5 and 6 are done.
