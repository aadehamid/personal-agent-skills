#!/usr/bin/env python3
"""A consistency graph of this project's sources, rebuilt from them on every run.

Usage:
  graph_tool.py summary          counts of nodes by label and links by type
  graph_tool.py check            where the sources disagree or cannot be read (exit 1 if so)
  graph_tool.py impact ID        everything linked to ID within three hops (needs relate)
  graph_tool.py query 'CYPHER'   any Cypher, run on a read-only copy of the graph (needs relate)
  graph_tool.py export           the graph as a Cypher script for relate or Neo4j

Installed from the consistency-graph skill. Keep the generic core below as it is
and change only the PROJECT section: the sources, the parsers that read them,
the rules a link must follow, and the counts the sources promise.
GRAPH_ROOT points the tool at another checkout, which the tests use.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.environ.get("GRAPH_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ----------------------------------------------------------------------------
# Generic core: reading sources, recording what each one says, finding clashes.
# ----------------------------------------------------------------------------

def read(root, rel):
    with open(os.path.join(root, rel), encoding="utf-8") as fh:
        return fh.read().replace("\r\n", "\n")


def markdown_tables(text):
    """Every pipe table in a markdown text, as (header, rows), each row a dict by header cell."""
    tables, lines = [], text.splitlines()
    i = 0
    while i + 1 < len(lines):
        head, rule = lines[i].strip(), lines[i + 1].strip()
        if head.startswith("|") and re.fullmatch(r"\|[\s:|-]+\|", rule):
            header = [c.strip() for c in head.strip("|").split("|")]
            rows, j = [], i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                cells = [c.strip() for c in lines[j].strip().strip("|").split("|")]
                rows.append({"_line": j + 1, "_cells": len(cells), **dict(zip(header, cells))})
                j += 1
            tables.append((header, rows))
            i = j
        else:
            i += 1
    return tables


class Graph:
    """Nodes and links with the source that stated each, and the problems met while reading."""

    def __init__(self, root):
        self.root = root
        self.nodes = {}       # id -> {"label", "props", "sources": {source: {prop: value}}}
        self.edges = {}       # (source_id, type, target_id) -> set of sources that state it
        self.problems = []

    def node(self, label, ident, source, **props):
        n = self.nodes.setdefault(ident, {"label": label, "props": {}, "sources": {}})
        if n["label"] != label:
            self.problems.append(f"{ident}: {source} calls it a {label}, another source a {n['label']}")
        stated = n["sources"].setdefault(source, {})
        for key, value in props.items():
            if value in (None, ""):
                continue
            if key in stated and stated[key] != value:
                self.problems.append(f"{ident}: {source} states {key} twice: {stated[key]!r} and {value!r}")
                continue
            stated[key] = value
            n["props"].setdefault(key, value)
        return ident

    def link(self, source_id, kind, target_id, source):
        self.edges.setdefault((source_id, kind, target_id), set()).add(source)

    def problem(self, message):
        self.problems.append(message)

    def clashes(self):
        """A property two sources state differently is a clash: report both, choose neither."""
        found = []
        for ident, n in sorted(self.nodes.items()):
            values = {}
            for source, props in n["sources"].items():
                for key, value in props.items():
                    values.setdefault(key, {}).setdefault(value, []).append(source)
            for key, seen in sorted(values.items()):
                if len(seen) > 1:
                    said = "; ".join(f"{', '.join(sorted(s))} says {v!r}" for v, s in sorted(seen.items()))
                    found.append(f"{ident}: sources disagree on {key}: {said}")
        return found


def check(graph):
    """Every finding: unreadable sources, clashes, broken or missing links, wrong counts."""
    findings = list(graph.problems) + graph.clashes()
    for (src, kind, dst), sources in sorted(graph.edges.items()):
        for end in (src, dst):
            if end not in graph.nodes:
                findings.append(f"{src} -{kind}-> {dst}: {end} is not defined by any source "
                                f"(stated in {', '.join(sorted(sources))})")
    for label, kind, direction, why in REQUIRED_LINKS:
        for ident, n in sorted(graph.nodes.items()):
            if n["label"] != label:
                continue
            ends = [e for e in graph.edges if e[1] == kind and (e[0] if direction == "out" else e[2]) == ident]
            if not ends:
                findings.append(f"{ident}: a {label} with no {kind} link ({why})")
    for label, expected, where in EXPECTED_COUNTS(graph):
        actual = sum(1 for n in graph.nodes.values() if n["label"] == label)
        if actual != expected:
            findings.append(f"{label}: the sources define {actual}, but {where} says {expected}")
    return findings


def cypher_seed(graph):
    """The graph as one Cypher script, one statement per line."""
    def lit(v):
        return "null" if v is None else json.dumps(v, ensure_ascii=False)
    out = []
    for label in sorted({n["label"] for n in graph.nodes.values()}):
        out.append(f"CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE;")
    for ident, n in sorted(graph.nodes.items()):
        props = {"id": ident, **{k: v for k, v in n["props"].items() if isinstance(v, (str, int, float, bool))},
                 "sources": sorted(n["sources"])}
        body = ", ".join(f"`{k}`: {lit(v)}" for k, v in props.items())
        out.append(f"CREATE (:{n['label']} {{{body}}});")
    for (src, kind, dst), sources in sorted(graph.edges.items()):
        if src in graph.nodes and dst in graph.nodes:
            out.append(f"MATCH (a {{id: {lit(src)}}}), (b {{id: {lit(dst)}}}) "
                       f"CREATE (a)-[:{kind} {{sources: {lit(sorted(sources))}}}]->(b);")
    return "\n".join(out) + "\n"


def run_relate(graph, statement, params):
    """Load the graph into a scratch store, then run the statement on it read-only."""
    if not shutil.which("relate"):
        sys.exit("graph_tool: relate is not installed. Install it with: curl -sSfL https://relatedb.ai/install.sh | bash")
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "graph")
        seed = subprocess.run(["relate", "query", "--database", db, "--mode", "jsonl"],
                              input=cypher_seed(graph), capture_output=True, text=True)
        if seed.returncode != 0:
            sys.stderr.write(seed.stdout + seed.stderr)
            sys.exit(seed.returncode)
        args = ["relate", "query", "--database", db, "--read-only", "--mode", "jsonl", "--max-rows", "0"]
        for key, value in params.items():
            args += ["--param", f"{key}={json.dumps(value)}"]
        # --command takes the statement as its value, so a statement starting with - is never a flag.
        p = subprocess.run(args + ["--command", statement], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if p.returncode != 0:
        sys.stderr.write(p.stdout + p.stderr)
        sys.exit(p.returncode)
    return [line for line in p.stdout.splitlines() if line.startswith("{")]


def usage(text):
    print("usage: graph_tool.py " + text, file=sys.stderr)
    return 2


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    cmd, args = (argv[0], argv[1:]) if argv else ("help", [])
    if cmd in ("help", "-h", "--help"):
        if args:
            return usage("help takes no arguments")
        print(__doc__.split("\n\nInstalled")[0].strip())
        return 0
    graph = build(ROOT)
    if cmd == "impact":
        if len(args) != 1:
            return usage("impact ID")
        if args[0] not in graph.nodes:
            print(f"graph_tool: no node {args[0]}", file=sys.stderr)
            return 2
        statement = ("MATCH p = (n {id: $id})-[*1..3]-(m) WHERE m <> n "
                     "RETURN m.id AS id, labels(m)[0] AS label, min(length(p)) AS hops ORDER BY hops, id")
        for row in run_relate(graph, statement, {"id": args[0]}):
            print(row)
        return 0
    if cmd == "query":
        if len(args) != 1:
            return usage("query 'CYPHER'")
        for row in run_relate(graph, args[0], {}):
            print(row)
        return 0
    if cmd not in ("summary", "check", "export"):
        return usage("summary|check|impact|query|export, or help")
    if args:
        return usage(f"{cmd} takes no arguments")
    if cmd == "summary":
        labels, kinds = {}, {}
        for n in graph.nodes.values():
            labels[n["label"]] = labels.get(n["label"], 0) + 1
        for (_, kind, _) in graph.edges:
            kinds[kind] = kinds.get(kind, 0) + 1
        print(json.dumps({"nodes": dict(sorted(labels.items())), "links": dict(sorted(kinds.items()))}))
        return 0
    if cmd == "check":
        findings = check(graph)
        for f in findings:
            print("graph_tool: " + f, file=sys.stderr)
        print(f"graph_tool: {len(findings)} finding(s)" if findings else "graph_tool: the sources agree",
              file=sys.stderr if findings else sys.stdout)
        return 1 if findings else 0
    sys.stdout.write(cypher_seed(graph))
    return 0


# ----------------------------------------------------------------------------
# PROJECT: replace this section. The example reads one markdown table of
# components, each with what it depends on and the decision behind it, and a
# second table that lists the decisions.
# ----------------------------------------------------------------------------

COMPONENTS = "docs/components.md"
DECISIONS = "docs/decisions.md"

# (label, link type, "out" or "in", why the link is required)
REQUIRED_LINKS = [
    ("Component", "DEFINED_BY", "out", "every component is chosen by a decision"),
]


def EXPECTED_COUNTS(graph):
    """(label, count, where the count is promised). Read the promise from a source, never type it here."""
    m = re.search(r"\*\*(\d+) components\*\*", read(graph.root, COMPONENTS))
    return [("Component", int(m.group(1)), COMPONENTS)] if m else []


def build(root):
    graph = Graph(root)
    for _, rows in markdown_tables(read(root, DECISIONS)):
        for row in rows:
            if row.get("Decision"):
                graph.node("Decision", row["Decision"], DECISIONS, title=row.get("Title"))
    for header, rows in markdown_tables(read(root, COMPONENTS)):
        if header[:3] != ["Component", "Depends on", "Decision"]:
            graph.problem(f"{COMPONENTS}: a table with columns {header} is not the component table")
            continue
        for row in rows:
            if row["_cells"] != len(header):
                graph.problem(f"{COMPONENTS}:{row['_line']}: row has {row['_cells']} cells, the header {len(header)}")
                continue
            name = graph.node("Component", row["Component"], COMPONENTS, owner=row.get("Owner"))
            for dep in [d.strip() for d in row["Depends on"].split(",") if d.strip() and d.strip() != "-"]:
                graph.link(name, "DEPENDS_ON", dep, COMPONENTS)
            if row["Decision"] and row["Decision"] != "-":
                graph.link(name, "DEFINED_BY", row["Decision"], COMPONENTS)
    return graph


if __name__ == "__main__":
    sys.exit(main())
