# ontology

A skill that makes an agent build a business ontology the way the enterprise-performance-model ontology was built: in gated steps, with every decision left to you, and with rules that keep promoted data from being corrupted. It also covers reusing public ontologies and projecting the result into a Neo4j property graph.

This README is for people. Agents do not read it. They read `SKILL.md` and the files it points to.

## Files

| Path | Read by | What it does |
|---|---|---|
| `SKILL.md` | agent, every run | The skill itself. The frontmatter `description` decides when it triggers. The body lists Steps 0 to 12, each with its "Done when" gate and the reference file to read, then the rules that apply at every step. |
| `references/foundations.md` | agent, Steps 0, 1 and 8 | Conceptual-modelling foundations, aligning a reference framework, the ten policies, source policies, and the scope review. |
| `references/identity-taxonomy.md` | agent, Steps 2 and 3 | Rules for stable IRIs and identity, and for building the SKOS concept scheme. |
| `references/promotion.md` | agent, Step 4 | The eleven rules for promoting provisional source data into governed triples, the predicate review method, the release gate and source-correction backlog, building the first release, and example predicate definitions. |
| `references/organization.md` | agent, Step 5 | Roles and the role register, RACI assignments, party roles as dated nodes, and real companies in a reference module. |
| `references/provenance.md` | agent, Step 6 | Definitions against runs: planned inputs and outputs, the PROV-O and P-Plan link from a run to its definition, and the shapes a consumer's run must meet. |
| `references/integration.md` | agent, Step 7 | Bringing back overlays: measures, market series, data products, value streams, systems, placement kinds, source tiers and consumer rules. |
| `references/shacl.md` | agent, Step 9 | What to shape and in what order, how to test shapes, and how to check a SHACL feature in a target engine. |
| `references/release.md` | agent, Step 10 and any release | Change classification, deprecation, approvals, the release package and its builder, candidates and the cut, the combined catalog, and the ontology header. |
| `references/regression.md` | agent, Step 11 | Tracing elements to competency questions, writing them as SPARQL, question statuses, and when the suite runs. |
| `references/lpg-projection.md` | agent, Step 12 and Step 1's target formats | The design rules (Rule 4 option 4a, qualified-relation nodes) and the check, reason, serialise, load, verify pipeline, with what running it taught. |
| `references/external-ontologies.md` | agent, Step 0 or when asked about existing ontologies | Where to look for public ontologies and code lists, how to assess them, the map, import or ignore choice, and rules for applying mappings. |
| `references/quality.md` | agent, Step 3 onward and before any hand-off | The ten-point definition quality bar and the soundness checks on every change. |
| `SOURCES.md` | you | What the skill was built from, the versions used, and how to check for updates. |
| `README.md` | you | This file. |

## Common tasks

**Change a rule.** Edit `SKILL.md` or the reference file that holds the rule. Keep each rule in one place. If the change came from the EPM build, update the EPM playbook in the same week so the two stay in step.

**Check the sources for updates.** Follow "How to check for updates" in `SOURCES.md`.

## Status

Last updated 2026-10-05 (first version).

- **No evals yet.** Write test prompts for three branches before tuning: starting a new ontology, promoting a workbook into triples, and planning a Neo4j projection. Then tune the description with skill-creator.
- **Rule 4 option 4a is a toolchain choice.** The skill uses qualified-relation nodes (the guideline's option 4a), not RDF 1.2 reifiers (4b), because rdflib and pySHACL do not support RDF 1.2 yet. Recheck rdflib issue #3524 and the RDF 1.2 W3C status every few months.
- **The LPG guideline master may change.** If the guideline in enterprise-people-graph is revised after v2.1 (for example to fix the pipeline defects in its issue #2), update `references/lpg-projection.md` and `SOURCES.md`.
- **Only one build so far.** Every rule comes from one ontology build. Expect changes after the people-graph build uses the skill.

## Sources

See `SOURCES.md`.
