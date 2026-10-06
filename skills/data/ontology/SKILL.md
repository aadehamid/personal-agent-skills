---
name: ontology
description: >-
  Method for building a business ontology from scratch (W3C stack: RDF, SKOS, OWL, SHACL, PROV-O, DCAT): competency questions, identity, SKOS taxonomy, governed relationships, roles and RACI, validation, publication, and projection to a Neo4j labelled property graph. Use when the user is designing, extending, reviewing, or releasing an ontology or knowledge graph; promoting spreadsheet or workbook data into governed triples; deciding whether to reuse a public ontology; writing SHACL shapes or competency questions; or mapping an ontology to a property graph.
---

# Ontology

Build the ontology in **gated** steps. Each step ends on its "done when" gate, and the next step starts only when the gate is met. The user (the ontology owner) makes every decision. Your job is the evidence, the options and a recommendation. A decision is real only when the owner has recorded it in their words.

## First, find where the build stands

Read the project's decision log, worklog and competency questions if they exist. Name the current step and its open gate before you do any work. If the project has its own playbook, its rules win over this skill where they conflict.

## The steps

Do Step 8 right after Step 0. Otherwise keep the order.

0. **Reference framework and existing ontologies.** Adopt the domain's reference framework (for example an industry process classification) as a consistency check, checked against the official published version. Survey public ontologies and code lists that cover parts of the scope, and give each one a treatment: **map** (the default), import, or ignore. Read `references/external-ontologies.md` for this step.
   Done when: every cited framework ID is verified, every divergence has a boundary note, every surveyed source has a treatment and a target step.
1. **Foundations.** Record ten policies: competency questions (owner-approved, locked); data scope; evidence order; URI base; language; versioning; license; modules; consumers; target formats.
   Done when: all ten are recorded with reasons and the competency questions are locked.
2. **Identity.** Keep local IDs as `skos:notation`, derive slugs, mint slugs where none exist. **Slugs are identity. Labels are presentation.**
   Done when: every node has a stable HTTP URI and nothing is identified by label.
3. **SKOS taxonomy.** One concept scheme, `broader`/`narrower`, labels, a definition on every concept. Definitions meet the quality bar in `references/quality.md`.
   Done when: every concept has a definition and a label; every concept except the scheme's top concepts (`skos:topConceptOf`) has exactly one parent; the mechanical checks pass.
4. **Relationships.** One predicate family at a time, one row at a time: identity, direction, definition test, verdict. **Hold** unclear rows for the source author. Keep a **conservation** ledger. Read `references/promotion.md` before this step.
   Done when: every row has a recorded verdict (APPROVE, STAND or HOLD), the ledger reconciles, and the evidence gate passes. A HOLD completes the row for this step: it emits no fact and goes to the source-correction backlog.
   **Release gate (before the first module release).** Release the core module only when every held row has gone back to the source author and has a fresh verdict after the correction. A row may stay held at release only with a recorded reason it is left out of this release. Check the release with a small SHACL slice (Step 9).
5. **Organizations and roles.** `org:Role`; an n-ary `ResponsibilityAssignment` for RACI; party roles on the relationship, not as subclasses; public reference instances of real companies in their own module; control between legal entities as its own relation.
   Done when: every in-scope process has RACI, none inferred from hierarchy, and every reference instance cites a source.
6. **Plans and runs.** Planned inputs and outputs on definitions; P-Plan bridges definitions to `prov:Activity` runs. Consuming systems hold the runs.
   Done when: no definition is typed as an occurrence and the definition-to-run pattern is defined.
7. **Integration.** Bring back parked overlays (value streams, capabilities, measures, data products) one at a time, as references to process nodes. Measures are definitions, never values. Apply the external mappings assigned to this step.
   Done when: every integration gap is linked or parked by decision.
8. **Scope review.** Each candidate area in or out, with a reason and a revival trigger.
   Done when: every candidate has a call, a reason and a trigger.
9. **SHACL.** Slice first (labels, IDs, no provisional namespace, references resolve), then evidence links, controlled values, definition-vs-occurrence. Core before SHACL-SPARQL.
   Done when: zero unexplained violations.
10. **Publication.** DCAT catalog, dataset, distributions; versions, dates, changelog; a manifest with checksums if consumers validate against it. Versioning rules: `references/versioning.md`.
    Done when: the catalog resolves and the release is retrievable.
11. **Regression.** Competency questions as SPARQL, re-run after each module and on every release.
    Done when: every question passes or is parked by decision.
12. **Property-graph projection (optional).** Read `references/lpg-projection.md`. Its design rules apply from Step 1; its pipeline runs here.
    Done when: in-graph SHACL is clean, the round-trip diff is empty, and the determinism hashes match.

## Rules that apply at every step

- **Define, don't record.** The ontology holds concepts, definitions, relationships, and public reference facts with a source and an as-of date. Event records and observed measure values live in the systems that use the ontology.
- **Map, don't import.** Link to external terms with `skos:exactMatch` / `skos:closeMatch`. Import only a small, stable, openly licensed source you would otherwise rebuild.
- **Qualified relations.** A relationship that carries a share, date, level or source becomes a node with its own IRI pointing at both ends (the `org:Membership` pattern). No blank nodes in released data.
- **SKOS first.** A naming hierarchy is a vocabulary, not a class hierarchy. Use OWL classes only where the business guarantees the logical commitment.
- **Cite every fact** in the project's evidence order: the anchor organization's own filings first, then peers, then industry sources.
- **Park** future concepts with a revival trigger. Never smuggle them into definitions.
- **Every count reconciles.** Recompute figures from source files. If they do not reconcile, report the gap and stop.
- Before you hand work to the owner, run the soundness checks in `references/quality.md` on what changed.
