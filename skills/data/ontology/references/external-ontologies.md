# Surveying and reusing public ontologies

Read this for Step 0, and whenever the user asks whether an existing ontology, vocabulary or code list covers part of the scope.

## Where to look

1. Industry standards bodies: code lists and data-exchange standards (product codes, site codes).
2. Published domain ontologies: GitHub, ontology portals, Linked Open Vocabularies (https://lov.linkeddata.es/).
3. Legal and financial registries: organizations, ownership, consolidation (for example GLEIF Level 2).
4. W3C and community vocabularies: ORG, PROV-O, P-Plan, OWL-Time, QUDT, SOSA/SSN.

Search the web for the domain plus "ontology", "OWL", "vocabulary" and "code list". Record a gap as a finding when nothing covers an area; do not stretch a neighboring ontology to fill it.

## Assess each candidate

| Point | Question |
|---|---|
| Scope fit | Which of your competency questions or concepts does it cover? |
| License | May you link to it, copy terms, redistribute? |
| Maintenance | Date of the last release; who maintains it? |
| Upper ontology | Does it pull in BFO or another foundation you would also have to adopt? |
| Size | How much of it would you never use? |

## Choose one treatment

- **Map** (default): keep your own term; add `skos:exactMatch` (same meaning) or `skos:closeMatch` (near enough for retrieval). You gain its authority without its structure.
- **Import**: only a small, stable, openly licensed source you would otherwise rebuild term for term.
- **Ignore**: record why, so nobody repeats the search.

Record every source in a register: coverage, license, treatment, and the step where you apply it. Apply each mapping at its step.

## Done when

Every surveyed source has a recorded treatment, license and target step, and every gap is recorded as a finding.
