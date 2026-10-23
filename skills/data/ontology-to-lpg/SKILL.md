---
name: ontology-to-lpg
description: >-
  Gated method for projecting an ontology built on the W3C stack (RDF, RDFS, OWL, SKOS, SHACL) into a Neo4j labelled property graph. Use when loading an OWL, RDF or SKOS ontology into Neo4j or another property graph; configuring or debugging n10s (neosemantics); deciding whether a term becomes a node, a relationship or a property; modelling a relationship that carries its own properties (qualified relations or RDF 1.2 reifiers); or validating a projection with SHACL in the graph, a round-trip diff or a determinism check.
---

# Ontology to labelled property graph

Project the ontology in **gated** steps. Each step ends on its "Done when" gate; start the next step only when the gate is met. The Turtle release is the master copy: the graph is a projection that can be rebuilt from it at any time.

Scope: from design rules to a verified, repeatable graph. Building the ontology itself (identity, taxonomy, shapes, releases) belongs to the `ontology` skill, which hands over at its Step 12; application Cypher and graph data-modelling advice belong to a graph-database skill.

## First, find where the projection stands

1. Read the project's projection configuration, manifest and last report, and the decision that records its Rule 4 choice, if they exist.
2. Read the project's own projection method, if it has one. Its rules win where they conflict with this skill. If it pins an earlier version of this method, read `references/versions.md`.
3. Name the current step and its open gate before you do any work.

## The steps

Before you work on a step, read the reference it names.

1. **Design rules.** Read `references/design-rules.md`. Apply it before the ontology's first release.
   Done when: the projection policy records the Rule 4 choice (4a or 4b) and its reason, and `scripts/check_projection_rules.py` reports no failure except a listed release exception.
2. **Inputs.** Read `references/inputs.md`; copy `templates/projection-config.json`.
   Done when: every released module is pinned at its newest version and `check_projection_rules.py --releases <folder>` passes; every namespace you own, and every standard namespace the data uses, has exactly one prefix; every qualified-relation class is registered with its ends; every rule gap is listed with its fix, and no listed gap is stale.
3. **Check.** Read `references/pipeline.md`, rules 1 to 3.
   Done when: the rule checker and pySHACL with every shape file (SHACL-AF on where a shape uses SPARQL) report nothing beyond listed exceptions, and no value fails the round-trip refusals.
4. **Reason and serialise.** Read `references/pipeline.md`, rules 4 to 7.
   Done when: `loadable.nt` and `inferred.nt` are sorted and de-duplicated; `inferred.nt` holds only IRI-to-IRI `rdf:type` and `rdfs:subClassOf` triples whose object is outside the OWL and RDFS namespaces; the shapes pass over both files together; the input fingerprint is recorded.
5. **Load.** Read `references/pipeline.md`, rules 8 to 14; generate the in-graph shapes with `scripts/in_graph_shapes.py`.
   Done when: every statement is generated; n10s runs in SHORTEN mode with the fixed prefixes in their order; every import ends with `terminationStatus` `OK`; the dropped constraints are recorded with their reasons; each constraint kind left in the graph has a pass and a fail test in the target engine.
6. **Verify.** Read `references/pipeline.md`, rules 15 to 17.
   Done when: the report shows zero violations in the graph and at least one on the deliberate mutant, zero triples lost and zero added in the round trip, and equal hashes for the sorted and shuffled loads.
7. **Run it in the repository.** Read `references/running.md`.
   Done when: CI runs check and serialise and fails on a stale manifest or report; every tool version and jar checksum is pinned; `inferred.nt`, the manifest and the report are committed together from one run; no container or temporary password is left behind.

For add-ons a consumer asks for (superclass labels, language keys, exact decimals, units, provenance, business keys) and the anti-patterns to review against, read `references/add-ons.md`. When the user asks what to learn first, or for exercises, read `references/learning-path.md`.

## Rules that apply at every step

- **The Turtle release is the master copy;** never edit the graph to fix the ontology.
- **Generate every statement** (configuration, prefixes, multivalued list, in-graph shapes) from the ontology and the configuration: `references/pipeline.md`, rule 8.
- **Silence is not a pass:** a check counts only once it has been seen to fail (`references/pipeline.md`, rules 14 and 15).
- **A rule gap is listed or fixed, never ignored:** `references/inputs.md`, rule 5.
- **Pin and fingerprint everything a result depends on:** `references/running.md`, rules 2 and 3.

## Templates and scripts

Copy from `templates/`: `projection-config.json` (the configuration), and `library-module.ttl` with `library-shapes.ttl` (a small module that passes every check, as a starting fixture). Run from `scripts/` with `uv run --with rdflib`: `check_projection_rules.py --config <config> --shapes <shapes>... [--releases <folder>] <data>...` and `in_graph_shapes.py --output <file> <shapes>...`. The checker exits 0 on a pass, 1 with one line per failure, 2 on bad input.
