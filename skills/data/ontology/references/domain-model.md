# Concept kinds, classes and properties

Serves Step 3. Read it before you decide what a term becomes (a SKOS concept, an OWL class, a property or a code-list value), and before you write a class or a property. The SKOS scheme itself is in `identity-taxonomy.md`, Step 3; the definition bar is in `quality.md`.

Standards: OWL 2 Web Ontology Language Primer (Second Edition), W3C Recommendation 11 December 2012, https://www.w3.org/TR/owl2-primer/; RDF Schema 1.1, W3C Recommendation 25 February 2014, https://www.w3.org/TR/rdf-schema/; SKOS Primer, W3C Working Group Note 18 August 2009, §5.2 "SKOS Concepts and OWL Classes", https://www.w3.org/TR/skos-primer/; SHACL, W3C Recommendation 20 July 2017, https://www.w3.org/TR/shacl/.

## Give every term one kind

1. **Record each term's kind in the identity table before you write it** (`templates/identity-table.md`). Take the first test that fits:

   | Kind | Test | Written as |
   |---|---|---|
   | **Code-list value** | It is one of the values a property takes from a governed list ("overdue", "lost"). | `skos:Concept` in the list's own scheme (`identity-taxonomy.md`, Step 3, rule 11) |
   | **Property** | It names a link between two things ("a loan's borrower") or between a thing and a value ("a loan's due date"). | `owl:ObjectProperty` or `owl:DatatypeProperty` (rules 5 to 8) |
   | **Class** | Consumers' records will be instances of it, and a competency question asks about their properties or links ("which copy is this loan of?"). | `owl:Class` (rule 4) |
   | **Concept** | The business names and classifies it, and no question asks about the properties of its instances: an activity in a process hierarchy, a category, a kind used only to sort things. | `skos:Concept` in the main scheme (`identity-taxonomy.md`, Step 3) |
   | **Reference individual** | A named real thing or a published parameter (one organization, the loan period a published policy sets). | An instance of a class, with a source and an as-of date (`foundations.md`, policy 2) |

   *Why:* a class asserts that its instances share properties and that its subclasses' members are its members; a SKOS hierarchy asserts only that one concept is broader than another (SKOS Primer §5.2). Typing a naming hierarchy as classes claims what the business never said; typing a records-bearing thing as a concept leaves its properties without a domain.
2. **When no test fits, or two do, put the term to the owner** with the evidence and a recommendation (`templates/decision-package.md`). *Why:* the kind decides which rules and checks apply, so a guess is a modelling decision.
3. **Give one IRI one kind.** When the business needs the same word as an activity in the hierarchy and as a class that records instantiate ("lending" the activity, "Loan" the record-bearing thing), mint two IRIs and link the class to the concept with `rdfs:seeAlso`. *Why:* each kind keeps its own rules (one parent per concept; a domain and range per property), and a reader never has to ask which meaning a triple uses.

## Classes

4. **Write each class with `rdfs:label` and `skos:definition` (tagged), a definition in the "thing" form of the quality bar (`quality.md`), and `rdfs:subClassOf` only where every member of the subclass is, by the business's own rule, a member of the parent.** Declare disjointness only where the business guarantees it (`foundations.md`, conceptual modelling, rule 6). *Why:* a subclass axiom makes a reasoner infer membership, so an unearned one puts things in the wrong class without an error.

## Properties

5. **Give each property exactly one kind:** `owl:ObjectProperty` when the value is a thing with an IRI (a member, a copy, a code-list value), `owl:DatatypeProperty` when it is a literal (a date, an amount). Never a bare `rdf:Property` and never one IRI as both. Name it with a verb or a role noun read from the domain ("borrower", "loanOf", "dueDate"), in the direction you store (`promotion.md`, rule 8). *Why:* validation and every downstream load decide relationship or value from the kind (`lpg-projection.md`, rule 1).
6. **State one `rdfs:domain` and one `rdfs:range` per property, and only where every use meets them.** RDF Schema 1.1 (§3.1, §3.2): where a property has more than one domain, "the resources denoted by subjects of triples with predicate P are instances of all the classes stated by the rdfs:domain properties". So two domains mean "both", not "either": where a property applies to two classes, give it a shared parent class as its domain, or make two properties. Use a concrete datatype as the range of a datatype property (`xsd:date`, `xsd:decimal`, `xsd:string`, `xsd:dateTimeStamp`), never `rdfs:Literal`; use `skos:Concept` as the range of a code-list property and name the scheme in its shape. *Why:* a domain and a range infer types; they never reject data, so a wrong one silently retypes things.
7. **Check each property's use with a SHACL shape, not with OWL restrictions:** one node shape per class, one property shape per property, with `sh:class` or `sh:datatype`, and a cardinality (`shacl.md`, rule 5). A code-list property's shape lists the allowed values or checks the scheme (`shacl.md`, rule 4). *Why:* OWL follows the open-world assumption: "in the case of an OWL 2 document it may simply be missing (but possibly true)" (OWL 2 Primer, §2 "What is OWL 2?"), so an OWL cardinality never flags a missing value, and a SHACL shape does.
8. **Write each property with `rdfs:label`, `skos:definition` in the "property" form of the quality bar, and its domain and range**, and trace it to a competency question (`regression.md`, rule 1). *Why:* a property no question needs is scope nobody asked for.

## Records stay out

9. **Define the class, not its instances.** The ontology holds `Loan`, its properties and its shapes; the loans themselves live in the lending system (`foundations.md`, policy 2). Ship one illustrative instance per class only inside a shapes test, marked as an illustration (`provenance.md`, rule 6). *Why:* an instance in the ontology is a record that goes stale the next day.

`templates/ontology-skeleton.ttl` shows each kind for a library (concepts, a code list, three classes, four properties); `templates/shapes-skeleton.ttl` shows their shapes. `scripts/check_taxonomy.py` checks the mechanical part of rules 4 to 6 and 8.
