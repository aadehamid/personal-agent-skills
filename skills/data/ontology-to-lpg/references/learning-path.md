# Learning path: the W3C skills a clean projection needs

Read it when the user asks what to learn before modelling for a property graph, or asks for practice exercises. Thirteen skills in priority order: ★★★ is needed for the five design rules, ★★ is important, ★ is good to know. About six to eight weeks at a few hours a week. Exercises use the library example in `design-rules.md`.

| # | Skill | Priority | Supports |
|---|---|---|---|
| 1 | RDF data model and IRIs (triple terms for Rule 4b) | ★★★ | Rules 3, 4 |
| 2 | Turtle and N-Triples (reifier syntax for Rule 4b) | ★★★ | Rule 4; serialise |
| 3 | RDFS: classes, properties, domain and range | ★★★ | Rule 1 |
| 4 | OWL 2: property kinds, the EL profile, reasoning | ★★★ | Rule 1; reason |
| 5 | XSD datatypes and literals | ★★★ | Rule 1; the type table |
| 6 | SHACL Core | ★★★ | Rule 2; check; verify |
| 7 | SPARQL (CONSTRUCT; triple terms for Rule 4b) | ★★ | serialise |
| 8 | Modelling patterns: n-ary relations, qualified relations, reification | ★★ | Rule 4 |
| 9 | SKOS for taxonomies and labels | ★★ | add-on B |
| 10 | Standard vocabularies: QUDT, PROV-O, OWL-Time | ★ | add-ons E, F |
| 11 | Canonicalisation and graph comparison | ★ | verify |
| 12 | Neo4j modelling and n10s | ★★★ | load |
| 13 | Research background: S3PG and PG-Schema | ★ | Rules 1, 2; add-on H |

## What to master, with one exercise each

1. **RDF and IRIs.** The four kinds of term (IRI, literal, blank node and, in RDF 1.2, triple term, allowed only as an object); asserting a triple against only reifying it; why blank nodes break determinism. *Exercise:* model one work with two authorships (author, then illustrator) as two qualified-relation nodes, and explain why the graph gets two `:lib__Authorship` nodes. Sources: RDF 1.2 Primer and Concepts; W3C "Cool URIs for the Semantic Web".
2. **Turtle and N-Triples.** Prefixes, the `;` and `,` shorthands, typed and tagged literals; for 4b, `<<( s p o )>>`, `~ reifier` and `{| ... |}`. *Exercise:* write the authorship in Turtle, convert it to sorted N-Triples, and confirm the sorted file does not change between runs. Sources: RDF 1.2 Turtle and N-Triples; Jena RIOT.
3. **RDFS.** `rdfs:domain` and `rdfs:range` infer types; they do not restrict. Use SHACL to restrict. *Exercise:* give `lib:copyOf` the domain `lib:Copy` and predict what a reasoner infers for a subject that is not typed as a copy. Source: RDF Schema.
4. **OWL 2.** The three property kinds (Rule 1); classes and named individuals; property characteristics the graph does not enforce; open world against closed world; the EL profile and ELK. *Exercise:* reason over the library module with ROBOT and ELK, and build `inferred.nt` by the set difference in `pipeline.md`, rule 6. Sources: OWL 2 Primer and Profiles; ROBOT `reason`.
5. **XSD.** Lexical form against value (`"01"^^xsd:integer` equals `"1"^^xsd:integer`); timezones; decimal precision against float; language tags. *Exercise:* write a shape that rejects an `xsd:dateTime` without a timezone. Sources: XML Schema 1.1 Part 2; the Cypher Manual's values and types.
6. **SHACL.** Node and property shapes, `sh:targetClass`, the cardinality, datatype, class, node-kind, `sh:in` and `sh:pattern` constraints; reports and severities; which constraints n10s runs (`pipeline.md`, rule 13). *Exercise:* write the authorship shape (an IRI, exactly one agent, exactly one inverse link from a work) and make it fail once on purpose. Sources: SHACL; pySHACL; *Validating RDF Data* (Labra Gayo and others).
7. **SPARQL.** SELECT, CONSTRUCT, ASK, FILTER, OPTIONAL, EXISTS, BIND; for 4b, `SUBJECT()`, `PREDICATE()`, `OBJECT()`, `isTRIPLE()`. *Exercise:* derive the direct edge `work lib:createdBy person` from the authorship nodes with one CONSTRUCT. Sources: SPARQL 1.1 and 1.2 Query.
8. **Modelling patterns.** The test in `design-rules.md`, rule 4: a link with its own identity or lifecycle is a domain class; a link that only carries facts is a Rule 4 case. *Exercise:* model a loan both as a qualified relation between a member and a copy and as a `lib:Loan` domain class, and write down why fines and renewals need the class. Source: W3C Note "Defining N-ary Relations on the Semantic Web".
9. **SKOS.** Concepts, schemes, preferred and alternative labels, broader and narrower, mappings; when a term is a concept and when a class. Sources: SKOS Primer and Reference.
10. **Standard vocabularies.** QUDT for units, PROV-O for provenance, OWL-Time for validity periods; search Linked Open Vocabularies before inventing a term.
11. **Comparison.** RDF Dataset Canonicalization (RDFC-1.0); rdflib `to_isomorphic` and `graph_diff`. *Exercise:* diff a graph against itself after a shuffle and get an empty result.
12. **Neo4j and n10s.** Labels, relationship types, properties and constraints; n10s configuration, import, validation and export; APOC's `apoc.merge.relationship` and `apoc.coll.sort`. *Exercise:* run the load and verify steps end to end on the library module. Sources: Neo4j GraphAcademy (data modeling and Cypher fundamentals); the neosemantics documentation.
13. **Research background.** S3PG (Kashif Rabbani, Matteo Lissandrini, Angela Bonifati and Katja Hose, "Transforming RDF Graphs to Property Graphs using Standardized Schemas", *Proceedings of the ACM on Management of Data* 2(6), article 242, December 2024, https://doi.org/10.1145/3698817) converts RDF graphs to property graphs driven by their SHACL shapes, emitting PG-Schema, and reports lossless transformation where other methods lose query answers. PG-Schema (Renzo Angles and others, "PG-Schema: Schemas for Property Graphs", *Proceedings of the ACM on Management of Data* 1(2), article 198, June 2023, https://doi.org/10.1145/3589778) proposes a schema language for property graphs, motivated, as its abstract says, by the ISO standardisation of GQL; Cypher 25's `GRAPH TYPE` (add-on H) states a subset of the same ideas. Neither is a tool this skill runs: read them for why shapes, not the OWL axioms, decide value against relationship (Rules 1 and 2), and for what add-on H's `GRAPH TYPE` can and cannot state. *Exercise:* write by hand the PG-Schema node type for `lib:Copy` from its shapes and compare it with what `build.py graph-type` prints.

## Flashcards

- A literal object becomes? A node property. An IRI object? A relationship.
- Two qualified-relation nodes for one link (4a) give how many graph nodes? Two. Two reifiers of one triple (4b) give how many relationships? Two.
- Which SHACL property decides one value or an array? `sh:maxCount`.
- Why must qualified-relation nodes and reifiers be IRIs? The IRI becomes the stable `uri` in the graph.
- What does Neo4j not do that OWL needs? Open-world reasoning.
- How does n10s match `sh:pattern`? Against the whole string, so anchor every pattern and check patterns before the load.
