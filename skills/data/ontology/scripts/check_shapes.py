#!/usr/bin/env python3
"""Step 9, the whole-graph gate: every shapes file, run together over every data file, finds no result
(references/shacl.md, rule 7).

Run: uv run --no-project --with rdflib --with pyshacl python3 check_shapes.py --shapes <s.ttl>... --data <d.ttl>...
     [--every-shapes-file-under <dir>]

The gate passes only when the report holds no result: SHACL makes sh:conforms true only when validation
produced no result at any severity (§3.6.1.1), so a warning or an info result fails too. Data and shapes
are read as given and nothing is inferred. A shapes graph that holds a SHACL rule (sh:rule) fails the
gate, because a rule adds triples to the data before the constraints run, so a rule could supply the
very value a shape requires. --every-shapes-file-under <dir> also fails when a file under <dir> named
*-shapes.ttl (the skill's naming, identity-taxonomy.md) is missing from --shapes, so a module that gains
shapes cannot stay out of the gate.

Prints one FAIL line per result. Exit 0 when the graph conforms, 1 when it does not or a shapes file is
left out, 2 when a file cannot be read or parsed, a shape is not valid SHACL, or the arguments are wrong
(including a --every-shapes-file-under that is not a directory).
"""
import argparse
import os
import sys

from pyshacl import validate
from rdflib import Graph
from rdflib.namespace import RDF, SH


def rule_nodes(shapes):
    """Every node in the shapes graph that holds a SHACL rule, or is one."""
    found = set(shapes.subjects(SH.rule, None)) | set(shapes.objects(None, SH.rule))
    for kind in (SH.TripleRule, SH.SPARQLRule):
        found |= set(shapes.subjects(RDF.type, kind))
    return sorted(found, key=str)


def results(data, shapes):
    """Each validation result as (severity, focus node, path, value, message), sorted; empty means conforms.
    Every result counts, whatever its severity. A rule in the shapes graph is a result of its own, and
    validation does not run."""
    rules = rule_nodes(shapes)
    if rules:
        return [("Rule", str(node), "", "", "sh:rule is not allowed: a rule changes the data before validation")
                for node in rules]
    _, report, _ = validate(data, shacl_graph=shapes, advanced=True)
    out = []
    for r in report.subjects(RDF.type, SH.ValidationResult):
        out.append((str(report.value(r, SH.resultSeverity)).rsplit("#", 1)[-1], str(report.value(r, SH.focusNode)),
                    str(report.value(r, SH.resultPath) or ""), str(report.value(r, SH.value) or ""),
                    str(report.value(r, SH.resultMessage) or "")))
    return sorted(out)


def describe(result):
    """One result as a line: severity, focus node, path, message."""
    sev, focus, path, _, msg = result
    return f"{sev} on {focus}" + (f" path {path}" if path else "") + f": {msg}"


def unlisted_shapes(root, listed):
    listed = {os.path.realpath(p) for p in listed}
    found = []
    for folder, _, files in os.walk(root):
        for name in files:
            path = os.path.join(folder, name)
            if name.endswith("-shapes.ttl") and os.path.realpath(path) not in listed:
                found.append(path)
    return sorted(found)


def main(argv):
    p = argparse.ArgumentParser(prog="check_shapes.py")
    p.add_argument("--shapes", nargs="+", required=True)
    p.add_argument("--data", nargs="+", required=True)
    p.add_argument("--every-shapes-file-under")
    try:
        args = p.parse_args(argv)
    except SystemExit:
        return 2
    root = args.every_shapes_file_under
    if root is not None and not os.path.isdir(root):
        print(f"ERROR not a directory: {root}", file=sys.stderr)
        return 2
    shapes, data = Graph(), Graph()
    try:
        for path in args.shapes:
            shapes.parse(path)
        for path in args.data:
            data.parse(path)
        found = results(data, shapes)
    except Exception as exc:  # a parser error, or pySHACL rejecting a malformed shape
        print(f"ERROR cannot read or apply the input: {exc}", file=sys.stderr)
        return 2
    fails = [f"shapes file not in the gate: {p}" for p in (unlisted_shapes(root, args.shapes) if root else [])]
    fails += [describe(r) for r in found]
    for line in fails:
        print("FAIL", line)
    if fails:
        print(f"{len(fails)} failure(s)", file=sys.stderr)
        return 1
    print(f"the whole graph conforms ({len(data)} data triples, {len(args.shapes)} shapes files)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
