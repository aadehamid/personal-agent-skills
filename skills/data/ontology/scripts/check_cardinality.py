#!/usr/bin/env python3
"""Step 9: every property has a cardinality, and no node shape is empty (references/shacl.md, rules 5
and 8).

Run: uv run --no-project --with rdflib python3 check_cardinality.py --shapes <s.ttl>... --data <d.ttl>...

A property is any subject the data types owl:ObjectProperty, owl:DatatypeProperty or
owl:AnnotationProperty. A property shape is any node whose sh:path is an IRI; it is live when it is not
deactivated and either has a target of its own or is the sh:property of a node shape that has a target
and is not deactivated, because a shape nothing targets never runs. A shape has a target when it holds
sh:targetClass, sh:targetNode, sh:targetSubjectsOf or sh:targetObjectsOf.

Checks:
  cardinality  every property has a live property shape on its path that states sh:minCount or
               sh:maxCount, properties declared but not used yet included (rule 5)
  empty-shape  no node shape with a target holds neither a property shape nor a constraint, because
               such a shape can never fail (rule 8); the skeleton gives a node shape only to a class
               that has properties

Prints one FAIL line per failure. Exit 0 when nothing fails, 1 when anything fails, 2 when a file cannot
be read or parsed or the arguments are wrong.
"""
import argparse
import sys

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, SH

PROPERTY_KINDS = (OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty)
TARGETS = (SH.targetClass, SH.targetNode, SH.targetSubjectsOf, SH.targetObjectsOf)
# SHACL predicates that describe a shape without constraining anything.
NOT_A_CONSTRAINT = {*TARGETS, SH.deactivated, SH.severity, SH.message, SH.name, SH.description,
                    SH.order, SH.group, SH.path, SH.defaultValue}


def deactivated(shapes, node):
    return shapes.value(node, SH.deactivated) == Literal(True)


def targeted(shapes, node):
    return any((node, t, None) in shapes for t in TARGETS)


def live_property_shapes(shapes):
    """Every property shape that runs: not deactivated, and targeted itself or held by a targeted node shape."""
    live = set()
    for ps in set(shapes.subjects(SH.path, None)):
        if not isinstance(shapes.value(ps, SH.path), URIRef) or deactivated(shapes, ps):
            continue
        holders = [n for n in shapes.subjects(SH.property, ps) if targeted(shapes, n) and not deactivated(shapes, n)]
        if targeted(shapes, ps) or holders:
            live.add(ps)
    return live


def constrains(shapes, node):
    return any(str(p).startswith(str(SH)) and p not in NOT_A_CONSTRAINT for p in shapes.predicates(node, None))


def check(data, shapes):
    """Return failures as (check name, message)."""
    fails = []
    stated = {}
    for ps in live_property_shapes(shapes):
        if (ps, SH.minCount, None) in shapes or (ps, SH.maxCount, None) in shapes:
            stated.setdefault(shapes.value(ps, SH.path), set()).add(ps)
    properties = sorted({p for kind in PROPERTY_KINDS for p in data.subjects(RDF.type, kind)}, key=str)
    for prop in properties:
        if prop not in stated:
            fails.append(("cardinality", f"{prop} has no live property shape stating sh:minCount or sh:maxCount"))
    node_shapes = {n for t in TARGETS for n in shapes.subjects(t, None)} | set(shapes.subjects(RDF.type, SH.NodeShape))
    for node in sorted(node_shapes, key=str):
        if (node, SH.path, None) in shapes or deactivated(shapes, node) or not targeted(shapes, node):
            continue
        if not constrains(shapes, node):
            fails.append(("empty-shape", f"{node} holds no property shape and no constraint, so it can never fail; "
                                         "drop it, or give it the class's property shapes"))
    return fails


def main(argv):
    p = argparse.ArgumentParser(prog="check_cardinality.py")
    p.add_argument("--shapes", nargs="+", required=True)
    p.add_argument("--data", nargs="+", required=True)
    try:
        args = p.parse_args(argv)
    except SystemExit:
        return 2
    shapes, data = Graph(), Graph()
    try:
        for path in args.shapes:
            shapes.parse(path)
        for path in args.data:
            data.parse(path)
    except Exception as exc:  # a missing file or an rdflib parser error
        print(f"ERROR cannot read the input: {exc}", file=sys.stderr)
        return 2
    fails = check(data, shapes)
    for name, message in fails:
        print(f"FAIL {name}: {message}")
    if fails:
        print(f"{len(fails)} check(s) failed", file=sys.stderr)
        return 1
    count = len({p for kind in PROPERTY_KINDS for p in data.subjects(RDF.type, kind)})
    print(f"every property has a cardinality ({count} properties)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
