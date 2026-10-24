#!/usr/bin/env python3
"""Step 9: every code-list property is shaped against its own list, and each such shape can fail
(references/shacl.md, rules 4 and 8).

Run: uv run --no-project --with rdflib --with pyshacl python3 check_code_lists.py --shapes <s.ttl>... --data <d.ttl>...
     [--not-code-list=<scheme IRI>]...

A code list is a skos:ConceptScheme in the data. A code-list property is any property outside the RDF,
RDFS, OWL and SKOS namespaces whose value, somewhere in the data, is a concept (an IRI or a blank node)
skos:inScheme a code list. --not-code-list leaves out a scheme whose concepts are things rather than coded
values (a taxonomy, a process hierarchy, an ontology header that is also a scheme), so properties that
link those concepts are not code-list properties.

A membership constraint on property P is one of
  scheme   a node shape with sh:targetObjectsOf P and a property shape sh:path skos:inScheme,
           sh:hasValue L; or a property shape sh:path P whose sh:node has that property shape;
  members  a property shape sh:path P with sh:in (a list of the allowed values).
sh:class skos:Concept is not one: it lets a value from the wrong list through. Two constraints on one
property both apply, as they do in SHACL.

Checks:
  covered     every code-list property has at least one membership constraint
  same-list   every value of the property (literals and blank nodes too) meets every constraint on it
  bites       for each constraint, moving one value to a concept that sits in a code list but meets none
              of the property's constraints makes that constraint's own shape report a result (its
              sh:sourceShape and sh:sourceConstraintComponent, so another shape firing, or another
              constraint on the same shape, proves nothing); with no such concept in the data,
              the check fails, because the shape cannot be shown to fail

Prints one FAIL line per failure. Exit 0 when nothing fails, 1 when anything fails, 2 when a file cannot
be read or parsed, a shape is not valid SHACL, or the arguments are wrong.
"""
import argparse
import sys

from pyshacl import validate
from rdflib import Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import OWL, RDF, RDFS, SH, SKOS

from check_shapes import rule_nodes

SKIP_NAMESPACES = (str(RDF), str(RDFS), str(OWL), str(SKOS))


def code_lists(data, excluded):
    return set(data.subjects(RDF.type, SKOS.ConceptScheme)) - excluded


def coded_properties(data, lists):
    """{property: set of lists its values sit in}."""
    out = {}
    for _, p, o in data:
        if str(p).startswith(SKIP_NAMESPACES) or isinstance(o, Literal):
            continue
        in_lists = set(data.objects(o, SKOS.inScheme)) & lists
        if in_lists:
            out.setdefault(p, set()).update(in_lists)
    return out


def scheme_pins(shapes, node):
    """(list, property shape) for each skos:inScheme sh:hasValue pin on a node shape."""
    return [(shapes.value(ps, SH.hasValue), ps) for ps in shapes.objects(node, SH.property)
            if shapes.value(ps, SH.path) == SKOS.inScheme and shapes.value(ps, SH.hasValue) is not None]


def constraints(shapes):
    """{property: [(kind, allowed, sources)]}: kind "scheme" with a list IRI, or "members" with a set of
    values. sources holds the (shape, constraint component) pairs whose result shows this constraint
    firing: the pin's own skos:inScheme property shape with sh:HasValueConstraintComponent, or the sh:in
    property shape with sh:InConstraintComponent. Another constraint on the same shape (sh:class,
    sh:minCount, an outer sh:node) is a different pair, so its result proves nothing about the pin."""
    out = {}
    for node in set(shapes.subjects(SH.targetObjectsOf, None)):
        for prop in shapes.objects(node, SH.targetObjectsOf):
            for scheme, ps in scheme_pins(shapes, node):
                out.setdefault(prop, []).append(("scheme", scheme, {(ps, SH.HasValueConstraintComponent)}))
    for ps in set(shapes.subjects(SH.path, None)):
        prop = shapes.value(ps, SH.path)
        if not isinstance(prop, URIRef) or prop == SKOS.inScheme:
            continue
        for node in shapes.objects(ps, SH.node):
            for scheme, inner in scheme_pins(shapes, node):
                out.setdefault(prop, []).append(("scheme", scheme, {(inner, SH.HasValueConstraintComponent)}))
        for head in shapes.objects(ps, SH["in"]):
            out.setdefault(prop, []).append(("members", frozenset(Collection(shapes, head)),
                                             {(ps, SH.InConstraintComponent)}))
    return out


def meets(data, value, constraint):
    kind, allowed, _ = constraint
    if kind == "scheme":
        return (value, SKOS.inScheme, allowed) in data
    return value in allowed


def label(constraint):
    kind, allowed, _ = constraint
    return str(allowed) if kind == "scheme" else "sh:in (" + " ".join(sorted(map(str, allowed))) + ")"


def fired(data, shapes):
    """(source shape, source constraint component, focus node, value) of every validation result,
    nested ones included."""
    _, report, _ = validate(data, shacl_graph=shapes, advanced=True)
    return {(report.value(r, SH.sourceShape), report.value(r, SH.sourceConstraintComponent),
             report.value(r, SH.focusNode), report.value(r, SH.value))
            for r in report.subjects(RDF.type, SH.ValidationResult)}


def check(data, shapes, excluded=frozenset()):
    """Return failures as (check name, message)."""
    if rule_nodes(shapes):
        return [("bites", "the shapes hold a sh:rule, which changes the data before validation; remove it")]
    lists = code_lists(data, set(excluded))
    coded = coded_properties(data, lists)
    shaped = constraints(shapes)
    fails = []
    for prop in sorted(coded, key=str):
        cons = shaped.get(prop)
        if not cons:
            fails.append(("covered", f"{prop} takes values from {sorted(map(str, coded[prop]))} and no shape pins its list"))
            continue
        good = []
        for s, o in sorted(data.subject_objects(prop), key=str):
            broken = [c for c in cons if not meets(data, o, c)]
            if broken:
                fails.append(("same-list", f"{prop} on {s} is {o}, which is not in {', '.join(label(c) for c in broken)}"))
            else:
                good.append((s, o))
        witnesses = sorted((c for c, sch in data.subject_objects(SKOS.inScheme)
                            if sch in lists and not isinstance(c, Literal) and not any(meets(data, c, k) for k in cons)),
                           key=str)
        if not witnesses:
            fails.append(("bites", f"{prop}: no concept of another code list to test its shapes with"))
            continue
        if not good:
            continue  # every value already fails same-list
        s, o = good[0]
        mutated = Graph()
        mutated += data
        mutated.remove((s, prop, o))
        mutated.add((s, prop, witnesses[0]))
        # A bite is a result that is new after the move, comes from the constraint's own shape and
        # component, and names the moved value (as its focus for a scheme pin, as its value for sh:in).
        # A result the same shape already gave for another node proves nothing.
        new = fired(mutated, shapes) - fired(data, shapes)
        for c in cons:
            if not any((shape, comp) in c[2] and witnesses[0] in (focus, value) for shape, comp, focus, value in new):
                fails.append(("bites", f"{prop}: moving {s}'s value to {witnesses[0]} does not fire the shape for {label(c)}"))
    return fails


def main(argv):
    p = argparse.ArgumentParser(prog="check_code_lists.py")
    p.add_argument("--shapes", nargs="+", required=True)
    p.add_argument("--data", nargs="+", required=True)
    p.add_argument("--not-code-list", action="append", default=[])
    try:
        args = p.parse_args(argv)
    except SystemExit:
        return 2
    shapes, data = Graph(), Graph()
    excluded = {URIRef(s) for s in args.not_code_list}
    try:
        for path in args.shapes:
            shapes.parse(path)
        for path in args.data:
            data.parse(path)
        fails = check(data, shapes, excluded)
    except Exception as exc:  # a parser error, or pySHACL rejecting a malformed shape
        print(f"ERROR cannot read or apply the input: {exc}", file=sys.stderr)
        return 2
    for name, message in fails:
        print(f"FAIL {name}: {message}")
    if fails:
        print(f"{len(fails)} check(s) failed", file=sys.stderr)
        return 1
    print(f"every code-list property is shaped against its list "
          f"({len(coded_properties(data, code_lists(data, excluded)))} properties)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
