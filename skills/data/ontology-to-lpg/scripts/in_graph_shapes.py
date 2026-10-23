#!/usr/bin/env python3
"""Generate the subset of the shapes that n10s 2025.06.1 can run inside Neo4j.

Run: uv run --with rdflib python3 in_graph_shapes.py --output <shapes-in-graph.ttl> <shapes.ttl>...

What it drops, and why (references/pipeline.md, rule 13):
  sh:datatype rdf:langString                   n10s rejects it
  sh:not, sh:languageIn, sh:node,
  sh:targetSubjectsOf, sh:targetObjectsOf      n10s does not support them
  sh:target                                    SHACL-SPARQL target; n10s never runs it
  sh:sparql                                    SHACL-SPARQL constraint; the check step runs it
  sh:pattern, sh:flags                         n10s matches the whole string (Cypher =~); SHACL searches it
  sh:in with a literal member                  n10s compares a literal list as strings
  sh:message, sh:severity                      not constraints; left out of the in-graph file
  a node shape left without sh:targetClass     n10s validates only targeted node shapes
The full shapes still run before the load; the round-trip diff carries their result into the graph.
sh:in lists of IRIs stay.

It writes the subset as Turtle and prints one line per dropped constraint, so the projection's
report can record what was dropped. Exit 0 on success, 2 when a file cannot be read or the
arguments are wrong.
"""
import sys

from rdflib import BNode, Graph, Literal
from rdflib.collection import Collection
from rdflib.namespace import RDF, SH

UNSUPPORTED = {
    SH["not"]: "n10s does not support sh:not",
    SH.languageIn: "n10s does not support sh:languageIn",
    SH.node: "n10s does not support sh:node",
    SH.targetSubjectsOf: "n10s does not support sh:targetSubjectsOf",
    SH.targetObjectsOf: "n10s does not support sh:targetObjectsOf",
    SH.target: "SHACL-SPARQL target; n10s never runs it",
    SH.sparql: "SHACL-SPARQL constraint; the check step runs it before the load",
    SH.pattern: "n10s matches sh:pattern against the whole string; SHACL searches it",
    SH.flags: "goes with sh:pattern",
}
NOT_CONSTRAINTS = {SH.message, SH.severity}


def _remove_subject(g, node):
    """Remove a node's triples and, recursively, those of the blank nodes it points to."""
    for _, _, o in list(g.triples((node, None, None))):
        g.remove((node, None, o))
        if isinstance(o, BNode):
            _remove_subject(g, o)


def subset(shapes):
    """Return (in-graph shapes, dropped) where dropped is a sorted list of (shape, constraint, reason)."""
    g = Graph()
    for prefix, ns in shapes.namespaces():
        g.bind(prefix, ns)
    g += shapes
    dropped = []
    for s, p, o in sorted(shapes, key=lambda t: tuple(str(x) for x in t)):
        if (s, p, o) not in g:
            continue
        reason = None
        if p in UNSUPPORTED:
            reason = UNSUPPORTED[p]
        elif p == SH.datatype and o == RDF.langString:
            reason = "n10s rejects sh:datatype rdf:langString"
        elif p == SH["in"] and any(isinstance(m, Literal) for m in Collection(shapes, o)):
            reason = "n10s compares a literal sh:in list as strings"
        elif p in NOT_CONSTRAINTS:
            g.remove((s, p, o))
            continue
        if reason:
            g.remove((s, p, o))
            if isinstance(o, BNode):
                _remove_subject(g, o)
            dropped.append((s, p, reason))
    for shape in sorted(set(g.subjects(RDF.type, SH.NodeShape)), key=str):
        if (shape, SH.targetClass, None) not in g:
            for prop in list(g.objects(shape, SH.property)):
                _remove_subject(g, prop)
            _remove_subject(g, shape)
            dropped.append((shape, RDF.type, "a node shape without sh:targetClass; n10s validates only targeted shapes"))
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
