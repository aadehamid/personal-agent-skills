# Surveying and reusing public ontologies

Serves Step 0, and the external mappings applied at later steps (Steps 5 and 7). Read it at Step 0, when applying a mapping, and whenever the user asks whether an existing ontology, vocabulary or code list covers part of the scope.

## Where to look

1. Sector standards bodies: code lists and data-exchange standards (product codes, item identifiers, circulation protocols).
2. Published domain ontologies: GitHub, ontology portals, Linked Open Vocabularies (https://lov.linkeddata.es/).
3. Registries and authority files: legal entities and their ownership (for example GLEIF Level 2), places, standard identifiers.
4. W3C and community vocabularies: ORG, PROV-O, P-Plan, DCAT, OWL-Time, QUDT, SOSA/SSN.

Search the web for the domain plus "ontology", "OWL", "vocabulary" and "code list".

## Assess each candidate

| Point | Question |
|---|---|
| Scope fit | Which of your competency questions or concepts does it cover? |
| Licence | May you link to it, copy terms, redistribute? Read the licence or end-user agreement itself, not a summary. |
| Maintenance | Date and version IRI of the last release; who maintains it? |
| Upper ontology | Does it pull in BFO or another foundation you would also have to adopt? |
| Size | How much of it would you never use? |

## Choose one treatment

- **Map (the default):** keep your own term and add `skos:exactMatch` (same meaning) or `skos:closeMatch` (near enough for retrieval). *Why:* you gain the source's authority without its structure; importing usually brings an upper ontology or a large model you must keep consistent, and the extra structure answers none of your competency questions.
- **Import:** only a small, stable, openly licensed source you would otherwise rebuild term for term.
- **Ignore:** record why. *Why:* nobody repeats the search.

## Rules

1. **Record every source in a register:** coverage, licence, version, treatment, and the step where you apply it. Apply each mapping at its step, not all at once. *Why:* a mapping needs the local concept it points from, which a later step builds.
2. **Use W3C vocabularies by IRI**, without importing them (`org:Role`, `prov:Activity`). *Why:* consumers read them with no mapping, and the import brings nothing a question needs.
3. **Map a registry by identifier:** the registry ID as an identifier on your node, with `rdfs:seeAlso` to its record. Where the registry lacks the relation you model, say so in a note. *Why:* the identifier is checkable, and the note stops a reader expecting a registry relation that does not exist.
4. **Check what a standard's licence allows before you map to it.** Pointing to a code by its identifier uses a standard without changing it; copying its code lists into the ontology may need its legends, or be forbidden. *Why:* many sector standards license use but not modification or derived works.
5. **Map only between things of the same kind.** A business process is not a BFO-typed class of logistics process, facility or shipment; a SKOS match between them claims a meaning match no source checks. Park such a mapping with a trigger (a concept layer of the matching kind, or a consumer that needs the external terms). *Why:* a cross-kind match is read as equivalence.
6. **Park a mapping that has no local concept to point from yet,** with a trigger naming the concept or module that will bring it. *Why:* a mapping without a local end cannot be stated.
7. **Cite each mapped source with its version or version IRI and the date you checked it.** *Why:* external ontologies change, and a mapping is correct only against the version you read.
8. **Record a gap as a finding when nothing covers an area; never stretch a neighbouring ontology to fill it.** *Why:* public ontologies often cover one part of a sector well and leave the rest bare, and a stretched mapping misleads.

## Done when

Every surveyed source has a recorded treatment, licence, version and target step, and every gap is recorded as a finding.
