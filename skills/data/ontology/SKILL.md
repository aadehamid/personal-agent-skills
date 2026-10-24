---
name: ontology
description: >-
  Gated method for building a business ontology for any domain on the W3C stack (RDF, SKOS, OWL, SHACL, PROV-O, DCAT). Use when designing, extending or reviewing an ontology or knowledge graph; deciding whether a term is a SKOS concept, an OWL class, a property, a metadata property, a code-list value or a reference individual; promoting spreadsheet or workbook data into governed triples; modelling roles, RACI or real organizations; writing SHACL shapes or competency questions as SPARQL; versioning, packaging or approving a release; or deciding whether to reuse a public ontology.
---

# Ontology

Build the ontology in **gated** steps. Each step ends on its "Done when" gate; start the next step only when the gate is met. The user, the ontology owner, makes every decision; your job is the evidence, the options and a recommendation. What counts as decided, and what stays with the owner under a delegation: `references/governance.md`, rules 6 and 12.

Scope: from intake to a released, checked ontology; Step 12 hands its property-graph projection to the `ontology-to-lpg` skill. Namespace hosting is the owner's decision (`references/release.md`, rule 20); event records and measure values stay in the consumers' systems (`references/foundations.md`, policy 2); application Cypher and data-model advice for a graph database belong to a graph-database skill.

## First, find where the build stands

1. Read the project's decision log, worklog, requirements file, competency questions and released packages, if they exist.
2. Read the project's playbook (its own written method), if it has one. Its rules win where they conflict with this skill.
3. For a new ontology, sort the inputs and fill `templates/requirements.yaml` before Step 0 (`references/governance.md`, rules 1 to 3).
4. Name the current step and its open gate before you do any work.

## The steps

Keep the order, except Step 8, which runs right after Step 0. Before you work on a step, read the reference it names.

0. **Reference framework and existing ontologies.** Read `references/foundations.md` and `references/external-ontologies.md`; record in `templates/survey-register.md`.
   Done when: every cited framework ID is verified against the publisher's copy (or the framework's absence is a recorded finding), every divergence has a boundary note, and the survey meets the "Done when" in `references/external-ontologies.md`.
1. **Foundations: the ten policies.** Read `references/foundations.md`; for target formats, `references/lpg-projection.md`. Record in `templates/policies.md`.
   Done when: all ten policies are recorded with their reasons and none is marked ASSUMED, and the owner has approved and locked the competency questions. If policy 10 says the ontology will be projected, it also records the Rule 4 option and its reason, and `ontology-to-lpg`'s design rules have been read.
2. **Identity.** Read `references/identity-taxonomy.md`; record in `templates/identity-table.md`.
   Done when: every node has an HTTP IRI under the base the URI policy records, every node has a kind, and nothing in the build identifies a node by its label.
3. **Taxonomy, classes and properties.** Read `references/domain-model.md`, `references/identity-taxonomy.md` and `references/quality.md`; start from `templates/ontology-skeleton.ttl` and `templates/shapes-skeleton.ttl`.
   Done when: every concept has a label and a definition that meets the quality bar for its kind; every concept except the top concepts has exactly one parent; every class and property has a label and a definition, and every object and datatype property one domain, one range and a cardinality shape (`references/domain-model.md`, rules 5 to 8); `scripts/check_taxonomy.py` passes; the review is recorded in `templates/definition-review.md`.
4. **Relationships.** Read `references/promotion.md`.
   Done when: every row has a recorded verdict (APPROVE, STAND or HOLD), the conservation ledger reconciles, and the evidence gate in `references/promotion.md` passes. The release gate for the first module release (the source-correction backlog) is in `references/promotion.md`; Step 10 checks it.
5. **Organizations and roles.** Read `references/organization.md`.
   Done when: under a recorded scope, every in-scope process has its RACI assignments and none is inferred from the hierarchy; every role string is in the role register; every reference instance cites its source and an as-of date.
6. **Plans and runs.** Read `references/provenance.md`.
   Done when: no definition is typed as an occurrence, and the definition-to-run pattern ships as shapes with an example run that passes, so every run a consumer records can link to its definition.
7. **Integration.** Read `references/integration.md`.
   Done when: every integration gap is linked or parked by a recorded decision.
8. **Scope review.** Read `references/foundations.md`; record in `templates/scope-review.md`.
   Done when: every candidate area has an in or out call and a reason, and every out call has a boundary note and a revival trigger.
9. **SHACL.** Read `references/shacl.md`.
   Done when: every module's shapes, the whole-graph gate and the release-package test meet the pass condition in `references/shacl.md`, rule 7, and each guard has a negative test that asserts its violation.
10. **Release and publication.** Read `references/release.md`.
    Done when: every released module is a package that passes `--verify`, the combined catalog lists every release and passes `--verify`, and each release is retrievable at its tag. Before the first module release, every row on the source-correction backlog has a fresh verdict (`references/promotion.md`, the first-release gate). "The catalog resolves" waits for the owner's hosting decision.
11. **Regression.** Read `references/regression.md`.
    Done when: every competency question passes on the released packages, or is partial, parked or waiting by a recorded decision that names what it waits for.
12. **Property-graph projection (optional).** Read `references/lpg-projection.md`, then load the `ontology-to-lpg` skill, which holds the method; its design rules apply from Step 1. To hold the release in triple stores and Neo4j or Aura with proof that nothing is lost, follow its `references/multi-store.md`.
    Done when: `ontology-to-lpg`'s steps 4 and 6 are done over every released package: its `build.py check-serialised` passes on `loadable.nt` and `inferred.nt`, its `build.py check-report` passes on the report (written only by a run whose every check passed, every compiled shape row tested), and the container has been removed with `docker rm -f -v <container>` or `docker compose ... down -v`.

## Rules that apply at every step

Each rule lives in the reference named; read it there.

- **Define, don't record:** `references/foundations.md`, policy 2.
- **Cite every fact in the evidence order:** `references/foundations.md`, policy 3.
- **One kind per term:** `references/domain-model.md`, rule 1.
- **Map, don't import:** `references/external-ontologies.md`.
- **Qualified relations:** `references/foundations.md`, conceptual modelling, rule 8.
- **Park, don't smuggle; invent no owner:** `references/foundations.md`, source policies.
- **Not yet answered means ASSUMED, marked, and reversible:** `references/governance.md`, rule 3.
- **Every count reconciles:** `references/quality.md`, counts.
- **Released packages never change:** `references/release.md`, rule 10.
- **Before any hand-off:** `references/quality.md`, soundness checks.
- **Governance:** read `references/governance.md` before you start a new ontology, record a decision, work under a delegation, set up checks, review a change, release or publish. It says what to do with and without the `way-of-working` skill.

## Templates and scripts

Copy from `templates/`: the requirements file, policies, survey register, scope review, parked list, identity table, Turtle and shapes skeletons, definition review, competency questions, decision record, decision package, answers file, release checklist and check script. Run from `scripts/` (with `uv run --with rdflib --with pyyaml`): `check_requirements.py` on the requirements file and `check_taxonomy.py` on the data files, never on `*-shapes.ttl` (`references/identity-taxonomy.md`, Step 2, rule 5); both exit non-zero on any failure.
