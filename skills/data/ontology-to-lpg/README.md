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
| `references/add-ons.md` | agent, when a consumer asks for more, or in review | Add-ons A to L (F: module tags, the module graph and the walk across modules; H: a `GRAPH TYPE`; I: the copy to Aura or another Neo4j; J: a SPARQL 1.1 triple store; K: Databricks, both now loaded and round-tripped by the `rdf-store` skill; L: a Data Modeling MCP model), the review of a loaded graph against Neo4j's modeling anti-patterns, and the anti-patterns. |
| `references/run-config.md` | agent, when one command should run every step and store | `run_projection.py`: the run configuration, each step and the check it runs, and the rebuild from a store. |
| `references/multi-store.md` | agent, when one release must live in several stores, or to read the diagrams | The multi-store plan hop by hop, the data-flow diagram box by box, and the validation map V1 to V14 and G1 to G4, each pointing to its rule. |
| `references/diagrams/` | you | The two diagrams: `.eraser` sources, `.excalidraw` scenes written by `make_data_flow.py` and `make_validation_path.py`, and PNGs from `excalidraw render`. |
| `references/learning-path.md` | agent, when you ask what to learn | Thirteen W3C, Neo4j and research topics in priority order, with an exercise each. |
| `references/versions.md` | agent, when a project pins an older version | What versions 2, 2.1, 2.2 and 2.3 changed. |
| `references/playbook.html` | you | This README and every reference above as one page to read in a browser, with the two diagrams. `scripts/build_playbook_html.py`, at the repository root, generates it from the Markdown: edit the Markdown, then rebuild. |
| `templates/projection-config.json` | agent, step 2 | The configuration `check_projection_rules.py`, `validate_data.py` and `build.py` read: the Rule 4 option and its reason, own namespaces, prefixes, qualified relations, package pins, release exceptions, tool versions. |
| `templates/run-config.json` | agent, every run after the first | The run configuration `run_projection.py` reads, for the library example in files mode. |
| `templates/projection-report.json` | agent, step 6 | The fields the verify step's report holds. Empty, so `build.py check-report` fails on it until a run fills it. |
| `templates/library-module.ttl` | agent and tests | A small released module (works, books, people, copies, authorships) that passes every check, with one subclass axiom so the reasoner infers one type. |
| `templates/library-shapes.ttl` | agent and tests | Its shapes, including constraints n10s cannot import or runs differently, so `in_graph_shapes.py` has something to leave out. |
| `scripts/check_projection_rules.py` | agent and check script | Rules 1, 2, 3, 4a and 5, the round-trip refusals, the package pins and the release exceptions. Needs rdflib. |
| `scripts/validate_data.py` | agent and check script | The check step: pySHACL with every shape and SHACL-AF, plus the refusals. Needs rdflib and pySHACL. |
| `scripts/build.py` | agent and check script | `merge` (the reasoner's input), `loadable`, `inferred`, `check-serialised` (the step 4 gate), `cypher --output load.cypher` (the load script, written to a file), `graph-type --output graph-type.cypher` (add-on H, written to a file), `data-model --output data-model.json` (add-on L, checked against the Data Modeling MCP server's validators), `manifest [--verify]` and `check-report`. Needs rdflib. |
| `scripts/load_verify.py` | agent, steps 5 and 6 | Loads into a running Neo4j with status checks, reads back `listShapes()` and compares it with the shapes file, runs one fail case per compiled row, the mutant, the round trip and the two hashed loads, and writes the report only when every check passed. Needs rdflib and the neo4j driver. |
| `scripts/copy_graph.py` | agent, add-on I | Copies the verified graph to another Neo4j (Aura included) with plain Cypher, only when its hash equals a passing report's, and compares graph hashes. Needs rdflib and the neo4j driver. |
| `scripts/module_tags.py` | agent, after step 6 or a copy (add-on F) | Tags every node and relationship with the package it came from (the package's version IRI, on the reserved property `graph`), checks the tags, builds the `:Module` graph with each requirement's pin, and writes its SPARQL CONSTRUCT. Needs rdflib and the neo4j driver. |
| `scripts/explore.py` | agent and you, add-on F | The walk from any node across modules, in Neo4j and in a SPARQL store, compared answer for answer (`walk`, `compare` over a project's saved walks and the module map), and the paste-able SPARQL walk. Needs rdflib and the neo4j driver. |
| `queries/` | you, add-on F | Paste-able forms: `walk.cypher` and `walk-visual.cypher` for Neo4j Browser or Bloom, `walk-2-hops.rq` for Fuseki, `module-map.cypher` and `module-map.rq`. `test_explore.py` fails when a generated file drifts from its generator. |
| `scripts/test_explore.py` | this repository's check script | Tests of `module_tags.py` (dependency order, each tag rule, inferred triples, the checks finding an untagged, wrongly tagged, missing or unstated node or edge, the module graph and its CONSTRUCT) and of `explore.py` (Neo4j and store walks agree on a fixture through a fake that emulates the Cypher and rdflib running the real SPARQL; a planted wrong tag makes them differ; the single-query SPARQL walk equals the stepwise one), and that `graph_hash` leaves the tag out. Needs rdflib. |
| `scripts/run_projection.py` | agent, every run after the first | One run configuration (`templates/run-config.json`), for released packages or plain RDF files, drives steps 2 to 6, add-ons F, H, I, J and K, the `rdf-store` skill's round trips and a rebuild from any store, with every check each has; `compare-triples` and `compare-reports` are the rebuild's two checks on their own. See `references/run-config.md`. Needs rdflib, uv and Docker. |
| `scripts/test_run_projection.py` | this repository's check script | Tests of `run_projection.py` with a stand-in for every command: the configuration's paths and refusals, the plan, every script called in order, no password in any command, the ROBOT checksum, the clean-up after a failure, the rebuild's input mapping and its two comparisons, a rebuild that fails on a changed graph hash, the choice of mode, and files mode (graph names, default shapes, the run manifest, a rebuild that keeps each file's graph name). Needs rdflib. |
| `scripts/model_review.py` | agent, after step 6 or a copy | Reviews a loaded graph against the anti-patterns of Neo4j's `neo4j-modeling-skill` 1.0.7 (missing `uri` constraint, generic labels and types, supernodes) and one local heuristic, computing degrees in Cypher, with a per-query timeout. Needs rdflib and the neo4j driver. |
| `scripts/triplestore.py` | agent, add-on J | Loads the same files into any SPARQL 1.1 store through the Graph Store Protocol and checks per-graph and per-predicate counts, and with `--projection-report` the three-way counts against the n10s export. Needs rdflib. |
| `scripts/shell.py` | every script | `q()` and `comment()`: the one helper every printed value goes through (shell-quoted, so a pasted line is safe); a test reads every script's syntax tree to hold that. `error_line()` prints an error as a fixed context and its type, never its text; `Refusal` is a script's own fixed message; `redact()` and `scrub()` keep credentials out of reports and of the scripts' own messages. |
| `scripts/in_graph_shapes.py` | agent and the projection's pipeline | Writes the import-safe shapes, lists each term left out with its reason, and prints an advisory prediction of what n10s will compile; it gates nothing. Needs rdflib. |
| `scripts/test_projection.py` | this repository's check script | Tests: the templates pass; each deliberate break gives exactly its own failure; exceptions cannot waive data errors and fail when stale or empty; the pins are checked numerically against a release folder; the sanitised shapes keep what n10s can run; the serialiser's order, the inferred filter, the fingerprints, the path-independent manifest, the report check and the generated Cypher; `load_verify.py`'s export parsing (multi-line tags included), schema-row filter, hash specification, shuffle and load checks; the command lines exit 0, 1 or 2. Needs rdflib and pySHACL. |
| `scripts/test_engine_gate.py` | this repository's check script | Tests of the engine-readback gate: what the sanitizer leaves out, the value-aware comparison with `listShapes()`, a generated case per row and its path-and-component match, `no case` failing the run, nothing carried between runs, the fail-closed report, the strict `check-serialised`, the `GRAPH TYPE` output, and the copy and triple-store scripts without a server. Needs rdflib and pySHACL. |
| `scripts/test_modeling.py` | this repository's check script | Tests of `model_review.py` (one break per rule, boundaries, the domain filter, the offender limit, the timeout, the atomic report and exit codes, on a fake that emulates its Cypher), of `build.py data-model` (the library and synthetic shapes, isolated mutants with exact problem lists, agreement with the pinned `mcp-neo4j-data-modeling` 0.8.2 package, the `GRAPH TYPE` pinned from before the shared mapping), of the per-query timeout in `copy_graph.py` and `load_verify.py`, and canary tests that no credential reaches output or a report. Needs rdflib, pySHACL and `mcp-neo4j-data-modeling==0.8.2`. |
| `docker/compose.yaml`, `docker/fuseki/Dockerfile` | agent and you, steps 5 and 6 and add-on J | Start Neo4j 2025.06.2 with the checked n10s jar and APOC (profile `neo4j`) and Jena Fuseki 6.2.0 built from its pinned package (profile `fuseki`), bound to localhost; `down -v` removes everything. The tests check their pins against `references/running.md` and `references/add-ons.md`. |
| `SOURCES.md` | you | Every source, with version, date and how to check for updates. |
| `README.md` | you | This file. |

## Common tasks

**Change a rule.** Edit the reference file that holds it; `SKILL.md` only points. Keep each rule in one place, with its reason and a source in `SOURCES.md`.

**A new n10s release.** Run `load_verify.py` on the library templates with a shape for every term in the new version: the `listShapes()` comparison and the fail cases (`references/pipeline.md`, rules 13 and 14) show what changed. Then compare the new `SHACLValidator.java` with `N10S_DATATYPES`, `INVERSE_UNREAD`, the prediction queries and every cited line number in `scripts/in_graph_shapes.py`. Update them, `references/pipeline.md`, rules 13 and 14, the jar checksums in `references/running.md`, rule 2, and the versions in `SOURCES.md`.

## Status

Last updated 2026-10-25.

- **No evals yet.** Write test prompts for three branches before tuning: designing a new ontology for a graph, adding a release to an existing projection, and debugging a silent in-graph SHACL check.
- **Scripts cover every step.** `load_verify.py` loads and verifies against a running container; its database parts are tested only by running it (on 2026-10-23 it passed end to end on the library templates, with extra shapes for every term, and on a private multi-module ontology), and its other parts by `test_projection.py` and `test_engine_gate.py`. A compiled row it cannot build a case for (such as `sh:nodeKind sh:BlankNode`, or a row on a `sh:targetQuery` shape) fails the run until `--manual-cases` gives one. `copy_graph.py` was run against a second local Neo4j and against Aura Free; `triplestore.py` against Apache Jena Fuseki 6.2.0. `model_review.py` ran on 2026-10-25 against a throwaway Neo4j 2025.06.2 holding small hand-made graphs: every query executed, the missing-constraint ERROR appeared and cleared once the constraint existed, and the reciprocal query returned only a real reciprocal pair (one edge between nodes that share labels was not reported). Its supernode rules found no hub there; they are tested on a fake that emulates its queries. It has not yet run on a projected ontology.
- **Option 4b has not been run end to end.** Every tested run used 4a. Recheck rdflib issue #3524 and the RDF 1.2 status every three months.
- **One source of experience.** The 2.3 changes come from one multi-module build. Expect changes after a second one.
