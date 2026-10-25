// The same walk as a picture: paste into Neo4j Browser (or save it as a Browser favourite, or as a
// Bloom search phrase with the parameter $iri). Colour nodes by the `graph` property to see modules.
:param iri => 'https://example.org/your-node';
MATCH p = (start:Resource {uri: $iri})-[*1..2]-(:Resource)
WHERE none(r IN relationships(p) WHERE type(r) STARTS WITH 'n4sch__')
RETURN p LIMIT 300;
