#!/usr/bin/env python3
"""Prepare the shapes file n10s 2025.06.1 imports, and predict what it will compile (advisory).

Run: uv run --no-project --with rdflib python3 in_graph_shapes.py --output <shapes-in-graph.ttl> <shapes.ttl>...

This script gates nothing. What n10s compiled is read back from the engine by load_verify.py
(n10s.validation.shacl.listShapes()), and that readback is the gate.

1. It writes a copy of the shapes without the terms that would make n10s throw on import or judge
   valid data wrong, and lists each with its reason:
     sh:datatype outside n10s's list   n10s throws for any datatype but xsd:boolean, string, integer,
                                       float, decimal, date, dateTime, anyURI and geo:wktLiteral
                                       (SHACLValidator.java at tag 2025.06.1, lines 1191 to 1209)
     sh:pattern, sh:flags              n10s matches the whole string (Cypher =~); SHACL searches it
     sh:in with a literal member       n10s compares a literal list as strings
     sh:hasValue with a literal        n10s compares a literal value as a string
     a value term on an inverse path   n10s checks it against the outgoing relationships: it reads
       (sh:class, sh:in, sh:datatype,  the inverse flag only for cardinality (line 580); a load with
       sh:nodeKind and the others)     sh:class on [ sh:inversePath p ] caught an outgoing p to an
                                       unclassed node and missed an incoming one
     a shape with sh:deactivated true  SHACL skips it, and n10s does not read the flag
   Everything else stays: what n10s does not read, it ignores, and load_verify.py reports it.

2. It prints a PREDICTION of the (target, path, term) rows n10s will list, made by running the
   selection patterns of n10s's PROP_CONSTRAINT_QUERY (lines 72 to 74 and 84 to 94) and
   NODE_CONSTRAINT_QUERY (lines 129 to 151) over the shapes with rdflib. It is a dry run for
   reading the shapes before a load; where it and the engine disagree, the engine is right.

Exit 0 on success, 2 when a file cannot be read or the arguments are wrong.
"""
import sys

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import SH, XSD

from shell import q

# n10s's own target extension, a Cypher query (not a SHACL term, so rdflib's SH does not list it).
TARGET_QUERY = URIRef(str(SH) + "targetQuery")
PREFIXES = "PREFIX sh: <http://www.w3.org/ns/shacl#>\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
TARGETS = """
  {
    { ?ns sh:targetClass ?targetClass . bind( false as ?targetIsQuery ) }
    union
    { %s bind( false as ?targetIsQuery ) }
    union
    { ?ns sh:targetQuery ?targetClass . bind( true as ?targetIsQuery ) }
  }"""
PROPERTY_ROWS = PREFIXES + """SELECT DISTINCT ?ns ?ps ?targetClass ?targetIsQuery WHERE {
  ?ns a ?shapeOrNodeShape ;
     sh:node?/sh:property ?ps .
  filter ( ?shapeOrNodeShape = sh:Shape || ?shapeOrNodeShape = sh:NodeShape )
""" + TARGETS % "?targetClass sh:property ?ps; a rdfs:Class ." + "\n}"
CLOSED_ROWS = PREFIXES + """SELECT DISTINCT ?ns ?targetClass ?targetIsQuery WHERE {
  ?ns a sh:NodeShape ;
      sh:closed true .
""" + TARGETS % "?targetClass a rdfs:Class . filter(?targetClass = ?ns) ." + "\n}"

NODE_CLASS_ROWS = PREFIXES + """SELECT DISTINCT ?ns ?targetClass ?targetIsQuery WHERE {
  ?ns a sh:NodeShape ;
      sh:class ?class .
""" + TARGETS % "?targetClass a rdfs:Class . filter(?targetClass = ?ns) ." + "\n}"

# SHACLValidator.getDatatypeCastExpressionSuff at tag 2025.06.1 accepts only these; others throw.
N10S_DATATYPES = {XSD.boolean, XSD.string, XSD.integer, XSD.float, XSD.decimal, XSD.date, XSD.dateTime,
                  XSD.anyURI, URIRef("http://www.opengis.net/ont/geosparql#wktLiteral")}
# The constraint terms of a property shape the prediction lists.
PREDICTED_TERMS = (SH.minCount, SH.maxCount, SH.datatype, SH["class"], SH.nodeKind, SH["in"], SH.hasValue,
                   SH.disjoint, SH.minInclusive, SH.maxInclusive, SH.minExclusive, SH.maxExclusive, SH.minLength,
                   SH.maxLength)
# Value terms n10s 2025.06.1 would check in the wrong direction on an inverse path: its
# SHACLValidator.java reads the "inverse" flag only for cardinality (line 580).
INVERSE_UNREAD = (SH.datatype, SH["class"], SH.nodeKind, SH["in"], SH.hasValue, SH.disjoint, SH.minInclusive,
                  SH.maxInclusive, SH.minExclusive, SH.maxExclusive, SH.minLength, SH.maxLength, SH.pattern)
# How n10s 2025.06.1 names a term in listShapes(), where that differs from the SHACL term.
LISTED_AS = {SH.nodeKind: "sh:NodeKind", SH.disjoint: "sh:hasValue"}


def _inverse(shapes, ps):
    path = shapes.value(ps, SH.path)
    return isinstance(path, BNode) and shapes.value(path, SH.inversePath) is not None


def sanitize_reason(shapes, p, o, s=None):
    """Why this term (on shape s) must not reach n10s, or None."""
    if s is not None and p in INVERSE_UNREAD and _inverse(shapes, s):
        return ("n10s checks a value constraint on an inverse path against the outgoing relationships; only "
                "cardinality reads the inverse flag")
    if p == SH.datatype and o not in N10S_DATATYPES:
        return f"n10s throws for sh:datatype {o.n3(shapes.namespace_manager)}"
    if p in (SH.pattern, SH.flags):
        return "n10s matches sh:pattern against the whole string; patterns are checked before the load only"
    if p == SH["in"] and any(isinstance(m, Literal) for m in Collection(shapes, o)):
        return "n10s compares a literal sh:in list as strings"
    if p == SH.hasValue and isinstance(o, Literal):
        return "n10s compares a literal sh:hasValue as a string"
    return None


def _remove_tree(g, node):
    for _, p, o in list(g.triples((node, None, None))):
        g.remove((node, p, o))
        if isinstance(o, BNode) and (None, None, o) not in g:
            _remove_tree(g, o)


def subset(shapes):
    """Return (shapes n10s can import, left out) where left out is a sorted list of (node, term, reason)."""
    g = Graph()
    for prefix, ns in shapes.namespaces():
        g.bind(prefix, ns)
    g += shapes
    dropped = []
    for shape in sorted(set(g.subjects(SH.deactivated, Literal(True))), key=str):
        for parent, _, _ in list(g.triples((None, SH.property, shape))):
            g.remove((parent, SH.property, shape))
        _remove_tree(g, shape)
        dropped.append((shape, SH.deactivated, "deactivated: SHACL skips it, and n10s does not read the flag"))
    for s, p, o in sorted(shapes, key=lambda t: tuple(str(x) for x in t)):
        if (s, p, o) not in g:
            continue
        reason = sanitize_reason(shapes, p, o, s)
        if reason:
            g.remove((s, p, o))
            if isinstance(o, BNode) and (None, None, o) not in g:
                _remove_tree(g, o)
            dropped.append((s, p, reason))
    return g, sorted(dropped, key=lambda t: (str(t[0]), str(t[1])))


def predict(g, name):
    """Advisory: the (target, path, term) rows n10s is expected to list for the shapes in g.
    name(iri) gives the SHORTEN name of an IRI. n10s lists a closed shape as an sh:ignoredProperties
    row with no path."""
    rows = set()
    for r in g.query(PROPERTY_ROWS):
        if r.targetIsQuery.toPython():
            continue
        path = g.value(r.ps, SH.path)
        inverse = g.value(path, SH.inversePath) if isinstance(path, BNode) else None
        if not isinstance(inverse or path, URIRef):
            continue
        for term in PREDICTED_TERMS:
            if (r.ps, term, None) in g:
                rows.add((name(r.targetClass), name(inverse or path), LISTED_AS.get(term, "sh:" + term.split("#")[-1])))
    for r in g.query(NODE_CLASS_ROWS):
        if not r.targetIsQuery.toPython():
            rows.add((name(r.targetClass), None, "sh:class"))
    for r in g.query(CLOSED_ROWS):
        if not r.targetIsQuery.toPython():
            rows.add((name(r.targetClass), None, "sh:ignoredProperties"))
    return rows


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
        print(f"ERROR cannot read the shapes: {q(exc)}", file=sys.stderr)
        return 2
    g, dropped = subset(shapes)
    g.serialize(output, format="turtle")
    # Every value is shell-quoted: a shapes file can put a newline or $(...) in an IRI or a literal.
    for shape, constraint, reason in dropped:
        print(f"left out {q(shape.n3(shapes.namespace_manager))} {q(constraint.n3(shapes.namespace_manager))}: "
              f"{q(reason)}")
    print(f"wrote {q(output)}: {len(g)} triples, {len(dropped)} term(s) left out")
    for target, path, term in sorted(predict(g, lambda iri: iri.n3(g.namespace_manager)), key=str):
        print(f"PREDICTION (advisory; load_verify.py reads what n10s compiled): {q(target)} {q(path)} {q(term)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
