# The pipeline: check, reason, serialise, load, verify

Serves the pipeline steps. Read it before writing or changing the projection's code. The five steps work from ten triples to hundreds of millions; only the loader changes with scale (`running.md`, rule 6). The tool versions named here are the ones tested: Neo4j 2025.06.2 (Community edition), n10s (neosemantics) 2025.06.1 with APOC, ROBOT 1.9.10. Every script named here is in this skill's `scripts/`; run each with `uv run --no-project --with rdflib python3 <script>` (add `--with pyshacl` for `validate_data.py`, `--with neo4j` for `load_verify.py`). `load_verify.py` runs steps 4 and 5 against the container end to end and writes the report; the rules below say what it does, so a project can also write its own.

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

1. **Check the design rules over the ontology, then validate the data with every shape, and stop the build on any failure.** Run `check_projection_rules.py --config <config> --shapes <every shape file> --releases <folder> <every released data file>`, then `validate_data.py --config <config> --shapes <every shape file> <every released data file>`, which runs pySHACL with SHACL-AF on (`advanced=True`, so SPARQL targets and constraints run) and the refusals of rule 3. Under Rule 4b every script of this skill stops with exit 2 (`check_projection_rules.py`, `validate_data.py`, `build.py cypher` and `load_verify.py`; rdflib cannot read triple terms): run the same checks in Jena SHACL or RDF4J, or stop and ask the owner which tool to use. *Why:* this is the full check; the graph later runs only a subset of the shapes (rule 13), so a constraint skipped here is never checked.

2. **After serialising, validate again over both output files together:** `validate_data.py --config <config> --shapes <every shape file> loadable.nt inferred.nt`. *Why:* an inference can break a shape, and the graph holds both files.

3. **Refuse any value that cannot survive the round trip.** Both scripts of rule 1 refuse, and no release exception waives either:
   - a plain or `xsd:string` literal that matches `@[A-Za-z]{1,8}(-[A-Za-z0-9]{1,8})*$` (it ends like a language tag, such as `"Spine@en"`). n10s stores a tagged literal as `"text@en"`, so it would read such a string back as tagged text;
   - an `xsd:decimal` whose nearest double, printed in its shortest form and read back as a decimal, does not equal its value. `"1"` (back as 1.0), `"0.64"` and `"12.5"` survive; `"0.1000000000000000055"` (back as 0.1) does not. Change the value, or adopt add-on C.

   *Why:* the round-trip comparison (rule 16) treats these as equal or as tagged, so it would hide a real change.

## 2. Reason

4. **Reason once, upstream, with ELK through ROBOT, over the merged released data:**

   ```bash
   uv run --no-project --with rdflib python3 build.py merge --output merged.ttl <every released data file>
   java -jar robot.jar reason --reasoner ELK --input merged.ttl \
     --axiom-generators "SubClass ClassAssertion" --include-indirect true --output reasoned.ttl
   ```

   Check `robot.jar` against its SHA-256 first (`running.md`, rule 2).

   `merged.ttl` holds every released data file (each package's module Turtle) and nothing else: no shapes, no inferred triples, no configuration. ELK is ROBOT's default reasoner. By default `reason` asserts only inferred subclass axioms, so name `ClassAssertion` to get inferred types too, and it asserts only direct ones, so add `--include-indirect true`: without it, an individual asserted as a `lib:Book` gets only its direct type, which is already asserted, and nothing is inferred. ROBOT fails the step on an incoherent ontology (an inconsistency or an unsatisfiable class). With the flag, `inferred.nt` holds every entailed type and superclass link, indirect ones included, except OWL and RDFS built-ins: a node then carries a label for each of its classes, so `MATCH (:lib__Work)` finds books. That is intended, and it does what add-on A asks for. To load only the asserted types, leave the flag out and accept that only axioms which change an individual's most specific type produce inferences. *Why:* a property graph does no OWL reasoning, so inferences must arrive as data.

## 3. Serialise

5. **Write `loadable.nt` and `inferred.nt` as sorted, de-duplicated N-Triples, and record the input fingerprint.** `uv run --no-project --with rdflib python3 build.py loadable --output loadable.nt <every released data file>`. Sorted means one triple per line, lines ordered by their UTF-8 bytes, duplicates removed: the order `LC_ALL=C sort -u` gives. The input fingerprint is the SHA-256 of the bytes of `loadable.nt` followed directly by the bytes of `inferred.nt` (one hash over the concatenation, not a hash of the two hashes); `build.py manifest` computes it. On the first run, write the manifest without `--verify`: `build.py manifest --config <config> --shapes <shapes>... --loadable loadable.nt --inferred inferred.nt --output projection-manifest.json <data>...`. It records each file's path relative to the manifest's own folder. *Why:* a fixed byte order makes the files diffable and their hash repeatable, and keeping inferences apart keeps them distinguishable from assertions.

6. **Build `inferred.nt` from the reasoner's input and output, compared as triples:** `uv run --no-project --with rdflib python3 build.py inferred --input merged.ttl --reasoned reasoned.ttl --output inferred.nt`. It keeps the triples of `reasoned.ttl` that are not in `merged.ttl`, then only `rdf:type` and `rdfs:subClassOf` triples whose subject and object are both IRIs, then drops those whose object is in the OWL or RDFS namespace. If you build it with other tools, put both files through the same serialiser before comparing lines, or compare triples: two serialisers write the same triple differently. *Why:* ROBOT writes through the OWL API, which declares every individual `owl:NamedIndividual` and adds `owl:Class`, `owl:Thing`, `owl:AnnotationProperty` and `rdfs:Datatype` declarations; they are new in the output but are not inferences about the domain. OWL axioms use blank nodes whose labels change from run to run, so a triple with a blank node never counts. On a SKOS-first ontology with few class axioms the file can rightly be empty; on the library template it holds one triple (`W-0043 rdf:type lib:Work`).

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

Start the container first, as `running.md`, rule 5 says.

8. **Generate every Cypher statement from the ontology and the configuration, and give the database its four files.** `build.py cypher --config <config> --shapes <every shape file> <every released data file> > load.cypher` writes the load script. It reads four files from the import folder mounted at `/import`: `merged.ttl` (rule 4), `shapes-in-graph.ttl` (rule 13), `loadable.nt` and `inferred.nt` (rules 5 and 6). `load_verify.py` copies them there and runs the script one statement at a time, checking each result (rule 11). By hand, copy the four files into the import folder and run the script inside the container: `docker exec -i lpg-projection cypher-shell -u neo4j -p "$PASSWORD" < load.cypher`. Use MERGE and SET with explicit ordering in anything you add. *Why:* hand-written Cypher drifts from the ontology, and n10s defaults are not deterministic (multivalued properties default to overwrite, and unknown namespaces get invented prefixes).

9. **Configure n10s with SHORTEN, not MAP**, and add the configuration's prefixes in its order:

   ```cypher
   CREATE CONSTRAINT n10s_unique_uri IF NOT EXISTS FOR (r:Resource) REQUIRE r.uri IS UNIQUE;
   CALL n10s.graphconfig.init({
     handleVocabUris: 'SHORTEN', handleRDFTypes: 'LABELS_AND_NODES',
     handleMultival: 'ARRAY', multivalPropList: [/* generated, rule 10 */],
     keepLangTag: true, keepCustomDataTypes: true });
   CALL n10s.nsprefixes.add('lib', 'https://id.example.org/library/');   // one per prefix, in order
   ```

   *Why:* in MAP mode n10s 2025.06.1 would not import shapes ("The graph is not namespace aware"), and MAP gives every term without a mapping the IGNORE treatment, which drops its namespace and breaks the round trip. SHORTEN keeps both; in it n10s ignores `n10s.mapping.add`, so the Rule 5 names come from a rename (`design-rules.md`, rule 5).

10. **Generate the multivalued list by one rule, and sort arrays only on `:Resource` nodes.** A predicate is literal-valued when any of its objects in the data is a literal. It goes in `multivalPropList` unless a property shape that an applied shape uses (any target kind, as `design-rules.md`, rule 2 defines it) gives its path `sh:maxCount 1`; it goes in anyway when one subject holds more than one literal value for it. So a standard predicate with no shape of its own (`rdfs:label`, `skos:prefLabel`, `dcterms:title`, `owl:versionInfo`) loads as an array, even with one value; give it a shape with `sh:maxCount 1` if consumers need a single value. After the load, sort each listed key, by its SHORTEN name, on resource nodes only:

    ```cypher
    MATCH (n:Resource) WHERE n.`lib__altTitle` IS NOT NULL SET n.`lib__altTitle` = apoc.coll.sort(n.`lib__altTitle`);
    ```

    Never sort every list property on every node: n10s keeps its own configuration in nodes without the `Resource` label (`_GraphConfig`, `_NsPrefDef`, `_n10sValidatorConfig`), and sorting the byte arrays of `_n10sValidatorConfig` corrupts it, after which `n10s.validation.shacl.listShapes()` fails with `StreamCorruptedException`. *Why:* an array's order otherwise follows the load order, and the rule decides every predicate the same way on every load.

11. **Load in a fixed order and check each import:**
    1. `n10s.onto.import.fetch('file:///import/merged.ttl', 'Turtle')`: the merged released data of rule 4, from which n10s builds its schema nodes (`n4sch__Class` and the rest);
    2. `n10s.validation.shacl.import.fetch('file:///import/shapes-in-graph.ttl', 'Turtle')`: the subset of rule 13;
    3. `n10s.rdf.import.fetch` of `loadable.nt`, then of `inferred.nt` (`'N-Triples'`).

    The two `rdf.import` calls and `onto.import` succeed when they return `terminationStatus` `OK`. The shapes import returns no `terminationStatus`: it returns one row per constraint it compiled, and it succeeds when that row count is above zero and equals the count of `CALL n10s.validation.shacl.listShapes()`. Record both counts in the report (`shapes_import_rows`, `in_graph_shape_constraints`). Neither counts every constraint that runs: `listShapes()` does not list `sh:disjoint`, which still runs, so the two counts are a check that the import finished, not an inventory. The paths assume the import folder is mounted at `/import` (`running.md`, rule 5). n10s keeps no graph names, so asserted and inferred triples merge in the graph; the two files keep them apart (add-on F if the graph itself must tell them apart). *Why:* a fixed order and a checked result make the load repeatable and stop a partial import from passing.

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

13. **Load into the graph only the constraints the engine can run, generate that subset from the full shapes, and record what was dropped and why:** `python3 in_graph_shapes.py --output shapes-in-graph.ttl <every shape file>`. For n10s 2025.06.1 it drops:
    - `sh:datatype` outside n10s's list (`xsd:boolean`, `xsd:string`, `xsd:integer`, `xsd:float`, `xsd:decimal`, `xsd:date`, `xsd:dateTime`, `xsd:anyURI`, `geo:wktLiteral`): n10s throws for any other, `rdf:langString` and `xsd:dateTimeStamp` among them;
    - `sh:not`, `sh:languageIn`, `sh:targetSubjectsOf` and `sh:targetObjectsOf`, which it does not support; `sh:node` on a property shape (a value shape), which it does not run; `sh:and`, `sh:or` and `sh:xone`, which its shape query does not read (a property shape in the dropped list stays when another shape still uses it through `sh:property`); SHACL-SPARQL targets, which it never runs; and SHACL-SPARQL constraints, which the check step runs;
    - `sh:pattern` (with `sh:flags`): n10s tests each value with Cypher `toString(x) =~ params.theRegex`, `=~` matches the whole string with Java's regular expressions, and SHACL searches the string with XPath's (SHACL §4.4.3, through SPARQL `REGEX` and `fn:matches`). An unanchored `"\S"` fails every value longer than one character in the graph and passes in pySHACL. Patterns are checked before the load only;
    - `sh:in` lists that hold a literal, and a literal `sh:hasValue`: n10s reads literal values as strings, so a stored boolean or number is compared with a string; a loaded `true` did not match `sh:in (true)`. `sh:in` lists and `sh:hasValue` values that are IRIs stay;
    - every other SHACL term n10s's shape query does not read, such as `sh:lessThan`, `sh:lessThanOrEquals`, `sh:equals`, `sh:uniqueLang` and `sh:qualifiedValueShape`: n10s ignores them, so a forced violation reports nothing. The script keeps only the terms the query reads (`sh:path`, `sh:inversePath`, `sh:class`, `sh:nodeKind`, `sh:datatype`, the counts, ranges and lengths, `sh:hasValue`, `sh:in`, `sh:disjoint`, `sh:targetClass`, n10s's own `sh:targetQuery`, `sh:property`, `sh:closed`, `sh:ignoredProperties`, and `sh:node` on a node shape). `sh:node` on a node shape that n10s applies stays: its shape query reads `sh:node?/sh:property` (`SHACLValidator.java`, line 73), one hop, so the reached shape's property shapes run for the same nodes; a second hop is dropped. This reading comes from the source; no run has yet tested it in the engine;
    - a SHACL-SPARQL constraint or target node named by an IRI, once its query is gone;
    - a shape with `sh:deactivated true`, which SHACL skips and n10s would run;
    - `sh:message`, `sh:severity`, `sh:name`, `sh:description`, `sh:order`, `sh:group` and `sh:defaultValue`, which are not constraints;
    - then every node shape n10s does not apply, with its property shapes unless a kept shape still uses them. n10s applies a shape with `sh:targetClass`, one with `sh:targetQuery`, and one that is itself an `rdfs:Class` (its query reads `a rdfs:Class`, not `owl:Class`), plus a shape a kept `sh:node` reaches. Give an `owl:Class` shape an explicit `sh:targetClass`.

    *Why:* a constraint the engine cannot run, or runs differently, reports silence or a false failure, and silence looks like a pass. The guarantee still holds: the check step ran every shape on exactly the triples that were loaded (rules 1 and 2), and an empty round-trip diff (rule 16) shows the graph holds exactly those triples.

14. **Test each constraint kind left in the graph with one change that must fail, before you trust its silence,** and re-run the tests on every new engine release. `load_verify.py` generates one case per kind from the in-graph shapes (`fail_cases`), runs each in a transaction it rolls back, and passes the case when `n10s.validation.shacl.validate()` reports the changed node (`focusNode`) with a component in the kind's expected set. The component is in the `propertyShape` column, as a full IRI such as `http://www.w3.org/ns/shacl#CountConstraintComponent`. A change can fire more than one component; the extra ones are expected. On the library template in n10s 2025.06.1:

    | Constraint kind | Generated change | Components reported |
    |---|---|---|
    | `sh:minCount 1` on a value | remove the first authorship's `lib__position` property | `CountConstraintComponent` |
    | `sh:maxCount 1` on a value | set the first authorship's `lib__position` to a list of two strings | `CountConstraintComponent`, and `DatatypeConstraintComponent` because the values became strings |
    | `sh:datatype xsd:integer` | set the first authorship's `lib__position` to a string | `DatatypeConstraintComponent` |
    | `sh:datatype xsd:string` | set a copy's `lib__barcode` to the integer 0 | `DatatypeConstraintComponent` |
    | `sh:class` | replace a copy's `lib__copyOf` relationships with one to a node without the `lib__Work` label | `ClassConstraintComponent` |
    | `sh:in` of IRIs | replace an authorship's `lib__creatorRole` with a relationship to a node outside the list | `InConstraintComponent` |
    | `sh:nodeKind sh:IRI` | add a string property `lib__hasAuthorship` to W-0042 | `NodeKindConstraintComponent`, and `ClassConstraintComponent` |
    | `sh:inversePath` with `sh:minCount 1` | delete the `lib__hasAuthorship` relationship from W-0042 into its first authorship (W-0042 keeps its second, so only the authorship fails) | `CountConstraintComponent` on the authorship |

    The script also generates cases for an inverse `sh:maxCount` (adds links into a node; `CountConstraintComponent`), `sh:closed` (sets a property the closed shape does not declare; `ClosedConstraintComponent`), `sh:disjoint` (adds the other property's value or link; `DisjointConstraintComponent`, with `CountConstraintComponent` and others when the added link breaks them too), `sh:hasValue` of an IRI, the four range constraints and the two length constraints (`EXPECTED` in `load_verify.py` lists each kind's components). The report's `kinds_without_case` lists every kind left in the graph, on a property the data uses, that got no generated case, and `build.py check-report` fails while a listed kind has no passing manual case; `load_verify.py` itself exits 0 and prints the list, so that you can add the cases before the gate runs. A shape with `sh:targetQuery` always needs one, because its nodes come from a query the script does not run. For such a kind, write a case the same way, run it while the container is still up, and record it in the report's `manual_cases` as `{"kind": <the kind as listed>, "cypher": <the change>, "focus": <the changed node's uri>, "components": [<what validate() reported on it>], "passed": true}`. `check-report` counts a manual case only when all five fields are filled (`passed` the JSON `true`, at least one component). A case is a Cypher change that returns the changed node's `uri` as `focus`, run in a transaction, validated, then rolled back:

    ```python
    tx = session.begin_transaction()
    focus = tx.run(change).single()["focus"]
    rows = tx.run("CALL n10s.validation.shacl.validate() YIELD focusNode, propertyShape RETURN *").data()
    tx.rollback()
    ```

    *Why:* the drop list and this table came from such tests, not from documentation.

## 5. Verify

15. **Run SHACL in the graph and require zero violations; then prove the check can fail.** Commit a deliberate mutant: remove one literal value a loaded `sh:minCount` shape requires, validate, require at least one violation on that node, restore the value, and require zero violations again. `load_verify.py` does it on the first such shape (`mutant_case`):

    ```cypher
    MATCH (n:`lib__Authorship`) WHERE n.`lib__position` IS NOT NULL WITH n ORDER BY n.uri LIMIT 1
    RETURN n.uri AS uri, n.`lib__position` AS value;                       // keep both
    MATCH (n:Resource {uri: $uri}) REMOVE n.`lib__position`;                 // the mutant
    CALL n10s.validation.shacl.validate() YIELD focusNode RETURN focusNode;  // must list $uri
    MATCH (n:Resource {uri: $uri}) SET n.`lib__position` = $value;          // restore
    ```

    Record the violation counts before and after the restore in the report. *Why:* zero violations from a check that cannot fire looks the same as a pass.

16. **Export the resources and diff against `loadable.nt` plus `inferred.nt`: zero triples lost, zero added.** Export with:

    ```cypher
    CALL n10s.rdf.export.cypher('MATCH (n:Resource) OPTIONAL MATCH (n)-[r]->(m) RETURN n, r, m')
    YIELD subject, predicate, object, isLiteral, literalType, literalLang
    RETURN subject, predicate, object, isLiteral, literalType, literalLang
    ```

    Then:
    - drop every row whose subject, predicate or (IRI) object is in `neo4j://graph.schema#`: those are the `n4sch__` schema nodes and properties `onto.import` added, not data;
    - build a tagged literal from `object` and `literalLang` when `literalLang` is set: with `keepLangTag`, n10s stores `"Lending@en"` but the export usually returns the text without the tag and sets `literalLang` to `en`;
    - when `literalLang` is empty and the type is `xsd:string` (or empty), split a trailing tag off the text with `^(.*)@([A-Za-z]{1,8}(?:-[A-Za-z0-9]{1,8})*)$` matched with DOTALL (Python `re.S`): n10s 2025.06.1 exports a tagged string that holds a newline as `xsd:string` `"text@en"` with no `literalLang`. The split is safe because rule 3 refused every source string that ends like a tag;
    - normalise both sides the same way, so the diff compares values, not spellings: a plain literal and an `xsd:string` literal with the same text are equal (RDF 1.1); integers load as INTEGER and export as `xsd:long`, so compare them as integers; decimals load as FLOAT and export as `xsd:double`, so compare them as doubles (rule 3 refused the decimals for which that hides a change);
    - compare with rdflib's `to_isomorphic` and `graph_diff`.

    With Rule 4b, first rebuild the `EdgeRecord`s from relationships that have a `uri`. *Why:* the diff is what proves the graph holds exactly what passed the check.

17. **Load twice into an empty database, the second time with the lines of `loadable.nt` shuffled (a fixed seed), and compare graph hashes.** `load_verify.py` overwrites the import folder's copy of `loadable.nt` with its lines shuffled by `random.Random(12).shuffle`, loads it, and puts the sorted file back afterwards; the committed file never changes. On Community edition, which has one user database, empty it between loads:

    ```cypher
    MATCH (n) DETACH DELETE n;      // the data, the schema nodes and n10s's _GraphConfig, _NsPrefDef and _n10sValidatorConfig nodes
    SHOW CONSTRAINTS YIELD name;    // then DROP CONSTRAINT `<name>` for each one listed
    ```

    Check that `MATCH (n) RETURN count(n)` and `SHOW CONSTRAINTS` both return nothing, then rerun the whole load script (rule 8), which recreates the constraint, the configuration and the prefixes. For a large graph, delete in batches (`CALL { ... } IN TRANSACTIONS`). The hash (`graph_hash` in `load_verify.py`, whose docstring is the full specification) is SHA-256 over canonical JSON of every `:Resource` node as `[uri, sorted labels, properties]` and every relationship between two `:Resource` nodes as `[source uri, type, target uri, relationship uri or "", relationship properties]`, nodes sorted by `uri` and relationships by their first four fields; list values keep their stored order (the load sorted them); a value JSON cannot hold, such as a date, is written as its string form. Schema nodes from `onto.import` are `:Resource` nodes and count; n10s's configuration nodes have no `Resource` label and do not. The raw row count of the export in rule 16 can differ between the two loads while the hashes and the exported triple sets are equal; compare the hashes and the triples, not the row counts. *Why:* equal hashes show the result does not depend on load order.
