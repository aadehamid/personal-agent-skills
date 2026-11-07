# Ontology visualization

This skill helps an agent build and maintain an ontology viewer in any domain.
It focuses on whether readers can understand terms, distinguish layers and
follow connections within and between modules. It covers both new viewers and
updates after ontology releases.

Ask the agent to use `ontology-visualization` with your source release and the
questions readers need to answer. The skill helps it choose views, preserve RDF
meaning, test the interface and prepare a delivery artifact. It supports offline
and hosted viewers without prescribing one renderer.

The method keeps ontology changes separate from presentation changes. A guide
or layout update can use the same ontology release without changing packages or
reloading stores. Publication follows the consuming project's authorization and
review requirements.

## Files

| Path | Reader | Purpose |
|---|---|---|
| `SKILL.md` | Agent | Entry point and routing for a new viewer or an update. |
| `references/playbook.md` | Agent and person | The method from reader tasks through construction, validation, delivery and later releases. |
| `assets/visualization-brief.md` | Agent and person | A project brief to record scope, source and acceptance evidence. |
| `agents/openai.yaml` | Skill host | Display metadata and a suggested invocation. |
| `SOURCES.md` | Person and maintainer | Sources, provenance, limitations and update instructions. |
| `evals/README.md` | Evaluator | Behavioral tasks and assessment criteria. |
| `evals/results-2026-11-07.md` | Person and maintainer | Observed results, corrections and coverage limits. |
| `evals/fixtures/v1/catalog.ttl` | Evaluator and test tools | Catalog classes, a taxonomy, multilingual definitions and a constraint. |
| `evals/fixtures/v1/lending.ttl` | Evaluator and test tools | Lending terms, a cross-module range, a second constraint and a lexical literal. |
| `README.md` | Person | This overview and current status. |

## Status

The three initial behavioral tasks passed on neutral Catalog and Lending fixtures on
2026-11-07: a first build, an ontology release update and an additive
documentation update. The trials checked source fidelity, existing links,
phone reading paths and the extracted offline artifacts. Browser coverage was
Chrome only; these small fixtures do not establish large-graph usability.
A focused follow-up corrected clipboard and audit-report defects in the
evaluation output, and a release-delta check that accepted invented entries.
Independent review then found anonymous-node identity and method-version
coverage gaps. A further release-update trial passed after the playbook changed;
it checks complete deltas and historical anonymous links when a new constraint
changes canonical IDs.
See the evaluation results for method hashes and coverage, and the pull request for repository
checks and review. No renderer or hosting service is installed by the skill.
