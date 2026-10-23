# The pipeline: check, reason, serialise, load, verify

Serves the pipeline steps. Read it before writing or changing the projection's code. The five steps work from ten triples to hundreds of millions; only the loader changes with scale (`running.md`, rule 6). The tool versions named here are the ones tested: Neo4j 2025.06.2, n10s (neosemantics) 2025.06.1 with APOC, ROBOT 1.9.10.

```
 module.ttl ──┐
 shapes.ttl ──┤  1 check  ─▶  2 reason  ─▶  3 serialise  ─▶  4 load  ─▶  5 verify
 config ──────┘   (rules,      (ELK,         (sorted N-Triples;  (n10s,      (SHACL in the graph,
                   SHACL)       once)         4b: flatten)        SHORTEN)    round trip, determinism)
```

| Purpose | Tool |
|---|---|
| Parse RDF, run SPARQL | Rule 4a: rdflib, Jena or RDF4J. Rule 4b: Jena 6.1.0+ or RDF4J 6.0.0+ |
| Reason | ROBOT (`robot reason --reasoner ELK`) |
| Validate | pySHACL (Rule 4a only; it is built on rdflib) or Jena SHACL |
| Load | n10s |
| Diff | rdflib `compare`, or Jena `rdfcompare` |

## 1. Check

1. **Check the design rules over the ontology, then validate the data with every shape, and stop the build on any failure.** Run `scripts/check_projection_rules.py` (Rules 1, 2, 3, 4a, the Rule 5 names, the release exceptions and the package pins). Then run pySHACL over the data with every shape file, with SHACL-AF on (`advanced=True`) when any shape uses a SPARQL target or constraint. *Why:* this is the full check; the graph later runs only a subset of the shapes (rule 13), so a constraint skipped here is never checked.

2. **After serialising, validate again over both output files together** (`loadable.nt` and `inferred.nt`). *Why:* an inference can break a shape, and the graph holds both files.

3. **Refuse any value that cannot survive the round trip:** a string that ends like a language tag (`"...@en"`), and an `xsd:decimal` whose value, printed as a double, is not its own lexical form (0.64 passes; 0.1000000000000000055 does not; or adopt add-on C). *Why:* the round-trip rules (rule 16) would otherwise hide a real change in these values.

## 2. Reason

4. **Reason once, upstream, with ELK through ROBOT:**

   ```bash
   robot reason --reasoner ELK --input merged.ttl --axiom-generators "SubClass ClassAssertion" --output reasoned.ttl
   ```

   ELK is ROBOT's default reasoner; by default `reason` asserts only inferred subclass axioms, so name `ClassAssertion` to get inferred types too. ROBOT fails the step on an incoherent ontology (an inconsistency or an unsatisfiable class). *Why:* a property graph does no OWL reasoning, so inferences must arrive as data.

## 3. Serialise

5. **Write two sorted, de-duplicated N-Triples files**, one triple per line: `loadable.nt`, the checked asserted data with no triple terms, and `inferred.nt`, the inferences. Record the SHA-256 of the two together as the input fingerprint. *Why:* sorted N-Triples make a diffable, hashable input, and keeping inferences apart keeps them distinguishable from assertions.

6. **Build `inferred.nt` as a set difference, and drop the reasoner's declarations:**
   1. Convert the reasoner's input and output to sorted N-Triples.
   2. Keep the output lines that are not in the input.
   3. Of those, keep only `rdf:type` and `rdfs:subClassOf` triples whose subject and object are both IRIs. Drop anything with a blank node: OWL axioms are written with blank nodes whose labels change from run to run.
   4. Drop triples whose object is in the OWL or RDFS namespace.

   *Why:* ROBOT writes through the OWL API, which declares every individual `owl:NamedIndividual` and adds `owl:Class`, `owl:Thing`, `owl:AnnotationProperty` and `rdfs:Datatype` declarations. They are new in the output but are not inferences about the domain. On a SKOS-first ontology with few class axioms the file can rightly be empty.

7. **Rule 4b only: flatten each reifier into a plain `EdgeRecord` node with SPARQL 1.2** (Jena 6.1.0+ or RDF4J 6.0.0+), then union, sort and de-duplicate. n10s cannot load triple terms, and RDF 1.1 N-Triples cannot write them. Check first that triple terms appear only as objects of `rdf:reifies`, so `keep.rq` drops nothing else.

   ```sparql
   # keep.rq: every triple whose object is not a triple term
   CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o FILTER(!isTRIPLE(?o)) }
   ```

   ```sparql
   # edges.rq: one EdgeRecord per reifier
   PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
   PREFIX lpg: <https://id.example.org/lpg-mapping#>
   CONSTRUCT { ?r a lpg:EdgeRecord ; lpg:edgeSource ?s ; lpg:edgePredicate ?p ; lpg:edgeTarget ?o ; lpg:asserted ?asserted . }
   WHERE {
     ?r rdf:reifies ?tt .
     BIND(SUBJECT(?tt) AS ?s) BIND(PREDICATE(?tt) AS ?p) BIND(OBJECT(?tt) AS ?o)
     BIND(EXISTS { ?s ?p ?o } AS ?asserted)
   }
   ```

   The 4b path has not been run end to end; the tested runs used 4a.

## 4. Load

8. **Generate every Cypher statement from the ontology and the configuration; use MERGE and SET with explicit ordering.** *Why:* hand-written Cypher drifts from the ontology, and n10s defaults are not deterministic (multivalued properties default to overwrite, and unknown namespaces get invented prefixes).

9. **Configure n10s with SHORTEN, not MAP:**

   ```cypher
   CREATE CONSTRAINT n10s_unique_uri IF NOT EXISTS FOR (r:Resource) REQUIRE r.uri IS UNIQUE;
   CALL n10s.graphconfig.init({
     handleVocabUris: 'SHORTEN', handleRDFTypes: 'LABELS_AND_NODES',
     handleMultival: 'ARRAY', multivalPropList: [/* generated from the shapes, rule 10 */],
     keepLangTag: true, keepCustomDataTypes: true });
   // then, in the configuration's order:
   CALL n10s.nsprefixes.add('lib', 'https://id.example.org/library/');
   ```

   *Why:* in MAP mode n10s 2025.06.1 would not import shapes ("The graph is not namespace aware"), and MAP gives every term without a mapping the IGNORE treatment, which drops its namespace and breaks the round trip. SHORTEN keeps both; in it n10s ignores `n10s.mapping.add`, so the Rule 5 names come from a rename (`design-rules.md`, rule 5).

10. **Generate the multivalued list from the shapes:** every literal-valued predicate without `sh:maxCount 1`, plus any that holds more than one value on one subject. After the load, sort every array property (`apoc.coll.sort`). *Why:* an array's order otherwise follows the load order.

11. **Load in a fixed order** (ontology with `n10s.onto.import.fetch`, the in-graph shapes with `n10s.validation.shacl.import.fetch`, `loadable.nt`, `inferred.nt` with `n10s.rdf.import.fetch`), and check that each import ends with `terminationStatus` `OK`. n10s keeps no graph names, so asserted and inferred triples merge in the graph; the two files keep them apart (add-on F if the graph itself must tell them apart). *Why:* a fixed order and a checked status make the load repeatable and stop a partial import from passing.

12. **Rule 4b only: after the load, turn each `EdgeRecord` into a relationship with properties**, generated once per reified predicate with the predicate's SHORTEN name, then delete plain edges that duplicate a reified one:

    ```cypher
    MATCH (r:lpg__EdgeRecord)-[:lpg__edgeSource]->(s), (r)-[:lpg__edgeTarget]->(t),
          (r)-[:lpg__edgePredicate]->(p {uri: 'https://id.example.org/library/createdBy'})
    WITH r, s, t ORDER BY r.uri
    CALL apoc.merge.relationship(s, 'lib__createdBy', {uri: r.uri}, apoc.map.removeKeys(properties(r), ['uri']), t, {}) YIELD rel
    DETACH DELETE r;
    MATCH (s)-[plain]->(t), (s)-[reified]->(t)
    WHERE type(plain) = type(reified) AND plain.uri IS NULL AND reified.uri IS NOT NULL
    DELETE plain;
    ```

## Shapes in the graph

13. **Load into the graph only the constraints the engine can run, generate that subset from the full shapes, and record what was dropped and why** (`scripts/in_graph_shapes.py`). For n10s 2025.06.1, drop:
    - `sh:datatype rdf:langString`, which n10s rejects;
    - `sh:not`, `sh:languageIn`, `sh:node`, `sh:targetSubjectsOf` and `sh:targetObjectsOf`, which it does not support; SHACL-SPARQL targets, which it never runs; and SHACL-SPARQL constraints, which the check step runs;
    - `sh:pattern` (with `sh:flags`): n10s tests each value with Cypher `toString(x) =~ params.theRegex`, and `=~` matches the whole string, where SHACL searches it (SHACL §4.4.3, through SPARQL `REGEX` and XPath `fn:matches`). An unanchored `"\S"` fails every value longer than one character in the graph and passes in pySHACL;
    - `sh:in` lists that hold a literal: n10s reads a literal list as strings and tests `val in params.theInLiterals`, so a stored boolean or number is compared with a string; a loaded `true` did not match `sh:in (true)`. Keep `sh:in` lists of IRIs; they run correctly;
    - `sh:message` and `sh:severity`;
    - then every node shape left without a `sh:targetClass`, with its property shapes.

    *Why:* a constraint the engine cannot run, or runs differently, reports silence or a false failure, and silence looks like a pass. The guarantee still holds: the check step ran every shape on exactly the triples that were loaded (rules 1 and 2), and an empty round-trip diff (rule 16) shows the graph holds exactly those triples. Treat the count of constraints n10s loads (`n10s.validation.shacl.listShapes()`) as a reported figure.

14. **Test each constraint kind you rely on in the target engine with one value that must pass and one that must fail, before you trust its silence,** and re-run those tests on every new engine release. *Why:* the drop list above came from such tests, not from documentation.

## 5. Verify

15. **Run SHACL in the graph and require zero violations; then prove the check can fail.** In the loaded graph, remove one value a loaded shape requires (a deliberate mutant), validate again, require at least one violation, and restore the value. *Why:* zero violations from a check that cannot fire looks the same as a pass.

16. **Export with `n10s.rdf.export.cypher` and diff against `loadable.nt` plus `inferred.nt`: zero triples lost, zero added.** Compare values, not spellings, by normalising both sides the same way:
    - a plain literal and an `xsd:string` literal with the same text are equal (RDF 1.1);
    - integers load as INTEGER and export as `xsd:long`; compare them as integers;
    - decimals load as FLOAT and export as `xsd:double`; compare them as doubles (rule 3 refused the decimals for which that hides a change);
    - with `keepLangTag`, n10s stores the tag inside the string (`"Lending@en"`) and exports the literal untagged; read the tag back out of the string before comparing (rule 3 refused source strings that end like a tag).

    With Rule 4b, first rebuild the `EdgeRecord`s from relationships that have a `uri`. *Why:* the diff is what proves the graph holds exactly what passed the check.

17. **Load twice into clean databases, the second time with the triples shuffled (a fixed seed), and compare graph hashes.** Hash nodes sorted by `uri` with their sorted labels and properties, and edges sorted by `(source uri, type, target uri, edge uri)`. *Why:* equal hashes show the result does not depend on load order.
