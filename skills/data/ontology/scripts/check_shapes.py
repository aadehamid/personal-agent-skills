#!/usr/bin/env python3
"""Step 9, the whole-graph gate: every shapes file, run together over every data file, finds no result
(references/shacl.md, rule 7).

Run: uv run --with rdflib --with pyshacl python3 check_shapes.py --shapes <s.ttl>... --data <d.ttl>...
     [--every-shapes-file-under <dir>]

The gate passes only when the report conforms: SHACL makes sh:conforms true only when validation
produced no result at any severity (§3.6.1.1), so a warning or an info result fails too. Data and
shapes are read as given; no inference runs. --every-shapes-file-under <dir> also fails when a file
under <dir> named shapes.ttl or *-shapes.ttl is missing from --shapes, so a module that gains shapes
cannot stay out of the gate.

Prints the report's results, one FAIL line each. Exit 0 when the graph conforms, 1 when it does not or a
shapes file is left out, 2 when a file cannot be read or parsed, or the arguments are wrong.
"""
import argparse
import os
import sys

from pyshacl import validate
from rdflib import Graph
from rdflib.namespace import RDF, SH


def results(data, shapes):
    """Each validation result as (severity, focus node, path, message), sorted; empty means conforms.
    Every result counts, whatever its severity and whatever pyshacl's own conforms flag says."""
    _, report, _ = validate(data, shacl_graph=shapes, advanced=True)
    out = []
    for r in report.subjects(RDF.type, SH.ValidationResult):
        sev = report.value(r, SH.resultSeverity)
        out.append((str(sev).rsplit("#", 1)[-1], str(report.value(r, SH.focusNode)),
                    str(report.value(r, SH.resultPath) or ""), str(report.value(r, SH.resultMessage) or "")))
    return sorted(out)


def unlisted_shapes(root, listed):
    listed = {os.path.realpath(p) for p in listed}
    found = []
    for folder, _, files in os.walk(root):
        for name in files:
            if name == "shapes.ttl" or name.endswith("-shapes.ttl"):
                path = os.path.join(folder, name)
                if os.path.realpath(path) not in listed:
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
    shapes, data = Graph(), Graph()
    try:
        for path in args.shapes:
            shapes.parse(path)
        for path in args.data:
            data.parse(path)
    except Exception as exc:
        print(f"ERROR cannot read input: {exc}", file=sys.stderr)
        return 2
    fails = [f"shapes file not in the gate: {p}" for p in
             (unlisted_shapes(args.every_shapes_file_under, args.shapes) if args.every_shapes_file_under else [])]
    fails += [f"{sev} on {focus}" + (f" path {path}" if path else "") + f": {msg}"
              for sev, focus, path, msg in results(data, shapes)]
    for line in fails:
        print("FAIL", line)
    if fails:
        print(f"{len(fails)} failure(s)", file=sys.stderr)
        return 1
    print(f"the whole graph conforms ({len(data)} data triples, {len(args.shapes)} shapes files)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
