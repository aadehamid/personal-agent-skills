#!/usr/bin/env python3
"""Copy a validated projection from the local Neo4j to another Neo4j (Aura included), then prove
the copy is identical by the graph hash.

n10s is not available on Aura, so the projection is built and verified locally (load_verify.py),
and this script copies the result with plain Cypher over the Python driver.

Run: NEO4J_PASSWORD=<local password> uv run --no-project --with rdflib --with neo4j python3 copy_graph.py \
         --source bolt://127.0.0.1:<port> --target-env <file> --report <projection-report.json> \
         [--batch 1000] [--replace]

--target-env names a file of KEY=VALUE lines: NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD and
optionally NEO4J_DATABASE (the format of an Aura credentials file). The password is never printed.

What it copies: every :Resource node (labels and properties, the n10s schema nodes included,
because the graph hash and the round trip count them) and every relationship between two :Resource
nodes. It leaves out n10s's own configuration nodes (_GraphConfig, _NsPrefDef,
_n10sValidatorConfig), which have no Resource label. It creates the n10s uniqueness constraint on
:Resource(uri) on the target first, then writes nodes and relationships in batches with UNWIND and
dynamic labels and types (Cypher 5.26 and later; Aura runs current versions).

--report is required: the projection report load_verify.py wrote. The script reads it before it
touches either database and stops (exit 2) unless it says passed: true with equal sorted and
shuffled hashes. It then hashes the source and stops (exit 1), before writing or deleting anything on
the target, unless that hash equals the report's determinism_hash_sorted: only the verified graph is
copied. It refuses a target that holds any node unless --replace is given, which deletes everything
on the target first (in batches). After the copy it hashes the target exactly as load_verify.py
does and fails unless it equals the source hash. Every printed value is shell-quoted.

Exit 0 when the hashes match, 1 when a copy or check fails, 2 on bad input.
"""
import os
import sys

import build
import load_verify as lv

CONFIG_LABELS = ("_GraphConfig", "_NsPrefDef", "_n10sValidatorConfig")
NODES = ("MATCH (n:Resource) RETURN n.uri AS uri, labels(n) AS labels, properties(n) AS props "
         "ORDER BY n.uri SKIP $skip LIMIT $limit")
EDGES = ("MATCH (a:Resource)-[r]->(b:Resource) RETURN a.uri AS s, type(r) AS t, b.uri AS o, properties(r) AS props "
         "ORDER BY s, t, o, r.uri SKIP $skip LIMIT $limit")
WRITE_NODES = "UNWIND $rows AS row CREATE (n:$(row.labels)) SET n = row.props"
WRITE_EDGES = ("UNWIND $rows AS row MATCH (a:Resource {uri: row.s}), (b:Resource {uri: row.o}) "
               "CREATE (a)-[r:$(row.t)]->(b) SET r = row.props")


def read_env_file(path):
    """KEY=VALUE lines; blank lines and # comments ignored; quotes around a value removed."""
    values = {}
    with open(path, encoding="utf-8") as f:
        for number, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, sep, value = line.partition("=")
            if not sep:
                raise ValueError(f"{path} line {number} is not KEY=VALUE")
            values[key.strip()] = value.strip().strip('"').strip("'")
    missing = [k for k in ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD") if not values.get(k)]
    if missing:
        raise ValueError(f"{path} lacks {', '.join(missing)}")
    return values


def describe_target(values):
    """The target as it may be printed: never the password, every value shell-quoted."""
    return f"{lv.q(values['NEO4J_URI'])} as {lv.q(values['NEO4J_USERNAME'])}" + (
        f" (database {lv.q(values['NEO4J_DATABASE'])})" if values.get("NEO4J_DATABASE") else "")


def verified_hash(report_path):
    """The determinism_hash_sorted of a report that passed, or ValueError."""
    import json
    with open(report_path, encoding="utf-8") as f:
        rep = json.load(f)
    if rep.get("passed") is not True:
        raise ValueError(f"{report_path} does not say passed: true; copy only a verified graph")
    h = rep.get("determinism_hash_sorted")
    if not h or h != rep.get("determinism_hash_shuffled"):
        raise ValueError(f"{report_path} has no pair of equal determinism hashes")
    return h


def batches(session, query, size):
    skip = 0
    while True:
        rows = session.run(query, skip=skip, limit=size).data()
        if not rows:
            return
        yield rows
        skip += size


def graph_hash(session):
    return lv.hash_graph(session)[0]


def count_nodes(session):
    return session.run("MATCH (n) RETURN count(n) AS n").single()["n"]


def empty_target(session, size):
    session.run(f"MATCH (n) CALL (n) {{ DETACH DELETE n }} IN TRANSACTIONS OF {int(size)} ROWS").consume()


def copy(source, target, size):
    copied = {"nodes": 0, "relationships": 0}
    target.run("CREATE CONSTRAINT n10s_unique_uri IF NOT EXISTS FOR (r:Resource) REQUIRE r.uri IS UNIQUE").consume()
    for rows in batches(source, NODES, size):
        target.run(WRITE_NODES, rows=[{"labels": r["labels"], "props": r["props"]} for r in rows]).consume()
        copied["nodes"] += len(rows)
    for rows in batches(source, EDGES, size):
        target.run(WRITE_EDGES, rows=rows).consume()
        copied["relationships"] += len(rows)
    return copied


def main(argv):
    try:
        opts, rest = build.options(argv, flags=("--replace",))
        build.need(opts, "--source", "--target-env", "--report")
        if rest:
            raise ValueError(f"unexpected arguments: {' '.join(rest)}")
        size = int(opts.get("--batch", 1000))
        password = os.environ.get("NEO4J_PASSWORD")
        if not password:
            raise ValueError("set NEO4J_PASSWORD to the local (source) password")
        target_values = read_env_file(opts["--target-env"])
        expected = verified_hash(opts["--report"])
    except (OSError, ValueError) as exc:
        print(f"ERROR {lv.q(exc)}", file=sys.stderr)
        return 2
    from neo4j import GraphDatabase
    try:
        with GraphDatabase.driver(opts["--source"], auth=("neo4j", password)) as src_driver, \
                GraphDatabase.driver(target_values["NEO4J_URI"],
                                     auth=(target_values["NEO4J_USERNAME"], target_values["NEO4J_PASSWORD"])) as dst_driver:
            database = target_values.get("NEO4J_DATABASE") or None
            with src_driver.session() as source, dst_driver.session(database=database) as target:
                source_hash = graph_hash(source)
                if source_hash != expected:
                    print(f"FAIL the source graph hash {source_hash} is not the report's {expected}; "
                          "nothing was written to the target")
                    return 1
                present = count_nodes(target)
                if present and not opts.get("--replace"):
                    print(f"FAIL the target {describe_target(target_values)} holds {present} nodes; "
                          "pass --replace to delete them first")
                    return 1
                if present:
                    empty_target(target, size)
                copied = copy(source, target, size)
                target_hash = graph_hash(target)
    except Exception as exc:  # a driver, network or Cypher error
        print(f"FAIL {lv.q(exc)}; the target may hold a partial copy")
        return 1
    print(f"copied {copied['nodes']} nodes and {copied['relationships']} relationships to {describe_target(target_values)}")
    if target_hash != source_hash:
        print(f"FAIL the target hash {target_hash} differs from the source hash {source_hash}")
        return 1
    print(f"the target hash equals the source hash: {source_hash}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
