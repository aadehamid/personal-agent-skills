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

5. `scripts/build.py` writes the reasoner's input, the N-Triples files, the load script and the manifest; `scripts/in_graph_shapes.py` writes the shapes Neo4j can run; `scripts/load_verify.py` loads, verifies and writes the report. Reason, load and verify run on a workstation with Java and Docker; `references/running.md` gives the jar checksums, the `docker run` line and what CI runs instead.

The `ontology` skill builds the ontology and hands over to this one at its Step 12. Each skill works without the other.

## Files

| Path | Read by | What it does |
|---|---|---|
| `SKILL.md` | agent, every run | The index: scope, where to start, the seven steps with their gates and references, the rules for every step, the templates and scripts. Its `description` decides when the skill triggers. |
| `references/design-rules.md` | agent, step 1 | What the projection keeps, the mental model, the five design rules (with options 4a and 4b), the OWL profile and the XSD to Cypher table. |
| `references/inputs.md` | agent, step 2 | Released packages and their pins, shapes, namespaces and prefixes, qualified-relation classes, and the release-exceptions list. |
| `references/pipeline.md` | agent, steps 3 to 6 | Check, reason, serialise (with the 4b flatten), load with n10s, the shapes that run in the graph, and verify. |
| `references/running.md` | agent, step 7 | Where each step runs, pins and checksums, the manifest and the report, clean-up, and scale. |
| `references/add-ons.md` | agent, when a consumer asks for more, or in review | Add-ons A to G and the anti-patterns. |
| `references/learning-path.md` | agent, when you ask what to learn | Twelve W3C and Neo4j skills in priority order, with an exercise each. |
| `references/versions.md` | agent, when a project pins an older version | What versions 2, 2.1, 2.2 and 2.3 changed. |
| `templates/projection-config.json` | agent, step 2 | The configuration `check_projection_rules.py`, `validate_data.py` and `build.py` read: the Rule 4 option and its reason, own namespaces, prefixes, qualified relations, package pins, release exceptions, tool versions. |
| `templates/projection-report.json` | agent, step 6 | The fields the verify step's report holds. Empty, so `build.py check-report` fails on it until a run fills it. |
| `templates/library-module.ttl` | agent and tests | A small released module (works, books, people, copies, authorships) that passes every check, with one subclass axiom so the reasoner infers one type. |
| `templates/library-shapes.ttl` | agent and tests | Its shapes, including constraints n10s cannot run, so the subset script has something to drop. |
| `scripts/check_projection_rules.py` | agent and check script | Rules 1, 2, 3, 4a and 5, the round-trip refusals, the package pins and the release exceptions. Needs rdflib. |
| `scripts/validate_data.py` | agent and check script | The check step: pySHACL with every shape and SHACL-AF, plus the refusals. Needs rdflib and pySHACL. |
| `scripts/build.py` | agent and check script | `merge` (the reasoner's input), `loadable`, `inferred`, `check-serialised` (the step 4 gate), `cypher` (the load script), `manifest [--verify]` and `check-report`. Needs rdflib. |
| `scripts/load_verify.py` | agent, steps 5 and 6 | Loads into a running Neo4j with status checks, runs the generated fail cases, the mutant, the round trip and the two hashed loads, and writes the report. Needs rdflib and the neo4j driver. |
| `scripts/in_graph_shapes.py` | agent and the projection's pipeline | Writes the in-graph subset of the shapes and lists each drop with its reason. Needs rdflib. |
| `scripts/test_projection.py` | this repository's check script | Tests: the templates pass; each deliberate break gives exactly its own failure; exceptions cannot waive data errors and fail when stale or empty; the pins are checked numerically against a release folder; each drop-list entry of the subset is exercised and the subset still catches a mutant; the serialiser's order, the inferred filter, the fingerprints, the path-independent manifest, the report check and the generated Cypher; `load_verify.py`'s export parsing (multi-line tags included), schema-row filter, hash specification, shuffle, fail-case generation and load checks; the command lines exit 0, 1 or 2. Needs rdflib and pySHACL. |
| `SOURCES.md` | you | Every source, with version, date and how to check for updates. |
| `README.md` | you | This file. |

## Common tasks

**Change a rule.** Edit the reference file that holds it; `SKILL.md` only points. Keep each rule in one place, with its reason and a source in `SOURCES.md`.

**A new n10s release.** Re-run the pass and fail tests of `references/pipeline.md`, rule 14, in the new version, then compare the new `SHACLValidator.java` with the copies in `scripts/in_graph_shapes.py`: the three query constants (`PROPERTY_ROWS`, `CLOSED_ROWS`, `NODE_CLASS_ROWS`), `PROPERTY_TERMS`, `N10S_DATATYPES` and every cited line number, and the Java lines pinned in `scripts/test_projection.py` (`JAVA_PROP_LINES` and the two beside it). Update them, `references/pipeline.md`, rules 13 and 14, the jar checksums in `references/running.md`, rule 2, and the versions in `SOURCES.md`.

## Status

Last updated 2026-10-23.

- **No evals yet.** Write test prompts for three branches before tuning: designing a new ontology for a graph, adding a release to an existing projection, and debugging a silent in-graph SHACL check.
- **Scripts cover every step.** `load_verify.py` loads and verifies against a running container; its database parts are tested only by running it (it passed end to end on the library templates on 2026-10-23), and its other parts by `test_projection.py`. It generates a fail case for every kind in `EXPECTED` in `load_verify.py` except a node-level `sh:class` (`nodeClass`); any other kind left in the graph needs a case written by hand.
- **Option 4b has not been run end to end.** Every tested run used 4a. Recheck rdflib issue #3524 and the RDF 1.2 status every three months.
- **One source of experience.** The 2.3 changes come from one multi-module build. Expect changes after a second one.
