#!/usr/bin/env python3
"""Generate the subset of the shapes that n10s 2025.06.1 can run inside Neo4j.

Run: uv run --no-project --with rdflib python3 in_graph_shapes.py --output <shapes-in-graph.ttl> <shapes.ttl>...

What it drops, and why (references/pipeline.md, rule 13):
  sh:datatype outside n10s's list              n10s throws for any datatype but xsd:boolean, string,
                                               integer, float, decimal, date, dateTime, anyURI and
                                               geo:wktLiteral (rdf:langString among them)
  sh:not, sh:languageIn,
  sh:targetSubjectsOf, sh:targetObjectsOf      n10s does not support them
  sh:node on a property shape                  n10s does not run value shapes. On a node shape that n10s
                                               applies it stays: n10s reads sh:node?/sh:property, one
                                               hop, so the reached shape's property shapes run for the
                                               same focus nodes. A second hop is dropped.
  sh:and, sh:or, sh:xone                       n10s's shape query does not read them
  sh:target                                    SHACL-SPARQL target; n10s never runs it
  sh:sparql                                    SHACL-SPARQL constraint; the check step runs it
  sh:pattern, sh:flags                         n10s matches the whole string (Cypher =~); patterns are
                                               checked before the load only
  sh:in with a literal member                  n10s compares a literal list as strings
  sh:hasValue with a literal                   n10s compares a literal value as a string
  sh:message, sh:severity, sh:name,
  sh:description, sh:order, sh:group,
  sh:defaultValue                              not constraints; left out of the in-graph file
  a shape with sh:deactivated true             SHACL skips it, and n10s does not read the flag
  any other SHACL term n10s's shape query does not read (sh:lessThan, sh:lessThanOrEquals, sh:equals,
  sh:uniqueLang, sh:qualifiedValueShape, sh:select, sh:prefixes, sh:declare and the rest): n10s
                                               ignores it, so it would report silence
  a SHACL-SPARQL constraint or target node     left with nothing but its type once its query is gone
  a node shape that n10s does not apply        one with no sh:targetClass, no sh:targetQuery and no
                                               rdfs:Class type (n10s does not read owl:Class as one), and
                                               not reached by a kept sh:node; its property shapes go too,
                                               unless a kept shape still uses them
The full shapes still run before the load; the round-trip diff carries their result into the graph.
sh:in lists and sh:hasValue values that are IRIs stay.

It writes the subset as Turtle and prints one line per dropped constraint, so the projection's
report can record what was dropped. Exit 0 on success, 2 when a file cannot be read or the
arguments are wrong.
"""
import sys

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import RDF, RDFS, SH, XSD

UNSUPPORTED = {
    SH["not"]: "n10s does not support sh:not",
    SH.languageIn: "n10s does not support sh:languageIn",
    SH.targetSubjectsOf: "n10s does not support sh:targetSubjectsOf",
    SH.targetObjectsOf: "n10s does not support sh:targetObjectsOf",
    SH["and"]: "n10s's shape query does not read sh:and",
    SH["or"]: "n10s's shape query does not read sh:or",
    SH.xone: "n10s's shape query does not read sh:xone",
    SH.target: "SHACL-SPARQL target; n10s never runs it",
    SH.sparql: "SHACL-SPARQL constraint; the check step runs it before the load",
    SH.pattern: "n10s matches sh:pattern against the whole string; patterns are checked before the load only",
    SH.flags: "goes with sh:pattern",
}
NOT_CONSTRAINTS = {p: "not a constraint" for p in (SH.message, SH.severity, SH.name, SH.description, SH.order,
                                                    SH.group, SH.defaultValue)}
# SHACLValidator.getDatatypeCastExpressionSuff at tag 2025.06.1 accepts only these; others throw.
N10S_DATATYPES = {XSD.boolean, XSD.string, XSD.integer, XSD.float, XSD.decimal, XSD.date, XSD.dateTime,
                  XSD.anyURI, URIRef("http://www.opengis.net/ont/geosparql#wktLiteral")}
# n10s's own target extension, a Cypher query (not a SHACL term, so rdflib's SH does not list it).
TARGET_QUERY = URIRef(str(SH) + "targetQuery")
# n10s's implicit class target reads only rdfs:Class (PROP_CONSTRAINT_QUERY: "?targetClass sh:property
# ?ps; a rdfs:Class"); an owl:Class shape without sh:targetClass is not applied in the graph.
CLASS_KINDS = (RDFS.Class,)
# The SHACL terms n10s 2025.06.1 reads (SHACLValidator.java, PROP_CONSTRAINT_QUERY and the two node
# queries, lines 59 to 180). Every other term in the SHACL namespace is dropped.
READ = {SH.path, SH.inversePath, SH["class"], SH.nodeKind, SH.datatype, SH.maxCount, SH.minCount,
        SH.minInclusive, SH.maxInclusive, SH.minExclusive, SH.maxExclusive, SH.minLength, SH.maxLength,
        SH.hasValue, SH["in"], SH.disjoint, SH.targetClass, TARGET_QUERY, SH.property, SH.closed,
        SH.ignoredProperties, SH.node}
SHAPE_TYPES = {SH.NodeShape, SH.PropertyShape, SH.Shape}


def _remove_subject(g, node):
    """Remove a node's triples and, recursively, those of the blank nodes it points to, except a blank
    node that something else still uses (a property shape that is also another shape's sh:property)."""
    for _, _, o in list(g.triples((node, None, None))):
        g.remove((node, None, o))
        if isinstance(o, BNode) and (None, None, o) not in g:
            _remove_subject(g, o)


def _reason(shapes, s, p, o):
    if p in UNSUPPORTED:
        return UNSUPPORTED[p]
    if p in NOT_CONSTRAINTS:
        return NOT_CONSTRAINTS[p]
    if p == SH.datatype and o not in N10S_DATATYPES:
        return f"n10s throws for sh:datatype {o.n3(shapes.namespace_manager)}"
    if p == SH["in"] and any(isinstance(m, Literal) for m in Collection(shapes, o)):
        return "n10s compares a literal sh:in list as strings"
    if p == SH.hasValue and isinstance(o, Literal):
        return "n10s compares a literal sh:hasValue as a string"
    if p == SH.node and (s, SH.path, None) in shapes:
        return "n10s does not run sh:node on a property shape (a value shape)"
    if str(p).startswith(str(SH)) and p not in READ:
        return f"n10s's shape query does not read {p.n3(shapes.namespace_manager)}"
    return None


def _applied(g, shape):
    """sh:targetClass or sh:targetQuery; or an rdfs:Class that is also typed sh:NodeShape (or sh:Shape):
    both n10s queries need ?ns typed as a shape (lines 72 to 74, and 129 to 130 for sh:closed)."""
    is_shape = (shape, RDF.type, SH.NodeShape) in g or (shape, RDF.type, SH.Shape) in g
    return ((shape, SH.targetClass, None) in g or (shape, TARGET_QUERY, None) in g
            or (is_shape and any((shape, RDF.type, k) in g for k in CLASS_KINDS)))


def hop_source(g, shape):
    """True when n10s follows sh:node from this shape: only from one with sh:targetClass or
    sh:targetQuery. PROP_CONSTRAINT_QUERY (SHACLValidator.java at 2025.06.1) reaches ?ps through
    "?ns a sh:NodeShape ; sh:node?/sh:property ?ps" (lines 72 to 74), but its implicit-class branch
    (lines 88 and 89) reads "?targetClass sh:property ?ps; a rdfs:Class", so an rdfs:Class runs only
    its own sh:property shapes."""
    return (shape, SH.targetClass, None) in g or (shape, TARGET_QUERY, None) in g


def applied_node_shapes(g):
    """Every shape n10s applies in g: one with sh:targetClass or sh:targetQuery, or one typed
    rdfs:Class (its own sh:property shapes, and sh:closed through NODE_CONSTRAINT_QUERY, line 138).
    An sh:node hop counts only from a hop_source. load_verify.py builds its inventories from this
    and from hop_source, so they cover exactly what the subset keeps and n10s reads."""
    candidates = set(g.subjects(RDF.type, None)) | set(g.subjects(SH.targetClass, None)) \
        | set(g.subjects(TARGET_QUERY, None))
    return {s for s in candidates if _applied(g, s)}


def subset(shapes):
    """Return (in-graph shapes, dropped) where dropped is a sorted list of (shape, constraint, reason).
    sh:message and sh:severity are removed but not listed: they are not constraints."""
    g = Graph()
    for prefix, ns in shapes.namespaces():
        g.bind(prefix, ns)
    g += shapes
    dropped = []
    for shape in sorted(set(shapes.subjects(SH.deactivated, Literal(True))), key=str):
        for parent, _, _ in list(g.triples((None, SH.property, shape))):
            g.remove((parent, SH.property, shape))
        _remove_subject(g, shape)
        dropped.append((shape, SH.deactivated, "deactivated: SHACL skips it, and n10s does not read the flag"))
    for s, p, o in sorted(shapes, key=lambda t: tuple(str(x) for x in t)):
        if (s, p, o) not in g:
            continue
        reason = _reason(shapes, s, p, o)
        if reason is None:
            continue
        g.remove((s, p, o))
        if isinstance(o, BNode):
            _remove_subject(g, o)
        if p not in NOT_CONSTRAINTS:
            dropped.append((s, p, reason))
    # An IRI-named SHACL-SPARQL constraint or target, left with only its type once its query is gone.
    for node in sorted({s for s in g.subjects(RDF.type, None) if isinstance(s, URIRef)}, key=str):
        preds = set(g.predicates(node, None))
        types = set(g.objects(node, RDF.type))
        if preds == {RDF.type} and all(str(t).startswith(str(SH)) and t not in SHAPE_TYPES for t in types) \
                and (None, None, node) not in g:
            _remove_subject(g, node)
            dropped.append((node, RDF.type, "a SHACL-SPARQL node left without its query"))
    node_shapes = sorted(set(g.subjects(RDF.type, SH.NodeShape)) | set(g.subjects(SH.node, None)), key=str)
    applied = {n for n in node_shapes if _applied(g, n)}
    # n10s follows sh:node one hop, and only from a shape with sh:targetClass or sh:targetQuery.
    for n in sorted(set(g.subjects(SH.node, None)), key=str):
        if n in applied and hop_source(g, n):
            continue
        reason = ("n10s does not follow sh:node from an rdfs:Class shape: its implicit-class query reads only "
                  "the class's own sh:property" if n in applied else
                  "n10s follows sh:node one hop, from a shape with sh:targetClass or sh:targetQuery only")
        for o in list(g.objects(n, SH.node)):
            g.remove((n, SH.node, o))
            dropped.append((n, SH.node, reason))
    reached = {o for n in applied for o in g.objects(n, SH.node)}
    node_shapes = sorted(set(g.subjects(RDF.type, SH.NodeShape)) | set(g.subjects(SH.property, None)) | reached,
                         key=str)
    unapplied = [n for n in node_shapes if n not in applied and n not in reached]
    kept_uses = {ps for n in node_shapes if n not in unapplied for ps in g.objects(n, SH.property)}
    for shape in unapplied:
        for prop in list(g.objects(shape, SH.property)):
            if prop not in kept_uses:
                _remove_subject(g, prop)
        _remove_subject(g, shape)
        dropped.append((shape, RDF.type, "a node shape n10s does not apply: no sh:targetClass or sh:targetQuery, "
                                         "not an rdfs:Class, and not reached by a kept sh:node"))
    return g, sorted(dropped, key=lambda t: (str(t[0]), str(t[1])))


def main(argv):
    if len(argv) < 3 or argv[0] != "--output" or any(a.startswith("-") for a in argv[2:]):
        print("usage: in_graph_shapes.py --output <shapes-in-graph.ttl> <shapes.ttl>...", file=sys.stderr)
        return 2
    output, paths = argv[1], argv[2:]
    shapes = Graph()
    try:
        for path in paths:
            shapes.parse(path, format="turtle")
    except Exception as exc:  # rdflib raises several parser types; any of them stops the run
        print(f"ERROR cannot read the shapes: {exc}", file=sys.stderr)
        return 2
    g, dropped = subset(shapes)
    g.serialize(output, format="turtle")
    for shape, constraint, reason in dropped:
        print(f"dropped {shape.n3(shapes.namespace_manager)} {constraint.n3(shapes.namespace_manager)}: {reason}")
    print(f"wrote {output}: {len(g)} triples, {len(dropped)} constraint(s) dropped")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
