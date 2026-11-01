# Ontology playbook

**What this is.** The `ontology` skill's narrative guide: the method for
building a business ontology from scratch, step by step, with the reasons
behind it. Anyone can follow it for their own domain. The rules live in the
skill's other references (`foundations.md`, `identity-taxonomy.md` and the
rest); each step below names the reference that holds its rules, and this
guide explains them rather than restating them. When the two differ, the
reference wins.
**Owner:** The decision owner. **Built with:** Kailey and Claude Code.
**Started:** 2026-09-17. **Rewritten as a company-neutral method:** 2026-10-05.
**Moved into the skill as its guide:** 2026-10-25.

## About this document

This guide tells a team how to build an ontology, in order, from an empty
repository to a published, tested release. It explains why each step comes
where it does and what each one hands to the next; the references hold the
rules, and `SKILL.md` holds each step's "Done when" gate. The evidence for
each section, from the build that proved the method, is in that build's
worklog, in its evidence map, so that the method reads the same in any
domain.

**Who it is for.** A data architect, ontologist or business analyst who must
turn a business's processes, parties and measures into a governed,
machine-readable model. You need to know what a triple is. Section 4 explains
each standard the method uses.

**The documents around this guide.** Each has one job, so a reader can follow a build from the business to the running stores without two documents competing.

| Document | Its job |
|---|---|
| This guide | The method for building the ontology, Steps 0 to 12 |
| The `ontology-to-lpg` skill's playbook (`references/ontology-to-neo4j-playbook.html` in that skill) | The method for Step 12: projecting the releases into a graph store with nothing lost, keeping other graphs beside them, and keeping the stores in step |
| A project's process record | How its business processes and their written definitions were decided |
| A project's worklog | What its build did at each step, and when |
| A project's guide | What its finished ontology holds, and why |
| A project's walkthrough | The whole story for a newcomer, from the business and its gaps to the stores, with the steps to rebuild it |

The two method documents stay company-neutral. A project's documents point to them, and they do not point back.

**Where it starts.** Before Step 0, an intake sorts what you bring into six kinds of input, with a hierarchy of the business's processes or concepts as the backbone (`governance.md`, rule 1). Competency questions are drafted there and locked at Step 1. To add a module to an ontology that already has releases, read `new-module.md`.

**How to read it.**

| Section | What it gives you | When to read it |
|---|---|---|
| §0 Foundations | Why the method starts with a conceptual model | Before you start |
| §1 The method | Steps 0 to 12: the purpose of each, how it connects to the next, and where its rules are | Step by step, as you build |
| §2 Policies | Why the policies exist, how to decide between sources, why to split into modules | Before any modeling choice |
| §3 Promoting provisional data | Why rough source data needs its own discipline | When you build the relationship layer |
| §4 Standards guide | Which W3C standards to use, for what, and what to set aside | When you choose a vocabulary |
| §5 Soundness checks | Where the checks for every change live | On every change |
| §6 Working agreements | How the team works together | When you set up the team |
| §7 Worked example | The method applied to a public library's lending | When a rule needs a concrete case |
| Appendices | Parking, versioning, and an example predicate set | When you need the detail |

**How to maintain it.** This guide changes only when the method changes. A
new rule goes in the reference that holds its step, and this guide gains a
sentence only when the narrative needs it. A decision about one project (an
IRI, a scope call, a ruling on one row) does not belong here; it goes in the
project's records (`governance.md`, rule 8).
`scripts/test_playbook_guide.py` fails when this guide names a project's
records, companies or paths.

**Where the rest of the skill is.** `SKILL.md` runs this method as a gated
procedure for an agent; `templates/` holds the files each step fills in, and
`scripts/` the checks that run the gates. Two companion skills carry parts of
it out:

- The `ontology-to-lpg` skill: the property-graph projection method used in
  Step 12.
- The `rdf-store` skill: loads the released files into a triple store (a
  SPARQL 1.1 store or a Databricks Delta table) and proves by a round trip
  that nothing was lost (Step 12, hop 3).

---

## 0. Foundations

**Rules:** `foundations.md`, "Conceptual modelling, before any syntax".

People used to fill gaps in data by asking each other what a field meant.
Agents cannot do that. Every consumer of your data, human or machine, needs
to know what it is reading. The ontology makes that knowledge durable, shared
and machine-readable. Build that foundation before anything consumes it, so
that everything built later connects to something trustworthy. A foundation
with no consumers yet is not unfinished. It is ready for them.

The method therefore starts with a conceptual model, settled with the
business before any syntax. The ideas come from Juha Korpela, "Building
Semantics with Conceptual Models" (Common Sense Data, 2026): model what the
business means, not how it stores data; capture entities and the verbs
between them before attributes; name entities as singular nouns that work in
a plain business sentence; define every one; add subtypes only where the
business tells kinds apart; and declare rather than suggest. A mind map helps
a workshop agree, but only a declared model converts into an ontology. Get
these right and the rest of the method is execution; get them wrong and no
tool fixes the result. Once the model is declared, the conversion to RDF is
mechanical, and `foundations.md` lists how each part maps.

---

## 1. The method

Follow the steps in order. Each step has a purpose, the reference that holds
its rules, and a "done when" gate in `SKILL.md`. Do not start a step until
the previous gate is met, unless the gate itself says what may go on while
it stays open: an answer the owner has not given yet (`governance.md`, rule
3), or a registry search that cannot run offline (`external-ontologies.md`,
"Offline"), which leaves Step 0 open and lets Step 1 start. The order
matters: identity before taxonomy, taxonomy before relationships,
relationships before responsibilities, responsibilities before interfaces,
integration before validation, and validation before publication. The one
exception to the order is Step 8, the scope review. Do it early, right after
Step 0.

Two principles run through every step:

- **Write the exam before the coursework.** The business owner approves the
  competency questions (Step 1) before any modeling. They become the
  regression tests (Step 11). A question the model cannot answer is a
  modeling gap, not a bad question.
- **One step at a time, with a gate.** Finish a step before you start the
  next, except where the gate names what may go on while it stays open.
  Record each decision as you make it, and change the source of truth
  with one consolidated proposal per step, not one change per decision.

### Step 0. Align the reference framework and survey existing ontologies

**Rules:** `foundations.md`, "Step 0"; `external-ontologies.md`.

**Purpose.** Find what already exists before you invent anything. A
published reference framework becomes your consistency check, and existing
ontologies and code lists give you terms to link to. Your local model stays
the source of truth; the framework only shows where you diverge, and every
divergence is written down so the next reviewer does not read it as an
error. Mapping, not importing, is the default, because an import brings
structure no competency question asked for. Expect gaps: public ontologies
often cover one part of a sector well and leave the rest bare, and a gap is
a finding, not a reason to stretch a neighbour.

### Step 1. Foundations

**Rules:** `foundations.md`, "Step 1"; for target formats, `lpg-projection.md`.

**Purpose.** Fix the ten policies that everything else assumes, before any
modeling, because changing one later means remodeling. The competency
questions come first: they are the acceptance test for the whole build. The
data-scope policy (define, don't record) decides what the ontology will
never hold, and the evidence order decides every later disagreement between
sources ("Deciding between sources", §2). If the ontology will ever be
projected into a property graph, adopt that projection's design rules now;
rules adopted after a release force a new release of every module they
break.

### Step 2. Identity normalization

**Rules:** `identity-taxonomy.md`, "Step 2".

**Purpose.** Give every node a stable identity before you say anything about
it. Labels change and collide; identity must not. Everything later (the
hierarchy, every relationship, every release) points at these IRIs, so a
label used as a key here breaks silently at every later step.

### Step 3. SKOS taxonomy

**Rules:** `domain-model.md`, `identity-taxonomy.md`, "Step 3", and `quality.md`.

**Purpose.** Build the controlled vocabulary: the hierarchy of names, with
labels and definitions. It is a vocabulary of names, not a class hierarchy,
so it uses SKOS first; turning each level into OWL classes asserts logical
commitments a naming hierarchy does not make. Decide each term's kind first
(`domain-model.md`): concept, class, property, code value or reference
individual. Definitions are where the ontology's meaning lives, so every
one, written or collected, meets the quality bar and passes the human gate
(`quality.md`). The mechanical checks, including the qSKOS issues, run before
any person reads a definition, so review time goes to meaning.

### Step 4. The relationship layer

**Rules:** `promotion.md`.

**Purpose.** Turn the verbs between concepts into governed relationships:
the predicates of your triples. Define each predicate before you read a
single row, review one predicate family at a time, and hold a row whose
meaning is unclear rather than change it, because the source author chose
the verb and a fix belongs in the source. Section 3 explains why this step
needs its own discipline.

The step ends with the first release of the core module. Before it, decide
which held rows go back to the source author for correction, and release
only when each of those rows has a fresh verdict. Released early, those rows
lose their provisional form and need a second release. `promotion.md`, "The
release gate and the source-correction backlog", says how to work that
backlog in batches, and "Building the first release from evidence" how to
cut the release.

### Step 5. Organizations, roles and responsibilities

**Rules:** `organization.md`.

**Purpose.** Say who is responsible, and describe the real organizations the
model refers to. Roles are positions people hold, not people: the same person
can be Accountable for one process and only Informed on another, and an
organization can be a customer in one deal and a supplier in the next. That
is why responsibility is an assignment node and a party role is a dated node,
never a subclass. Real organizations sit in their own reference module, each
fact with its source and as-of date, so the core stays reusable.

### Step 6. Interfaces and provenance

**Rules:** `provenance.md`.

**Purpose.** Separate what is planned from what happened. The ontology holds
the process definitions and the pattern a run follows; the consuming systems
hold the runs. The recipe is not the meal: a definition typed as an activity
would make every count of "what happened" include the catalogue. The step
ships its pattern as shapes, so a consumer can test its own records against
the released definitions.

### Step 7. Cross-model integration

**Rules:** `integration.md`; for mappings, `external-ontologies.md`, "Record mappings as SSSOM".

**Purpose.** Link the models to each other: processes to value streams,
capabilities, systems, measures and data products. Overlays come back from
the parked list one at a time and reference process nodes rather than
duplicate them, because a value stream cuts across the hierarchy and cannot
be a parent. Measures are definitions, never values, and most of them are
operational metrics: a KPI is a designation with a target and an owner, not
a kind of measure. The mappings assigned to this step in Step 0 are applied
here, kept as data with their justification. Each gap earlier steps exposed
gets a recorded decision; "unowned, parked" beats an invented owner.

#### The integration-module pattern

Some rules apply across modules rather than inside one: which links make a
claim of ownership, which source wins, and what a consumer may do with the
graph. Put them in one integration package that sits above the modules it
governs and holds no new business facts, only statements about the other
modules' terms. It holds three kinds of rule, each of which `integration.md`
states (rules 25 to 28). Keeping each kind as its own vocabulary, with its own
namespace and source folder, released together as one package, is one way to
lay it out, not a rule:

- **Placement** says what each placing link claims. A link that names the
  process owning a thing *certifies*; every other placement is *context*.
- **Authority** gives every cited source one evidence tier, so that when two
  sources define one concept differently, a query can say which wins
  ("Deciding between sources", §2).
- **Consumer** writes down how a catalog binds a measure to the data product
  that publishes its values, what an agent may answer from the graph alone,
  and what it must refuse.

A worked case, in the lending domain of §7. The measure *loan turnover* is
defined in the measures module. The lending process produces the *loans*
data product, so `producedBy` is a certifying placement: lending owns that
data. The lending system is linked to the shelving process because staff
check shelf locations in it; that link is context, and nobody may read it as
"the lending system owns shelving". Two sources define loan turnover: the
library's own lending policy (tier 1) and a national library statistics
glossary (a sector source). The policy's definition wins; the glossary's
stays in the graph, cited and marked as the losing one. When an agent is
asked for last month's loan turnover, it answers what the measure is, which
definition wins and which data product publishes it. It quotes a value only
from the source the catalog binds to that measure, naming the source, and it
never computes one from the graph.

The integration package depends on every module it describes, so it is
released after them and pins their current versions. Its tests fail when a
consumer rule names a graph term that does not exist (`integration.md`,
rule 28).

#### Identifiers on measures

When a consumer already refers to measures by code, give each measure a
stable identifier in the ontology, as `dcterms:identifier`, and let its kind
decide its prefix: one prefix for measures designated as KPIs, another for
operational metrics, none for trackers, reports and things that are not
measures. Fix the width (four digits keeps codes sorting as text) and number
each prefix in one recorded order. A measure promoted to KPI later takes a
new KPI identifier; its old one is kept and never reused. Where an asset
already uses a code for a measure, keep that code as a recorded exception
rather than renumber the asset.

The skill ships no identifier check, so write one in the module's build,
and make it check the rule, not a list of values: every identifier follows
its kind or a recorded exception, is used once, and sits in its prefix's run
in the recorded order with no gap. Add SHACL shapes that say the same for
consumers: the identifier's pattern, none on the kinds that take none, one on
every other measure. A real multi-module ontology built both in its own module (2026-10-28).

Carry the identifiers into a BI semantic layer through the fields consumers
search, not the field they query by. In a real multi-module ontology
(2026-10-28 and 29) the agents queried Databricks metric-view measures by
name, so the identifier went into each measure's comment, display name and
synonyms and into a tag on each view, and the names stayed. A measure that
implements no ontology measure, such as a row count, says so in its comment
and carries no identifier; a test pins each measure to the identifiers the
identifier table gives it, so a swapped or extra identifier fails. Views
over the triple table then give each identified measure's definition, grain
and basis inside the warehouse, read from the released graph rather than
copied, so an agent there can read what a measure is before it answers.
Scope every statement about this to the identified measures: the project's
reviews caught "every measure carries an identifier" in several wordings,
code comments included.

### Step 8. Scope review (do it early)

**Rules:** `foundations.md`, "Step 8".

**Purpose.** Decide what is in and out before the foundations harden. An
area enters scope only with a hook into the ontology's purpose; every area
left out gets a reason and a revival trigger, so nobody re-argues the call
from scratch.

### Step 9. SHACL validation

**Rules:** `shacl.md`.

**Purpose.** Turn every rule that can be checked mechanically into a shape.
Start with a small slice before the first release, so the release is checked
by shapes and not only by scripts, then grow it. RDFS and OWL infer; they do
not validate, so checking is SHACL's job. A shape that has never failed may
pass vacuously, so each one is proved by a test that breaks the data on
purpose, and every module's shapes also run together on the whole graph,
where a shape that targets too broadly shows itself.

### Step 10. Publication

**Rules:** `release.md`; `packaging-walkthrough.md` for the interview.

**Purpose.** Ship a published, versioned artifact, not a file on a disk.
Every module ships the same package shape, built by one script, so a
consumer can validate against an exact version, and a released package never
changes. A changelog says what changed and what the release is not yet fit
for ("Known gaps"). When a project has files but no packages yet, the
packaging walk-through asks one question at a time and builds the packages
from the answers.

### Step 11. SPARQL regression tests

**Rules:** `regression.md`.

**Purpose.** Prove the ontology keeps answering its exam. The competency
questions from Step 1 become SPARQL, and the suite runs against the released
packages on every release and after every module lands. Start the harness
early, before most questions can pass, so each module's pull request moves
its own questions to answerable. A failing test is a regression or a
recorded, deliberate change; it is never a surprise.

### Step 12. Property-graph projection (optional)

**Rules:** `lpg-projection.md`, then the `ontology-to-lpg` skill (its `references/pipeline.md`, `running.md` and `multi-store.md`).

**Purpose.** Load the finished ontology into a labelled property graph, such
as Neo4j, for applications that query in Cypher. The Turtle files stay the
master copy. A property graph does no OWL reasoning, so reasoning happens
once upstream and its results are loaded beside the asserted triples. The
projection is proved, not assumed: SHACL runs inside the graph, a round trip
back to RDF shows nothing was lost, and two loads in different orders give
the same graph. The same validated files then go to every other store, a
triple store and Databricks among them, and each hop is compared with the
files, so a loss shows exactly where it happened. The `ontology-to-lpg`
skill holds the pipeline, the store hops and the checks; the `rdf-store`
skill holds the triple-store hop.

---

## 2. Policies

**Rules:** `foundations.md`, "Step 1: record the ten policies" and "Source
policies that apply from Step 1".

The policies are the rules every later step assumes: what the ontology
holds, how sources rank, how identity, language, versions, licences and
modules work, and who consumes it. Record each with its reason before any
modeling, because each one, changed later, means remodeling. A project
records its own applications of them in its decision log; a policy itself
changes only when the method improves, by a dated amendment with the owner's
agreement. Three of them need more than their rule, and get their own
sections below.

### Deciding between sources

The evidence order of Step 1 (`foundations.md`, policy 3) decides between
sources. Make it decide the same way every time:

1. **Rank the source types once,** in tiers, before any modeling: the
   organization's own governing documents first, then peers' published
   equivalents, then sector standards and sector-specific sources, then
   generic frameworks, which support a decision but never settle one alone
   (`foundations.md`, policy 3).
2. **Give every cited source exactly one tier, and every tier one rank.**
   Record the tiers as data in the integration package, not as prose, so a
   query can say which source wins.
3. **Let the best tier win, concept by concept.** Keep the losing
   definition in the graph, cited and marked as the one that lost, so a
   reviewer sees the disagreement instead of finding it later.
4. **Change a tier only by a recorded decision,** because a new tier can
   change which definition wins across the whole graph.

In the lending example: the library's lending policy (tier 1) and a national
library statistics glossary (a sector source) both define *overdue*. The
policy says a loan is overdue the day after its due date; the glossary
allows a grace period. The policy wins, and the glossary's definition stays
as the marked loser. If the library later adopts the glossary's grace
period, it records that decision and updates the policy, and the winner
changes because the source changed, not because someone edited a label.

### Why split an ontology into modules

The module policy (`foundations.md`, policy 8) says how to split. This is
why the split pays:

- **Each module releases on its own schedule.** A change to the measures
  does not make the process taxonomy wait, and each module pins the
  versions of the modules it requires.
- **Reviews and approvals stay small.** A pull request touches one module,
  and its owner approves it.
- **Organization-specific facts sit apart from neutral ones.** Reference
  instances of real organizations go in their own module, so the rest can
  be reused in another organization.
- **Each module carries its own shapes and tests,** and a whole-graph gate
  catches what breaks between them (`shacl.md`).
- **Consumers load only what they need.** A package's dependency closure
  is read from the released manifests: each dependency brings what its own
  release requires, and only where two paths reach different releases of one
  module is the highest loaded (`release.md`, rule 12).
- **A projection can tag every node with its module,** so a walk across the
  graph shows where each fact came from (Step 12).

The split has costs. A module's pin can lag: it was released against an
older version of another module, and stays so until its next release. That
is why the closure rule and the whole-graph gate exist, and why each
release's changelog names the versions it requires.

---

## 3. Promoting provisional data without corrupting it

**Rules:** `promotion.md`.

Most builds start from rough source data: a workbook, a spreadsheet, an
export. A common pattern is to capture it first as provisional annotations
in a staging namespace, then promote it to governed properties. The staging
layer may be the only copy of facts such as "which process uses which
input", so a careless promotion corrupts those facts silently: the triples
look fine but no longer say what the business said.

The eleven rules in `promotion.md` each come from a failure in a real build.
Target labels were renamed under approved rows between two package versions,
and only a commit pin and a field-by-field diff showed it. A label named two
concepts in two branches, so a join on labels would have misresolved both
without an error. The first evidence pass counted notes as citations and
hierarchy closeness as evidence, and was wrong and confident; the fix was a
check that failed on the broken premise, not a corrected row. Zero staging
triples proved deletion, not migration, until a ledger accounted for every
triple. Mirrored rows doubled the fact count. And a mistyped source verb
cannot be repaired by a script that picks a nicer predicate, because that
hides an authoring error inside the ontology. When the source is a
spreadsheet, the conversion is a reviewed mapping run as a deterministic
build step (`promotion.md`, "From a spreadsheet to triples").

## 4. Standards guide

Each entry says what the standard is, why it belongs in the build, and what
it is not for. The rejections matter as much as the adoptions.

### RDF: the grammar
**What:** the subject-predicate-object triple model.
**Why:** every other standard here is a vocabulary written in RDF.
**Not for:** carrying meaning alone. RDF without a vocabulary has no words.

### SKOS: the taxonomy and the mappings
**What:** `ConceptScheme`, `prefLabel`, `altLabel`, `broader`, `narrower`,
`notation`, and the mapping properties `exactMatch` and `closeMatch`.
**Why:** a process hierarchy is a vocabulary of names. SKOS gives labels,
aliases, hierarchy, and links to external sources without claiming each node
is a class.
**Rejected:** converting hierarchy levels into OWL classes mechanically.

### Dublin Core Terms: describing sources
**What:** `dcterms:title`, `references`, `license`, `provenance`, `source`.
**Why:** the ontology constantly describes its sources: which framework
version, which filing, which license.
**Not for:** describing the domain itself.

### RDFS and OWL: the schema layer, used sparingly
**What:** classes, properties, subclass and subproperty, domain and range,
equivalence, disjointness, inverses.
**Why:** you need some real classes (process definition, responsibility
assignment, named KPI) and precise property kinds.
**Constrained:** RDFS and OWL infer. They do not validate. Domain and range
create new triples; they do not check data. Assert disjointness or
cardinality only where the business guarantees it. Keep to the OWL 2 EL
profile if you will project to a property graph.

### PROV-O and P-Plan: plans, runs and trust
**What:** `prov:Entity`, `prov:Activity`, `prov:Agent`, and P-Plan's plans
and steps.
**Why:** two jobs. P-Plan and PROV-O separate a planned process from its
runs. PROV-O also records who asserted what, when, and on what authority.
**Rejected:** typing taxonomy concepts as `prov:Activity` by default.
**Watch for:** shapes that describe process runs usually target every
`prov:Activity`. Anything else typed `prov:Activity`, such as a business
decision recorded as PROV, then fails them, because it has no qualified
association naming a process as its plan. In a real project (2026-10-29) a
decision trail of ten decisions gave ten such violations. Either type the
other activities differently or narrow the shapes' target; otherwise say that
such records fail those shapes and that nothing validates them against them.
Do not write that the shapes "do not apply": by their target, they do.

### ORG: organizations and roles
**What:** `org:Organization`, `org:Role`, `org:Membership`, sites and
units.
**Why:** RACI needs roles, not people, and reference instances need
organizations and sites. `org:Membership` is the model for qualified
relations.
**With:** FOAF for the people and teams behind roles, `dcat:contactPoint`
for ownership, and a registry vocabulary for legal-entity relations, such as
GLEIF Level 2 for accounting consolidation, by mapping.

### SHACL: the checking layer
**What:** shapes, run against the data to produce a validation report.
**Why:** every rule that a machine can check becomes a shape, including
cardinality and the property-graph design rules.
**Constrained:** Core first. Reports are questions for a person.

### DCAT: publishing
**What:** catalog, dataset, distribution, data service.
**Why:** the end state is a published, versioned artifact with many
serializations.
**With:** DQV for quality measurements, and ODRL where rights need more
than a license URI.

### Property-graph projection
**What:** loading the ontology into a labelled property graph (Neo4j with
the n10s plugin) by a fixed pipeline.
**Why:** some applications query in Cypher. The projection gives them the
ontology without making the graph database the master copy.
**Constrained:** a property graph does no OWL reasoning. Reason upstream and
load the results.

### Reusing external ontologies
**What:** public domain ontologies, registry vocabularies and industry code
lists.
**Why:** they give your terms external authority and help others integrate
with you.
**Constrained:** map by default (`external-ontologies.md`). Check the license, the maintenance
status and any upper ontology before you rely on one.

### What to evaluate and set aside
- **RDF 1.2 reifiers.** They attach properties to a single triple. As of
  October 2026, the W3C specification is a Candidate Recommendation. Apache
  Jena 6.1.0+ and RDF4J 6.0.0+ read and write it; rdflib and pySHACL do not.
  Use qualified-relation nodes (`foundations.md`, conceptual modelling, rule 8) unless every tool in your pipeline
  supports it.
- **W3C SIOC.** An online-community vocabulary. It does not apply to a
  process ontology.
- **The Open Data Product Specification family.** The W3C stack covers the
  need without a second modeling style. Revisit if data-product catalog work
  demands it.

---

## 5. Soundness checks

**Rules:** `quality.md`, "Soundness checks on every change"; identity checks in `identity-taxonomy.md`, Step 2; predicate checks in `promotion.md`.

Soundness is a set of checks a person runs on every change, beside the check
script: what was checked and by whom, whether every figure was recomputed
from the source files, whether a wrong figure was searched for everywhere it
could appear, and whether the change's one safety fact was proved by running
code. They catch what a script cannot judge. When a new failure teaches a
new check, it goes in `quality.md`.

### Testing and validation, end to end

A change is trusted only after it has passed every check below. Each one
catches a kind of failure the others cannot see. Each item names the rule
that holds it; the rule, not this list, is the source.

1. **Tests written from the decision.** The module's tests pin its figures,
   its new IRIs and its corrected statements by hand, written from what was
   decided (`release.md`, rule 29).
2. **The mechanical checks.** The taxonomy checker runs on the data files
   before any review (`identity-taxonomy.md`, rule 13), and on each new
   package beside the one it replaces: what the release fixes is gone, the
   other findings are unchanged, and a new one appears only with a recorded
   decision; a first release records its counts as the baseline
   (`release.md`, rule 30).
3. **Shapes on every package.** Each written release package conforms to
   its own shapes over its released closure (`shacl.md`, rule 9), and no
   `sh:message` holds a single quote unless that message is tested in the
   target engine (`shacl.md`, rule 19).
4. **The classification, proved.** A test compares the release with the one
   before it: every earlier IRI is still declared, nothing is newly
   deprecated in a minor or patch release, and every deprecated term names
   its successor; a first release, with no earlier package, checks only the
   last of these (`release.md`, rules 3, 5 and 28).
5. **The competency questions.** The regression suite runs on the released
   packages after every module lands and on every release, and checks each
   question's status (`regression.md`, rule 13).
6. **The sweep, then the check script.** Every claim the change makes is
   searched for in all its wordings, then the project's full check script
   runs (`quality.md`, "Soundness checks on every change"). The check script
   runs every check the build has, each builder's verify command among them
   (`governance.md`, rule 15; `release.md`, rule 9), and the whole suite runs
   before a review, not only the module's tests (`regression.md`, rule 14).
7. **The projection and the stores.** In the property graph, SHACL runs
   inside the graph, a deliberate broken case is caught, a round trip back
   to RDF loses and adds nothing, and two loads in different orders give the
   same graph. Each triple-store copy's hash equals the source's, the Aura
   copy's hash equals the local graph's, and walks compare Neo4j with the
   triple store (the `ontology-to-lpg` skill: `multi-store.md`, and
   `add-ons.md`, section F).
8. **Review.** A reviewer who did not write the change reviews it before the
   pull request opens, and the pull request's reviewer gives the verdict;
   nothing merges past a hold (`governance.md`, "Review").
9. **Approval.** The release's approval is quoted in its manifest and
   pinned in a test that reads the saved answer (`release.md`, rules 6
   and 7).

---

## 6. Working agreements

**Rules:** `governance.md` (decisions, delegation, checks, review, generated
content and candidates from documents); `quality.md` (the definition quality
bar and the human gate).

The team checks the policies and the decision log before any modeling
choice, and raises a rule that seems wrong with the owner rather than
overriding it. Subject-matter text, whether a person wrote it or a tool
collected it, goes through the same human gate. Every change goes through a
pull request that a reviewer merges or holds. Nothing is decided until the
owner has recorded it; a merge decides nothing, and what the agent adds to a
decision is marked as the agent's. One agreement no reference holds:

- **Merging a branch with main.** When a merge conflicts in a table, merge
  the row: keep one row per key, carrying both sides' changes. Keeping both
  sides of a table conflict duplicates rows. It is safe only for entries
  that are separate by design, such as decision-log groups and index rows;
  then put the rows back in their order.

When a practice is proven, it goes in the reference a reader would look in,
with its reason, in the same week.

---

## 7. Worked example

How the method plays out on a small domain: a public library's lending.
This section illustrates. The rules are in the skill's references, and the example's
names and codes are invented.

**The source.** The library's process map lists its activities in a
hierarchy with local codes (`LND 1.2`), the roles responsible for each in a
RACI column, and a status column. A published classification of library
services is the reference framework.

**Step 0.** Every framework ID the process map cites is checked against the
framework's current published edition, and one stale ID is corrected. The
survey finds a public vocabulary for bibliographic records. The library
maps its "copy" concept to it and imports nothing.

**Step 8 (done early).** Interlibrary loans go in, because lending depends
on them. Room bookings go out with a boundary note ("handled entirely in the
booking system; nothing depends on it") and a revival trigger: a consumer
asks which rooms a lending event uses.

**Steps 1 and 2.** The competency questions ask what the ontology can
answer from definitions and reference facts: "what makes a loan overdue?",
not "which loans are overdue today?". The ontology defines `Loan`, its
properties and its shapes; the lending system holds the loans themselves.
The loan period that the published lending policy sets is a reference
fact, recorded with the policy's edition. Local codes become
`skos:notation` and slugs (`LND 1.2` becomes `LND-1-2`).

**Step 3.** One concept scheme. The circulation branch's primary question,
"how do copies reach members and come back?", is the placement test for
every new concept. The status column holds "overdue", "returned late" and
"overdue/hold pending": a loan's state, its history and another member's
hold. It becomes three controlled fields, each with its own code list.

**Step 4.** "Renewal precedes return" links two siblings, so their
nearness is enough for the sequence. "Cataloguing enables lending" needs
independent evidence, and the lending definition names cataloguing. A row
whose source says "informs" where the pattern wants "requires" is held with
that reason, never remapped.

**Step 5.** The RACI column spells "Circulation Desk" and "circulation
desk": one role. "Librarian / Cataloguer" splits into two roles. A member
holds a Borrower role from the day the card is issued and a Volunteer role
from a later date. Both are dated nodes that point at one person; neither
is a subclass of party.

**Step 6.** "Lending" is a process definition. Lending one copy on one day
is a run of it: a `prov:Activity` whose qualified association has
`prov:hadPlan` pointing at the definition. The lending system records the
runs.

**Step 7.** "Loans per member" and "loans per active member" have
different denominators, so they are two measures, and each definition
names its basis. Loan turnover is an operational metric until the library
names it as one of the few measures of a stated objective, with a target
and an accountable owner.

**Steps 9 to 11.** A shape takes each loan state from the loan-state list,
so a cadence value used as a loan state fails. Each competency question
becomes a SPARQL query with a status, and every release runs the suite.
The module header follows Appendix B.

---

## Appendix A. Parked items

A parked item is something you deliberately defer, recorded in
`templates/parked-list.md` with what it would cover, the competency questions
it would answer, a "done when" and a revival trigger (`foundations.md`,
source policies). Never delete one; revive it or close it by decision. A
library's two parked items show the pattern.

### Fines and fees module (worked example, parked)

Not modeled yet. The questions it would answer are kept, so a later pass
can use them unchanged:

- What is a fine, a fee and a waiver?
- Does an overdue loan have a fine, or is it one?
- Who owns the fee schedule, and who owns the overdue measure?
- How does a fine charged on a date relate to the fee schedule that set it?

Done when: loans reference fines and do not subclass them.
Revival trigger: a consumer needs to reason about money owed, not only
about loan states.

### Value-stream, capability, activity, event, decision, KPI and data-product layer (worked example, parked)

Value streams, capabilities, activities, events, decisions, KPIs and data
products are often parked together. They come back as overlays over the
process backbone, one at a time, never as a second hierarchy inside it. A
value stream cuts across the tree (a borrowing journey touches membership,
circulation and fines), and every concept has exactly one parent, so a
value stream cannot be a parent. Overlays reference process nodes by ID.

Done when: a consumer needs one of these layers. Then promote that overlay
against the released backbone.
Revival trigger: someone asks for the borrowing journey end to end, and the
backbone alone cannot answer.

---

## Appendix B. Versioning in detail

**Rules:** `release.md`.

Term IRIs are permanent; versions describe what changed around them. A
consumer who bookmarked a concept IRI must still get a correct answer years
later. That one idea drives the rest: the version lives on the module
header, never in a term IRI; a concept is deprecated and points at its
successor, never deleted; and a change is classified by the meaning-change
test (would every answer given under the old definition still be correct
under the new one?), because a false major costs a version number and a
false patch corrupts consumers silently. `release.md` holds the
classification, deprecation, the release package, candidates and the cut,
the catalog, the header with its version IRI, and who approves; the
`templates/ontology-skeleton.ttl` header shows the pattern.

---

## Appendix C. Example predicate set

**Rules:** `promotion.md`, "Example predicate definitions".

`promotion.md` gives a set of process-to-process predicates from a real
build, each with a definition shaped by the confusion it prevents: enablement
against sequence, information flow against output dependency, requirement,
assurance, constraint, governance, trigger and sequence. Use them as a
starting point and write your own definitions to your evidence. The same
build also split its "enables" rows by disposition: a row whose fact was
already carried by an output dependency merged as extra evidence on that
fact and emitted no new triple.
