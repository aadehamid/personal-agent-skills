# Visualization playbook

This method turns an ontology into a reference that people can navigate and
understand. It applies to any business domain. The source ontology supplies the
meaning; the viewer supplies reading paths, explanations and navigation.

Contents: 1. Reader tasks; 2. Source contract; 3. Views and layers;
4. Construction; 5. Validation; 6. Delivery; 7. Updates after a release.

## 1. Start with reader tasks

Identify who reads the viewer and the questions they need to answer. Use concrete
tasks such as finding a term's definition, following a parent concept, or
explaining how two modules connect. Agree the coverage: the full ontology, named
modules, or a pilot with clear links to the remaining model.

Inspect existing guides and viewers before choosing another tool. Evaluate a
candidate against representative source data, its licence, delivery constraints
and supported RDF constructs. Inspect the deployed application as well as its
repository when using another site as a reference; they may run different
versions. Record what was observed and what could not be tested.

Choose delivery from the reader's setting. An offline reference can embed data,
styles, fonts and scripts and open through `file:`. A hosted viewer may need
search services, access controls or larger datasets. Neither is a universal
requirement. Keep implementation details out of ordinary reader flows unless
they help a decision.

Done when the brief names the audience, reading tasks, coverage, source,
delivery mode and evidence needed to accept the viewer.

## 2. Define the source contract

### Bind the input

Select an immutable release, commit or snapshot. Record each input's path,
version and digest, including manifests and catalogs that select the packages.
Verify actual bytes against the recorded source. A clean Git status alone can
miss files marked assume-unchanged. Check the permission modes required by the delivery contract when preserving
a release tree. Git records the executable flag, not all POSIX permissions.

Enumerate included and excluded inputs. Distinguish current packages, historical
packages, examples and operational records. Namespace membership alone is not a
reliable module boundary: imported terms may occur in several packages. Preserve
the source's module membership and version metadata.

For a pilot, state the main navigation coverage separately from the supporting
context. A term outside the pilot may supply a relationship endpoint without
being part of the pilot's term index. Show where those links lead.

### Preserve RDF meaning

Parse RDF with a suitable parser. Keep full IRIs as identities. Store literal
lexical forms, language tags and datatypes; a label is display text, not a key.
State the label and definition predicates and language fallback explicitly.
Retain alternate definitions rather than silently selecting one as the sole
meaning. Escape text and identifiers for their HTML, JSON and URL contexts.

Scope blank nodes according to their serialization. Identically written blank
node labels in separate Turtle documents do not identify the same node. A
dataset serialization can share blank nodes across its graphs; preserve that
sharing. Preserve graph names where the source has them. File provenance is
useful metadata but does not recreate a named graph that a flattened export lost.

Blank-node labels and canonical IDs identify nodes within a snapshot; they do
not establish identity across releases. An unrelated addition can change them.
Use links scoped to an immutable viewer release for anonymous nodes and retain
the previous viewer snapshots for those links. Named term links use their full IRIs. A persistent anonymous-node
mapping needs separate evidence; do not add identifiers to the ontology merely
to keep viewer links working.

An existing viewer may have anonymous links without a release identifier.
Before replacing its published URL, define how those legacy links resolve.
Carry forward published snapshot URLs and legacy mappings through successive
updates. If one legacy fragment could name nodes in several releases, offer
explicit historical destinations instead of choosing a release silently. Test
two successive updates when migrating legacy links. A source pin alone does not
identify the delivered viewer; renderer changes can also change anonymous IDs.

Keep a lossless statement representation alongside display indexes. A record
needs subject, predicate and object RDF terms, graph identity where present,
and source membership. Compute incoming relationships from the same statements
used for outgoing relationships. Retain unknown predicates and anonymous
supporting nodes in an exact-facts view even if the overview omits them.

Prefer asserted statements for the initial view. If inference is required,
record the rules, label inferred statements and preserve the asserted source
separately. Count the stated population: unique terms, triples, quads or module
memberships are different quantities.

Done when extraction can account for the agreed source set without silently
dropping, inventing or changing statements.

## 3. Design views around meaning

### Give readers a starting point

An overview should explain the ontology's purpose and offer direct entry to the
main reader tasks. A module page should state its purpose, version and useful
starting terms. A term page should lead with its label, kind and definition,
followed by scope notes and relationships. Keep the full identifier and exact
facts available without making them the first thing a new reader must decode.

Reading groups can separate business concepts, vocabulary, and rules and
evidence. These are interface groups, not new ontology axioms. Explain what each
group contains and adapt the names to the model. A conceptual class is different
from an operational record; a taxonomy concept is different from an OWL class.

### Explain connections

| Recorded relation | What the view should communicate |
|---|---|
| `rdfs:subClassOf` | A class hierarchy. Keep it distinct from concept hierarchy. |
| `skos:broader` | A concept's broader concept. Do not relabel it as subclassing or process sequence. |
| `rdfs:domain`, `rdfs:range` | Vocabulary semantics about subjects and objects. These statements do not establish required fields or cardinality. |
| SHACL constraints | Validation rules for their targets and paths. Show the scope and exact constraint. |
| Domain relationships | The named predicate between its actual endpoints, with its recorded direction. |
| Package dependencies | Dependencies declared by a package. These do not assert a business relationship between terms. |

Show within-module and cross-module paths. Group cross-module statements by the
other module and offer a concrete example that a reader can follow. Label
aggregate edges with their aggregation rule and let readers inspect the source
statements. A module importing another module is not evidence for a business
connection between their concepts.

Use a small graph around the selected term when it helps reading. Pair it with
a statement list that exposes the same meaning without relying on colour,
position or a pointer device. Label any graph limit and provide the complete
list. Handle cycles and multiple parents without inventing a single parent.

### Follow a guided path

When readers start from a process, lifecycle or value stream, keep that entry
available as they explore. Let them descend through the recorded hierarchy to
its deepest level, then follow connected concepts across modules. Show the
selected concept's parents, children and adjacent statements. A connection card
should name both endpoints and the predicate, with the source direction visible
even when the reader follows an incoming link.

Treat hierarchy, membership and sequence as separate relations. Order stages
only when the source supplies an order; disclose absent or conflicting positions.
Parse an ordering literal according to its declared datatype while preserving
its original lexical form. Keep member processes distinct from the taxonomy
concepts they realize, including when their labels match.

Retain the actual statements followed in a reading trail. Validate saved paths
against the current snapshot and keep their title and starting context
consistent with the path. Explain any restart at a trail limit. If a guided
entry is absent from the selected release, mark it unavailable while keeping
the supported reference pages usable.

### Keep navigation readable

Provide search over names, definitions and identifiers, with filters that match
the reader's vocabulary. Preserve search text, filters and page when returning
from a term. Keep keyboard focus on a usable control after paging.
Use the identity and link rules in section 2, encode links safely, and show a
useful not-found view for obsolete or malformed links. Link only to destinations the
viewer can resolve; display an unresolved reference honestly.

Long incoming lists and evidence can overwhelm the definition. Start with a
short list and make the remainder expandable or paginated, with truthful totals.
On small screens, labelled statement cards can keep source, predicate and target
visible. Test actual text lengths, touch targets, keyboard focus, zoom and both
themes if the viewer offers them.

Done when a reader can complete the brief's tasks without interpreting a dense
graph or remembering unexplained technical labels.

## 4. Build a complete reading path first

Separate the source adapter, normalized statements, display indexes, authored
guide and rendering. Reuse a verified adapter when its source contract matches.
Keep framework and renderer choices replaceable; do not copy a domain's module
names or an old release's paths into a generic adapter.

Implement one path from overview to module to term to a related term in another
module, then back to the search or originating page. Include at least one
constraint or evidence node when those are in scope. Test this path using the
real input before extending coverage. A pilot limits the agreed scope; it does
not silently redefine a request for the whole ontology.

Add a short usage guide around questions a reader can answer. Explain the
different relation types beside their use. Keep authored summaries separate from
verbatim source definitions, and cite the source terms behind each example.

Record borrowed code, assets, licences, exact versions and modifications. A
design reference alone does not require copying its software. A library's name
does not establish support for the ontology's constructs; prove support on the
input.

Done when the reading path works, all agreed modules and term kinds are covered,
and unsupported cases are explicit rather than silently omitted.

## 5. Validate semantics and usability separately

Semantic validation starts from the raw source, not from the viewer's own count.
Reconstruct its asserted statements and compare them with the selected source.
Use graph or dataset isomorphism where blank-node identifiers differ. Compare
graph membership when the contract is a dataset. Preserve lexical literals by
configuring parsers appropriately; value equality does not prove term equality.
Check for both missing statements and invented statements.

For summarized views, verify every displayed edge against its source or stated
derivation. Reconcile omitted detail with the complete-facts view. Verify every
source term kind, definition predicate, language and module required by the
contract, including anonymous constraints and references outside the main index.

Exercise failures that could otherwise look correct: duplicate labels with
different IRIs, the same blank-node label in separate files, changed language or
datatype, an invented edge, a missing module, stale source hashes and a changed
payload with an updated HTML hash. A self-consistent manifest alone proves
neither semantics nor source identity.

Run browser tasks against the delivery mode readers will use. Check search,
filters, back navigation, deep links, reloads, keyboard access, copy actions,
empty results and cross-module links. Delay clipboard completion while
navigating away and confirm that it cannot select or label a different term.
Inspect screenshots and read the text.
Automated overflow checks do not prove that a phone user can see both endpoints
of a relationship. Test a long term and a densely connected term.

For guided paths, render synthetic multiple-parent and cyclic hierarchies in
the browser. Exercise the trail limit, saved paths from another starting view,
missing entry concepts and labels containing markup. Model tests alone do not
exercise tree expansion, heading rendering or browser history. Check that the
browser tests fail when the corresponding UI behavior is deliberately broken
in a disposable copy.

For an offline promise, block and count HTTP requests, open through `file:`, and
exercise navigation. Test the extracted delivery archive as well as the build
folder. For a hosted promise, test its base path, asset loading and access rules.
Keep results tied to source, implementation and artifact identities. Any later
change requires the affected checks again.

Done when semantic comparisons, negative cases and reader tasks pass, with
manual inspection recorded and any untested behavior stated plainly.

## 6. Deliver the exact tested artifact

Build into a separate new staging directory. Keep the previous release available
while preparing the replacement. Inspect the final artifact's relative links,
input scope, licence notices and exposure of project-only material. Use the
project's release checks and independent review where required.

Keep implementation and authored documentation in their source repository.
Place generated files in the delivery repository or artifact as its workflow
requires. Record the dependency between those changes. Publish only after the
required checks and any requested reader review are satisfied. Preserve the
source and output digests so a recipient can identify the version tested.

For an additive documentation release, compare every pre-existing path, byte
and required permission mode against the baseline and allow only the agreed
additions. Compare generated files with the reviewed builder's complete output;
a payload check or self-recorded hash cannot detect altered scripts or notices.
Keep audit reports outside the inputs and delivery, and refuse to overwrite them.
Use a normal branch and review for an update that must preserve release history;
an orphan-branch publishing tool may violate that contract. Read the publishing
tool before using it.

Done when the delivered artifact matches the tested candidate, or when it is
explicitly labelled a candidate awaiting the required review.

## 7. Update after each release

First classify the change from source evidence:

| Change | Required work |
|---|---|
| Ontology release | Select the new immutable input set; compare terms, statements, versions and graph membership; regenerate and verify the viewer. |
| Presentation or guide only | Keep ontology inputs fixed; prove their semantic payload is unchanged; test affected reader tasks. |
| Renderer or dependency update | Keep source inputs fixed initially; verify supported constructs and output fidelity before changing the source set. |

For an ontology release, match named terms by full IRI. Compare anonymous
structures with blank-node-aware correspondence, using named anchors and
subgraph isomorphism where they establish a match. Record the matching method.
Independent canonicalization followed by tuple subtraction can report unchanged
constraints as removed and added. If correspondence is ambiguous, report the
unmatched structures and that uncertainty without claiming persistent identity.
Verify the complete added and removed statement sets under that correspondence,
including empty sets, rather than their counts alone.

Separate added, removed and deprecated terms from label or definition changes.
Check changed constraints, module memberships, dependencies and cross-module
edges. Retest with an unrelated anonymous constraint added: the unchanged
constraint must retain its meaning, and old anonymous links must still identify
the old release. Preserve named term links. If an identifier disappears, provide the project's chosen
not-found or historical view; redirect only when a recorded replacement
justifies it. Never infer equivalence from a similar label.

Update examples, counts, module descriptions and reading paths affected by the
new input. Generate figures from the new packages. Retest old deep links as
well as new terms. Compare semantic scope before accepting a renderer update
that produces fewer terms or statements.

A documentation-only update does not require changing ontology versions or
reloading stores. Preserve those assets unless the user separately authorizes
such work. Keep release publication distinct from deployment of data or
projections. A source repository may have moved beyond the release being
documented; build from the chosen release rather than an unpinned working tree.

Run sections 5 and 6 on the new candidate. Record what changed, which source it
documents, test results and remaining limitations. Keep a rollback path that
restores the previous viewer without altering the ontology.

Done when the new viewer explains the chosen release, preserved links and
changed paths have been tested, and delivery follows the agreed review process.
