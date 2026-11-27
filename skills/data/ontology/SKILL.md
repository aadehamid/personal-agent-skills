---
name: ontology
description: >-
  Gated method for building a business ontology for any domain on the W3C stack (RDF, SKOS, OWL, SHACL, PROV-O, DCAT). Use when designing, extending or reviewing an ontology or knowledge graph; deciding whether a term is a SKOS concept, an OWL class, a property, a metadata property, a code-list value or a reference individual; promoting spreadsheet or workbook data into governed triples; modelling roles, RACI or real organizations; writing SHACL shapes or competency questions as SPARQL; versioning, packaging or approving a release; or deciding whether to reuse a public ontology.
---

# Ontology

Build the ontology in **gated** steps. Each step ends on its "Done when" gate; start the next step only when the gate is met, or when the gate itself names what may go on while it stays open (an owner's "not yet", `references/governance.md`, rule 3; an offline survey, Step 0). The user, the ontology owner, makes every decision; your job is the evidence, the options and a recommendation. What counts as decided, and what stays with the owner under a delegation: `references/governance.md`, rules 6 and 12.

Scope: from intake to a released, checked ontology; Step 12 hands its property-graph projection to the `ontology-to-lpg` skill. Namespace hosting is the owner's decision (`references/release.md`, rule 20); event records and measure values stay in the consumers' systems (`references/foundations.md`, policy 2); application Cypher and data-model advice for a graph database belong to a graph-database skill.

## First, find where the build stands

1. Read the project's decision log, worklog, requirements file, competency questions and released packages, if they exist.
2. Read the project's playbook (its own written method), if it has one. Its rules win where they conflict with this skill.
3. For a new ontology, sort the inputs and fill `templates/requirements.yaml` before Step 0 (`references/governance.md`, rules 1 to 3). The hierarchy of the business's processes or concepts counts as representative data and is the backbone of Steps 2 and 3, so name it, or its absence, there. For a reference that describes a whole industry rather than one organization, also read `references/industry-reference.md`; to build one from an organization's existing release, `references/generalization.md`.
4. To add a module to an ontology that already has releases, read `references/new-module.md`; it narrows the steps below. For a logical data model exported from a modelling tool, also read `references/logical-model.md`.
5. Name the current step and its open gate before you do any work.

## The steps

Keep the order, except Step 8, which runs right after Step 0; Step 1 may also start while Step 0 waits only on offline registry searches. Before you work on a step, read the reference it names. When the user asks why the method works this way, or wants it explained step by step with an example, read `references/playbook.md`, the narrative guide; the references below hold the rules.

0. **Reference framework and existing ontologies.** Read `references/foundations.md` and `references/external-ontologies.md`; record in `templates/survey-register.md`.
   Done when: every cited framework ID is verified against the publisher's copy (or the framework's absence is a recorded finding), every divergence has a boundary note, and the survey meets the "Done when" in `references/external-ontologies.md`. Offline, a registry search recorded as "not run (offline)" with its date leaves this step open and still lets Step 1 start (`references/external-ontologies.md`, "Offline").
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
   Done when: every module's shapes, the whole-graph gate and the release-package test meet the pass condition in `references/shacl.md`, rule 7, every property has a cardinality (rule 5), and each guard has a negative test that asserts its violation. `scripts/check_shapes.py`, `scripts/check_cardinality.py`, `scripts/check_code_lists.py` and `scripts/check_packages.py` run those gates.
10. **Release and publication.** Read `references/release.md`; when the user has files but no packages yet, run the interview in `references/packaging-walkthrough.md`.
    Done when: every released module is a package that passes `build_package.py verify`, each release meets `references/release.md`, rules 28 to 30, first releases included, the combined catalog (`scripts/build_catalog.py`) lists every release and passes `verify`, and, where the project uses git, each release is retrievable at its tag. Before the first module release, every row on the source-correction backlog has a fresh verdict (`references/promotion.md`, the first-release gate). "The catalog resolves" waits for the owner's hosting decision.
11. **Regression.** Read `references/regression.md`.
    Done when: every competency question passes on the released packages (plus the example graph of a module under `new-module.md`, rule 9), or is partial, parked or waiting by a recorded decision that names what it waits for; `scripts/run_regression.py` runs the questions and checks each status.
12. **Property-graph projection (optional).** Read `references/lpg-projection.md`, then load the `ontology-to-lpg` skill, which holds the method; its design rules apply from Step 1. To hold the release in triple stores and Neo4j or Aura with proof that nothing is lost, follow its `references/multi-store.md`; the triple-store hops (Jena Fuseki, Databricks) use the `rdf-store` skill.
    Done when: every "Done when" gate of `ontology-to-lpg` steps 2 to 6 is met, in that skill's words, over the newest release of every module: its step 2 (`check_projection_rules.py --releases`) proves each module is pinned at its newest version, its step 4 passes `build.py check-serialised`, then `validate_data.py` over `loadable.nt` and `inferred.nt` together, then records the manifest, and its step 6 ends with `build.py check-report` passing and the clean-up line `load_verify.py` printed.

## Rules that apply at every step

Each rule lives in the reference named; read it there.

- **Define, don't record:** `references/foundations.md`, policy 2.
- **Cite every fact in the evidence order:** `references/foundations.md`, policy 3 (for an industry reference, `references/industry-reference.md`, rule 3).
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

Copy from `templates/`: the requirements file, policies, survey register, scope review, parked list, identity table, Turtle and shapes skeletons, definition review, competency questions with their `regression-expected.csv`, decision record, decision package, answers file, package answers, release checklist and check script. Run from `scripts/` (with `uv run --with rdflib --with pyyaml`): `check_requirements.py` on the requirements file and `check_taxonomy.py` on the data files, never on `*-shapes.ttl` (`references/identity-taxonomy.md`, Step 2, rule 5); `check_candidates.py` on candidate terms a model drew from a document (`references/governance.md`, "Candidates from documents"). For Step 4 from a spreadsheet: `build_tabular.py` with `--verify` (`references/promotion.md`, "From a spreadsheet to triples"). For Step 9, with `--with pyshacl` too: `check_shapes.py` (the whole-graph gate), `check_cardinality.py` (every property has a cardinality and no node shape is empty), `check_code_lists.py` (every code-list property shaped against its own list, run over the modules plus the shapes tests' illustration file) and `check_packages.py` (every release package intact and conforming over its closure). For Step 10: `build_package.py` (writes, verifies and tags one module's release package from an answers file), `build_catalog.py` (writes and verifies the combined catalog of every package), `check_changelogs.py` (every release's changelog states its known gaps), and `build_docs.py` with `check_docs.py` (each released package's documentation pages, built with Widoco and checked against its manifest). For Step 11: `run_regression.py`. Each script's docstring gives its command line, and each exits non-zero on any failure.
