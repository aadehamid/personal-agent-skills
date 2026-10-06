# Projecting an ontology into a labelled property graph

Read this when the ontology will be loaded into Neo4j or another labelled property graph (LPG). The design rules apply from Step 1, the pipeline at Step 12. The full guideline is Hamid's Ontology_to_LPG_Conversion_Playbook v2.1: https://github.com/aadehamid/enterprise-people-graph/tree/main/guideline_to_map_ontology_to_LPG. Turtle stays the master copy.

## Mental model

```
literal object     -> node property
IRI object         -> relationship
rdf:type           -> label
qualified relation -> node with its own IRI, linked to both ends
everything else    -> stays in the Turtle files
```

## Design rules

1. **One kind and a concrete range per property.** Object, datatype or annotation property; never bare `rdf:Property` or `rdfs:Literal`. Prefer zoned `xsd:dateTimeStamp`.
2. **SHACL cardinality on every property.** `sh:maxCount 1` gives a single value; no maximum gives a sorted array.
3. **Stable IRIs, no blank nodes, fixed prefixes.** Every individual and every qualified-relation node gets a permanent IRI. Register each prefix once.
4. **Relationship properties go on qualified-relation nodes: the guideline's Rule 4 option 4a, its default.** Pick one Rule 4 option for the whole ontology. Option 4b, RDF 1.2 reifiers, fits when the tools that read and validate the source data (Jena 6.1.0+ or RDF4J 6.0.0+, with a SHACL engine that reads triple terms) can read triple terms; the pipeline then flattens them before n10s, which cannot load them. A link the business tracks as a thing in its own right (its own lifecycle or identity, referred to by other records) is a domain class, an ordinary node outside Rule 4. The arcs that define a qualified-relation node do not count toward that test: its links to its two ends, and an inverse such as `prov:qualifiedAssociation` or `org:hasMembership`. Why 4a here: as of October 2026, RDF 1.2 is a W3C Candidate Recommendation, rdflib and pySHACL do not support it (Jena 6.1.0+ and RDF4J 6.0.0+ do), and n10s does not read it. A qualified-relation node needs none of that and loads as an ordinary node, so the guideline's flatten queries are unnecessary. Revisit when the toolchain supports RDF 1.2.
5. **Explicit LPG names where the local name is not good enough**, through one annotation property (`lpg:name`), with a CI check for name collisions.

Keep reasoning within the OWL 2 EL profile. EL has no inverse properties: store one direction per fact and materialize inverses before loading if consumers need them.

## Pipeline

1. **Check.** Meta-shapes over the ontology (the five rules) and data shapes over the data. Any violation stops the build.
2. **Reason.** ELK via ROBOT, once, upstream (`robot reason ... --output reasoned.ttl`).
3. **Serialise.** Write two sorted N-Triples files: `loadable.nt` (the asserted data) and `inferred.nt` (the IRI-only `rdf:type` and `rdfs:subClassOf` triples in the reasoner's output that are not in its input). Two files keep assertions and inferences apart; inside Neo4j they merge, because n10s keeps no graph names.
4. **Load.** n10s with a generated config: fixed prefixes, generated name mappings, `handleMultival: ARRAY` with the list from `sh:maxCount`, language tags kept. Order: ontology, shapes, `loadable.nt`, `inferred.nt`. Every statement uses MERGE/SET with explicit ordering. Above roughly 10M triples, generate CSVs from the same mapping and use `neo4j-admin database import`.
5. **Verify.** In-graph SHACL with zero violations; export and diff back to RDF (against `loadable.nt` plus `inferred.nt`) with zero lost and zero added triples; load twice into clean databases with shuffled input and compare graph hashes.

Done when: all three verify checks pass on the published release.

## Anti-patterns

Relying on n10s defaults; blank-node identities; hand-written Cypher that is not generated from the ontology; expecting Neo4j to reason; treating Neo4j as the master copy.
