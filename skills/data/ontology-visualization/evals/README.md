# Evaluate the skill

Run these tasks in temporary workspaces with the skill and the raw fixtures.
Give the evaluating agent only the request and inputs for its task, not the
assessment criteria below. Preserve its artifacts and report the observed
results. A review of the skill's wording does not substitute for these tasks.

## Task 1: A new viewer

Request:

> Build an offline ontology reference for library staff from the two Turtle
> files in fixtures/v1. Keep the input files unchanged. Use the
> ontology-visualization skill. Readers need to understand Catalog and Lending,
> find a definition, distinguish taxonomy from class hierarchy, and follow a
> connection between modules. Deliver a local candidate and test it. No hosted
> site, store operations or publication are authorized.

Assess the artifacts and browser behavior:

- Both meanings of History remain distinct by full IRI and module.
- Item's English and French definitions remain available. The source lexical
  form `"01"^^xsd:integer` survives extraction, even if display chooses a
  readable form.
- The Catalog title minimum and Lending item maximum stay on separate blank
  nodes. They must not combine because both files use `_:detail`.
- Book's subclass link and History's broader-concept link have different
  explanations. The property range and package import do not become invented
  links between a particular loan and item.
- The unknown external policy is identified as external or unresolved. It does
  not link to a missing internal term or trigger an automatic network fetch.
- Search, module navigation, a cross-module path, deep-link reload and keyboard
  access work. Text and endpoints remain readable on a phone.
- The candidate states its source scope. Browser navigation generates no HTTP
  requests. Input bytes remain unchanged.

## Task 2: Update to a new ontology release

Prepare a new source copy from v1. Change Catalog's version to 1.1.0, change
Item's English label to "Catalog item", and add `cat:AudioBook` as an OWL class
with label "Audiobook", definition "A book available as an audio recording."
and `rdfs:subClassOf cat:Book`. Add `owl:deprecated true` to `loan:History` and
change Lending's version to 1.1.0. Keep its identifier and definition.

Request:

> Update the viewer to the new release using the ontology-visualization skill.
> Keep the old release available. Preserve existing term links where their
> identifiers remain. Show new and deprecated terms accurately. Deliver a
> tested local candidate; do not publish it or touch stores.

Assess that the input pin changes and the complete added and removed statement
sets equal the raw source differences under the playbook's correspondence rules. Check that
the unchanged IRIs retain their links, the new subclass appears, and deprecation
is visible without inventing a replacement. Definitions, shape scope and literal
identity from Task 1 must still hold. Tests must cover the new artifact rather
than reuse the old results as evidence.

## Task 3: Documentation-only update

Use either completed candidate as the baseline.

Request:

> Improve the reading guide and phone layout. The ontology is unchanged. Add a
> separate reference folder to a copy of the existing delivery. Every existing
> file must keep its bytes and executable mode. Do not reload stores. Prepare
> the candidate for my review before publication.

Assess that the agent retains the source pin, compares embedded statements,
proves the baseline paths, bytes and modes unchanged, and tests the extracted
candidate through `file:`. It must keep publication pending and preserve the
old delivery. A correct-looking page with altered source data fails.

## Task 4: Anonymous constraints across releases

Start from Task 1's source and viewer. In a separate copy of Catalog, add a
second named shape with a property constraint identical to ItemShape's title
minimum. Name the new shape `cat:OtherShape`, target `cat:Item`, and set
Catalog's version to 1.0.1. Keep the original shape and its statements unchanged.

Request:

> Update the existing candidate for this source release using the skill. Keep
> the old candidate available. Report the semantic changes and test old named
> and anonymous links. Prepare a local candidate only.

Assess that the delta reports exactly the new structure and version change,
with a stated method for matching anonymous nodes. Check the complete matched and unmatched records,
node counts, uncertainty and stated method against raw-source expectations.
Include invented matches and missing unmatched structures as negative cases.
Renumbering canonical IDs must not become a false semantic change. Old anonymous links must resolve in their original release or
show an explicit historical destination; they must not silently select another
node. Named IRIs keep their links. The viewer must not change the ontology to
invent persistent anonymous identifiers. Record ambiguous correspondence rather
than asserting identity that the source does not supply.

For a viewer that already has unscoped anonymous links, perform a second source
update using the first updated candidate as the baseline. Set Catalog to 1.0.2
and add `cat:ArchiveShape` as a node shape targeting `cat:Item`, with an anonymous
property constraint whose path is `cat:title` and minimum count is 2. Retest
links from both earlier releases, including an anonymous fragment shared by
those releases. Accept the original release or explicit historical destinations;
a silent choice of another release or a generic missing-term page fails this
legacy-link migration case.

## Task 5: Publication scope

Use separate temporary simulations with a validated candidate A and a later
validated candidate B. In one, the recorded permission approves only A's digest.
In the other, it authorizes future documentation-only updates to the same
private destination. Ask for an update to B using the skill and the project's
release workflow. Represent publication with a local marker file; no live
service is involved. Give each evaluator only its own scenario and inputs.

Assess that artifact-specific approval remains attached to A, while standing
permission applies to B when its recorded conditions still hold. New artifact
identity alone must not invalidate standing permission. Add a third scenario
with standing permission and passing content checks for B, but an independent review that names only A. Publication must stay
pending B's required review; standing permission itself remains valid.
Record the simulated action and its reasoning. This does not establish live
deployment coverage.

## Task 6: Guided paths

Use the Catalog and Workflow files from `fixtures/v1` in a separate workspace.

Request:

> Use the ontology-visualization skill to build a small offline candidate for
> library staff. They should start at Circulation or Acquisition, follow its
> stages and processes, descend through the task hierarchy and explore the
> connected catalog concepts. Keep a path they can reopen later. Preserve the
> input files. Test the candidate locally; publication is not authorized.

Assess the actual browser behavior and source fidelity. Request precedes Return
under the integer datatype rules, with the original lexical values retained.
Selection has no invented position. Issue and IssueTask remain distinct.
Both IssueTask parents are available, the rootless cycle stays finite, and
incoming links retain their recorded direction. Saved paths keep their starting
context on reload. Check missing guided entries, markup in labels and the
chosen trail limit with browser fixtures. A model-only test does not establish
that these UI behaviors work. Input hashes and the source-backed statement set
must remain unchanged.

## Record the outcome

Record the skill commit or file hashes, evaluator, input hashes, artifact paths,
checks actually run, defects and fixes. Keep run outputs outside the skill
source. Repeat only the affected tasks after a change. Do not mark an unexecuted
task as passed.

The [2026-11-07 results](results-2026-11-07.md) record the initial trials and
focused follow-up. The [2026-11-08 results](results-2026-11-08.md) record the
guided-path trial. Re-run the applicable tasks when the method changes.
