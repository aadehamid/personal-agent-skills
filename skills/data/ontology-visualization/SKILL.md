---
name: ontology-visualization
description: Build an ontology viewer that explains terms, layers and connections, or update an existing viewer from a new release. Covers source fidelity, navigation, usability and release validation across domains.
---

# Ontology visualization

Build a readable, source-backed view of an ontology. Readers must be able to find
a concept, understand its meaning, distinguish the kinds of information shown,
and follow relationships within and between modules.

## Choose the work

- **New viewer:** read [the visualization playbook](references/playbook.md),
  sections 1 to 6. Start with a representative reading path and the actual
  source packages. Extend it to the agreed coverage after the path works.
- **Update after a release:** read playbook sections 2, 5, 6 and 7. Compare the
  old and new source sets before changing the viewer. Reuse the existing design
  where it still explains the model.
- **Usability revision with unchanged ontology:** read sections 3, 5 and 7.
  Keep the source pin fixed and prove that the semantic payload stays equal.

Before implementation, fill the applicable fields in
[the visualization brief](assets/visualization-brief.md) from repository
evidence and the user's instructions. Resolve only missing choices that affect
scope, interpretation or delivery. Existing authorization remains valid within its recorded scope. Distinguish
standing permission from approval of a particular candidate. Apply a requested
review to the candidate being released.

## Keep meaning and presentation separate

Use released identifiers and statements as the source of meaning. Give authored
guidance its own place, with links to the terms it explains. An attractive graph
is not evidence of a relationship. Every displayed arrow needs a predicate and
source, or an explicit explanation that it is a derived view.

The playbook's reading groups are a design option. Match the domain's model and
the reader's tasks. Preserve distinctions between classes, concepts,
individuals, constraints and evidence even when the interface groups them.

Choose the renderer after checking the data it supports. A class-and-property
browser may omit concepts, individuals or definitions stored in another
predicate. A reference page and an interactive graph may complement each other;
share one verified data extraction when practical. A second viewer is justified
by a distinct reader task, not by a second library being available.

## Deliver and maintain

Keep the source adapter, authored guide, presentation and tests under version
control. Keep source pins and publication details in the consuming project.
Use that project's review and release process. This skill does not authorize
ontology changes, store reloads, public hosting or publication.

Done when the agreed reader tasks pass, source fidelity and coverage are proved,
the exact delivery artifact is tested, and the release notes state its source
versions, scope and remaining limitations. A requested user review remains a
release condition. Record pending publication as pending.

For skill maintenance or a behavioral check, use
[the evaluation tasks](evals/README.md). They exercise a new viewer, an ontology
release update and a documentation-only update without requiring a particular
UI framework.
