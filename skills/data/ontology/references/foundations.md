# Foundations, policies and scope

Serves Steps 0, 1 and 8. Read it before the first modelling choice, at Step 0, at Step 1, and whenever a choice seems to contradict a policy.

## Conceptual modelling, before any syntax

These come from Juha Korpela, *Building Semantics with Conceptual Models* (Common Sense Data, 2026). Settle the conceptual model with the business first; the conversion to RDF is then mechanical.

1. **Model the business, not the storage.** Leave out any distinction that exists only because of a table, a feed or a system boundary. *Why:* a storage concern baked into a concept outlives the system that caused it.
2. **Entities and relationships first; attributes later.** *Why:* teams that start with attributes get stuck in them and lose the structure.
3. **Name each entity as a singular noun** ("Loan", never "Loans" or "Loan Data"), and test it in a plain business sentence as subject or object ("A member borrows a copy"). Rename it until the sentence works. *Why:* the entity plays exactly those roles in your triples.
4. **Define every entity**, in plain business language, with no exceptions. *Why:* terms plus definitions are the semantics; a term without one is a guess for every consumer.
5. **Name every relationship with a verb** that says why A relates to B in the business. Two verbs for two business realities between the same pair are two relationships ("a member *reserves* a title" and "a member *borrows* a copy"). *Why:* the verbs become your predicates, and consumers depend on the distinction.
6. **Add subtypes only where the business tells the kinds apart in practice**, and declare no disjointness until the business guarantees it. *Why:* extra generalization makes the model unreadable, and an unearned disjointness axiom makes valid data inconsistent.
7. **Declare, don't suggest.** A workshop mind map suggests; the conceptual model declares and stays true until the business changes. *Why:* only a declared model converts into an ontology.

The conversion: each entity becomes a SKOS concept or an `owl:Class` (SKOS first, see SKILL.md); each statement becomes a triple; each definition becomes `skos:definition`; each noun becomes `skos:prefLabel`; each subtype link becomes `skos:broader` or `rdfs:subClassOf`; each verb becomes an `owl:ObjectProperty`.

## Step 0: align the reference framework

1. **Adopt the official, current version of the domain's reference framework** (for example an industry process classification) and check every cited element ID against the published workbook. *Why:* mirrors and old citations drift, and one wrong ID misleads every later mapping.
2. **Store the framework with its attribution and licence notice intact.** *Why:* most frameworks permit reuse only with the notice travelling with every copy.
3. **Make the local model the source of truth and the framework the check.** Framework IDs attach by `dcterms:references`; they never replace local IDs. *Why:* you model your own business; the framework only shows where you diverge.
4. **Record every divergence as a boundary note with a reason.** Never hide one, and never quietly conform. *Why:* an unexplained divergence reads as an error to the next reviewer.
5. **Survey public ontologies and code lists, and give each a treatment** (map, import or ignore) and a target step. Method: `external-ontologies.md`.

## Step 1: record the ten policies

Record each policy with its reason before any modelling. *Why:* every later step assumes them, and changing one later means remodelling.

1. **Competency questions.** Draft the questions the ontology must answer; the owner approves and locks them. They are the acceptance test (Step 11, `regression.md`). *Why:* write the exam before the coursework; a question the model cannot answer is a modelling gap, not a bad question.
2. **Data scope: define, don't record.** The ontology holds concepts, definitions, relationships, and public reference facts about real organizations and assets, each with a source and an as-of date. Stable attributes (a site's capacity, an ownership share) are reference facts. Event records ("member 1042 borrowed copy 7") and observed measure values ("loan turnover was 3.1 in May") are not. *Why:* records and values change daily in the systems that compute them; an ontology that holds them becomes a stale second copy.
3. **Evidence order.** Rank sources: the anchor organization's own filings and publications first, then direct peers, then industry-specific sources. Generic frameworks support a decision but never settle one alone. Cite every fact; a fact without a citation stays out. *Why:* the closest source knows the business best, and the order settles disagreements.
4. **URI policy.** A persistent base behind a redirect, scoped to the organization, never to a person or a project. Local IDs become `skos:notation`. No version in term IRIs. Detail: `identity-taxonomy.md`. *Why:* a rename then changes one redirect, not every identity.
5. **Language policy.** Declare the primary language and tag every literal. *Why:* tagged and untagged literals are different RDF terms, so SPARQL treats them as different values.
6. **Version policy.** Semantic versioning per module and per release; deprecate, never delete. Detail: `release.md`.
7. **Licence policy.** Decide before publishing anything; proprietary is the safe default for competitively sensitive operations. Respect each reference's licence: carry its attribution, cite IDs freely, quote sparingly. *Why:* a closed artifact can be opened later; an open one cannot be closed.
8. **Module policy.** Split into modules with one-way dependencies and no cycles, checked in CI. Cross-module use is by IRI, never by redefinition. *Why:* a cycle makes a module impossible to release on its own.
   - **One module owns each domain's concepts.** No `customer` module beside a `party` module; a domain is a view across modules. *Why:* two owners give two definitions.
   - **Reference instances of real companies, sites and assets go in their own module.** *Why:* the core stays company-neutral and reusable, and the reference module versions as filings change.
   - **When two modules hold the same thing, link them with `skos:exactMatch`; never merge them.** Where the IRIs differ, hold the match by hand in the build and fail the build if the target is missing or shares no label with it. *Why:* each module stays built from its own source.
9. **Consumers.** Record who will consume the ontology and whether any consumer is active yet. Only the owner can state this fact. *Why:* release rules depend on it; with no active consumer, provisional data can be retired in one release.
10. **Target formats.** If the ontology will be projected into a labelled property graph, adopt the projection's design rules now (`lpg-projection.md`). *Why:* rules adopted late force a remodel of released modules.

### Source policies that apply from Step 1

- **Derived from unpublishable material only with permission.** When the owner's material cannot be published, what you derive from it (definitions, tables, mappings) goes in only with the owner's recorded permission. Mark each derived claim as what the material shows or as the builder's reading. *Why:* a reviewer cannot re-check the material, so the marking is the only signal of which claims rest on a reading.
- **A source outside the evidence order may guide a reading, never support it.** A vendor page can suggest what a code means; the record cites only admissible sources and calls the reading the builder's until the owner confirms it. *Why:* an inadmissible citation looks like evidence it is not.
- **Leave an uncertain identity unsettled in the data.** Where two sources may name one thing, keep both names, place facts on one only as a marked reading, and record the open question. Record the owner's exact words when they answer: "assume" is an assumption, not a confirmation. *Why:* a merge made on a guess is costly to split.
- **Confirm an ambiguous source field before you name a term after it.** A column called `org` is not W3C ORG until someone confirms its business meaning. *Why:* a term named on a guess carries the guess into every query.
- **Park, don't smuggle.** Future concepts go on a parked list with what they would cover, the competency questions they would answer, a "done when" and a revival trigger. Data fields, systems, KPIs, controls and thresholds are never process concepts. Revive or close a parked item by decision; never delete it. *Why:* smuggled concepts enter without review, and deleted ones get searched for again.
- **Invent no owner to fill a gap.** "Unowned, parked" beats a guess. *Why:* an invented owner is a fact with no source.

## Step 8: scope review (right after Step 0)

1. **Take candidate areas one at a time.** Put one in scope only with a real hook into the ontology's purpose: a value-chain link, a responsibility (RACI) feed, a data-product dependency. *Why:* an area with no hook adds terms no question needs.
2. **Give every out-of-scope area a boundary note with a reason** ("handled entirely in the lending system; nothing depends on it") **and a revival trigger.** *Why:* the trigger says when to look again, so nobody re-argues the call from scratch.
3. **Cover enabling functions as well as the value chain, where they have a hook.** *Why:* finance or IT processes often own the data products and roles the value chain depends on.
4. **Send newly relevant framework elements through this review before modelling them.** *Why:* a framework release is not a scope decision.
