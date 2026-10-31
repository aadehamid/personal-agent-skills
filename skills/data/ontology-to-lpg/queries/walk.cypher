// The walk (add-on F): every relationship within 2 hops of one node, both directions, with its
// predicate type and module tag, and the tag of the node at each end. Paste into Neo4j Browser; change
// the IRI, and the 2 in [*1..2] for another hop limit. n10s's schema relationships (n4sch__*) are derived
// from the ontology (the triples they repeat are ordinary relationships too), so no path crosses one,
// as explore.py's walk never does. A graph loaded with a separator other than n10s's (run-config.md,
// `separator`) names them n4sch plus that separator: change 'n4sch__' in the WHERE line to match.
:param iri => 'https://example.org/your-node';
MATCH p = (start:Resource {uri: $iri})-[*1..2]-(:Resource)
WHERE none(x IN relationships(p) WHERE type(x) STARTS WITH 'n4sch__')
UNWIND relationships(p) AS r
WITH DISTINCT r
RETURN startNode(r).uri AS subject, startNode(r).graph AS subject_module, type(r) AS predicate,
       endNode(r).uri AS object, endNode(r).graph AS object_module, r.graph AS module
ORDER BY module, subject, predicate, object;
