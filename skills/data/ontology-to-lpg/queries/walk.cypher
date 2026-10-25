// The walk (add-on F): every relationship within 2 hops of one node, both directions, with its
// predicate type and module tag, and the tag of the node at each end. Paste into Neo4j Browser; change
// the IRI, and the 2 in [*1..2] for another hop limit. n10s's schema relationships (n4sch__*) repeat
// rdfs:domain, rdfs:range and rdfs:subClassOf triples, so they are left out, as explore.py does.
:param iri => 'https://example.org/your-node';
MATCH p = (start:Resource {uri: $iri})-[*1..2]-(:Resource)
UNWIND relationships(p) AS r
WITH DISTINCT r WHERE NOT type(r) STARTS WITH 'n4sch__'
RETURN startNode(r).uri AS subject, startNode(r).graph AS subject_module, type(r) AS predicate,
       endNode(r).uri AS object, endNode(r).graph AS object_module, r.graph AS module
ORDER BY module, subject, predicate, object;
