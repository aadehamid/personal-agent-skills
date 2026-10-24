# ontology-to-lpg

An agent skill for projecting an ontology built on the W3C stack (RDF, RDFS, OWL, SKOS, SHACL) into a Neo4j labelled property graph. The agent works in seven gated steps: design rules, inputs, check, reason and serialise, load, verify, and running it in a repository. The result is a graph that holds exactly the triples that passed every shape, and loads the same way every time. The Turtle release stays the master copy.

The skill is version 2.3 of the Ontology-to-LPG Conversion Playbook. Version 2.2 lived in the enterprise-people-graph repository; on 2026-10-23 the owner decided to move the guideline into this skill, and the repositories that kept a copy now point here. Version 2.3 adds what a projection of a multi-module enterprise ontology learned in October 2026, written in neutral terms with a library example. `references/versions.md` lists the changes.

This README is for people. Agents read `SKILL.md` and the files it points to.

## How to use it

1. Install the skill where your agent finds skills, and ask the agent to project your ontology into Neo4j, or to check whether it is ready for a projection.
2. The agent starts at the design rules and asks you to record the Rule 4 option and its reason in your projection policy. If the ontology is not released yet, it stops there and applies the rules before the first release.
3. After a release, it fills a copy of `templates/projection-config.json` with you: the Rule 4 option and reason, your namespaces and prefixes, your released packages, your qualified-relation classes. It lists each rule gap in a released module as a release exception, with the release that will close it.
4. Run the checks the agent runs:

   ```sh
   uv run --no-project --with rdflib python3 scripts/check_projection_rules.py --config projection-config.json \
     --shapes <shapes.ttl> --releases <release folder> <module.ttl>
   uv run --no-project --with rdflib --with pyshacl python3 scripts/validate_data.py --config projection-config.json \
     --shapes <shapes.ttl> <module.ttl>
   ```

   Each prints one line per failure and exits 1, or prints a pass line and exits 0.

5. `scripts/build.py` writes the reasoner's input, the N-Triples files, the load script and the manifest; `scripts/in_graph_shapes.py` writes the shapes n10s can import without breaking; `scripts/load_verify.py` loads, reads back what n10s compiled, tests every compiled row, verifies and writes the report only when every check passed. Reason, load and verify run on a workstation with Java and Docker; `references/running.md` gives the jar checksums, the `docker run` line and what CI runs instead.

The `ontology` skill builds the ontology and hands over to this one at its Step 12. Each skill works without the other.

## Files

| Path | Read by | What it does |
|---|---|---|
| `SKILL.md` | agent, every run | The index: scope, where to start, the seven steps with their gates and references, the rules for every step, the templates and scripts. Its `description` decides when the skill triggers. |
| `references/design-rules.md` | agent, step 1 | What the projection keeps, the mental model, the five design rules (with options 4a and 4b), the OWL profile and the XSD to Cypher table. |
| `references/inputs.md` | agent, step 2 | Released packages and their pins, shapes, namespaces and prefixes, qualified-relation classes, and the release-exceptions list. |
| `references/pipeline.md` | agent, steps 3 to 6 | Check, reason, serialise (with the 4b flatten), load with n10s, the shapes that run in the graph, and verify. |
| `references/running.md` | agent, step 7 | Where each step runs, pins and checksums, the manifest and the report, clean-up, and scale. |
| `references/add-ons.md` | agent, when a consumer asks for more, or in review | Add-ons A to K (H: a `GRAPH TYPE`; I: the copy to Aura or another Neo4j; J: a SPARQL 1.1 triple store; K: Databricks, planned) and the anti-patterns. |
| `references/multi-store.md` | agent, when one release must live in several stores, or to read the diagrams | The multi-store plan hop by hop, the data-flow diagram box by box, and the validation map V1 to V14 and G1 to G4, each pointing to its rule. |
| `references/diagrams/` | you | The two diagrams: `.eraser` sources, `.excalidraw` scenes written by `make_data_flow.py` and `make_validation_path.py`, and PNGs from `excalidraw render`. |
| `references/learning-path.md` | agent, when you ask what to learn | Thirteen W3C, Neo4j and research topics in priority order, with an exercise each. |
| `references/versions.md` | agent, when a project pins an older version | What versions 2, 2.1, 2.2 and 2.3 changed. |
| `templates/projection-config.json` | agent, step 2 | The configuration `check_projection_rules.py`, `validate_data.py` and `build.py` read: the Rule 4 option and its reason, own namespaces, prefixes, qualified relations, package pins, release exceptions, tool versions. |
| `templates/projection-report.json` | agent, step 6 | The fields the verify step's report holds. Empty, so `build.py check-report` fails on it until a run fills it. |
| `templates/library-module.ttl` | agent and tests | A small released module (works, books, people, copies, authorships) that passes every check, with one subclass axiom so the reasoner infers one type. |
| `templates/library-shapes.ttl` | agent and tests | Its shapes, including constraints n10s cannot import or runs differently, so `in_graph_shapes.py` has something to leave out. |
| `scripts/check_projection_rules.py` | agent and check script | Rules 1, 2, 3, 4a and 5, the round-trip refusals, the package pins and the release exceptions. Needs rdflib. |
| `scripts/validate_data.py` | agent and check script | The check step: pySHACL with every shape and SHACL-AF, plus the refusals. Needs rdflib and pySHACL. |
| `scripts/build.py` | agent and check script | `merge` (the reasoner's input), `loadable`, `inferred`, `check-serialised` (the step 4 gate), `cypher` (the load script), `graph-type` (add-on H), `manifest [--verify]` and `check-report`. Needs rdflib. |
| `scripts/load_verify.py` | agent, steps 5 and 6 | Loads into a running Neo4j with status checks, reads back `listShapes()` and compares it with the shapes file, runs one fail case per compiled row, the mutant, the round trip and the two hashed loads, and writes the report only when every check passed. Needs rdflib and the neo4j driver. |
| `scripts/copy_graph.py` | agent, add-on I | Copies the verified graph to another Neo4j (Aura included) with plain Cypher and compares graph hashes. Needs the neo4j driver. |
| `scripts/triplestore.py` | agent, add-on J | Loads the same files into any SPARQL 1.1 store through the Graph Store Protocol and checks per-graph, per-predicate and three-way counts. Needs rdflib. |
| `scripts/in_graph_shapes.py` | agent and the projection's pipeline | Writes the import-safe shapes, lists each term left out with its reason, and prints an advisory prediction of what n10s will compile; it gates nothing. Needs rdflib. |
| `scripts/test_projection.py` | this repository's check script | Tests: the templates pass; each deliberate break gives exactly its own failure; exceptions cannot waive data errors and fail when stale or empty; the pins are checked numerically against a release folder; each drop-list entry of the subset is exercised and the subset still catches a mutant; the serialiser's order, the inferred filter, the fingerprints, the path-independent manifest, the report check and the generated Cypher; `load_verify.py`'s export parsing (multi-line tags included), schema-row filter, hash specification, shuffle and load checks; the command lines exit 0, 1 or 2. Needs rdflib and pySHACL. |
| `scripts/test_engine_gate.py` | this repository's check script | Tests of the engine-readback gate: what the sanitizer leaves out, the value-aware comparison with `listShapes()`, a generated case per row and its path-and-component match, `no case` failing the run, nothing carried between runs, the fail-closed report, the strict `check-serialised`, the `GRAPH TYPE` output, and the copy and triple-store scripts without a server. Needs rdflib and pySHACL. |
| `docker/compose.yaml`, `docker/fuseki/Dockerfile` | agent and you, steps 5 and 6 and add-on J | Start Neo4j 2025.06.2 with the checked n10s jar and APOC (profile `neo4j`) and Jena Fuseki 6.2.0 built from its pinned package (profile `fuseki`), bound to localhost; `down -v` removes everything. The tests check their pins against `references/running.md` and `references/add-ons.md`. |
| `SOURCES.md` | you | Every source, with version, date and how to check for updates. |
| `README.md` | you | This file. |

## Common tasks

**Change a rule.** Edit the reference file that holds it; `SKILL.md` only points. Keep each rule in one place, with its reason and a source in `SOURCES.md`.

**A new n10s release.** Run `load_verify.py` on the library templates with a shape for every term in the new version: the `listShapes()` comparison and the fail cases (`references/pipeline.md`, rules 13 and 14) show what changed. Then compare the new `SHACLValidator.java` with `N10S_DATATYPES`, `INVERSE_UNREAD`, the prediction queries and every cited line number in `scripts/in_graph_shapes.py`. Update them, `references/pipeline.md`, rules 13 and 14, the jar checksums in `references/running.md`, rule 2, and the versions in `SOURCES.md`.

## Status

Last updated 2026-10-23.

- **No evals yet.** Write test prompts for three branches before tuning: designing a new ontology for a graph, adding a release to an existing projection, and debugging a silent in-graph SHACL check.
- **Scripts cover every step.** `load_verify.py` loads and verifies against a running container; its database parts are tested only by running it (on 2026-10-23 it passed end to end on the library templates, with extra shapes for every term, and on a private multi-module ontology), and its other parts by `test_projection.py` and `test_engine_gate.py`. A compiled row it cannot build a case for (such as `sh:nodeKind sh:BlankNode`, or a row on a `sh:targetQuery` shape) fails the run until `--manual-cases` gives one. `copy_graph.py` was run against a second local Neo4j and against Aura Free; `triplestore.py` against Apache Jena Fuseki 6.2.0.
- **Option 4b has not been run end to end.** Every tested run used 4a. Recheck rdflib issue #3524 and the RDF 1.2 status every three months.
- **One source of experience.** The 2.3 changes come from one multi-module build. Expect changes after a second one.
