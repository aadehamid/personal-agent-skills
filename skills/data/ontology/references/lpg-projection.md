# Projecting an ontology into a labelled property graph

Serves Step 12, and Step 1's target-format policy. Read it when the ontology will be loaded into Neo4j or another labelled property graph (LPG): the design rules apply from Step 1, the pipeline runs at Step 12. It condenses the Ontology-to-LPG Conversion Playbook, version 2.2 (October 2026), and the tool behaviour observed when the pipeline ran in October 2026. The Turtle release stays the master copy.

## Mental model

```
literal object     -> node property
IRI object         -> relationship
rdf:type           -> label
qualified relation -> node with its own IRI, linked to both ends
everything else    -> stays in the Turtle files
```

## Design rules (adopt at Step 1)

1. **One kind and a concrete range per property** (`domain-model.md`, rules 5 and 6), with `owl:AnnotationProperty` as a third kind for metadata about terms. Prefer zoned `xsd:dateTimeStamp`. *Why:* the loader decides node property or relationship from the kind, and its type from the range.
2. **A SHACL cardinality on every property** (`shacl.md`, rule 5): `sh:maxCount 1` loads a single value; no maximum loads a sorted array. *Why:* the loader's multi-value list is generated from it.
3. **Stable IRIs and no blank nodes in the data, as `identity-taxonomy.md`, Step 2, rules 3 and 5 say; one registered prefix per namespace.** *Why:* the IRI becomes the node's identity in the graph, and the fixed prefixes make the shortened names the same on every load (rule 12).
4. **Relationship properties go on qualified-relation nodes (the guideline's option 4a, its default).** Choose one option for the whole ontology. Option 4b, RDF 1.2 reifiers, fits only when every tool that reads and validates the data reads triple terms (Apache Jena 6.1.0+ or Eclipse RDF4J 6.0.0+); rdflib and pySHACL do not, and n10s cannot load them. A link with its own identity or lifecycle is a domain class, outside this rule (`foundations.md`, conceptual modelling, rule 8). *Why:* as of October 2026, RDF 1.2 is a W3C Candidate Recommendation (Snapshot, 7 April 2026), and a qualified-relation node loads as an ordinary node with no flatten step.
   - **Each qualified-relation node has exactly one value for each end.** An end may be reached by an inverse link from the end to the node (`prov:qualifiedAssociation`, `org:hasMembership`); count that link as the end, and check that exactly one such link points to each node. *Why:* the arcs that define the node are not domain links, and the guideline allows the inverse form.
5. **Explicit LPG names through one annotation property (`lpg:name`)**, with a CI check for collisions. n10s applies them only in MAP mode; in SHORTEN mode (rule 12) add them as a generated, idempotent rename after the load and reverse it in the export. *Why:* MAP mode breaks in-graph SHACL in n10s (neosemantics issue #237, open since 2021-11-09).

Keep reasoning within the OWL 2 EL profile. EL has no inverse properties: store one direction per fact and materialize inverses before the load if consumers need them.

## Inputs

6. **Project the released packages, each at its newest version, not the source files**, and run each package's own shapes plus any shapes that check the whole graph. *Why:* consumers get what was released, and the projection tests the releases, not a working tree.
7. **Apply Rules 1 and 2 to the predicates of every module namespace you own, each with its fixed prefix** (the prefix its package uses where it has one). *Why:* a rule checked on one module lets every later module break it.
8. **List each rule gap in a released module with its fix, and fail the build on an unlisted gap or on a listed gap that no longer occurs.** A gap in a released module (a property with no range, a property with no cardinality shape) can only close in that module's next release. *Why:* the list keeps the projection running without hiding the gap, and a stale entry means the list no longer describes the releases.

## Pipeline

9. **Check.** Run the meta-shapes for the five rules over the ontology, then pySHACL over the data with every shape, SHACL-AF on for SPARQL targets and constraints. Refuse any value that cannot survive the round trip: a string that ends like a language tag (`"...@en"`), and an `xsd:decimal` whose value, printed as a double, is not its own lexical form (0.64 passes; 0.1000000000000000055 does not). After the serialise step, run the shapes again over both output files together. Any violation stops the build. *Why:* this is the full check, and an inference can break a shape.
10. **Reason.** ELK through ROBOT, once, upstream (`robot reason --reasoner ELK`). *Why:* a property graph does no OWL reasoning.
11. **Serialise.** Write two sorted, de-duplicated N-Triples files: `loadable.nt` (the asserted data) and `inferred.nt`, built as the difference between the reasoner's output and its input, keeping only IRI-to-IRI `rdf:type` and `rdfs:subClassOf` triples and dropping any whose object is an OWL or RDFS built-in. Record the SHA-256 of both as the input fingerprint. *Why:* the OWL API writes declarations such as `owl:NamedIndividual` into the output, and they are not inferences; on a SKOS-first ontology the inferred file can rightly be empty.
12. **Load.** n10s with a generated configuration: `handleVocabUris: 'SHORTEN'` with the fixed prefixes, `handleMultival: 'ARRAY'` with the list generated from `sh:maxCount`, language tags kept. Load in a fixed order: ontology, in-graph shapes, `loadable.nt`, `inferred.nt`. Every statement uses MERGE/SET with explicit ordering. Above roughly 10M triples, generate CSVs from the same mapping and use `neo4j-admin database import`. *Why:* n10s 2025.06.1 imports and validates shapes only in a namespace-aware graph, and n10s defaults are not deterministic.
13. **Load only the shapes the engine can run, and record what was dropped and why.** n10s 2025.06.1 rejects `sh:datatype rdf:langString`; does not support `sh:not`, `sh:languageIn`, `sh:node`, `sh:targetSubjectsOf` or `sh:targetObjectsOf`; never runs a shape with a SPARQL target; matches `sh:pattern` against the whole string; and compares literal `sh:in` values as strings (`shacl.md`, rules 17 and 18, with the implementation lines; test each in the engine as rule 16 says). Generate the in-graph file from the full shapes: drop those constraints, then drop node shapes left without `sh:targetClass`. Keep `sh:in` lists of IRIs. *Why:* a constraint the engine cannot run reports silence, which looks like a pass. The check step's full pySHACL run (rule 9) plus an empty round-trip diff keeps the guarantee: the graph holds exactly the triples that passed every shape.
14. **Verify.**
    - In-graph SHACL returns zero violations; then remove one value a shape requires, require a violation, and restore it.
    - Export with n10s and diff against `loadable.nt` plus `inferred.nt`: zero lost, zero added. Compare values, not spellings: a plain literal equals an `xsd:string` one; integers return as `xsd:long` and decimals as `xsd:double`; a kept language tag comes back inside the string.
    - Load twice into clean databases, the second time in shuffled order, and compare graph hashes.
    *Why:* the three together show the graph is a complete, repeatable copy of what passed the check.

## Running it

15. **Pin the tools by version and checksum, and check the checksums before every run:** Neo4j, n10s, APOC and ROBOT versions in the manifest; each plugin jar's download URL and SHA-256 in the pipeline's README. *Why:* a different jar changes which constraints run and how values round-trip.
16. **Commit a report that goes stale.** Record the input fingerprint and a fingerprint of every shape file in the report. CI runs the check and serialise steps and fails when the inputs or shapes no longer match the committed report; a workstation runs reason, load and verify (they need Java and a Neo4j container). *Why:* a projection result that outlives its inputs is a false pass.
17. **Remove the container and any temporary database password after each run.** *Why:* a forgotten container with a known password is an open database on the workstation.

## Anti-patterns

Relying on n10s defaults; loading shapes the engine cannot run and reading its silence as a pass; loading the reasoner's declarations as inferences; blank-node identities; hand-written Cypher not generated from the ontology; expecting Neo4j to reason; treating Neo4j as the master copy.
