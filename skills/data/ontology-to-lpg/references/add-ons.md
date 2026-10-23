# Add-ons and anti-patterns

Read it when a consumer asks for something the core pipeline does not give (superclass labels, split language keys, exact decimals, units, provenance, business keys), or when reviewing a projection.

## Add-ons (adopt only when needed, and record each)

| Add-on | Use when | What to add |
|---|---|---|
| A. Superclass labels | `MATCH (:lib__Item)` should find copies without walking the hierarchy | After the load, add the labels of inferred superclasses, except `owl:Thing` and upper-ontology roots |
| B. Language policy | Labels in several languages | `lpg:langPolicy "splitKeys"`, giving `label_en`, `label_fr` |
| C. Exact decimals | Fines, fees, anything computed with exact arithmetic | `lpg:cypherType "STRING"` on `xsd:decimal` properties |
| D. Known exclusions | OWL axioms you will not project | List them in `exclusions.nt`; the round-trip diff ignores them |
| E. Units | Quantities with units | QUDT value and unit pattern, not custom datatypes |
| F. Named graphs and provenance | Several sources or versions | Load each graph separately; tag nodes and relationships with `graph` |
| G. Business keys | Consumers MERGE on a key such as a barcode | `lpg:keyProperty true`, giving an extra uniqueness constraint |

## Anti-patterns

Each is a way the projection passes while being wrong.

- Relying on n10s defaults: overwrite for multivalued properties, invented `ns0` prefixes.
- Loading shapes the engine cannot run, and reading its silence as a pass.
- Loading the reasoner's OWL API declarations as inferences.
- Blank-node qualified-relation nodes or reifiers: the node or relationship then has no stable identity.
- Merging two reifiers of one triple into one relationship.
- Cypher written by hand rather than generated from the ontology.
- Projecting working source files instead of released packages.
- An exception list that is never checked for stale entries.
- Expecting Neo4j to do OWL reasoning.
- Treating Neo4j as the master copy instead of the Turtle files.
