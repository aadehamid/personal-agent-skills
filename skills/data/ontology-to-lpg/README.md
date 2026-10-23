# ontology-to-lpg

An agent skill for projecting an ontology built on the W3C stack (RDF, RDFS, OWL, SKOS, SHACL) into a Neo4j labelled property graph. The agent works in seven gated steps: design rules, inputs, check, reason and serialise, load, verify, and running it in a repository. The result is a graph that holds exactly the triples that passed every shape, and loads the same way every time. The Turtle release stays the master copy.

The skill is version 2.3 of the Ontology-to-LPG Conversion Playbook. Version 2.2 lived in the enterprise-people-graph repository; on 2026-10-23 the owner decided to move the guideline into this skill, and the repositories that kept a copy now point here. Version 2.3 adds what a projection of a multi-module enterprise ontology learned in October 2026, written in neutral terms with a library example. `references/versions.md` lists the changes.

This README is for people. Agents read `SKILL.md` and the files it points to.

## How to use it

1. Install the skill where your agent finds skills, and ask the agent to project your ontology into Neo4j, or to check whether it is ready for a projection.
2. The agent starts at the design rules. If the ontology is not released yet, it applies them before the first release. If it is, it lists each gap as a release exception with the release that will close it.
3. It fills a copy of `templates/projection-config.json` with you: your namespaces and prefixes, your released packages, your qualified-relation classes.
4. Run the checks the agent runs:

   ```sh
   uv run --with rdflib python3 scripts/check_projection_rules.py --config projection-config.json \
     --shapes <shapes.ttl> --releases <release folder> <module.ttl>
   uv run --with rdflib python3 scripts/in_graph_shapes.py --output shapes-in-graph.ttl <shapes.ttl>
   ```

   The checker prints one line per failure and exits 1, or prints a pass line and exits 0. The second script writes the shapes Neo4j can run and lists what it dropped.

5. Reason, load and verify run on a workstation with Java and Docker; `references/running.md` says what CI runs instead.

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
| `templates/projection-config.json` | agent, step 2 | The configuration both scripts read: Rule 4 choice, own namespaces, prefixes, qualified relations, package pins, release exceptions. |
| `templates/library-module.ttl` | agent and tests | A small released module (works, people, copies, authorships) that passes every check. |
| `templates/library-shapes.ttl` | agent and tests | Its shapes, including constraints n10s cannot run, so the subset script has something to drop. |
| `scripts/check_projection_rules.py` | agent and check script | Rules 1, 2, 3, 4a and 5, the package pins and the release exceptions. Needs rdflib. |
| `scripts/in_graph_shapes.py` | agent and the projection's pipeline | Writes the in-graph subset of the shapes and lists each drop with its reason. Needs rdflib. |
| `scripts/test_projection.py` | this repository's check script | Tests: the templates pass; each deliberate break fails with only its own check and message; stale and empty exceptions fail; the pins are checked against a release folder; the subset drops and keeps the right constraints and still catches a mutant; the command lines exit 0, 1 or 2. Needs rdflib and pySHACL. |
| `SOURCES.md` | you | Every source, with version, date and how to check for updates. |
| `README.md` | you | This file. |

## Common tasks

**Change a rule.** Edit the reference file that holds it; `SKILL.md` only points. Keep each rule in one place, with its reason and a source in `SOURCES.md`.

**A new n10s release.** Re-run the pass and fail tests of `references/pipeline.md`, rule 14, in the new version, then update the drop list in `scripts/in_graph_shapes.py` and the versions in `SOURCES.md`.

## Status

Last updated 2026-10-23.

- **No evals yet.** Write test prompts for three branches before tuning: designing a new ontology for a graph, adding a release to an existing projection, and debugging a silent in-graph SHACL check.
- **Scripts cover the design and inputs checks and the in-graph subset.** The reason, serialise, load and verify steps are described; each project writes its own pipeline, as the build behind version 2.3 did.
- **Option 4b has not been run end to end.** Every tested run used 4a. Recheck rdflib issue #3524 and the RDF 1.2 status every three months.
- **One source of experience.** The 2.3 changes come from one multi-module build. Expect changes after a second one.
