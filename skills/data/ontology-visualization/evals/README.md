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

Assess that the input pin changes, the complete added and removed statement sets equal the raw source differences,
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

## Record the outcome

Record the skill commit or file hashes, evaluator, input hashes, artifact paths,
checks actually run, defects and fixes. Keep run outputs outside the skill
source. Repeat only the affected tasks after a change. Do not mark an unexecuted
task as passed.

The [2026-11-07 results](results-2026-11-07.md) record the initial trials and
focused follow-up. Re-run the applicable tasks when the method changes.
