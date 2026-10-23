# Design rules: what the ontology must do so the projection needs no guesses

Serves the design step. Read it before an ontology that will be projected is modelled, or before its first release. A rule adopted after a release forces a new release of every module that breaks it. Examples use a library: works, people, copies, loans. Base `https://id.example.org/library/`, prefix `lib:`.

## What the projection keeps

| Kept | How |
|---|---|
| Every individual, type, literal value and link | Nodes, labels, properties, relationships |
| Facts about one link (a role, an order, a source, a validity period) | Properties of a qualified-relation node (Rule 4a), or of a relationship (Rule 4b) |
| Class and property hierarchy, domains and ranges | Schema nodes from `n10s.onto.import`; in SHORTEN mode `:n4sch__Class`, `:n4sch__Relationship` and `:n4sch__Property`, linked by `n4sch__SCO`, `n4sch__DOMAIN` and `n4sch__RANGE` |
| Cardinality and constraints | SHACL: every shape before the load, and the subset the engine can run inside the graph (`pipeline.md`) |
| A full round trip back to RDF | An automated diff (`pipeline.md`, verify) |

**Not kept:** OWL reasoning (open world, complex class expressions, property chains). Neo4j has no reasoner. The pipeline runs one first and loads its inferences as data. The axioms stay in the Turtle files, which stay the master copy.

## Mental model

```
literal object            -> node property
IRI object                -> relationship
rdf:type                  -> label
qualified-relation node   -> node with its own IRI, linked to both ends (Rule 4a)
reifier (rdf:reifies)     -> properties on that relationship (Rule 4b)
everything else           -> stays in the Turtle files
```

## The five rules

Each rule can be checked by a script; `scripts/check_projection_rules.py` checks Rules 1, 2, 3, 4a and the Rule 5 names.

1. **Give every property you own exactly one kind, and every object or datatype property one concrete range.** The kinds are `owl:ObjectProperty`, `owl:DatatypeProperty` and `owl:AnnotationProperty`. n10s itself decides from each value, not from the kind: an IRI value loads as a relationship and a literal as a node property, so an annotation property with IRI values (`rdfs:seeAlso <...>`) loads as relationships. The kind and range are what the checks, the multivalued list and the XSD to Cypher table read. A concrete range is one IRI: for a datatype property, a datatype in the XSD to Cypher table below (an unlisted XSD type, `rdf:HTML` or a custom `rdfs:Datatype` fails); for an object property, a class; never `rdfs:Literal` or `rdfs:Resource`, never a bare `rdf:Property`. An annotation property needs no range. A property counts as yours when its IRI is in one of your namespaces and it is used as a predicate, declared with a property kind, or given a domain, a range or a parent property. Prefer zoned `xsd:dateTimeStamp` for timestamps. *Why:* the checks, the multivalued list and the XSD to Cypher table read the kind and the range; with one of each, every value of the property is either an IRI (a relationship) or a literal of one type (a property of one Cypher type, table below). A vague range lets values of both sorts in, and the property then loads as relationships for some subjects and properties for others.

   ```turtle
   lib:barcode   a owl:DatatypeProperty ; rdfs:range xsd:string .   # literal values: a node property
   lib:copyOf    a owl:ObjectProperty   ; rdfs:range lib:Work .     # IRI values: a relationship
   lib:shelfNote a owl:AnnotationProperty .                         # literal values here: a node property
   ```

2. **State a cardinality for every property you own in SHACL:** `sh:maxCount 1` for a single value; `sh:minCount` with no `sh:maxCount` for a list (write `sh:minCount 0` for an optional list, so the choice is stated). Annotation properties too. The cardinality counts only on a property shape that an applied shape uses: one with any target (`sh:targetClass`, `sh:targetNode`, `sh:targetSubjectsOf`, `sh:targetObjectsOf`, a SHACL-SPARQL `sh:target`), one that is itself a class, or one reached from those through `sh:node`, `sh:and`, `sh:or` or `sh:xone`. A loose shape with the same `sh:path` states nothing. The check covers the properties the data uses; a property declared but not yet used loads nothing, so it needs its cardinality only once data uses it (the `ontology` skill's shape rules still ask for it at release). *Why:* `sh:maxCount 1` loads one value and anything else loads a sorted array; the loader's list of multi-valued properties is generated from the shapes, so an unstated cardinality is a guess.

   ```turtle
   lib:CopyShape a sh:NodeShape ; sh:targetClass lib:Copy ;
     sh:property [ sh:path lib:barcode ; sh:datatype xsd:string ; sh:minCount 1 ; sh:maxCount 1 ] ;
     sh:property [ sh:path lib:copyOf  ; sh:class lib:Work ; sh:minCount 1 ; sh:maxCount 1 ] .
   lib:WorkShape a sh:NodeShape ; sh:targetClass lib:Work ;
     sh:property [ sh:path lib:altTitle ; sh:datatype rdf:langString ; sh:minCount 0 ] .   # a sorted array
   ```

3. **Give every individual a permanent IRI, put no blank node in the data, and register one fixed prefix per namespace.** Never generate IRIs per run. Qualified-relation nodes and reifiers need IRIs most, because the IRI becomes the node's or relationship's `uri` in the graph. Register a prefix for every namespace a predicate or a class uses, your own and the standard ones, wherever the class appears: as a type, a declared class, a superclass, a domain or range, or a shape's target or `sh:class`. A datatype range counts too, so `xsd:` needs its prefix; and never two prefixes for one namespace. *Why:* in SHORTEN mode n10s names a term by its namespace's prefix, two underscores and the local name (`lib__barcode`), and invents a numbered `ns` prefix for a namespace it does not know; fixed prefixes make the names the same on every load.

4. **Choose one pattern for links that carry properties, record it, and use it everywhere.** Rule 4 covers a link whose only job is to carry facts about one relationship. A link the business tracks as a thing in its own right is a domain class instead, outside Rule 4: it has its own identity or lifecycle, and other records refer to it. A `lib:Loan` is one: it has a loan number, and fines and renewals point at it. *Why:* mixing patterns makes the conversion code guess which one a link uses.

   **4a, the default: qualified-relation nodes.** The link becomes a node with its own IRI that points at both ends, the pattern of W3C ORG's `org:Membership` and PROV-O's qualified relations. It is plain RDF, so rdflib, pySHACL, Jena, RDF4J and n10s all read it, and it needs no flatten step.

   ```turtle
   <https://id.example.org/library/authorship/W-0042-P-17> a lib:Authorship ;
       lib:authorshipAgent <https://id.example.org/library/person/P-17> ;
       lib:creatorRole lib:illustrator ;
       lib:position 2 ;
       lib:source "Catalogue record 0042, field 700" .
   <https://id.example.org/library/work/W-0042> lib:hasAuthorship <https://id.example.org/library/authorship/W-0042-P-17> .
   ```

   In the graph this is a `:lib__Authorship` node with its properties, a relationship to the person, and one from the work.

   - **Give each qualified-relation node exactly one value for each end**, with `sh:minCount 1 ; sh:maxCount 1` on each end's property in a shape that targets the qualified-relation class. The checker fails when that shape is missing, even while the data happens to hold one value.
   - **An end may point at the node instead, by an inverse link** (`lib:hasAuthorship` above, like `prov:qualifiedAssociation` or `org:hasMembership`). Count that link as the end, check that exactly one such link points at each node, and shape it from the node's side with `sh:path [ sh:inversePath lib:hasAuthorship ] ; sh:minCount 1 ; sh:maxCount 1`. n10s runs that inverse-path shape in the graph. *Why:* the arcs that define the node are not domain links, and the inverse form is the one PROV-O and ORG use.
   - **Register every qualified-relation class with its ends** in the projection's configuration (`inputs.md`, rule 3), and add each new one when a module defines it. *Why:* the rule check finds the nodes by their class.
   - If a consumer also wants a direct edge (`work lib:createdBy person`), assert that triple too, or derive it with a SPARQL CONSTRUCT before the load. Never hand-write it in Cypher.
   - Choose 4a while any tool in the pipeline lacks RDF 1.2 support.

   **4b: RDF 1.2 reifiers.** Use it only when every tool that reads and validates the data reads RDF 1.2 triple terms: Apache Jena 6.1.0 or later, or Eclipse RDF4J 6.0.0 or later. Jena 5.4.0 to 6.0.x was an experimental preview. rdflib and pySHACL do not read RDF 1.2, so a Python pipeline built on them uses 4a. n10s cannot load triple terms, so 4b needs the flatten step in `pipeline.md`. RDF 1.2 Concepts is a W3C Candidate Recommendation (Snapshot, 7 April 2026), not yet a Recommendation.

   ```turtle
   <https://id.example.org/library/work/W-0042> lib:createdBy <https://id.example.org/library/person/P-17>
       ~ <https://id.example.org/library/authorship/W-0042-P-17> {| lib:position 2 |} .
   ```

   Rules for reifiers: one reifier gives one relationship, which carries the reifier's `uri`; two reifiers of one triple give two parallel relationships, never merged; an asserted triple with no reifier gives one plain relationship; a triple term that is not asserted gives a relationship with `asserted: false`, or is left out by a recorded exclusion (`add-ons.md`, D); a reifier's properties are literal-valued, and a link to another resource is stored as a string property such as `approvedBy_uri`, which the round trip restores.

5. **Name the graph explicitly only where the SHORTEN name is not good enough, through one annotation property (`lpg:name`), and check that no two terms share a name.** n10s applies such mappings only in MAP mode, and the pipeline uses SHORTEN (`pipeline.md`, rule 9). So add the names as a generated, idempotent rename after the load, before verify, and reverse it before the round-trip export. *Why:* MAP mode breaks in-graph SHACL in n10s (neosemantics issue #237, open since 2021-11-09; its fix, PR #361, is open), and without the rename every name is already unique by construction.

## Where the Rule 4 choice is recorded

**Record the Rule 4 option and its reason in the projection policy, and copy both into the configuration's `rule4` and `rule4_reason`.** The projection policy is the project's written decision to project the ontology into a property graph. Any recorded place that holds the option and its reason counts: for an ontology built with the `ontology` skill, policy 10 (target formats) in its `templates/policies.md`; otherwise a decision record the owner approved, or the project's own method. For the library example, the policy is the template configuration's `rule4` and `rule4_reason`. *Why:* the policy is the decision, and the configuration is the copy the scripts read; every script of this skill (`check_projection_rules.py`, `validate_data.py`, `build.py cypher`, `load_verify.py`) stops with exit 2 under `4b`, because each reads RDF 1.1 only.

## OWL profile

**Keep reasoning within OWL 2 EL**, and run ELK (`pipeline.md`, reason). EL has no inverse properties: store one direction per fact, and materialise the inverse before the load if consumers need it. *Why:* EL reasoning is fast and predictable on large hierarchies, and a property graph does no reasoning of its own.

## XSD to Cypher types (fixed)

| XSD | Cypher |
|---|---|
| string, token, normalizedString | STRING |
| boolean | BOOLEAN |
| integer, long, int, nonNegativeInteger | INTEGER (64-bit, range-checked) |
| double, float | FLOAT |
| decimal | FLOAT, or STRING with add-on C. Refuse a decimal whose value, printed as a double, is not its own lexical form (0.64 passes; 0.1000000000000000055 does not), or adopt add-on C |
| date | DATE |
| dateTimeStamp, or dateTime with a timezone | ZONED DATETIME |
| dateTime without a timezone | LOCAL DATETIME (better: forbid it in SHACL) |
| duration | DURATION |
| anyURI | STRING |
| rdf:langString, rdf:dirLangString (RDF 1.2) | STRING with the tag kept inside it (`keepLangTag`), or add-on B |
