# Sources

## Project experience

The workflow is derived from building and testing offline ontology references:
pinning released inputs, separating reader views from source facts, preserving
anonymous constraints, inspecting phone layouts, and validating the extracted
delivery artifact. The implementation and project-specific decisions remain in
their consuming repository. This skill contains the method and neutral library
examples. No project code or ontology data is copied into the skill.

## Standards

The playbook paraphrases these sources. No specification text is vendored.
Check the cited sections when changing the semantic contract. Sources were read
2026-11-07 unless a row records another date.

| Source | Version and date | Use |
|---|---|---|
| [RDF 1.1 Concepts and Abstract Syntax](https://www.w3.org/TR/rdf11-concepts/) | W3C Recommendation, 25 February 2014 | Sections 3 and 4: RDF term identity, literals, blank-node scope, graph isomorphism and datasets. |
| [RDF Schema 1.1](https://www.w3.org/TR/rdf-schema/) | W3C Recommendation, 25 February 2014 | Sections 3.1 to 3.4: range, domain, subclass and subproperty semantics. |
| [SKOS Reference](https://www.w3.org/TR/skos-reference/) | W3C Recommendation, 18 August 2009 | Concepts, schemes, labels, documentation and semantic relations. |
| [Shapes Constraint Language](https://www.w3.org/TR/shacl/) | W3C Recommendation, 20 July 2017 | Targets, property paths and cardinality constraints. |
| [XML Schema Definition Language 1.1, Part 2: Datatypes](https://www.w3.org/TR/2012/REC-xmlschema11-2-20120405/) | W3C Recommendation, 5 April 2012; read 2026-11-08 | Integer lexical forms and the whitespace facet used when reading stage order. |

## Viewer design references

[Horoi](https://github.com/kvistgaard/horoi/tree/33caa8cc916e7efb767a5c2831216ff1cb11c509)
was inspected at commit `33caa8cc916e7efb767a5c2831216ff1cb11c509` on
2026-11-07. Its reference-page approach informed the method. Its class/property
renderer illustrates why a candidate must be tested against the input's term
kinds and definition predicates. This skill includes no Horoi code. A consuming
project that reuses it must retain its Apache 2.0 notices and record modifications.

[Brick's ontology site](https://ontology.brickschema.org/) was inspected on
2026-11-07. The live HTML referenced RDF Garden's version-2 explorer; browser
inspection returned HTTP 429. The skill claims no verified interactive behavior
or licence for that explorer, and includes none of its code. For an update,
inspect the live deployment and its actual dependency version again.

To refresh these references, retrieve the current primary source, retain a local
snapshot under the ignored `upstream/` folder when comparison is useful, and
compare only the claims the playbook relies on. Record the new version and date
after verifying them. A new upstream release does not automatically require a
viewer migration.
