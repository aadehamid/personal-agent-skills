#!/usr/bin/env python3
"""Generate the subset of the shapes that n10s 2025.06.1 can run inside Neo4j.

Run: uv run --no-project --with rdflib python3 in_graph_shapes.py --output <shapes-in-graph.ttl> <shapes.ttl>...

What it drops, and why (references/pipeline.md, rule 13):
  sh:datatype outside n10s's list              n10s throws for any datatype but xsd:boolean, string,
                                               integer, float, decimal, date, dateTime, anyURI and
                                               geo:wktLiteral (rdf:langString among them)
  sh:not, sh:languageIn, sh:node,
  sh:targetSubjectsOf, sh:targetObjectsOf      n10s does not support them
  sh:and, sh:or, sh:xone                       n10s's shape query does not read them
  sh:target                                    SHACL-SPARQL target; n10s never runs it
  sh:sparql                                    SHACL-SPARQL constraint; the check step runs it
  sh:pattern, sh:flags                         n10s matches the whole string (Cypher =~); patterns are
                                               checked before the load only
  sh:in with a literal member                  n10s compares a literal list as strings
  sh:hasValue with a literal                   n10s compares a literal value as a string
  sh:message, sh:severity                      not constraints; left out of the in-graph file
  a node shape that n10s does not apply        one with neither sh:targetClass nor a class type;
                                               its property shapes go too, unless a kept node shape
                                               still uses them
The full shapes still run before the load; the round-trip diff carries their result into the graph.
sh:in lists and sh:hasValue values that are IRIs stay.

It writes the subset as Turtle and prints one line per dropped constraint, so the projection's
report can record what was dropped. Exit 0 on success, 2 when a file cannot be read or the
arguments are wrong.
"""
import sys

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import OWL, RDF, RDFS, SH, XSD

UNSUPPORTED = {
    SH["not"]: "n10s does not support sh:not",
    SH.languageIn: "n10s does not support sh:languageIn",
    SH.node: "n10s does not support sh:node",
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
NOT_CONSTRAINTS = {SH.message: "not a constraint", SH.severity: "not a constraint"}
# SHACLValidator.getDatatypeCastExpressionSuff at tag 2025.06.1 accepts only these; others throw.
N10S_DATATYPES = {XSD.boolean, XSD.string, XSD.integer, XSD.float, XSD.decimal, XSD.date, XSD.dateTime,
                  XSD.anyURI, URIRef("http://www.opengis.net/ont/geosparql#wktLiteral")}
CLASS_KINDS = (OWL.Class, RDFS.Class)


def _remove_subject(g, node):
    """Remove a node's triples and, recursively, those of the blank nodes it points to."""
    for _, _, o in list(g.triples((node, None, None))):
        g.remove((node, None, o))
        if isinstance(o, BNode):
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
    return None


def _applied(g, shape):
    return (shape, SH.targetClass, None) in g or any((shape, RDF.type, k) in g for k in CLASS_KINDS)


def subset(shapes):
    """Return (in-graph shapes, dropped) where dropped is a sorted list of (shape, constraint, reason).
    sh:message and sh:severity are removed but not listed: they are not constraints."""
    g = Graph()
    for prefix, ns in shapes.namespaces():
        g.bind(prefix, ns)
    g += shapes
    dropped = []
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
    node_shapes = sorted(set(g.subjects(RDF.type, SH.NodeShape)), key=str)
    unapplied = [n for n in node_shapes if not _applied(g, n)]
    kept_uses = {ps for n in node_shapes if n not in unapplied for ps in g.objects(n, SH.property)}
    for shape in unapplied:
        for prop in list(g.objects(shape, SH.property)):
            if prop not in kept_uses:
                _remove_subject(g, prop)
        _remove_subject(g, shape)
        dropped.append((shape, RDF.type, "a node shape n10s does not apply: no sh:targetClass and not a class"))
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
