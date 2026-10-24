#!/usr/bin/env python3
"""Step 11: run the competency-question queries against the released packages (references/regression.md).

Run: uv run --with rdflib python3 run_regression.py --expected <expected.csv> --queries <dir> <file.ttl>...

<file.ttl>... are the released packages the questions run on (each module's Turtle; the closure, not a
working tree). <expected.csv> has the columns question, status, queries, waits_for; one row per locked
question. queries is a ";"-separated list of file names in <dir>. Each status (regression.md, rules 10
and 11) is one of:
  answerable          every listed query must run and give its expected result; waits_for is empty
  partial             the graph part's queries must pass; waits_for names the rest
  waiting:<what>      no query yet; <what> names the step, module or decision it waits for
  parked:<decision>   parked by a recorded decision, which counts as passing; no query
  drafted             written but not yet locked or run; no query
A query whose first line is a comment containing "(must be none)" must return no rows (rule 5); every
other query must return at least one row.

Prints one line of coverage, then one FAIL line per failure. Exit 0 when nothing fails, 1 when anything
fails, 2 when a file cannot be read or parsed, or the arguments are wrong.
"""
import argparse
import csv
import os
import sys
from collections import Counter

from rdflib import Graph

COLUMNS = ["question", "status", "queries", "waits_for"]
NO_QUERY = ("waiting", "parked", "drafted")


def must_be_none(text):
    first = text.lstrip().splitlines()[0] if text.strip() else ""
    return first.startswith("#") and "(must be none)" in first


def check(graph, rows, queries_dir):
    """Return (failures, status counts). A failure names the question, and the query where there is one."""
    failures, statuses = [], Counter()
    seen = set()
    for row in rows:
        q, status = row["question"].strip(), row["status"].strip()
        kind, _, detail = status.partition(":")
        statuses[kind] += 1
        names = [n.strip() for n in (row["queries"] or "").split(";") if n.strip()]
        waits = (row["waits_for"] or "").strip()
        if q in seen:
            failures.append(f"Q{q}: listed twice")
        seen.add(q)
        if kind not in ("answerable", "partial") + NO_QUERY:
            failures.append(f"Q{q}: unknown status {status!r}")
            continue
        if kind in ("waiting", "parked") and not detail.strip():
            failures.append(f"Q{q}: {kind} must name what it {'waits for' if kind == 'waiting' else 'was parked by'}")
        if kind in NO_QUERY and names:
            failures.append(f"Q{q}: {kind} but lists queries")
        if kind in ("answerable", "partial") and not names:
            failures.append(f"Q{q}: {kind} with no query")
        if kind == "partial" and not waits:
            failures.append(f"Q{q}: partial must name what the rest waits for")
        if kind == "answerable" and waits:
            failures.append(f"Q{q}: answerable but names something it waits for")
        for name in names:
            path = os.path.join(queries_dir, name)
            try:
                with open(path, encoding="utf-8") as f:
                    text = f.read()
                n = len(list(graph.query(text)))
            except Exception as exc:  # a missing file or a SPARQL syntax error fails the question
                failures.append(f"Q{q} {name}: cannot run: {exc}")
                continue
            if must_be_none(text) and n:
                failures.append(f"Q{q} {name}: {n} row(s), expected none")
            if not must_be_none(text) and not n:
                failures.append(f"Q{q} {name}: no rows")
    return failures, statuses


def main(argv):
    p = argparse.ArgumentParser(prog="run_regression.py")
    p.add_argument("--expected", required=True)
    p.add_argument("--queries", required=True)
    p.add_argument("files", nargs="+")
    try:
        args = p.parse_args(argv)
    except SystemExit:
        return 2
    try:
        with open(args.expected, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames != COLUMNS:
                print(f"ERROR {args.expected}: columns must be {','.join(COLUMNS)}, got {reader.fieldnames}",
                      file=sys.stderr)
                return 2
            rows = list(reader)
        graph = Graph()
        for path in args.files:
            graph.parse(path)
    except Exception as exc:
        print(f"ERROR cannot read input: {exc}", file=sys.stderr)
        return 2
    if not rows:
        print(f"ERROR {args.expected}: no questions", file=sys.stderr)
        return 2
    failures, s = check(graph, rows, args.queries)
    print(f"competency coverage: {len(rows)} questions; answerable {s['answerable']}, partial {s['partial']}, "
          f"waiting {s['waiting']}, parked {s['parked']}, drafted {s['drafted']} ({len(graph)} triples)")
    for line in failures:
        print("FAIL", line)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
