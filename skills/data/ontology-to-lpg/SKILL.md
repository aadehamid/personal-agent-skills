---
name: ontology-to-lpg
description: >-
  Gated method for projecting an ontology built on the W3C stack (RDF, RDFS, OWL, SKOS, SHACL) into a Neo4j labelled property graph. Use when loading an OWL, RDF or SKOS ontology into Neo4j or another property graph; configuring or debugging n10s (neosemantics); deciding whether a term becomes a node, a relationship or a property; modelling a relationship that carries its own properties (qualified relations or RDF 1.2 reifiers); or validating a projection with SHACL in the graph, a round-trip diff or a determinism check.
---

# Ontology to labelled property graph

Project the ontology in **gated** steps. Each step ends on its "Done when" gate; start the next step only when the gate is met. The Turtle release is the master copy: the graph is a projection that can be rebuilt from it at any time.

Scope: from design rules to a verified, repeatable graph. Building the ontology itself (identity, taxonomy, shapes, releases) belongs to the `ontology` skill, whose Step 1 records the projection policy and whose Step 12 hands over to step 2 here; application Cypher and graph data-modelling advice belong to a graph-database skill.

## First, find where the projection stands

1. Read the project's projection policy (`references/design-rules.md`, "Where the Rule 4 choice is recorded"), configuration, manifest and last report, if they exist.
2. Read the project's own projection method, if it has one. Its rules win where they conflict with this skill. If it pins an earlier version of this method, read `references/versions.md`.
3. Name the current step and its open gate before you do any work.

## The steps

Before you work on a step, read the reference it names. The scripts run with `uv run --no-project --with rdflib` (add `--with pyshacl` for `validate_data.py`).

1. **Design rules.** Read `references/design-rules.md`. Apply it before the ontology's first release.
   Done when: the projection policy records the Rule 4 option (4a or 4b) and its reason. If no module is released yet, stop here: apply the design rules in the ontology build, and return at step 2 after the first release.
2. **Inputs and rule check.** Read `references/inputs.md`; copy `templates/projection-config.json` and copy the Rule 4 option and reason into it.
   Done when: `check_projection_rules.py --config <config> --shapes <shapes>... --releases <folder> <data>...` exits 0, so every released module is pinned at its newest version; every namespace you own, and every standard namespace the data and shapes use, has exactly one prefix; every qualified-relation class is registered with its ends and their shapes; and every listed rule gap has a fix and still occurs. Under Rule 4b the script stops with exit 2: run the checks in Jena or RDF4J, or stop and ask the owner.
3. **Check.** Read `references/pipeline.md`, rules 1 to 3.
   Done when: `validate_data.py --config <config> --shapes <shapes>... <data>...` exits 0: the data conforms to every shape with SHACL-AF on, and no value is refused.
4. **Reason and serialise.** Read `references/pipeline.md`, rules 4 to 7; use `build.py merge`, ROBOT, `build.py loadable` and `build.py inferred`.
   Done when: `loadable.nt` and `inferred.nt` exist in byte order without duplicates; `inferred.nt` holds only IRI-to-IRI `rdf:type` and `rdfs:subClassOf` triples whose object is outside the OWL and RDFS namespaces; `validate_data.py` exits 0 over both files together; `build.py manifest` has recorded the input fingerprint.
5. **Load.** Read `references/running.md`, rules 2 and 5 (pinned jars and the container), then `references/pipeline.md`, rules 8 to 14. Generate the in-graph shapes with `in_graph_shapes.py` and the load script with `build.py cypher`.
   Done when: the container runs `neo4j:2025.06.2` bound to `127.0.0.1` with the checked jars; `onto.import` and both `rdf.import` calls return `terminationStatus` `OK`; the shapes import's row count is above zero and equals the `listShapes()` count; the dropped constraints are recorded with their reasons; each constraint kind left in the graph has a fail case (`references/pipeline.md`, rule 14).
6. **Verify.** Read `references/pipeline.md`, rules 15 to 17; write the report in the shape of `templates/projection-report.json`.
   Done when: the report shows zero violations in the graph and at least one on the deliberate mutant, zero triples lost and zero added in the round trip (schema rows excluded), and equal hashes for the sorted and shuffled loads.
7. **Run it in the repository.** Read `references/running.md`.
   Done when: CI runs the commands of `references/running.md`, rule 1, and `build.py manifest --verify` fails after an input or shape file is edited; `build.py check-report` passes on the committed report; `inferred.nt`, the manifest and the report are committed together from one run; `docker ps -a` lists no projection container.

For add-ons a consumer asks for (superclass labels, language keys, exact decimals, units, provenance, business keys) and the anti-patterns to review against, read `references/add-ons.md`. When the user asks what to learn first, or for exercises, read `references/learning-path.md`.

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
- `build.py`: `merge`, `loadable`, `inferred`, `cypher`, `manifest [--verify]` and `check-report`;
- `in_graph_shapes.py`: the subset of the shapes n10s can run, with each drop listed;
- `test_projection.py`: the tests of all four, run by the repository's check script (`uv run --no-project --with rdflib --with pyshacl python3 -m unittest test_projection`).

Each script exits 0 on a pass, 1 with one line per failure, 2 on bad input.
