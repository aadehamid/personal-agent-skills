# ontology

An agent skill for building a business ontology in any domain, on the W3C stack (RDF, SKOS, OWL, SHACL, PROV-O, DCAT). The agent works in thirteen gated steps, from intake and competency questions to a released, checked package and an optional Neo4j property-graph projection. You, the ontology owner, make every decision; the agent brings the evidence, the options and a recommendation, and records your answers word for word.

The method comes from a downstream refining enterprise's process ontology, built privately and rewritten here in neutral terms. The examples use a public library's lending and, in two places, Marathon Petroleum's public SEC filings.

This README is for people. Agents read `SKILL.md` and the files it points to.

## How to use it

1. Install the skill where your agent finds skills, and ask the agent to start an ontology for your domain.
2. The agent fills `templates/requirements.yaml` with you: purpose, users, scope, draft competency questions, and the inputs you have. Where an input is missing, it stops and asks.
3. It then works through Steps 0 to 12 in `SKILL.md`. Each step names the reference to read, the template to fill and the "Done when" gate. Expect a question from the agent at every decision; answer "not yet" when you are unsure, and the agent marks the item as assumed and keeps it reversible.
4. From Step 3, run the checks the agent runs:

   ```sh
   uv run --with pyyaml python3 scripts/check_requirements.py requirements.yaml
   uv run --with rdflib python3 scripts/check_taxonomy.py <your module>.ttl
   ```

   Each prints one line per failure and exits 1, or prints a pass line and exits 0.

The skill works on its own. If the `way-of-working` skill is installed too, the agent follows it for decision records, the pull-request loop, the check script's design and a shared tool for figures; `references/governance.md` says what changes without it.

## Files

| Path | Read by | What it does |
|---|---|---|
| `SKILL.md` | agent, every run | The index: the scope line, where to start, Steps 0 to 12 with their gates and references, the rules that apply at every step, and the templates and scripts. Its `description` decides when the skill triggers. |
| `references/foundations.md` | agent, Steps 0, 1 and 8 | Conceptual modelling, aligning a reference framework, the ten policies, source policies, and the scope review. |
| `references/identity-taxonomy.md` | agent, Steps 2 and 3 | Stable IRIs and slugs, the SKOS concept scheme, code lists, and the register that maps source strings to code values. |
| `references/domain-model.md` | agent, Step 3 | When a term is a concept, a class, a property, a metadata (annotation) property, a code-list value or a reference individual, and how to write classes and properties (definition; for object and datatype properties, domain, range and cardinality shape; for annotation properties, label and definition only). |
| `references/quality.md` | agent, Step 3 onward and before any hand-off | The definition quality bar, with a form for each kind of term, and the soundness checks on every change. |
| `references/promotion.md` | agent, Step 4 | Promoting provisional source data into governed triples: eleven rules, the predicate review, the source-correction backlog, the first release, example predicate definitions. |
| `references/organization.md` | agent, Step 5 | Roles and the role register, RACI assignments, party roles as dated nodes, and real organizations in a reference module. |
| `references/provenance.md` | agent, Step 6 | Definitions against runs: PROV-O and P-Plan, and the shapes a consumer's run must meet. |
| `references/integration.md` | agent, Step 7 | Bringing back overlays: measures, market series, data products, value streams, systems, placement kinds, source tiers and consumer rules. |
| `references/shacl.md` | agent, Step 9 | What to shape and in what order, how to test shapes, and how to check a SHACL feature in a target engine. |
| `references/release.md` | agent, Step 10 and any release | Change classification, deprecation, approvals, release packages, candidates, the catalog and the ontology header. |
| `references/regression.md` | agent, Step 11 | Tracing elements to competency questions, writing them as SPARQL, question statuses, and when the suite runs. |
| `references/lpg-projection.md` | agent, Step 12 and Step 1's target formats | Design rules for a property-graph projection and the check, reason, serialise, load and verify pipeline. |
| `references/external-ontologies.md` | agent, Step 0 or when asked about existing ontologies | Where to find public ontologies and code lists, how to assess them, and the map, import or ignore choice. |
| `references/governance.md` | agent, before a new ontology, a decision, a delegation, setting up checks, a review, a release or publication | Intake and requirements, "not yet" answers, decision records, delegation, checks, generated content, review, privacy, and claims; with and without `way-of-working`. |
| `templates/requirements.yaml` | agent, before Step 0 | The intake and requirements file, with its schema in the header. |
| `templates/survey-register.md` | agent, Step 0 | The reference framework's verified elements, boundary notes, and the survey of public ontologies. |
| `templates/scope-review.md` | agent, Step 8 | In or out call per candidate area, with boundary notes and revival triggers. |
| `templates/policies.md` | agent, Step 1 | The ten policies with choice, reason and deciding record. |
| `templates/parked-list.md` | agent, from Step 1 | Parked future concepts with their questions, "done when" and revival trigger. |
| `templates/competency-questions.md` | agent, Step 1 and Step 11 | The regression table: tested parts, status, what each waits for, the elements it needs, and what was left out. |
| `templates/identity-table.md` | agent, Step 2 | Each node's IRI, kind, notation, slug source and renames, and the source-string register. |
| `templates/ontology-skeleton.ttl` | agent, Step 3 | A module header, a concept scheme, a code-list scheme, three classes, four object and datatype properties and one annotation property, for a library. Passes `check_taxonomy.py`. |
| `templates/shapes-skeleton.ttl` | agent, Step 3 | The SHACL node and property shapes for the skeleton's loan class and its concepts, with cardinalities. |
| `templates/definition-review.md` | agent, Step 3 | The quality-bar review sheet, one row per term. |
| `templates/decision-record.md` | agent, when recording a decision | A numbered record: the question and recommendation quoted, context with the agent's plan, the owner's decision (their words only), alternatives, the owner's recorded words, evidence. |
| `templates/decision-package.md` | agent, when asking the owner a question | A question with context, options (recommendation first), what each changes, and an answer box. |
| `templates/answers-file.md` | agent, when saving the owner's answers | The owner's words verbatim, with the agent's questions inside comments. |
| `templates/release-checklist.md` | agent, before each release | The release gate as a checklist, each item pointing to its rule. |
| `templates/check.sh` | agent, when setting up a repository | A check-script skeleton with the four-snapshot no-writes guard; it fails until every TODO is replaced. |
| `scripts/check_requirements.py` | agent and check script | Checks the requirements file's structure (fields, types, allowed values, ids, record rules) and its scope conflicts; a person still reviews what the text means. Needs PyYAML. |
| `scripts/check_taxonomy.py` | agent and check script | The Step 2 and 3 mechanical checks on data Turtle files (not shapes files). Needs rdflib. |
| `scripts/test_checks.py` | this repository's check script | Tests: the templates pass; each deliberate break fails with only its own check and message; both command lines exit 0, 1 or 2 as documented; the shapes skeleton works under pySHACL; and `templates/check.sh`, copied into a fresh repository, fails while TODOs remain, catches a write, and checks data files but not shapes files. Needs rdflib, PyYAML and pySHACL. |
| `SOURCES.md` | you | Every source the skill draws on, what it took, versions, how to check for updates, and which outside proposals it adopted. |
| `README.md` | you | This file. |

## Common tasks

**Change a rule.** Edit the reference file that holds it; `SKILL.md` only points. Keep each rule in one place, with a one-sentence reason and a source.

**Check the sources for updates.** Follow "How to check for updates" in each section of `SOURCES.md`.

## Status

Last updated 2026-10-22.

- **No evals yet.** One walk-through on a library's lending process (Steps 0, 8, 1, 2 and 3) shaped this version. Write test prompts for three branches before tuning: starting a new ontology, promoting a workbook into triples, and planning a Neo4j projection.
- **Scripts cover Steps 0 to 3 only.** Later steps describe their checks; the project writes them.
- **Outside proposals not adopted yet:** a check that cited sources still hold, a queryable decision trace, a quality scorecard, views for the projection's consumers, and extraction artifacts. Reasons are in `SOURCES.md`, section 6.
- **Rule 4 option 4a is a toolchain choice.** The projection uses qualified-relation nodes, not RDF 1.2 reifiers, because rdflib and pySHACL do not read RDF 1.2 yet. Recheck rdflib issue #3524 and the RDF 1.2 status every three months.
- **Two sources of experience.** Most rules come from one private build and one walk-through. Expect changes after a second full build.
