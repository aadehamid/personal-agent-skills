#!/usr/bin/env python3
"""The load and verify steps against a running Neo4j with n10s and APOC, ending in the report.

Run: NEO4J_PASSWORD=... uv run --no-project --with rdflib --with neo4j python3 load_verify.py \
         --config <config.json> --shapes <shapes.ttl>... --bolt bolt://127.0.0.1:<port> \
         --import-dir <folder mounted at /import> --merged merged.ttl --loadable loadable.nt \
         --inferred inferred.nt --report projection-report.json [--plugins-dir <folder>] <data.ttl>...

What it does, in order (references/pipeline.md, rules 8 to 17):
  1. Writes shapes-in-graph.ttl (in_graph_shapes.subset) and copies merged.ttl, loadable.nt and
     inferred.nt into the import folder.
  2. Empties the database: every node, then every constraint; checks both are gone.
  3. Runs the load script build.py generates, one statement at a time. onto.import and both
     rdf.import calls must return terminationStatus OK; the shapes import must return as many rows as
     n10s.validation.shacl.listShapes() lists, and more than zero.
  4. Validates in the graph (zero violations required).
  5. Runs one generated fail case per constraint kind, each in a transaction that is rolled back. A
     case passes when validate() reports its focus node with a component (the propertyShape column)
     in the kind's expected set.
  6. Commits the deliberate mutant (removes one required literal), requires a violation on its focus
     node, restores the value, and requires zero violations again.
  7. Exports the resources, leaves out schema rows, rebuilds tagged literals, normalises values and
     diffs against loadable.nt plus inferred.nt.
  8. Hashes the graph, empties it, overwrites the import copy of loadable.nt with its lines shuffled
     (random.Random(12)), loads again, hashes again, and puts the sorted file back.
  9. Writes the report and exits 0 when every check passed, 1 otherwise, 2 on bad input.

The graph hash (graph_hash): every :Resource node as [uri, sorted labels, properties] and every
relationship between two :Resource nodes as [source uri, type, target uri, relationship uri or "",
relationship properties]; both lists sorted (nodes by uri, relationships by their first four fields,
a missing uri counting as ""); property maps with sorted keys; list values in their stored order (the
load sorts them); any value JSON cannot hold (dates, times, durations, points) written with str();
the whole serialised with json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False),
encoded as UTF-8 and hashed with SHA-256. Schema nodes from onto.import are :Resource nodes and are
included: they come from the same files on both loads.
"""
import json
import os
import random
import re
import shutil
import sys

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, SH, XSD

import build
import check_projection_rules as cpr
import in_graph_shapes as igs

SCHEMA_NS = "neo4j://graph.schema#"
EXPORT = ("CALL n10s.rdf.export.cypher('MATCH (n:Resource) OPTIONAL MATCH (n)-[r]->(m) RETURN n, r, m') "
          "YIELD subject, predicate, object, isLiteral, literalType, literalLang "
          "RETURN subject, predicate, object, isLiteral, literalType, literalLang")
VALIDATE = ("CALL n10s.validation.shacl.validate() YIELD focusNode, propertyShape, resultMessage "
            "RETURN focusNode, propertyShape, resultMessage")
# n10s 2025.06.1 sometimes exports a tagged string, notably one that holds a newline, as an
# xsd:string "text@en" with no literalLang. DOTALL lets the text span lines. Safe because the check
# step refuses any source string that ends like a tag (pipeline.md, rule 3).
TAGGED_TEXT = re.compile(r"^(.*)@([A-Za-z]{1,8}(?:-[A-Za-z0-9]{1,8})*)$", re.S)
INTEGERS = {XSD.integer, XSD.long, XSD.int, XSD.short, XSD.byte, XSD.nonNegativeInteger, XSD.positiveInteger}
COMPONENT = "http://www.w3.org/ns/shacl#"
EXPECTED = {
    "minCount": {"CountConstraintComponent", "MinCountConstraintComponent"},
    "maxCount": {"CountConstraintComponent", "MaxCountConstraintComponent"},
    "inverseMinCount": {"CountConstraintComponent", "MinCountConstraintComponent"},
    "inverseMaxCount": {"CountConstraintComponent", "MaxCountConstraintComponent"},
    "closed": {"ClosedConstraintComponent"},
    "disjoint": {"DisjointConstraintComponent"},
    "datatype": {"DatatypeConstraintComponent"},
    "class": {"ClassConstraintComponent"},
    "in": {"InConstraintComponent"},
    "nodeKind": {"NodeKindConstraintComponent"},
    "hasValue": {"HasValueConstraintComponent"},
    "minInclusive": {"ValueRangeConstraintComponent", "MinInclusiveConstraintComponent"},
    "maxInclusive": {"ValueRangeConstraintComponent", "MaxInclusiveConstraintComponent"},
    "minExclusive": {"ValueRangeConstraintComponent", "MinExclusiveConstraintComponent"},
    "maxExclusive": {"ValueRangeConstraintComponent", "MaxExclusiveConstraintComponent"},
    "minLength": {"LengthConstraintComponent", "MinLengthConstraintComponent"},
    "maxLength": {"LengthConstraintComponent", "MaxLengthConstraintComponent"},
}


class Failed(Exception):
    pass


# ---------- pure parts (tested without Neo4j) ----------

def canonical(term):
    """One spelling per value: plain = xsd:string; integer types as xsd:integer; decimal, double and
    float as a double (pipeline.md, rule 16)."""
    if not isinstance(term, Literal) or term.language:
        return term
    if term.datatype in (None, XSD.string):
        return Literal(str(term))
    if term.datatype in INTEGERS:
        return Literal(int(term), datatype=XSD.integer)
    if term.datatype in (XSD.decimal, XSD.double, XSD.float):
        return Literal(repr(float(term)), datatype=XSD.double)
    return term


def canonical_graph(g):
    out = Graph()
    for s, p, o in g:
        out.add((s, p, canonical(o)))
    return out


def is_schema_row(row):
    return (str(row["subject"]).startswith(SCHEMA_NS) or str(row["predicate"]).startswith(SCHEMA_NS)
            or (not row["isLiteral"] and str(row["object"]).startswith(SCHEMA_NS)))


def row_object(row):
    if not row["isLiteral"]:
        return URIRef(row["object"])
    text, lang, dtype = row["object"], row.get("literalLang"), row.get("literalType")
    if lang:
        return Literal(text, lang=lang)
    if dtype in (None, "", str(XSD.string)):
        m = TAGGED_TEXT.match(str(text))
        if m:
            return Literal(m.group(1), lang=m.group(2))
        return Literal(str(text))
    return Literal(text, datatype=URIRef(dtype))


def rows_to_graph(rows):
    """The exported data as a graph, schema rows left out. Returns (graph, schema rows skipped)."""
    g, skipped = Graph(), 0
    for row in rows:
        if is_schema_row(row):
            skipped += 1
            continue
        g.add((URIRef(row["subject"]), URIRef(row["predicate"]), row_object(row)))
    return g, skipped


def diff(source, exported):
    from rdflib.compare import graph_diff, to_isomorphic
    _, lost, added = graph_diff(to_isomorphic(canonical_graph(source)), to_isomorphic(canonical_graph(exported)))
    return sorted(" ".join(t.n3() for t in x) for x in lost), sorted(" ".join(t.n3() for t in x) for x in added)


def _plain(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return str(value)


def graph_hash(nodes, edges):
    """SHA-256 of the canonical JSON described in the module docstring."""
    node_list = sorted(([n["uri"], sorted(n["labels"]), {k: _plain(v) for k, v in n["props"].items()}]
                        for n in nodes), key=lambda x: x[0])
    edge_list = sorted(([e["s"], e["t"], e["o"], e["u"] or "", {k: _plain(v) for k, v in (e["props"] or {}).items()}]
                        for e in edges), key=lambda x: x[:4])
    text = json.dumps({"nodes": node_list, "relationships": edge_list}, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)
    return build.sha_bytes(text.encode("utf-8"))


def shuffled(text, seed=12):
    lines = text.splitlines()
    random.Random(seed).shuffle(lines)
    return "".join(line + "\n" for line in lines)


def _label(iri, cfg):
    return build.shorten(URIRef(iri), cfg)


def fail_cases(subset, data, cfg):
    """One fail case per constraint kind: (kind, shape, Cypher that mutates one node and returns its
    uri as focus). Generated from the in-graph shapes and the data; each runs in a rolled-back
    transaction (pipeline.md, rule 14)."""
    literal_preds = {p for _, p, o in data if isinstance(o, Literal)}
    cases = {}
    for ns in sorted(subset.subjects(SH.targetClass, None), key=str):
        for cls in sorted(subset.objects(ns, SH.targetClass), key=str):
            T = _label(cls, cfg)
            for ps in sorted(subset.objects(ns, SH.property), key=str):
                path = subset.value(ps, SH.path)
                if path is None:
                    continue
                inverse = subset.value(path, SH.inversePath) if not isinstance(path, URIRef) else None
                if inverse is not None:
                    k = _label(inverse, cfg)
                    if subset.value(ps, SH.minCount) is not None and int(subset.value(ps, SH.minCount)) >= 1:
                        cases.setdefault("inverseMinCount", (ps, (
                            f"MATCH (n:`{T}`)<-[:`{k}`]-() WITH DISTINCT n ORDER BY n.uri LIMIT 1 "
                            f"MATCH (n)<-[r:`{k}`]-() DELETE r RETURN DISTINCT n.uri AS focus")))
                    if subset.value(ps, SH.maxCount) is not None:
                        cases.setdefault("inverseMaxCount", (ps, (
                            f"MATCH (n:`{T}`)<-[:`{k}`]-() WITH DISTINCT n ORDER BY n.uri LIMIT 1 "
                            f"MATCH (o:Resource) WHERE NOT (o)-[:`{k}`]->(n) AND o <> n WITH n, o ORDER BY o.uri "
                            f"LIMIT {int(subset.value(ps, SH.maxCount)) + 1} CREATE (o)-[:`{k}`]->(n) "
                            "RETURN DISTINCT n.uri AS focus")))
                    continue
                if not isinstance(path, URIRef):
                    continue
                k = _label(path, cfg)
                literal = path in literal_preds
                pick_prop = f"MATCH (n:`{T}`) WHERE n.`{k}` IS NOT NULL WITH n ORDER BY n.uri LIMIT 1 "
                pick_rel = f"MATCH (n:`{T}`)-[:`{k}`]->() WITH DISTINCT n ORDER BY n.uri LIMIT 1 "
                min_count = subset.value(ps, SH.minCount)
                if min_count is not None and int(min_count) >= 1:
                    if literal:
                        cases.setdefault("minCount", (ps, pick_prop + f"REMOVE n.`{k}` RETURN n.uri AS focus"))
                    else:
                        cases.setdefault("minCount", (ps, pick_rel + f"MATCH (n)-[r:`{k}`]->() DELETE r "
                                                                     "RETURN DISTINCT n.uri AS focus"))
                if subset.value(ps, SH.maxCount) == Literal(1) and literal:
                    cases.setdefault("maxCount", (ps, pick_prop + f"SET n.`{k}` = [toString(n.`{k}`), "
                                                                  f"toString(n.`{k}`) + ' (second)'] RETURN n.uri AS focus"))
                dt = subset.value(ps, SH.datatype)
                if dt is not None and literal:
                    wrong = "0" if dt == XSD.string else "'not a value of this datatype'"
                    cases.setdefault(f"datatype {dt.n3(subset.namespace_manager)}",
                                     (ps, pick_prop + f"SET n.`{k}` = {wrong} RETURN n.uri AS focus"))
                cls_c = subset.value(ps, SH["class"])
                if cls_c is not None and not literal:
                    C = _label(cls_c, cfg)
                    cases.setdefault("class", (ps, pick_rel + f"MATCH (n)-[r:`{k}`]->() WITH n, collect(r) AS rs "
                                               f"MATCH (o:Resource) WHERE NOT o:`{C}` WITH n, rs, o ORDER BY o.uri LIMIT 1 "
                                               f"FOREACH (r IN rs | DELETE r) CREATE (n)-[:`{k}`]->(o) "
                                               "RETURN n.uri AS focus"))
                members = subset.value(ps, SH["in"])
                if members is not None and not literal:
                    from rdflib.collection import Collection
                    allowed = json.dumps([str(m) for m in Collection(subset, members)])
                    cases.setdefault("in", (ps, pick_rel + f"MATCH (n)-[r:`{k}`]->() WITH n, collect(r) AS rs "
                                            f"MATCH (o:Resource) WHERE NOT o.uri IN {allowed} WITH n, rs, o "
                                            f"ORDER BY o.uri LIMIT 1 FOREACH (r IN rs | DELETE r) "
                                            f"CREATE (n)-[:`{k}`]->(o) RETURN n.uri AS focus"))
                if subset.value(ps, SH.nodeKind) == SH.IRI and not literal:
                    cases.setdefault("nodeKind", (ps, pick_rel + f"SET n.`{k}` = 'not an IRI' RETURN n.uri AS focus"))
                has_value = subset.value(ps, SH.hasValue)
                if isinstance(has_value, URIRef) and not literal:
                    cases.setdefault("hasValue", (ps, pick_rel + f"MATCH (n)-[r:`{k}`]->() DELETE r "
                                                                 "RETURN DISTINCT n.uri AS focus"))
                for kind, delta in (("minInclusive", "- 1"), ("maxInclusive", "+ 1"),
                                    ("minExclusive", "- 0"), ("maxExclusive", "+ 0")):
                    bound = subset.value(ps, SH[kind])
                    if bound is not None and literal:
                        cases.setdefault(kind, (ps, pick_prop + f"SET n.`{k}` = {bound.toPython()} {delta} "
                                                                "RETURN n.uri AS focus"))
                other = subset.value(ps, SH.disjoint)
                if isinstance(other, URIRef):
                    k2 = _label(other, cfg)
                    if literal:
                        cases.setdefault("disjoint", (ps, pick_prop + f"SET n.`{k2}` = n.`{k}` RETURN n.uri AS focus"))
                    else:
                        cases.setdefault("disjoint", (ps, f"MATCH (n:`{T}`)-[:`{k}`]->(m) WITH n, m ORDER BY n.uri, m.uri "
                                                          f"LIMIT 1 CREATE (n)-[:`{k2}`]->(m) RETURN n.uri AS focus"))
                for kind in ("minLength", "maxLength"):
                    bound = subset.value(ps, SH[kind])
                    if bound is not None and literal:
                        value = "''" if kind == "minLength" else f"'{'x' * (int(bound) + 1)}'"
                        if kind == "minLength" and int(bound) == 0:
                            continue
                        cases.setdefault(kind, (ps, pick_prop + f"SET n.`{k}` = {value} RETURN n.uri AS focus"))
            if (ns, SH.closed, Literal(True)) in subset:
                key = f"{_label(URIRef(cfg.own[0] + 'notInTheShape'), cfg)}"
                cases.setdefault("closed", (ns, f"MATCH (n:`{T}`) WITH n ORDER BY n.uri LIMIT 1 "
                                                f"SET n.`{key}` = 'a property the closed shape does not declare' "
                                                "RETURN n.uri AS focus"))
    return [(kind, ps, cypher) for kind, (ps, cypher) in sorted(cases.items())]


def kept_kinds(subset, data):
    """The constraint kinds left in the graph that can check something now: those on a property the
    data uses, plus closed node shapes. Each needs a fail case (pipeline.md, rule 14)."""
    used = set(data.predicates())
    kinds = set()
    for ns in subset.subjects(SH.targetClass, None):
        if (ns, SH.closed, Literal(True)) in subset:
            kinds.add("closed")
        for ps in subset.objects(ns, SH.property):
            path = subset.value(ps, SH.path)
            inverse = subset.value(path, SH.inversePath) if path is not None and not isinstance(path, URIRef) else None
            if (inverse or path) not in used:
                continue
            min_count = subset.value(ps, SH.minCount)
            if min_count is not None and int(min_count) >= 1:
                kinds.add("inverseMinCount" if inverse else "minCount")
            if subset.value(ps, SH.maxCount) is not None:
                kinds.add("inverseMaxCount" if inverse else "maxCount")
            dt = subset.value(ps, SH.datatype)
            if dt is not None:
                kinds.add(f"datatype {dt.n3(subset.namespace_manager)}")
            node_kind = subset.value(ps, SH.nodeKind)
            if node_kind is not None:
                kinds.add("nodeKind" if node_kind == SH.IRI else f"nodeKind {node_kind.n3(subset.namespace_manager)}")
            for p, kind in ((SH["class"], "class"), (SH["in"], "in"), (SH.hasValue, "hasValue"), (SH.disjoint, "disjoint"),
                            (SH.minInclusive, "minInclusive"), (SH.maxInclusive, "maxInclusive"),
                            (SH.minExclusive, "minExclusive"), (SH.maxExclusive, "maxExclusive"),
                            (SH.maxLength, "maxLength")):
                if subset.value(ps, p) is not None:
                    kinds.add(kind)
            min_length = subset.value(ps, SH.minLength)
            if min_length is not None and int(min_length) > 0:
                kinds.add("minLength")
    return sorted(kinds)


def expected_components(kind):
    return EXPECTED["datatype"] if kind.startswith("datatype") else EXPECTED.get(kind, set())


def component(value):
    return str(value).replace(COMPONENT, "")


def mutant_case(subset, data, cfg):
    """The deliberate mutant: the first minCount case on a literal value (pipeline.md, rule 15)."""
    literal_preds = {p for _, p, o in data if isinstance(o, Literal)}
    for ns in sorted(subset.subjects(SH.targetClass, None), key=str):
        for cls in sorted(subset.objects(ns, SH.targetClass), key=str):
            for ps in sorted(subset.objects(ns, SH.property), key=str):
                path, mc = subset.value(ps, SH.path), subset.value(ps, SH.minCount)
                if isinstance(path, URIRef) and path in literal_preds and mc is not None and int(mc) >= 1:
                    return _label(cls, cfg), _label(path, cfg)
    return None


# ---------- the database ----------

def wipe(session):
    session.run("MATCH (n) DETACH DELETE n").consume()
    for name in session.run("SHOW CONSTRAINTS YIELD name RETURN name").value():
        session.run(f"DROP CONSTRAINT `{name}`").consume()
    left = session.run("MATCH (n) RETURN count(n) AS n").single()["n"]
    constraints = session.run("SHOW CONSTRAINTS YIELD name RETURN count(*) AS n").single()["n"]
    if left or constraints:
        raise Failed(f"the database is not empty after the wipe: {left} nodes, {constraints} constraints")


def load(session, statements):
    """Run the load script; check each import. Returns (shapes import rows, listShapes count)."""
    shapes_rows = None
    for stmt in statements:
        result = session.run(stmt)
        rows = result.data()
        if "n10s.validation.shacl.import" in stmt:
            shapes_rows = len(rows)
        elif "n10s.rdf.import" in stmt or "n10s.onto.import" in stmt:
            status = rows[0].get("terminationStatus") if rows else None
            if status != "OK":
                raise Failed(f"{stmt} returned terminationStatus {status!r}: {rows[:1]}")
    listed = session.run("CALL n10s.validation.shacl.listShapes() YIELD target RETURN count(*) AS n").single()["n"]
    if not shapes_rows or shapes_rows != listed:
        raise Failed(f"the shapes import returned {shapes_rows} rows but listShapes() lists {listed}")
    return shapes_rows, listed


def violations(runner):
    return runner.run(VALIDATE).data()


def run_fail_cases(session, cases):
    results = []
    for kind, ps, cypher in cases:
        tx = session.begin_transaction()
        try:
            record = tx.run(cypher).single()
            focus = record["focus"] if record else None
            rows = violations(tx) if focus else []
        finally:
            tx.rollback()
        seen = sorted({component(r["propertyShape"]) for r in rows if r["focusNode"] == focus})
        ok = focus is not None and bool(set(seen) & expected_components(kind))
        results.append({"kind": kind, "shape": str(ps), "focus": focus, "cypher": cypher,
                        "expected": sorted(expected_components(kind)), "components": seen, "passed": ok})
    return results


def mutant(session, label, key):
    record = session.run(f"MATCH (n:`{label}`) WHERE n.`{key}` IS NOT NULL WITH n ORDER BY n.uri LIMIT 1 "
                         f"RETURN n.uri AS uri, n.`{key}` AS value").single()
    if record is None:
        raise Failed(f"no {label} node has {key} for the mutant")
    uri, value = record["uri"], record["value"]
    session.run(f"MATCH (n:Resource {{uri: $uri}}) REMOVE n.`{key}`", uri=uri).consume()
    caught = [r for r in violations(session) if r["focusNode"] == uri]
    session.run(f"MATCH (n:Resource {{uri: $uri}}) SET n.`{key}` = $value", uri=uri, value=value).consume()
    after = violations(session)
    return {"focus": uri, "removed": key, "violations": len(caught), "after_restore": len(after)}


def hash_graph(session):
    nodes = session.run("MATCH (n:Resource) RETURN n.uri AS uri, labels(n) AS labels, properties(n) AS props").data()
    edges = session.run("MATCH (a:Resource)-[r]->(b:Resource) RETURN a.uri AS s, type(r) AS t, b.uri AS o, "
                        "r.uri AS u, properties(r) AS props").data()
    schema = sum(1 for e in edges if e["t"].startswith("n4sch__"))
    return graph_hash(nodes, edges), len(nodes), len(edges), schema


def plugin_checksums(folder):
    if not folder:
        return {}
    return {name: build.sha_bytes(build.read_bytes(os.path.join(folder, name)))
            for name in sorted(os.listdir(folder)) if name.endswith(".jar")}


# ---------- the run ----------

def run(driver, cfg, data_paths, shape_paths, import_dir, merged, loadable, inferred, plugins_dir=None):
    data, shapes = build.parse(data_paths), build.parse(shape_paths)
    subset, dropped = igs.subset(shapes)
    subset.serialize(os.path.join(import_dir, "shapes-in-graph.ttl"), format="turtle")
    for src, name in ((merged, "merged.ttl"), (loadable, "loadable.nt"), (inferred, "inferred.nt")):
        shutil.copyfile(src, os.path.join(import_dir, name))
    statements = [line for line in build.cypher(cfg, data, shapes).splitlines() if line.strip()]
    loadable_text = open(loadable, encoding="utf-8").read()
    inferred_text = open(inferred, encoding="utf-8").read()
    report = {
        "input_fingerprint": build.sha_bytes(build.read_bytes(loadable), build.read_bytes(inferred)),
        "shapes_fingerprint": build.sha_bytes(*(build.read_bytes(p) for p in shape_paths)),
        "dropped_constraints": [{"shape": str(s), "constraint": str(p), "reason": r} for s, p, r in dropped],
        "versions": cfg.versions,
        "plugin_jars_sha256": plugin_checksums(plugins_dir),
    }
    with driver.session() as session:
        wipe(session)
        report["shapes_import_rows"], report["in_graph_shape_constraints"] = load(session, statements)
        found = violations(session)
        report["shacl_violations_in_graph"] = len(found)
        report["fail_cases"] = run_fail_cases(session, fail_cases(subset, data, cfg))
        covered = {c["kind"] for c in report["fail_cases"]}
        report["kinds_without_case"] = [k for k in kept_kinds(subset, data) if k not in covered]
        target = mutant_case(subset, data, cfg)
        if target is None:
            raise Failed("no minCount shape on a literal value to use as the mutant")
        m = mutant(session, *target)
        report["mutant"] = m
        report["in_graph_mutant_violations"] = m["violations"]
        rows = session.run(EXPORT).data()
        exported, skipped = rows_to_graph(rows)
        source = Graph().parse(data=loadable_text + inferred_text, format="nt")
        lost, added = diff(source, exported)
        report.update({"export_rows": len(rows), "schema_rows_skipped": skipped,
                       "roundtrip_lost": len(lost), "roundtrip_added": len(added)})
        sorted_hash, nodes, rels, schema = hash_graph(session)
        report.update({"determinism_hash_sorted": sorted_hash, "nodes": nodes, "relationships": rels,
                       "schema_relationships": schema})
        wipe(session)
        target_file = os.path.join(import_dir, "loadable.nt")
        try:
            with open(target_file, "w", encoding="utf-8") as f:
                f.write(shuffled(loadable_text))
            load(session, statements)
            report["determinism_hash_shuffled"] = hash_graph(session)[0]
        finally:
            shutil.copyfile(loadable, target_file)
    report["samples"] = {"violations": found[:5], "lost": lost[:10], "added": added[:10],
                         "failed_cases": [c for c in report["fail_cases"] if not c["passed"]][:5]}
    return report


def passed(report):
    return (report["shacl_violations_in_graph"] == 0 and report["in_graph_mutant_violations"] > 0
            and report["mutant"]["after_restore"] == 0
            and report["roundtrip_lost"] == 0 and report["roundtrip_added"] == 0
            and report["determinism_hash_sorted"] == report["determinism_hash_shuffled"]
            and all(c["passed"] for c in report["fail_cases"]) and not report["kinds_without_case"])


def main(argv):
    try:
        opts, data = build.options(argv)
        build.need(opts, "--config", "--bolt", "--import-dir", "--merged", "--loadable", "--inferred", "--report")
        if not data or not opts.get("--shapes"):
            raise ValueError("give the data files and at least one --shapes file")
        password = os.environ.get("NEO4J_PASSWORD")
        if not password:
            raise ValueError("set NEO4J_PASSWORD")
        cfg = build.load_config(opts["--config"])
    except (OSError, ValueError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(opts["--bolt"], auth=("neo4j", password))
    try:
        report = run(driver, cfg, data, opts["--shapes"], opts["--import-dir"], opts["--merged"],
                     opts["--loadable"], opts["--inferred"], opts.get("--plugins-dir"))
    except Failed as exc:
        print(f"FAIL {exc}")
        return 1
    finally:
        driver.close()
    with open(opts["--report"], "w", encoding="utf-8") as f:
        f.write(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")
    summary = {k: report[k] for k in ("shapes_import_rows", "in_graph_shape_constraints", "shacl_violations_in_graph",
                                      "in_graph_mutant_violations", "roundtrip_lost", "roundtrip_added", "nodes",
                                      "relationships", "determinism_hash_sorted", "determinism_hash_shuffled")}
    summary["fail_cases"] = {c["kind"]: ("pass" if c["passed"] else "FAIL") + f" {c['components']}"
                             for c in report["fail_cases"]}
    summary["kinds_without_case"] = report["kinds_without_case"]
    print(json.dumps(summary, indent=1))
    if not passed(report):
        print("FAIL the verify step did not pass; see the report's samples")
        return 1
    print(f"wrote {opts['--report']}: every check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
