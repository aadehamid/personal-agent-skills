---
name: ontology
description: >-
  Gated method for building a business ontology on the W3C stack (RDF, SKOS, OWL, SHACL, PROV-O, DCAT). Use when designing, extending or reviewing an ontology or knowledge graph; promoting spreadsheet or workbook data into governed triples; modelling roles, RACI or real organizations; writing SHACL shapes or competency questions as SPARQL; versioning, packaging or approving a release; deciding whether to reuse a public ontology; or projecting an ontology into a Neo4j property graph.
---

# Ontology

Build the ontology in **gated** steps. Each step ends on its "Done when" gate; start the next step only when the gate is met. The user, the ontology owner, makes every decision. Your job is the evidence, the options and a recommendation. A decision is real only when the owner has recorded it in their own words, or when it falls inside a delegation the owner recorded and says so. A statement only the owner can make (who consumes the ontology) and the approvals reserved to the owner (`references/release.md`) stay with the owner even under a delegation.

## First, find where the build stands

1. Read the project's decision log, worklog, competency questions and released packages, if they exist.
2. Name the current step and its open gate before you do any work.
3. If the project has its own playbook, its rules win where they conflict with this skill.

## The steps

Keep the order, except Step 8, which runs right after Step 0. Before you work on a step, read the reference it names.

0. **Reference framework and existing ontologies.** Read `references/foundations.md` and `references/external-ontologies.md`.
   Done when: every cited framework ID is verified against the published source, every divergence has a boundary note, and the survey meets the "Done when" in `references/external-ontologies.md`.
1. **Foundations: the ten policies.** Read `references/foundations.md`; for target formats, `references/lpg-projection.md`.
   Done when: all ten policies are recorded with their reasons, and the owner has approved and locked the competency questions.
2. **Identity.** Read `references/identity-taxonomy.md`.
   Done when: every node has a stable HTTP IRI and nothing in the build identifies a node by its label.
3. **SKOS taxonomy.** Read `references/identity-taxonomy.md` and `references/quality.md`.
   Done when: every concept has a label and a definition that meets the quality bar; every concept except the top concepts has exactly one parent; the mechanical checks pass.
4. **Relationships.** Read `references/promotion.md`.
   Done when: every row has a recorded verdict (APPROVE, STAND or HOLD), the conservation ledger reconciles, and the evidence gate passes. The release gate for the first module release (the source-correction backlog) is in `references/promotion.md`; Step 10 checks it.
5. **Organizations and roles.** Read `references/organization.md`.
   Done when: under a recorded scope, every in-scope process has its RACI assignments and none is inferred from the hierarchy; every role string is in the role register; every reference instance cites its source and an as-of date.
6. **Plans and runs.** Read `references/provenance.md`.
   Done when: no definition is typed as an occurrence, and the definition-to-run pattern ships as shapes with an example run that passes, so every run a consumer records can link to its definition.
7. **Integration.** Read `references/integration.md`.
   Done when: every integration gap is linked or parked by a recorded decision.
8. **Scope review.** Read `references/foundations.md`.
   Done when: every candidate area has an in or out call, a reason and a revival trigger.
9. **SHACL.** Read `references/shacl.md`.
   Done when: every module's shapes, the whole-graph gate and the release-package test run with zero unexplained violations, and each guard has a negative test that asserts its violation.
10. **Release and publication.** Read `references/release.md`.
    Done when: every released module is a package that passes `--verify`, the combined catalog lists every release and passes `--verify`, and each release is retrievable at its tag. Before the first module release, every row on the source-correction backlog has a fresh verdict (`references/promotion.md`, the first-release gate). "The catalog resolves" waits for the owner's hosting decision.
11. **Regression.** Read `references/regression.md`.
    Done when: every competency question passes on the released packages, or is partial or waiting with what it waits for, and only a recorded decision parks one.
12. **Property-graph projection (optional).** Read `references/lpg-projection.md`; its design rules apply from Step 1.
    Done when: over every released package, the in-graph SHACL is clean and its mutant fails, the round-trip diff is empty, and two load orders give equal hashes.

## Rules that apply at every step

Each rule lives in the reference named; read it there.

- **Define, don't record:** `references/foundations.md`, policy 2.
- **Cite every fact in the evidence order:** `references/foundations.md`, policy 3.
- **Map, don't import:** `references/external-ontologies.md`.
- **SKOS first:** `references/identity-taxonomy.md`, Step 3, rule 1.
- **Qualified relations:** `references/foundations.md`, conceptual modelling, rule 8.
- **Park, don't smuggle; invent no owner:** `references/foundations.md`, source policies.
- **Every count reconciles:** `references/quality.md`, counts.
- **Released packages never change:** `references/release.md`, rule 10.
- **Before any hand-off:** `references/quality.md`, soundness checks.
