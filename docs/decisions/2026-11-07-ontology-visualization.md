# A reusable ontology visualization skill

Status: Decided  
Date: 2026-11-07

## Context

The current ontology-viewer work provides a method that can be reused in other
domains. The owner asked to add that method to this repository as a skill and
playbook. The source request is saved in
[the answers file](2026-11-07-visualization-answers.md).

## Decision

Create a visualization skill in the personal skills repository. Include a
visualization playbook for building from scratch and updating after each
release. Apply the process across domains, capturing the method from the
current ontology-viewer work.

## Implementation choices

The agent chose the name `ontology-visualization` and the `data` category.
The playbook covers reader tasks, RDF fidelity, layers and connections,
construction, testing, delivery and later updates. Neutral Catalog and Lending
fixtures exercise it without carrying a consuming project's ontology or
private identifiers into the skill. These are implementation choices within
the request, not further decisions attributed to the owner.

## Alternatives considered

Keeping the method only in the consuming project would not provide the
requested reusable skill. A fixed renderer or copied application would narrow
the method to one implementation; neither is required by the request.

## Recorded words

From [the answers file](2026-11-07-visualization-answers.md):

> can you add to the goal that. We should also create a visualization skill in my personal akill repo. It should alos contains visualization playbook, which will include how to build the visualization from sratc and how to update visualization after each release. This should apply in any domain. The intent is to captured how we have visualize the ntology in this repo. So that we have something resuable to do the same and follow the same process everytime

## Evidence

The skill's `SOURCES.md` identifies the RDF standards and design references.
Its evaluation tasks cover a new viewer, a new ontology release and an additive
documentation update. The pull request records the observed results and limits.
