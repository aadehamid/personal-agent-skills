#!/usr/bin/env python3
"""Generate the subset of the shapes that n10s 2025.06.1 can run inside Neo4j.

Run: uv run --no-project --with rdflib python3 in_graph_shapes.py --output <shapes-in-graph.ttl> <shapes.ttl>...

The subset is built from n10s's own queries, not from rules written beside them. n10s compiles
shapes with three SPARQL queries in SHACLValidator.java at tag 2025.06.1 (commit 6a5846b):
PROP_CONSTRAINT_QUERY (lines 59 to 123), NODE_CONSTRAINT_QUERY (lines 125 to 151) and
NODE_ADDITIONAL_CONSTRAINT_QUERY (lines 154 to 180), run at lines 982, 1090 and 1131. This script
runs their selection patterns, quoted below, with rdflib over the shapes, and copies into the subset
only what a row of one of them reaches:

  property rows (lines 72 to 74 and 84 to 94):
    ?ns a ?shapeOrNodeShape ; sh:node?/sh:property ?ps .
    filter ( ?shapeOrNodeShape = sh:Shape || ?shapeOrNodeShape = sh:NodeShape )
    { { ?ns sh:targetClass ?targetClass . } union
      { ?targetClass sh:property ?ps; a rdfs:Class . } union
      { ?ns sh:targetQuery ?targetClass . } }
  closed rows (lines 129 to 151):
    ?ns a sh:NodeShape ; sh:closed true .  with the same three targets, the class one as
    "?targetClass a rdfs:Class . filter(?targetClass = ?ns)"
  node-class rows (lines 158 to 180): ?ns a sh:NodeShape, the same targets, and ?ns sh:class

From each property shape a row reaches, it copies the terms the property query reads (lines 76 to
119: sh:path or an inverse path, sh:class, sh:nodeKind, sh:datatype, the counts, ranges and lengths,
sh:hasValue, sh:in, sh:disjoint), except values n10s mishandles:
  sh:datatype outside n10s's list              n10s throws for any datatype but xsd:boolean, string,
                                               integer, float, decimal, date, dateTime, anyURI and
                                               geo:wktLiteral (lines 1191 to 1209)
  sh:pattern, sh:flags                         n10s matches the whole string (Cypher =~); patterns are
                                               checked before the load only
  sh:in with a literal member                  n10s compares a literal list as strings
  sh:hasValue with a literal                   n10s compares a literal value as a string
  sh:path values other than a predicate or    the query reads only sh:path and sh:path/sh:inversePath
  an inverse path                              (lines 76 and 77) and skips the rest (line 989); a
                                               shape with no usable path, or none at all (line 992
                                               throws), leaves the subset with its edges
  a count, range or length that is not a       n10s reads it as a literal number and would throw
  literal
  sh:message, sh:severity and the other        not constraints; left out of the in-graph file
  non-validating terms
A shape with sh:deactivated true is removed first: SHACL skips it, and n10s does not read the flag.
Everything else is dropped and listed with its reason, which names the condition that failed for
that node. The full shapes still run before the load; the round-trip diff carries their result
into the graph.

Exit 0 on success, 2 when a file cannot be read or the arguments are wrong.
"""
import sys

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import RDF, RDFS, SH, XSD

# n10s's own target extension, a Cypher query (not a SHACL term, so rdflib's SH does not list it).
TARGET_QUERY = URIRef(str(SH) + "targetQuery")
SHAPE_TYPES = {SH.NodeShape, SH.PropertyShape, SH.Shape}
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
  ?ns a sh:NodeShape .
""" + TARGETS % "?targetClass a rdfs:Class . filter(?targetClass = ?ns) ." + """
  { ?ns sh:class ?class . filter(isIRI(?class)) } union { ?ns sh:class [ sh:not ?dc ] . filter(isIRI(?dc)) }
}"""

# The terms PROP_CONSTRAINT_QUERY reads from a property shape (lines 76 to 119).
PROPERTY_TERMS = {SH.path, SH["class"], SH.nodeKind, SH.datatype, SH.maxCount, SH.minCount, SH.minInclusive,
                  SH.maxInclusive, SH.minExclusive, SH.maxExclusive, SH.minLength, SH.maxLength, SH.hasValue,
                  SH["in"], SH.disjoint}
NOT_CONSTRAINTS = {SH.message, SH.severity, SH.name, SH.description, SH.order, SH.group, SH.defaultValue}
KNOWN_REASONS = {
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
# SHACLValidator.getDatatypeCastExpressionSuff at tag 2025.06.1 accepts only these; others throw.
N10S_DATATYPES = {XSD.boolean, XSD.string, XSD.integer, XSD.float, XSD.decimal, XSD.date, XSD.dateTime,
                  XSD.anyURI, URIRef("http://www.opengis.net/ont/geosparql#wktLiteral")}


def _rows(g, query, columns):
    return sorted({tuple(bool(r[c].toPython()) if c == "targetIsQuery" else r[c] for c in columns)
                   for r in g.query(query)}, key=lambda row: tuple(str(x) for x in row))


def property_rows(g):
    """Rows of n10s's property query: (node shape, property shape, target class or query, is query)."""
    return _rows(g, PROPERTY_ROWS, ("ns", "ps", "targetClass", "targetIsQuery"))


def closed_rows(g):
    """Rows of n10s's closed-shape query: (node shape, target class or query, is query)."""
    return _rows(g, CLOSED_ROWS, ("ns", "targetClass", "targetIsQuery"))


def node_class_rows(g):
    """Rows of n10s's node-level sh:class query: (node shape, target class or query, is query)."""
    return _rows(g, NODE_CLASS_ROWS, ("ns", "targetClass", "targetIsQuery"))


def value_reason(shapes, p, o):
    """Why n10s cannot run this term of an applied property shape, or None when it can."""
    if p in KNOWN_REASONS:
        return KNOWN_REASONS[p]
    if p == SH.node:
        return "n10s does not run sh:node on a property shape (a value shape)"
    if p == SH.datatype and o not in N10S_DATATYPES:
        return f"n10s throws for sh:datatype {o.n3(shapes.namespace_manager)}"
    if p == SH["in"] and any(isinstance(m, Literal) for m in Collection(shapes, o)):
        return "n10s compares a literal sh:in list as strings"
    if p == SH.hasValue and isinstance(o, Literal):
        return "n10s compares a literal sh:hasValue as a string"
    if p == SH.path:
        return path_reason(shapes, o)
    if str(p).startswith(str(SH)) and p not in PROPERTY_TERMS:
        return f"n10s's shape query does not read {p.n3(shapes.namespace_manager)}"
    return None


NUMERIC_TERMS = {SH.minCount, SH.maxCount, SH.minLength, SH.maxLength, SH.minInclusive, SH.maxInclusive,
                 SH.minExclusive, SH.maxExclusive}


def path_reason(g, path):
    """Why n10s cannot use this one sh:path value, or None. It reads ?path and ?invPath (lines 76 and
    77); a blank-node path that is not an inverse path is skipped (line 989)."""
    if isinstance(path, URIRef) or (path is not None and isinstance(g.value(path, SH.inversePath), URIRef)):
        return None
    return "n10s reads a predicate or an inverse path only (lines 76 and 77); it skips this path (line 989)"


def usable_paths(g, ps):
    """The sh:path values of ps that n10s compiles, in a fixed order (not the store's order)."""
    return sorted((o for o in g.objects(ps, SH.path) if path_reason(g, o) is None), key=lambda t: (isinstance(t, BNode), str(t)))


def shape_path_reason(g, ps):
    """Why n10s compiles no path of ps, or None when at least one of its sh:path values is usable. A
    missing path throws at path.stringValue() (line 992), and the catch at line 1161 loses every
    later row; a shape with only skipped paths compiles nothing. Either way the shape leaves the
    subset with its edges."""
    paths = list(g.objects(ps, SH.path))
    if not paths:
        return "it has no sh:path; n10s would throw on it and stop reading the remaining shapes (lines 992, 1161)"
    if not usable_paths(g, ps):
        return "none of its sh:path values is a predicate or an inverse path; n10s skips each (line 989)"
    return None


def value_reason(shapes, p, o):
    """Why n10s cannot run this term of an applied property shape, or None when it can."""
    if p in KNOWN_REASONS:
        return KNOWN_REASONS[p]
    if p == SH.node:
        return "n10s does not run sh:node on a property shape (a value shape)"
    if p == SH.datatype and o not in N10S_DATATYPES:
        return f"n10s throws for sh:datatype {o.n3(shapes.namespace_manager)}"
    if p == SH["in"] and any(isinstance(m, Literal) for m in Collection(shapes, o)):
        return "n10s compares a literal sh:in list as strings"
    if p == SH.hasValue and isinstance(o, Literal):
        return "n10s compares a literal sh:hasValue as a string"
    if p in NUMERIC_TERMS and not isinstance(o, Literal):
        return f"n10s reads {p.n3(shapes.namespace_manager)} as a literal number; this value would throw"
    if p == SH.path:
        return path_reason(shapes, o)
    if str(p).startswith(str(SH)) and p not in PROPERTY_TERMS:
        return f"n10s's shape query does not read {p.n3(shapes.namespace_manager)}"
    return None


def _copy_tree(src, dst, node):
    """Copy a blank node's triples (an RDF list, an inverse path) recursively."""
    for _, p, o in src.triples((node, None, None)):
        dst.add((node, p, o))
        if isinstance(o, BNode):
            _copy_tree(src, dst, o)


def _is_shape(g, s):
    return (s, RDF.type, SH.NodeShape) in g or (s, RDF.type, SH.Shape) in g


def _has_target(g, s):
    return (s, SH.targetClass, None) in g or (s, TARGET_QUERY, None) in g


def _short(g, term):
    return term.n3(g.namespace_manager)


def _source_facts(g, s):
    """The conditions that keep s from being the ?ns of a property row, for any property shape."""
    facts = []
    if not _is_shape(g, s):
        facts.append("it is not typed sh:NodeShape or sh:Shape (lines 72 to 74)")
    if not _has_target(g, s):
        facts.append("it has no sh:targetClass or sh:targetQuery (lines 84 to 94)")
    return facts


def property_reason(g, ps):
    """Why no row of the property query applies ps, naming only the conditions that failed."""
    reason = shape_path_reason(g, ps)
    if reason:
        return "PROP_CONSTRAINT_QUERY: " + reason
    reachers = {n for n in g.subjects(SH.property, ps)} | {n for m in g.subjects(SH.property, ps)
                                                            for n in g.subjects(SH.node, m)}
    typed = sorted((n for n in reachers if _is_shape(g, n)), key=str)
    if not typed:
        return ("PROP_CONSTRAINT_QUERY (lines 72 to 74) returns no row: no shape typed sh:NodeShape or sh:Shape "
                "reaches it through sh:node?/sh:property")
    return ("PROP_CONSTRAINT_QUERY (lines 84 to 94) returns no row: the typed shapes that reach it ("
            + ", ".join(_short(g, n) for n in typed)
            + ") have no sh:targetClass or sh:targetQuery, and no rdfs:Class has it as its own sh:property")


def node_reason(g, s, p, o, kept_ps):
    """Why the triple (s, p, o) of a node shape is not in the subset, naming only what failed for it."""
    if p == SH.property:
        if o in kept_ps:
            return "this link is not read, though the property shape is applied through another shape: " + \
                "; ".join(_source_facts(g, s) or ["no row of the property query uses it"])
        return f"its property shape {_short(g, o)} is not applied: " + property_reason(g, o)
    if p == SH.node:
        if (o, SH.property, None) not in g:
            return f"PROP_CONSTRAINT_QUERY returns no row through it: {_short(g, o)} has no sh:property"
        facts = _source_facts(g, s)
        if (o, RDF.type, RDFS.Class) not in g:
            facts.append(f"{_short(g, o)} is not an rdfs:Class with its own sh:property")
        return "PROP_CONSTRAINT_QUERY returns no row through it: " + "; ".join(
            facts or ["no property shape behind it is applied"])
    if p in (SH.closed, SH.ignoredProperties):
        facts = []
        if p == SH.closed and o != Literal(True):
            facts.append("only sh:closed true is read")
        if (s, RDF.type, SH.NodeShape) not in g:
            facts.append("it is not typed sh:NodeShape (sh:Shape is not enough for this query)")
        if p == SH.ignoredProperties and (s, SH.closed, Literal(True)) not in g:
            facts.append("it does not say sh:closed true")
        if not _has_target(g, s):
            facts.append("it has no sh:targetClass or sh:targetQuery" + (
                ", and its class branch cannot stand in: filter(?targetClass = ?ns) sits inside the union group "
                "(line 138), where ?ns is unbound, so that branch returns no row"
                if (s, RDF.type, RDFS.Class) in g else ""))
        return "NODE_CONSTRAINT_QUERY (lines 129 to 151) returns no row: " + "; ".join(facts or ["no row reads it"])
    if p == SH["class"]:
        facts = []
        if not (isinstance(o, URIRef) or isinstance(g.value(o, SH["not"]), URIRef)):
            facts.append("this sh:class value is neither an IRI nor sh:not of one")
        if (s, RDF.type, SH.NodeShape) not in g:
            facts.append("it is not typed sh:NodeShape")
        if not _has_target(g, s):
            facts.append("it has no sh:targetClass or sh:targetQuery" + (
                " (its class branch filters on ?ns inside the union group, line 167, and returns no row)"
                if (s, RDF.type, RDFS.Class) in g else ""))
        return "NODE_ADDITIONAL_CONSTRAINT_QUERY (lines 158 to 180) returns no row: " + "; ".join(
            facts or ["no row reads it"])
    facts = _source_facts(g, s)
    if facts:
        return "no n10s query applies this shape: " + "; ".join(facts)
    return ("no n10s query applies this shape: none of its property shapes is applied, and it is not a "
            "targeted sh:NodeShape with sh:closed true or a node-level sh:class")


def _add_target(g, out, ns, target, is_query):
    if is_query:
        out.add((ns, TARGET_QUERY, target))
    elif (ns, SH.targetClass, target) in g:
        out.add((ns, SH.targetClass, target))
    else:
        out.add((target, RDF.type, RDFS.Class))


def _is_property_shape(g, s):
    return (s, SH.path, None) in g or ((None, SH.property, s) in g and not _is_shape(g, s))


def subset(shapes):
    """Return (in-graph shapes, dropped) where dropped is a sorted list of (node, term, reason)."""
    g = Graph()
    for prefix, ns in shapes.namespaces():
        g.bind(prefix, ns)
    g += shapes
    dropped = []
    for shape in sorted(set(shapes.subjects(SH.deactivated, Literal(True))), key=str):
        for parent, _, _ in list(g.triples((None, SH.property, shape))):
            g.remove((parent, SH.property, shape))
        for _, p, o in list(g.triples((shape, None, None))):
            g.remove((shape, p, o))
        dropped.append((shape, SH.deactivated, "deactivated: SHACL skips it, and n10s does not read the flag"))

    out = Graph()
    for prefix, ns in shapes.namespaces():
        out.bind(prefix, ns)
    rows = [row for row in property_rows(g) if shape_path_reason(g, row[1]) is None]
    for ns, ps, target, is_query in rows:
        for t in (SH.NodeShape, SH.Shape):
            if (ns, RDF.type, t) in g:
                out.add((ns, RDF.type, t))
        _add_target(g, out, ns, target, is_query)
        if not is_query and (target, SH.property, ps) in g:
            out.add((target, SH.property, ps))
        if (ns, SH.property, ps) in g:
            out.add((ns, SH.property, ps))
        for mid in g.objects(ns, SH.node):
            if (mid, SH.property, ps) in g:
                out.add((ns, SH.node, mid))
                out.add((mid, SH.property, ps))
    kept_ps = {row[1] for row in rows}
    for ps in sorted(kept_ps, key=str):
        for _, p, o in g.triples((ps, None, None)):
            if p == RDF.type or (p in PROPERTY_TERMS and value_reason(g, p, o) is None):
                out.add((ps, p, o))
                if isinstance(o, BNode):
                    _copy_tree(g, out, o)
    for ns, target, is_query in closed_rows(g):
        out.add((ns, RDF.type, SH.NodeShape))
        out.add((ns, SH.closed, Literal(True)))
        _add_target(g, out, ns, target, is_query)
        for head in g.objects(ns, SH.ignoredProperties):
            out.add((ns, SH.ignoredProperties, head))
            _copy_tree(g, out, head)
    for ns, target, is_query in node_class_rows(g):
        out.add((ns, RDF.type, SH.NodeShape))
        _add_target(g, out, ns, target, is_query)
        for o in g.objects(ns, SH["class"]):
            if isinstance(o, URIRef) or isinstance(g.value(o, SH["not"]), URIRef):
                out.add((ns, SH["class"], o))
                if isinstance(o, BNode):
                    _copy_tree(g, out, o)

    for s, p, o in sorted(g, key=lambda t: tuple(str(x) for x in t)):
        if (s, p, o) in out or p in NOT_CONSTRAINTS:
            continue
        recordable = str(p).startswith(str(SH)) or (p == RDF.type and o in SHAPE_TYPES)
        if not recordable or (isinstance(s, BNode) and not _is_property_shape(g, s)):
            continue
        if s in kept_ps:
            reason = value_reason(g, p, o) or f"n10s's shape query does not read {_short(g, p)}"
        elif p in KNOWN_REASONS:
            reason = KNOWN_REASONS[p]
        elif _is_property_shape(g, s):
            reason = property_reason(g, s)
        else:
            reason = node_reason(g, s, p, o, kept_ps)
        dropped.append((s, p, reason))
    seen, unique = set(), []
    for s, p, r in sorted(dropped, key=lambda t: (str(t[0]), str(t[1]), t[2])):
        if (s, p, r) not in seen:
            seen.add((s, p, r))
            unique.append((s, p, r))
    return out, unique


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
