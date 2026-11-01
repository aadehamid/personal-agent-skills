#!/usr/bin/env python3
"""Step 4 and any promotion of spreadsheet or CSV rows: build triples from a reviewed mapping, deterministically
(references/promotion.md, "From a spreadsheet to triples"). Morph-KGC is the engine to use for a spreadsheet or CSV;
maplib is for a source that is already a dataframe in Python.

Run, with the engine's packages:
  uv run --no-project --with morph-kgc==2.10.0 --with rdflib python3 build_tabular.py \
      --engine morph-kgc --mapping <folder>/<name>.rml.ttl --out <file.nt> [--verify]
  uv run --no-project --with maplib==0.20.26 --with polars --with rdflib python3 build_tabular.py \
      --engine maplib --mapping <folder>/<name>.maplib.py --out <file.nt> [--verify]

morph-kgc runs an RML mapping file; its rml:source paths are read relative to the mapping's folder. maplib runs a
Python file whose build(folder) returns a maplib Model, with the folder holding the mapping. Either way the triples
are written as N-Triples, one per line, sorted, so the same input always gives the same bytes. Blank nodes are
refused, because a sorted file cannot make their labels stable (references/identity-taxonomy.md, Step 2, rule 5).

--verify writes nothing: it builds afresh and fails unless the result equals --out byte for byte, so an edited
cell, an edited mapping or a hand edit to the output fails the check script (references/release.md, rule 9).

Exit 0 on success, 1 when --verify finds a difference or the build yields a blank node, 2 when an input cannot be
read or the arguments are wrong.
"""
import argparse
import contextlib
import importlib.util
import io
import logging
import os
import sys
import tempfile

from rdflib import BNode, Graph


def build_morph_kgc(mapping):
    import morph_kgc

    folder = os.path.dirname(os.path.abspath(mapping))
    config = f"[CONFIGURATION]\noutput_format=N-TRIPLES\n[DataSource1]\nmappings={os.path.abspath(mapping)}\n"
    logging.disable(logging.INFO)
    cwd = os.getcwd()
    os.chdir(folder)
    try:
        return morph_kgc.materialize(config)
    finally:
        os.chdir(cwd)


def build_maplib(mapping):
    spec = importlib.util.spec_from_file_location("tabular_mapping", os.path.abspath(mapping))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    model = module.build(os.path.dirname(os.path.abspath(mapping)))
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "out.nt")
        model.write(path, format="ntriples")
        return Graph().parse(path, format="nt")


def canonical(graph):
    """Sorted N-Triples text of graph; raises ValueError on a blank node."""
    if any(isinstance(term, BNode) for triple in graph for term in triple):
        raise ValueError("the build produced a blank node")
    lines = graph.serialize(format="nt", encoding="utf-8").decode("utf-8").splitlines()
    return "".join(line + "\n" for line in sorted(set(l for l in lines if l.strip())))


def build(engine, mapping):
    with contextlib.redirect_stdout(io.StringIO()):
        graph = build_morph_kgc(mapping) if engine == "morph-kgc" else build_maplib(mapping)
    return canonical(graph)


def main(argv):
    p = argparse.ArgumentParser(prog="build_tabular.py")
    p.add_argument("--engine", choices=["morph-kgc", "maplib"], required=True)
    p.add_argument("--mapping", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--verify", action="store_true")
    try:
        args = p.parse_args(argv)
    except SystemExit:
        return 2
    if not os.path.isfile(args.mapping):
        print(f"ERROR cannot read the mapping {args.mapping}", file=sys.stderr)
        return 2
    try:
        text = build(args.engine, args.mapping)
    except ValueError as exc:
        print(f"FAIL blank-node: {exc}")
        return 1
    except Exception as exc:  # an unreadable source file, a malformed mapping
        print(f"ERROR cannot build from {args.mapping}: {exc}", file=sys.stderr)
        return 2
    if args.verify:
        try:
            with open(args.out, "rb") as f:  # bytes, so a changed line ending is a difference too
                written = f.read()
        except OSError as exc:
            print(f"ERROR cannot read {args.out}: {exc}", file=sys.stderr)
            return 2
        if written != text.encode("utf-8"):
            old, new = set(written.decode("utf-8", "replace").splitlines()), set(text.splitlines())
            for line in sorted(old - new):
                print(f"FAIL verify: only in {args.out}: {line}")
            for line in sorted(new - old):
                print(f"FAIL verify: only in a fresh build: {line}")
            if old == new:
                print(f"FAIL verify: {args.out} holds the same triples in another order or layout")
            return 1
        print(f"{args.out} equals a fresh build ({len(text.splitlines())} triples)")
        return 0
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"wrote {args.out} ({len(text.splitlines())} triples)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
