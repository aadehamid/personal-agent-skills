#!/usr/bin/env python3
"""Step 9: every code-list property is shaped against its own list, and each such shape can fail
(references/shacl.md, rules 4 and 8).

Run: uv run --with rdflib --with pyshacl python3 check_code_lists.py --shapes <s.ttl>... --data <d.ttl>...
     [--not-code-list=<scheme IRI>]...

A code list is a skos:ConceptScheme in the data. A code-list property is any property outside the RDF,
RDFS, OWL and SKOS namespaces whose value, somewhere in the data, is a concept skos:inScheme a code list.
--not-code-list leaves out a scheme whose concepts are things, not coded values (a process hierarchy,
say), so properties that link those concepts are not code-list properties.

A membership shape for property P and list L is either
  a node shape with sh:targetObjectsOf P and a property shape sh:path skos:inScheme, sh:hasValue L; or
  a property shape sh:path P whose sh:node has a property shape sh:path skos:inScheme, sh:hasValue L.
sh:class skos:Concept is not one: it lets a value from the wrong list through.

Checks:
  covered     every code-list property has a membership shape
  same-list   every value of the property is in the list its shape names
  bites       moving one value of the property to a concept of another code list adds a SHACL result
              (needs a second code list; with one, the check says it cannot run)

Prints one FAIL line per failure. Exit 0 when nothing fails, 1 when anything fails, 2 when a file cannot
be read or parsed, or the arguments are wrong.
"""
import argparse
import sys

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SH, SKOS

from check_shapes import results

SKIP_NAMESPACES = (str(RDF), str(RDFS), str(OWL), str(SKOS))


def code_lists(data, excluded):
    return set(data.subjects(RDF.type, SKOS.ConceptScheme)) - excluded


def coded_properties(data, lists):
    """{property: set of lists its values sit in}."""
    out = {}
    for s, p, o in data:
        if str(p).startswith(SKIP_NAMESPACES) or not isinstance(o, URIRef):
            continue
        in_lists = set(data.objects(o, SKOS.inScheme)) & lists
        if in_lists:
            out.setdefault(p, set()).update(in_lists)
    return out


def membership_lists(shapes, node):
    """The lists a node shape pins skos:inScheme to."""
    return {shapes.value(ps, SH.hasValue) for ps in shapes.objects(node, SH.property)
            if shapes.value(ps, SH.path) == SKOS.inScheme and shapes.value(ps, SH.hasValue) is not None}


def membership_shapes(shapes):
    """{property: set of lists} over both shape forms in the docstring."""
    out = {}
    for node in set(shapes.subjects(SH.targetObjectsOf, None)):
        for prop in shapes.objects(node, SH.targetObjectsOf):
            out.setdefault(prop, set()).update(membership_lists(shapes, node))
    for ps in set(shapes.subjects(SH.path, None)):
        prop = shapes.value(ps, SH.path)
        for node in shapes.objects(ps, SH.node):
            if isinstance(prop, URIRef):
                out.setdefault(prop, set()).update(membership_lists(shapes, node))
    return {p: lists for p, lists in out.items() if lists}


def check(data, shapes, excluded=frozenset()):
    """Return failures as (check name, message)."""
    lists = code_lists(data, set(excluded))
    coded = coded_properties(data, lists)
    shaped = membership_shapes(shapes)
    fails = []
    baseline = None
    for prop in sorted(coded, key=str):
        named = shaped.get(prop)
        if not named:
            fails.append(("covered", f"{prop} takes values from {sorted(map(str, coded[prop]))} and no shape pins its list"))
            continue
        for s, o in data.subject_objects(prop):
            schemes = set(data.objects(o, SKOS.inScheme))
            if isinstance(o, URIRef) and not schemes & named:
                fails.append(("same-list", f"{prop} on {s} is {o}, which is not in {sorted(map(str, named))}"))
        others = [c for c, sch in data.subject_objects(SKOS.inScheme) if sch in lists - named]
        if not others:
            fails.append(("bites", f"{prop}: no concept of another code list to test the shape with"))
            continue
        use = next(((s, o) for s, o in data.subject_objects(prop) if set(data.objects(o, SKOS.inScheme)) & named), None)
        if use is None:
            continue  # every value is already in the wrong list; same-list has failed for each
        s, o = use
        mutated = Graph()
        mutated += data
        mutated.remove((s, prop, o))
        mutated.add((s, prop, sorted(others, key=str)[0]))
        if baseline is None:
            baseline = set(results(data, shapes))
        if not set(results(mutated, shapes)) - baseline:
            fails.append(("bites", f"{prop}: a value from another list on {s} adds no SHACL result"))
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
    try:
        for path in args.shapes:
            shapes.parse(path)
        for path in args.data:
            data.parse(path)
    except Exception as exc:
        print(f"ERROR cannot read input: {exc}", file=sys.stderr)
        return 2
    fails = check(data, shapes, {URIRef(s) for s in args.not_code_list})
    for name, message in fails:
        print(f"FAIL {name}: {message}")
    if fails:
        print(f"{len(fails)} check(s) failed", file=sys.stderr)
        return 1
    print(f"every code-list property is shaped against its list ({len(coded_properties(data, code_lists(data, {URIRef(s) for s in args.not_code_list})))} properties)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
