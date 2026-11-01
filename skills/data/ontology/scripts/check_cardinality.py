#!/usr/bin/env python3
"""Step 9: every property has a cardinality, and no node shape is empty (references/shacl.md, rules 5
and 8).

Run: uv run --no-project --with rdflib python3 check_cardinality.py --shapes <s.ttl>... --data <d.ttl>...

A property is any subject the data types owl:ObjectProperty, owl:DatatypeProperty or
owl:AnnotationProperty. Its cardinality is stated by a property shape (a node whose sh:path is the
property's IRI) holding sh:minCount or sh:maxCount, and counts only when a validator applies that
shape to the property's own subjects:
  applied   the property shape is reached from a root shape with the root's focus nodes kept: through
            sh:property, sh:node, sh:and, sh:or or sh:xone from a node shape, with no deactivated shape
            on the way (sh:deactivated true). Below a property shape the focus moves to that property's
            values, so a shape reached from there says nothing about the root's nodes. A root shape has
            a target (sh:targetClass, sh:targetNode, sh:targetSubjectsOf, sh:targetObjectsOf, a
            SHACL-SPARQL sh:target) or is itself a class (the implicit class target).
  its own   the root's target covers the property's subjects:
              - sh:targetSubjectsOf the property, always;
              - sh:targetClass or the implicit class, when it is an rdfs:domain of the property or a
                class that domain is rdfs:subClassOf, directly or through other classes in the data;
              - sh:targetNode, when the data types that node as the domain itself;
              - sh:targetObjectsOf or sh:targetSubjectsOf another property, when that property's
                rdfs:range or rdfs:domain is the domain itself.
            A target on a subclass of the domain leaves the domain's other members out, so it does not
            count.
            A property with no domain (an annotation property) is covered only by sh:targetSubjectsOf
            the property, since nothing else says which things carry it. A SHACL-SPARQL target covers
            no property, because this check does not run its query and cannot show what it selects;
            state the cardinality on a Core target (shacl.md, rule 6).

Checks:
  cardinality  every property has an applied property shape of its own stating sh:minCount or
               sh:maxCount, properties declared but not used yet included (rule 5)
  empty-shape  no root node shape holds neither a property shape nor a constraint, because such a
               shape can never fail (rule 8); the skeleton gives a node shape only to a class that
               has properties

Prints one FAIL line per failure. Exit 0 when nothing fails, 1 when anything fails, 2 when a file cannot
be read or parsed or the arguments are wrong.
"""
import argparse
import sys

from rdflib import Graph, Literal
from rdflib.collection import Collection
from rdflib.namespace import OWL, RDF, RDFS, SH

PROPERTY_KINDS = (OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty)
CLASS_KINDS = (RDFS.Class, OWL.Class)
TARGETS = (SH.targetClass, SH.targetNode, SH.targetSubjectsOf, SH.targetObjectsOf, SH.target)
LISTS = (SH["and"], SH["or"], SH.xone)
# SHACL predicates that describe a shape without constraining anything.
NOT_A_CONSTRAINT = {*TARGETS, SH.deactivated, SH.severity, SH.message, SH.name, SH.description,
                    SH.order, SH.group, SH.path, SH.defaultValue}


def deactivated(shapes, node):
    return shapes.value(node, SH.deactivated) == Literal(True)


def is_class(shapes, node):
    return any((node, RDF.type, kind) in shapes for kind in CLASS_KINDS)


def roots(shapes):
    """Every shape a validator starts from: a target of its own, or the implicit class target."""
    found = {s for t in TARGETS for s in shapes.subjects(t, None)}
    found |= {s for s in shapes.subjects(RDF.type, SH.NodeShape) if is_class(shapes, s)}
    found |= {s for s in shapes.subjects(SH.property, None) if is_class(shapes, s)}
    return {s for s in found if not deactivated(shapes, s)}


def reached(shapes, root):
    """Every shape that applies to the root's own focus nodes: through sh:property, sh:node, sh:and,
    sh:or and sh:xone, stopping at a deactivated shape and below a property shape, whose reuse applies
    to its values."""
    seen, frontier = {root}, [root]
    while frontier:
        shape = frontier.pop()
        if (shape, SH.path, None) in shapes:
            continue
        nxt = [o for p in (SH.property, SH.node) for o in shapes.objects(shape, p)]
        for p in LISTS:
            for head in shapes.objects(shape, p):
                nxt += list(Collection(shapes, head))
        for n in nxt:
            if n not in seen and not deactivated(shapes, n):
                seen.add(n)
                frontier.append(n)
    return seen


def superclasses(data, cls):
    """The class and every class it is rdfs:subClassOf, through the data's own classes."""
    out, frontier = {cls}, [cls]
    while frontier:
        c = frontier.pop()
        for parent in data.objects(c, RDFS.subClassOf):
            if parent not in out:
                out.add(parent)
                frontier.append(parent)
    return out


def selected_types(shapes, data, root):
    """The classes the nodes of the root's instance targets are known to be in."""
    types = {t for node in shapes.objects(root, SH.targetNode) for t in data.objects(node, RDF.type)}
    types |= {t for q in shapes.objects(root, SH.targetObjectsOf) for t in data.objects(q, RDFS.range)}
    types |= {t for q in shapes.objects(root, SH.targetSubjectsOf) for t in data.objects(q, RDFS.domain)}
    return types


def covers(shapes, data, root, prop):
    """Whether the root's target covers the property's subjects."""
    if (root, SH.targetSubjectsOf, prop) in shapes:
        return True
    classes = set(shapes.objects(root, SH.targetClass))
    if is_class(shapes, root):
        classes.add(root)
    types = selected_types(shapes, data, root)
    for domain in data.objects(prop, RDFS.domain):
        if classes & superclasses(data, domain) or domain in types:
            return True
    return False


def applied_property_shapes(shapes):
    """(path, property shape) for every property shape a root applies to its own focus nodes."""
    return {(shapes.value(n, SH.path), n) for root in roots(shapes) for n in reached(shapes, root)
            if (n, SH.path, None) in shapes}


def states(shapes, node, prop):
    return (shapes.value(node, SH.path) == prop
            and ((node, SH.minCount, None) in shapes or (node, SH.maxCount, None) in shapes))


def constrains(shapes, node):
    return any(str(p).startswith(str(SH)) and p not in NOT_A_CONSTRAINT for p in shapes.predicates(node, None))


def check(data, shapes):
    """Return failures as (check name, message)."""
    fails = []
    applied = {root: reached(shapes, root) for root in roots(shapes)}
    properties = sorted({p for kind in PROPERTY_KINDS for p in data.subjects(RDF.type, kind)}, key=str)
    for prop in properties:
        if not any(covers(shapes, data, root, prop) and any(states(shapes, node, prop) for node in nodes)
                   for root, nodes in applied.items()):
            fails.append(("cardinality", f"{prop} has no applied property shape of its own stating sh:minCount or sh:maxCount"))
    for root in sorted(applied, key=str):
        if (root, SH.path, None) in shapes:
            continue
        if not constrains(shapes, root):
            fails.append(("empty-shape", f"{root} holds no property shape and no constraint, so it can never fail; "
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
