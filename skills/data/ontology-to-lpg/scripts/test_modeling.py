#!/usr/bin/env python3
"""Tests of model_review.py (the anti-pattern review) and build.py data-model (the Data Modeling MCP
format). No database: the review runs on a fake query layer, one break per rule."""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

from rdflib import Graph

import build
import copy_graph as cg
import load_verify as lv
import model_review as mr
import triplestore as ts
from shell import redact
from test_engine_gate import passing_report

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = os.path.join(HERE, "..", "templates")

GOOD_CONSTRAINT = {"type": "UNIQUENESS", "entityType": "NODE", "labelsOrTypes": ["Resource"], "properties": ["uri"]}


def emulated_domain(labels, skipped, schema_prefix):
    """The Cypher DOMAIN list: $skipped and the schema labels under $schema_prefix left out."""
    return [lb for lb in labels if lb not in skipped and not lb.startswith(schema_prefix)]


def fake(labels=("Resource", "lib__Work", "lib__Person"), types=("lib__createdBy",),
         constraints=(GOOD_CONSTRAINT,), nodes=None, edges=None, calls=None):
    """run(statement, **params) answering the review's queries. nodes are (uri, labels, degree);
    edges are (type, source labels, target labels). The three degree and direction queries are
    emulated in Python with the semantics of their Cypher (median by percentileCont; the domain filter
    first; offenders ordered by degree and cut at $limit), so the rules can be tested without Neo4j."""
    import statistics
    nodes = nodes if nodes is not None else [("w1", ["Resource", "lib__Work"], 1), ("p1", ["Resource", "lib__Person"], 1)]
    edges = edges if edges is not None else [("lib__createdBy", ["Resource", "lib__Work"], ["Resource", "lib__Person"])]

    def run(stmt, **params):
        if calls is not None:
            calls.append((stmt, params))
        if stmt == mr.LABELS:
            return [{"label": lb} for lb in labels]
        if stmt == mr.TYPES:
            return [{"type": t} for t in types]
        if stmt == mr.CONSTRAINTS:
            return list(constraints)
        skipped, schema = params["skipped"], params["schema_prefix"]
        reviewed = [(u, emulated_domain(lbs, skipped, schema), d) for u, lbs, d in nodes if emulated_domain(lbs, skipped, schema)]
        if stmt == mr.LABEL_MEDIANS:
            by = {}
            for _, dl, d in reviewed:
                for lb in dl:
                    by.setdefault(lb, []).append(d)
            return [{"label": lb, "median": float(statistics.median(ds))} for lb, ds in by.items()]
        if stmt == mr.OFFENDERS:
            m = params["medians"]
            hits = [{"uri": u, "labels": dl, "degree": d} for u, dl, d in reviewed
                    if d > params["max_degree"] or (d >= params["min_degree"] and any(
                        d >= params["factor"] * max(m.get(lb, 0), 1) for lb in dl))]
            return sorted(hits, key=lambda r: (-r["degree"], r["uri"]))[:params["limit"]]
        if stmt == mr.RECIPROCAL:
            # A pair (x, y) of one edge: x on its source and not its target, y the reverse.
            pairs = {}
            for t, a, b in edges:
                da, db = emulated_domain(a, skipped, schema), emulated_domain(b, skipped, schema)
                for x in (lb for lb in da if lb not in db):
                    for y in (lb for lb in db if lb not in da):
                        pairs.setdefault(t, set()).add((x, y))
            return [{"type": t, "a": x, "b": y} for t, ps in sorted(pairs.items()) for x, y in sorted(ps)
                    if x < y and (y, x) in ps][:params["limit"]]
        raise AssertionError("unexpected statement " + stmt)
    return run


def rules(found):
    return [f["rule"] for f in found[0]]


def work(uri, degree, *extra):
    return (uri, ["Resource", "lib__Work", *extra], degree)


class Review(unittest.TestCase):
    def test_a_clean_projection_has_no_finding(self):
        self.assertEqual(mr.review(fake()), ([], False))

    def test_missing_uri_constraint_is_an_error(self):
        found, _ = mr.review(fake(constraints=()))
        self.assertEqual([(f["severity"], f["rule"]) for f in found], [("ERROR", "missing-key-constraint")])

    def test_a_constraint_on_another_property_does_not_count(self):
        other = dict(GOOD_CONSTRAINT, properties=["lib__barcode"])
        self.assertEqual(rules(mr.review(fake(constraints=(other,)))), ["missing-key-constraint"])

    def test_a_node_key_constraint_counts(self):
        self.assertEqual(mr.review(fake(constraints=(dict(GOOD_CONSTRAINT, type="NODE_KEY"),)))[0], [])

    def test_a_generic_label_is_a_warning(self):
        found, _ = mr.review(fake(labels=("Resource", "lib__Work", "lib__Entity")))
        self.assertEqual([(f["severity"], f["rule"]) for f in found], [("WARNING", "generic-label")])

    def test_resource_and_schema_labels_are_not_generic(self):
        self.assertEqual(mr.review(fake(labels=("Resource", "_GraphConfig", "n4sch__Class", "lib__Work")))[0], [])

    def test_a_generic_relationship_type_is_a_warning_in_any_spelling(self):
        for name in ("lib__relatedTo", "lib__HAS", "RELATED_TO", "lib__CONNECTED_TO", "lib__related-to", "connected-to"):
            with self.subTest(name=name):
                found, _ = mr.review(fake(types=(name,)))
                self.assertEqual([(f["severity"], f["rule"]) for f in found], [("WARNING", "generic-type")])

    def test_a_node_over_the_limit_is_a_supernode(self):
        found, _ = mr.review(fake(nodes=[work("w1", 11)]), max_degree=10)
        self.assertEqual([(f["severity"], f["rule"]) for f in found], [("WARNING", "supernode")])

    def test_a_node_at_the_limit_is_not_a_supernode(self):
        self.assertEqual(mr.review(fake(nodes=[work("w1", 10)]), max_degree=10, min_degree=11)[0], [])

    def test_a_node_far_above_its_label_median_is_a_warning_candidate(self):
        nodes = [work(f"w{i}", 2) for i in range(5)] + [work("hub", 60)]
        found, _ = mr.review(fake(nodes=nodes))
        self.assertEqual([(f["severity"], f["rule"]) for f in found], [("WARNING", "supernode-candidate")])
        self.assertIn("hub", found[0]["message"])
        self.assertIn("median 2 of lib__Work", found[0]["message"])

    def test_the_factor_and_minimum_are_boundaries(self):
        base = [work(f"w{i}", 5) for i in range(5)]
        self.assertEqual(rules(mr.review(fake(nodes=base + [work("hub", 50)]))), ["supernode-candidate"])   # 50 = 10 x 5
        self.assertEqual(mr.review(fake(nodes=base + [work("hub", 49)]))[0], [])                              # under both
        self.assertEqual(mr.review(fake(nodes=[work(f"w{i}", 1) for i in range(5)] + [work("hub", 49)]))[0], [])

    def test_internal_nodes_are_left_out_of_every_degree_rule(self):
        nodes = [("cfg", ["_GraphConfig"], 200000), ("cls", ["Resource", "n4sch__Class"], 200000)]
        self.assertEqual(mr.review(fake(nodes=nodes + [work("w1", 1)]))[0], [])
        self.assertEqual(rules(mr.review(fake(nodes=nodes + [work("w1", 200000)]))), ["supernode"])

    def test_offenders_stop_at_the_limit(self):
        nodes = [work(f"w{i:02}", 200000) for i in range(5)]
        found, capped = mr.review(fake(nodes=nodes), limit=3)
        self.assertEqual(len(found), 3)
        self.assertTrue(capped)

    def test_degree_work_is_done_in_cypher(self):
        calls = []
        mr.review(fake(calls=calls))
        sent = [stmt for stmt, _ in calls]
        self.assertIn("percentileCont(degree, 0.5)", mr.LABEL_MEDIANS)
        self.assertIn("LIMIT $limit", mr.OFFENDERS)
        self.assertIn("size(dl) > 0", mr.OFFENDERS)
        self.assertEqual(sent.count(mr.OFFENDERS), 1)
        offender_params = next(p for stmt, p in calls if stmt == mr.OFFENDERS)
        self.assertEqual(sorted(offender_params), ["factor", "limit", "max_degree", "medians", "min_degree", "schema_prefix", "skipped"])
        self.assertEqual({p["schema_prefix"] for stmt, p in calls if "schema_prefix" in p}, {"n4sch" + mr.SEP})
        self.assertIn("NOT l STARTS WITH $schema_prefix", mr.DOMAIN)

    def test_a_renamed_graphs_schema_labels_and_local_names_are_read_under_its_separator(self):
        # Under one underscore the schema label is n4sch_Class: left out of every degree rule only when
        # the review is told the separator; generic names are found only then too.
        nodes = [("cls", ["Resource", "n4sch_Class"], 200000), ("w1", ["Resource", "lib_Work"], 1)]
        labels, types = ("Resource", "n4sch_Class", "lib_Work", "lib_Entity"), ("lib_HAS",)
        found, _ = mr.review(fake(labels=labels, types=types, nodes=nodes), sep="_")
        self.assertEqual([(f["severity"], f["rule"]) for f in found], [("WARNING", "generic-label"), ("WARNING", "generic-type")])
        self.assertEqual(rules(mr.review(fake(labels=labels, types=types, nodes=nodes))), ["supernode"])
        # the schema prefix the Cypher gets is the separator's
        calls = []
        mr.review(fake(calls=calls), sep="_")
        self.assertEqual({p["schema_prefix"] for stmt, p in calls if "schema_prefix" in p}, {"n4sch_"})

    def test_one_type_in_both_directions_is_an_info_local_heuristic(self):
        edges = [("lib__about", ["Resource", "lib__Work"], ["Resource", "lib__Person"]),
                 ("lib__about", ["Resource", "lib__Person"], ["Resource", "lib__Work"])]
        found, _ = mr.review(fake(edges=edges))
        self.assertEqual([(f["severity"], f["rule"]) for f in found], [("INFO", "reciprocal-type")])
        self.assertIn("local heuristic", found[0]["message"])

    def test_many_label_pairs_return_only_the_reciprocal_ones(self):
        edges = [("lib__next", ["Resource", f"lib__L{i:02}"], ["Resource", f"lib__L{i + 1:02}"]) for i in range(59)]
        edges += [("lib__about", ["Resource", "lib__Work"], ["Resource", "lib__Person"]),
                  ("lib__about", ["Resource", "lib__Person"], ["Resource", "lib__Work"]),
                  ("lib__cites", ["Resource", "lib__Work"], ["Resource", "lib__Copy"]),
                  ("lib__cites", ["Resource", "lib__Copy"], ["Resource", "lib__Work"])]
        found, _ = mr.review(fake(edges=edges))
        self.assertEqual([f["message"].split(";")[0] for f in found],
                         ["lib__about runs from lib__Person to lib__Work and from lib__Work to lib__Person",
                          "lib__cites runs from lib__Copy to lib__Work and from lib__Work to lib__Copy"])
        found, _ = mr.review(fake(edges=edges), limit=1)
        self.assertEqual(rules((found, False)), ["reciprocal-type"])

    def test_the_reciprocal_query_checks_existence_and_is_limited(self):
        calls = []
        mr.review(fake(calls=calls), limit=7)
        self.assertIn("EXISTS { MATCH (b2:$(y))-[:$(t)]->(a2:$(x))", mr.RECIPROCAL)
        self.assertNotIn("collect(", mr.RECIPROCAL)
        self.assertIn("LIMIT $limit", mr.RECIPROCAL)
        self.assertEqual(next(p for stmt, p in calls if stmt == mr.RECIPROCAL)["limit"], 7)

    def test_one_edge_between_nodes_that_share_two_labels_is_not_reciprocal(self):
        # The Cursor review of 5869898: a projection loads inferred types, so two concepts can both be
        # skos:Concept and a narrower class; one skos:broader edge between them is one direction.
        edges = [("skos__broader", ["Resource", "skos__Concept", "lib__Narrower"],
                  ["Resource", "skos__Concept", "lib__Narrower"])]
        self.assertEqual(mr.review(fake(edges=edges))[0], [])
        self.assertIn("NOT x IN lb", mr.RECIPROCAL)
        self.assertIn("NOT x IN labels(b2) AND NOT y IN labels(a2)", mr.RECIPROCAL)

    def test_a_real_reciprocal_pair_with_a_shared_superclass_is_still_found(self):
        edges = [("lib__about", ["Resource", "lib__Agent", "lib__Work"], ["Resource", "lib__Agent", "lib__Person"]),
                 ("lib__about", ["Resource", "lib__Agent", "lib__Person"], ["Resource", "lib__Agent", "lib__Work"])]
        found, _ = mr.review(fake(edges=edges))
        self.assertEqual([f["message"].split(";")[0] for f in found],
                         ["lib__about runs from lib__Person to lib__Work and from lib__Work to lib__Person"])

    def test_skill_md_runs_the_tests_with_the_pin_check_sh_uses(self):
        # The Cursor review of 5869898: SKILL.md's test command lacked the package the parity test imports.
        skill = open(os.path.join(HERE, "..", "SKILL.md"), encoding="utf-8").read()
        check = open(os.path.join(HERE, "..", "..", "..", "..", "scripts", "check.sh"), encoding="utf-8").read()
        pin = "--with mcp-neo4j-data-modeling==0.8.2"
        self.assertIn(pin, next(line for line in check.splitlines() if "test_modeling" in line))
        self.assertIn(pin, next(line for line in skill.splitlines() if "test_modeling" in line and "uv run" in line))

    def test_a_type_between_nodes_of_one_label_is_not_reciprocal(self):
        edges = [("skos__broader", ["Resource", "skos__Concept"], ["Resource", "skos__Concept"])]
        self.assertEqual(mr.review(fake(edges=edges))[0], [])

    def test_errors_come_first(self):
        found, _ = mr.review(fake(constraints=(), labels=("Resource", "lib__Thing")))
        self.assertEqual([f["rule"] for f in found], ["missing-key-constraint", "generic-label"])

    def test_bad_flags_are_refused(self):
        for argv in ([], ["--uri"], ["--uri", "bolt://x", "--env", "f"], ["--uri", "bolt://x", "--factor", "0"],
                     ["--uri", "bolt://x", "--colour", "red"], ["--uri", "bolt://x", "--query-timeout", "0"],
                     ["--uri", "bolt://x", "--query-timeout", "soon"]):
            with self.subTest(argv=argv):
                self.assertEqual(run_main(mr.main, argv)[0], 2)


class FakeSession:
    """A driver session that records each query it is given and answers with no rows."""

    def __init__(self, fail=None):
        self.queries, self.params, self.fail = [], [], fail

    def run(self, query, parameters=None, **_):
        self.queries.append(query)
        self.params.append(parameters or {})
        if self.fail:
            raise self.fail
        result = mock.MagicMock()
        result.data.return_value = [] if "SHOW CONSTRAINTS" not in str(getattr(query, "text", query)) else [GOOD_CONSTRAINT]
        return result

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def neo4j_with(session):
    """A neo4j module whose driver hands out session, and whose Query keeps its text and timeout."""
    class Query:   # the driver's neo4j.Query: a statement and its timeout
        def __init__(self, text, timeout=None):
            self.text, self.timeout = text, timeout
    fake_module = mock.MagicMock()
    fake_module.Query = Query
    fake_module.GraphDatabase.driver.return_value.__enter__.return_value.session.return_value = session
    return fake_module


class Cli(unittest.TestCase):
    def main(self, session, *extra):
        with mock.patch.dict(os.environ, {"NEO4J_PASSWORD": "pw"}), mock.patch.dict(sys.modules, {"neo4j": neo4j_with(session)}):
            return run_main(mr.main, ["--uri", "bolt://h", *extra])

    def test_every_query_carries_the_timeout(self):
        session = FakeSession()
        code, out = self.main(session, "--query-timeout", "7")
        self.assertEqual(code, 0, out)
        self.assertTrue(session.queries)
        self.assertEqual({q.timeout for q in session.queries}, {7.0})

    def test_the_default_timeout_is_120_seconds(self):
        session = FakeSession()
        self.main(session)
        self.assertEqual({q.timeout for q in session.queries}, {120.0})

    def test_a_timed_out_query_exits_2(self):
        code, out = self.main(FakeSession(fail=Exception("Neo.ClientError.Transaction.TransactionTimedOut")))
        self.assertEqual(code, 2)
        self.assertIn("review query failed", out)

    def test_an_unwritable_report_exits_2_and_keeps_the_old_one(self):
        folder = tempfile.mkdtemp()
        report = os.path.join(folder, "r.json")
        with open(report, "w") as f:
            f.write("OLD")
        with mock.patch.object(mr.json, "dump", side_effect=OSError("disk full")):
            code, out = self.main(FakeSession(), "--report", report)
        self.assertEqual(code, 2, out)
        with open(report) as f:
            self.assertEqual(f.read(), "OLD")
        self.assertEqual(os.listdir(folder), ["r.json"])

    def test_a_report_in_a_missing_folder_exits_2(self):
        code, out = self.main(FakeSession(), "--report", os.path.join(tempfile.mkdtemp(), "no", "r.json"))
        self.assertEqual(code, 2, out)
        self.assertIn("report was not written", out)

    def test_a_clean_review_writes_the_report(self):
        report = os.path.join(tempfile.mkdtemp(), "r.json")
        code, _ = self.main(FakeSession(), "--report", report)
        self.assertEqual(code, 0)
        with open(report) as f:
            self.assertEqual(json.load(f), {"errors": 0, "findings": [], "offenders_capped": False})

    def test_the_separator_reaches_every_cypher_analysis_and_a_bad_one_exits_2(self):
        session = FakeSession()
        code, out = self.main(session, "--separator", "_")
        self.assertEqual(code, 0, out)
        self.assertEqual({p["schema_prefix"] for p in session.params if "schema_prefix" in p}, {"n4sch_"})
        self.assertEqual(sum("schema_prefix" in p for p in session.params), 3)
        session = FakeSession()
        self.main(session)
        self.assertEqual({p["schema_prefix"] for p in session.params if "schema_prefix" in p}, {"n4sch" + mr.SEP})
        session = FakeSession()
        code, out = self.main(session, "--separator", "x")
        self.assertEqual(code, 2, out)
        self.assertEqual(session.queries, [])


class Timeouts(unittest.TestCase):
    """copy_graph.py and load_verify.py run every statement through load_verify.Timed."""

    def test_timed_wraps_statements_and_transactions(self):
        raw = mock.MagicMock()
        with mock.patch.dict(sys.modules, {"neo4j": neo4j_with(None)}):
            timed = lv.Timed(raw, 9)
            timed.run("RETURN 1", {"a": 1})
            timed.begin_transaction()
        sent = raw.run.call_args.args[0]
        self.assertEqual((sent.text, sent.timeout), ("RETURN 1", 9))
        self.assertEqual(raw.begin_transaction.call_args.kwargs, {"timeout": 9})

    def test_bad_timeouts_are_refused(self):
        for value in ("0", "-1", "soon"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                lv.query_timeout({"--query-timeout": value})
        self.assertEqual(lv.query_timeout({}), 120)

    def test_copy_graph_wraps_both_sessions(self):
        env = tempfile.NamedTemporaryFile("w", suffix=".env", delete=False)
        env.write("NEO4J_URI=bolt://h\nNEO4J_USERNAME=neo4j\nNEO4J_PASSWORD=x\n")
        env.close()
        self.addCleanup(os.remove, env.name)
        seen = []
        with mock.patch.dict(os.environ, {"NEO4J_PASSWORD": "local"}), mock.patch.dict(sys.modules, {"neo4j": mock.MagicMock()}), \
                mock.patch.object(cg, "database_identity", side_effect=lambda s: seen.append(s) or len(seen)):
            run_main(cg.main, ["--source", "bolt://x", "--target-env", env.name, "--query-timeout", "5",
                               "--report", passing_report(self)])
        self.assertEqual([(type(s).__name__, s.seconds) for s in seen], [("Timed", 5.0), ("Timed", 5.0)])

    def test_load_verify_wraps_its_session(self):
        tmp = tempfile.mkdtemp()
        captured = {}

        def fake_run(driver, *args, **kwargs):
            captured["timeout"] = args[-1] if len(args) >= 10 else kwargs.get("timeout")
            raise lv.Failed("stop here")
        with mock.patch.dict(os.environ, {"NEO4J_PASSWORD": "pw"}), mock.patch.dict(sys.modules, {"neo4j": mock.MagicMock()}), \
                mock.patch.object(lv, "run", side_effect=fake_run):
            run_main(lv.main, ["--config", os.path.join(TEMPLATES, "projection-config.json"), "--bolt", "bolt://h",
                               "--import-dir", tmp, "--merged", "m", "--loadable", "l", "--inferred", "i",
                               "--report", os.path.join(tmp, "r.json"), "--query-timeout", "33",
                               "--shapes", os.path.join(TEMPLATES, "library-shapes.ttl"),
                               os.path.join(TEMPLATES, "library-module.ttl")])
        self.assertEqual(captured["timeout"], 33.0)


def library():
    cfg = build.load_config(os.path.join(TEMPLATES, "projection-config.json"))
    shapes = Graph().parse(os.path.join(TEMPLATES, "library-shapes.ttl"))
    data = Graph().parse(os.path.join(TEMPLATES, "library-module.ttl"))
    return cfg, shapes, data


LIBRARY_GRAPH_TYPE = """CYPHER 25
ALTER CURRENT GRAPH TYPE SET {
  (:`lib__Authorship` => {`lib__position` :: INTEGER NOT NULL, `lib__source` :: STRING NOT NULL}),
  (:`lib__Copy` => {`lib__barcode` :: STRING NOT NULL, `lib__shelfNote` :: STRING}),
  (:`lib__Person` => {`lib__name` :: STRING NOT NULL}),
  (:`lib__Work` => {`lib__altTitle` :: LIST<STRING NOT NULL>, `lib__title` :: STRING NOT NULL}),
  (:`lib__Authorship`)-[:`lib__authorshipAgent` =>]->(:`lib__Person`),
  (:`lib__Copy`)-[:`lib__copyOf` =>]->(:`lib__Work`),
  (:`lib__Work`)-[:`lib__hasAuthorship` =>]->(:`lib__Authorship`)
}"""   # written by build.py graph-type at c27ef9f, before element_types existed

SYNTHETIC_SHAPES = """
@prefix sh: <http://www.w3.org/ns/shacl#> . @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix lib: <https://id.example.org/library/> .
lib:A a sh:NodeShape ; sh:targetClass lib:Work ;
  sh:property [ sh:path lib:title ; sh:datatype xsd:string ; sh:minCount 1 ; sh:maxCount 1 ] ;
  sh:property [ sh:path lib:tag ; sh:datatype xsd:string ; sh:minCount 0 ] ;
  sh:property [ sh:path lib:size ; sh:datatype xsd:hexBinary ; sh:maxCount 1 ] ;
  sh:property [ sh:path lib:copyOf ; sh:class lib:Person ] .
lib:B a sh:NodeShape ; sh:targetClass lib:Copy ;
  sh:property [ sh:path lib:copyOf ; sh:class lib:Work ] ;
  sh:property [ sh:path lib:note ; sh:in ( "a" ) ] .
"""
SYNTHETIC_DATA = """
@prefix lib: <https://id.example.org/library/> .
lib:w1 lib:title "t" ; lib:tag "x", "y" .
"""


def synthetic():
    cfg = build.load_config(os.path.join(TEMPLATES, "projection-config.json"))
    return cfg, Graph().parse(data=SYNTHETIC_SHAPES, format="turtle"), Graph().parse(data=SYNTHETIC_DATA, format="turtle")


def lone_node(**change):
    """A model of one node and no relationship, so a node rule breaks alone."""
    node = {"label": "lib__Work", "key_property": {"name": "uri", "type": "STRING"},
            "properties": [{"name": "lib__title", "type": "STRING"}]}
    node.update(change)
    return {"nodes": [node], "relationships": []}


class DataModel(unittest.TestCase):
    def test_the_library_graph_type_is_unchanged_by_the_shared_mapping(self):
        statement, left_out = build.graph_type(*library())
        self.assertEqual(statement, LIBRARY_GRAPH_TYPE)
        self.assertEqual(len(left_out), 9)

    def test_the_library_model_has_its_nodes_and_relationships(self):
        model = build.data_model(*library())
        self.assertEqual([n["label"] for n in model["nodes"]],
                         ["lib__Authorship", "lib__Copy", "lib__Person", "lib__Work"])
        self.assertEqual([(r["start_node_label"], r["type"], r["end_node_label"]) for r in model["relationships"]],
                         [("lib__Authorship", "lib__authorshipAgent", "lib__Person"),
                          ("lib__Copy", "lib__copyOf", "lib__Work"),
                          ("lib__Work", "lib__hasAuthorship", "lib__Authorship")])
        self.assertEqual({n["key_property"]["name"] for n in model["nodes"]}, {"uri"})
        self.assertEqual(build.data_model_problems(model), [])

    def test_library_properties_carry_list_and_cardinality(self):
        nodes = {n["label"]: {p["name"]: (p["type"], p["description"]) for p in n["properties"]}
                 for n in build.data_model(*library())["nodes"]}
        self.assertEqual(nodes["lib__Work"], {"lib__altTitle": ("LIST", "LIST<STRING NOT NULL>"),
                                              "lib__title": ("STRING", "NOT NULL")})
        self.assertEqual(nodes["lib__Copy"], {"lib__barcode": ("STRING", "NOT NULL"), "lib__shelfNote": ("STRING", None)})
        self.assertEqual(nodes["lib__Authorship"], {"lib__position": ("INTEGER", "NOT NULL"),
                                                    "lib__source": ("STRING", "NOT NULL")})

    def test_synthetic_graph_type(self):
        statement, left_out = build.graph_type(*synthetic())
        self.assertEqual(statement, "CYPHER 25\nALTER CURRENT GRAPH TYPE SET {\n"
                         "  (:`lib__Work` => {`lib__tag` :: LIST<STRING NOT NULL>, `lib__title` :: STRING NOT NULL})\n}")
        self.assertEqual(left_out, [
            "lib__Copy.lib__note: no sh:datatype or sh:class to map",
            "lib__Copy.lib__note: sh:in (no GRAPH TYPE form)",
            "lib__Copy: no typed property, so no node element type",
            "lib__Work.lib__size: sh:datatype http://www.w3.org/2001/XMLSchema#hexBinary has no GRAPH TYPE property type",
            "lib__copyOf: relationship type used between several label pairs (lib__Copy->lib__Work, "
            "lib__Work->lib__Person); one identifying pair only"])

    def test_synthetic_model_keeps_what_the_graph_type_cannot(self):
        model = build.data_model(*synthetic())
        self.assertEqual([(n["label"], [p["name"] for p in n["properties"]]) for n in model["nodes"]],
                         [("lib__Copy", []), ("lib__Person", []), ("lib__Work", ["lib__tag", "lib__title"])])
        self.assertEqual([(r["start_node_label"], r["type"], r["end_node_label"]) for r in model["relationships"]],
                         [("lib__Copy", "lib__copyOf", "lib__Work"), ("lib__Work", "lib__copyOf", "lib__Person")])
        self.assertEqual(model["metadata"]["not_in_graph_type"], [
            "lib__Copy: no typed property, so no node element type",
            "lib__copyOf: relationship type used between several label pairs (lib__Copy->lib__Work, "
            "lib__Work->lib__Person); one identifying pair only"])
        self.assertEqual(build.data_model_problems(model), [])

    def test_graph_type_comments_are_the_two_lists_together(self):
        for case in (library(), synthetic()):
            _, left_out = build.graph_type(*case)
            meta = build.data_model(*case)["metadata"]
            self.assertEqual(sorted(left_out), sorted(meta["left_out"] + meta["not_in_graph_type"]))

    def test_each_rule_breaks_alone_with_its_exact_problem(self):
        two = lone_node()
        two["nodes"].append(json.loads(json.dumps(two["nodes"][0])))
        cases = {
            "empty label": (lone_node(label=""), ["a node has no non-empty str label ('')"]),
            "no key": ({"nodes": [{"label": "lib__Work"}], "relationships": []}, ["node 'lib__Work' has no key property"]),
            "nameless property": (lone_node(properties=[{"type": "STRING"}]), ["node 'lib__Work': a property has no str name"]),
            "number type": (lone_node(properties=[{"name": "p", "type": 3}]), ["node 'lib__Work': property 'p' has a bad type"]),
            "repeated property": (lone_node(properties=[{"name": "p"}, {"name": "p"}]),
                                  ["property 'p' appears 2 times in node 'lib__Work'"]),
            "repeated label": (two, ["node label 'lib__Work' appears 2 times"]),
        }
        rel = lone_node()
        cases.update({
            "empty type": (dict(rel, relationships=[{"type": "", "start_node_label": "lib__Work", "end_node_label": "lib__Work"}]),
                           ["relationship (lib__Work)-[]->(lib__Work) has no non-empty str type"]),
            "unknown start": (dict(rel, relationships=[{"type": "t", "start_node_label": "X", "end_node_label": "lib__Work"}]),
                              ["relationship (X)-[t]->(lib__Work): its start node is not in the model"]),
            "unknown end": (dict(rel, relationships=[{"type": "t", "start_node_label": "lib__Work", "end_node_label": "X"}]),
                            ["relationship (lib__Work)-[t]->(X): its end node is not in the model"]),
            "repeated relationship property": (dict(rel, relationships=[{"type": "t", "start_node_label": "lib__Work",
                                                                         "end_node_label": "lib__Work",
                                                                         "properties": [{"name": "p"}, {"name": "p"}]}]),
                                               ["property 'p' appears 2 times in relationship (lib__Work)-[t]->(lib__Work)"]),
        })
        self.assertEqual(build.data_model_problems(lone_node()), [])
        self.assertEqual(build.data_model_problems(lone_node(properties=[{"name": "uri"}])), [])   # the key is excepted
        for name, (model, expected) in cases.items():
            with self.subTest(name=name):
                self.assertEqual(build.data_model_problems(model), expected)
        self.corpus = [lone_node(), build.data_model(*library()), build.data_model(*synthetic())] + [m for m, _ in cases.values()]

    def test_it_agrees_with_the_pinned_mcp_package(self):
        # The canonical validator: mcp-neo4j-data-modeling 0.8.2 (check.sh installs it for this test).
        from mcp_neo4j_data_modeling.data_model import DataModel as Canonical
        self.test_each_rule_breaks_alone_with_its_exact_problem()
        for model in self.corpus:
            with self.subTest(model=json.dumps(model)[:80]):
                try:
                    Canonical.model_validate(model, strict=True)
                    canonical_ok = True
                except Exception:
                    canonical_ok = False
                self.assertEqual(build.data_model_problems(model) == [], canonical_ok)

    def test_the_command_writes_the_model_or_refuses_it(self):
        out = os.path.join(tempfile.mkdtemp(), "data-model.json")
        args = ["data-model", "--config", os.path.join(TEMPLATES, "projection-config.json"),
                "--shapes", os.path.join(TEMPLATES, "library-shapes.ttl"), "--output", out,
                os.path.join(TEMPLATES, "library-module.ttl")]
        code, _ = run_main(build.main, args)
        self.assertEqual(code, 0)
        with open(out, encoding="utf-8") as f:
            self.assertEqual(len(json.load(f)["nodes"]), 4)
        os.remove(out)
        with mock.patch.object(build, "data_model_problems", return_value=["planted"]):
            code, printed = run_main(build.main, args)
        self.assertEqual(code, 1)
        self.assertIn("FAIL planted", printed)
        self.assertFalse(os.path.exists(out))


CANARY, CANARY2 = "canaryPW1", "canaryPW2"


def run_main(main, argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = main(argv)
    return code, out.getvalue()


def leaky_neo4j():
    """A neo4j module whose driver fails with the URI and the credentials in its message, as a real
    driver's configuration error can."""
    fake = mock.MagicMock()

    def driver(uri, auth=None, **_):
        raise Exception(f"cannot reach {uri} as {auth}")
    fake.GraphDatabase.driver.side_effect = driver
    return fake


class Secrets(unittest.TestCase):
    """Finding #1 of the 2026-10-25 review: no password or token reaches the output or a report."""

    def test_redact_hides_userinfo_tokens_and_fragments(self):
        self.assertEqual(redact(f"neo4j+s://neo4j:{CANARY}@x.io:7687"), "neo4j+s://***@x.io:7687")
        self.assertEqual(redact(f"https://{CANARY}@host/x"), "https://***@host/x")   # userinfo without a colon
        self.assertEqual(redact(f"https://h/ds?graph=g&token={CANARY}#{CANARY2}"), "https://h/ds?graph=g&token=***")
        self.assertEqual(redact(f"https://h/q?X-Amz-Signature={CANARY}"), "https://h/q?X-Amz-Signature=***")
        self.assertEqual(redact("bolt://127.0.0.1:7687"), "bolt://127.0.0.1:7687")
        self.assertEqual(redact("not a url"), "not a url")

    def test_model_review_prints_no_credential(self):
        with mock.patch.dict(os.environ, {"NEO4J_PASSWORD": CANARY2}), mock.patch.dict(sys.modules, {"neo4j": leaky_neo4j()}):
            code, out = run_main(mr.main, ["--uri", f"bolt://neo4j:{CANARY}@h:7687"])
        self.assertEqual(code, 2)
        self.assertNotIn(CANARY, out)
        self.assertNotIn(CANARY2, out)
        self.assertIn("the review query failed (Exception)", out)

    def test_copy_graph_prints_no_credential(self):
        env = tempfile.NamedTemporaryFile("w", suffix=".env", delete=False)
        env.write(f"NEO4J_URI=neo4j+s://neo4j:{CANARY}@x.io\nNEO4J_USERNAME=neo4j\nNEO4J_PASSWORD={CANARY}\n")
        env.close()
        self.addCleanup(os.remove, env.name)
        with mock.patch.dict(os.environ, {"NEO4J_PASSWORD": CANARY2}), mock.patch.dict(sys.modules, {"neo4j": leaky_neo4j()}):
            code, out = run_main(cg.main, ["--source", f"bolt://neo4j:{CANARY2}@h", "--target-env", env.name,
                                           "--report", passing_report(self)])
        self.assertEqual(code, 1, out)
        self.assertNotIn(CANARY, out)
        self.assertNotIn(CANARY2, out)
        self.assertNotIn(CANARY, cg.describe_target({"NEO4J_URI": f"bolt://u:{CANARY}@h", "NEO4J_USERNAME": "u"}))

    def test_load_verify_prints_no_credential(self):
        tmp = tempfile.mkdtemp()
        with mock.patch.dict(os.environ, {"NEO4J_PASSWORD": CANARY2}), mock.patch.dict(sys.modules, {"neo4j": leaky_neo4j()}):
            code, out = run_main(lv.main, ["--config", os.path.join(TEMPLATES, "projection-config.json"),
                                           "--bolt", f"bolt://neo4j:{CANARY}@h", "--import-dir", tmp,
                                           "--merged", "m.ttl", "--loadable", "l.nt", "--inferred", "i.nt",
                                           "--report", os.path.join(tmp, "r.json"),
                                           "--shapes", os.path.join(TEMPLATES, "library-shapes.ttl"),
                                           os.path.join(TEMPLATES, "library-module.ttl")])
        self.assertEqual(code, 1, out)
        self.assertNotIn(CANARY, out)
        self.assertNotIn(CANARY2, out)

    def test_load_verify_scrubs_its_own_messages(self):
        tmp = tempfile.mkdtemp()
        with mock.patch.dict(os.environ, {"NEO4J_PASSWORD": CANARY2}), mock.patch.dict(sys.modules, {"neo4j": mock.MagicMock()}), \
                mock.patch.object(lv, "run", side_effect=lv.Failed(f"check failed near {CANARY2}")):
            code, out = run_main(lv.main, ["--config", os.path.join(TEMPLATES, "projection-config.json"),
                                           "--bolt", "bolt://h", "--import-dir", tmp, "--merged", "m.ttl",
                                           "--loadable", "l.nt", "--inferred", "i.nt", "--report", os.path.join(tmp, "r.json"),
                                           "--shapes", os.path.join(TEMPLATES, "library-shapes.ttl"),
                                           os.path.join(TEMPLATES, "library-module.ttl")])
        self.assertEqual(code, 1, out)
        self.assertIn("check failed near ***", out)
        self.assertNotIn(CANARY2, out)

    def store_run(self, put=None, counts=None):
        import urllib.error  # noqa: F401
        tmp = tempfile.mkdtemp()
        nt = os.path.join(tmp, "inferred.nt")
        open(nt, "w").close()
        report = os.path.join(tmp, "ts.json")
        module = os.path.join(TEMPLATES, "library-module.ttl")
        graph = ts.graph_iri(Graph().parse(module), module, ts.DEFAULT_BASE)
        n = len(Graph().parse(module))

        def select(store, sparql, default_graphs=()):
            if "GROUP BY ?p" in sparql:
                return [{"p": {"value": p}, "n": {"value": str(c)}}
                        for p, c in (counts or ts.predicate_counts([Graph().parse(module)])).items()]
            return [{"n": {"value": str(n if graph in sparql else 0)}}]
        with mock.patch.object(ts.Store, "put_graph", side_effect=put or (lambda *a: 201)), \
                mock.patch.object(ts.Store, "select", select):
            code, out = run_main(ts.main, ["--gsp", f"http://u:{CANARY}@h/ds?token={CANARY2}",
                                           "--query", f"http://u:{CANARY}@h/q", "--inferred", nt, "--report", report, module])
        return code, out, report

    def test_triplestore_failure_prints_no_credential(self):
        import urllib.error
        code, out, _ = self.store_run(put=urllib.error.URLError(f"refused http://u:{CANARY}@h token={CANARY2}"))
        self.assertEqual(code, 1, out)
        self.assertNotIn(CANARY, out)
        self.assertNotIn(CANARY2, out)

    def test_triplestore_setup_errors_print_no_credential(self):
        tmp = tempfile.mkdtemp()
        env = os.path.join(tmp, "store.env")
        with open(env, "w") as f:
            f.write(f"SPARQL_USER=storeuser\nSPARQL_PASSWORD={CANARY2}\n")
        nt = os.path.join(tmp, "inferred.nt")
        open(nt, "w").close()
        gsp = f"http://storeuser:{CANARY}@h/ds?token={CANARY2}"
        # An input path that holds the URL and the password, so the open error carries them.
        missing = f"/nonexistent/{gsp}/{CANARY2}.ttl"
        code, out = run_main(ts.main, ["--env", env, "--gsp", gsp, "--query", f"http://storeuser:{CANARY}@h/q",
                                       "--inferred", nt, "--report", os.path.join(tmp, "r.json"), missing])
        self.assertEqual(code, 2, out)
        self.assertNotIn(CANARY, out)
        self.assertNotIn(CANARY2, out)
        self.assertNotIn("storeuser", out)
        self.assertIn("ERROR", out)

    def test_an_env_configured_url_in_an_error_prints_no_secret(self):
        tmp = tempfile.mkdtemp()
        url = f"https://{CANARY}@h/ds?token={CANARY2}"
        nt = os.path.join(tmp, "inferred.nt")
        open(nt, "w").close()
        # 1. The env file fails to parse on a line that holds the URL.
        bad = os.path.join(tmp, "bad.env")
        with open(bad, "w") as f:
            f.write(f"{url}\n")
        # 2. The env file parses, and an input path that holds its URL fails to open.
        good = os.path.join(tmp, "good.env")
        with open(good, "w") as f:
            f.write(f"SPARQL_GSP={url}\nSPARQL_QUERY={url}\n")
        for env, data in ((bad, nt), (good, f"/nonexistent/{url}.ttl")):
            with self.subTest(env=os.path.basename(env)):
                code, out = run_main(ts.main, ["--env", env, "--inferred", nt, "--report", os.path.join(tmp, "r.json"), data])
                self.assertEqual(code, 2, out)
                self.assertNotIn(CANARY, out)
                self.assertNotIn(CANARY2, out)
        env = os.path.join(tmp, "neo.env")
        with open(env, "w") as f:
            f.write(f"NEO4J_URI={url}\nNEO4J_USERNAME=neo4j\nNEO4J_PASSWORD={CANARY2}\n")
        with mock.patch.dict(sys.modules, {"neo4j": leaky_neo4j()}):
            code, out = run_main(mr.main, ["--env", env])
        self.assertEqual(code, 2, out)
        self.assertNotIn(CANARY, out)
        self.assertNotIn(CANARY2, out)

    def test_an_error_prints_its_type_only(self):
        from shell import Refusal, error_line
        self.assertEqual(error_line("x failed", ValueError(f"bad {CANARY}")), "x failed (ValueError)")
        self.assertEqual(error_line("x failed", FileNotFoundError(2, "No such file", f"/a/{TOKEN}.ttl")),
                         "x failed (FileNotFoundError)")
        self.assertEqual(error_line("x failed", Refusal("missing --report")), "missing --report")


    def test_triplestore_reports_store_no_credential(self):
        for counts, name in ((None, ""), ({"urn:x": 1}, ".failed")):
            with self.subTest(report=name or "passed"):
                code, out, report = self.store_run(counts=counts)
                with open(report + name, encoding="utf-8") as f:
                    text = f.read()
                self.assertNotIn(CANARY, text + out)
                self.assertNotIn(CANARY2, text + out)



TOKEN = "ghp_Z9tokenLike0123456789"   # a token-shaped string with no URL or @ in it


class NoUserText(unittest.TestCase):
    """A refusal or error line never holds text the user supplied: no path, no value, no unknown option
    (quick check of 8bf10b2). Each path is tried with a token-shaped path and a --secret TOKEN argument."""

    def tokenpath(self, content=None, suffix=".env"):
        folder = os.path.join(tempfile.mkdtemp(), TOKEN)
        os.mkdir(folder)
        path = os.path.join(folder, TOKEN + suffix)
        if content is not None:
            with open(path, "w") as f:
                f.write(content)
        return path

    def clean(self, out):
        self.assertNotIn(TOKEN, out)

    def test_copy_graph(self):
        bad_env = self.tokenpath(f"{TOKEN}\n")
        for argv in (["--source", "bolt://h", "--target-env", bad_env, "--report", passing_report(self)],
                     ["--source", "bolt://h", "--target-env", self.tokenpath(), "--report", passing_report(self)],
                     ["--source", "bolt://h", "--target-env", bad_env, "--report", passing_report(self), "--secret", TOKEN],
                     ["--source", "bolt://h", "--target-env", bad_env, "--report", self.tokenpath(suffix=".json")]):
            with self.subTest(argv=argv[-2:]), mock.patch.dict(os.environ, {"NEO4J_PASSWORD": "pw"}):
                code, out = run_main(cg.main, argv)
                self.assertEqual(code, 2, out)
                self.clean(out)
        code, out = run_main(cg.main, ["--source", "bolt://h", "--target-env", bad_env, "--report", "r", "--secret", TOKEN])
        self.assertIn("unknown option(s) or argument(s): 1", out)

    def test_triplestore(self):
        tmp = tempfile.mkdtemp()
        nt = os.path.join(tmp, "inferred.nt")
        open(nt, "w").close()
        module = os.path.join(TEMPLATES, "library-module.ttl")
        unearned = self.tokenpath(json.dumps({"passed": False}), ".json")
        base = ["--gsp", "http://h/ds", "--query", "http://h/q", "--inferred", nt, "--report", os.path.join(tmp, "r.json")]
        for argv in (["--env", self.tokenpath(f"{TOKEN}\n"), "--inferred", nt, "--report", os.path.join(tmp, "r.json"), module],
                     base + [self.tokenpath(suffix=".ttl")],
                     base + ["--projection-report", unearned, module],
                     base + ["--projection-report", self.tokenpath(suffix=".json"), module],
                     base + ["--cq", self.tokenpath(suffix=".rq"), module],
                     base + ["--secret", TOKEN, self.tokenpath(suffix=".ttl")]):
            with self.subTest(argv=argv[-3:]):
                code, out = run_main(ts.main, argv)
                self.assertEqual(code, 2, out)
                self.clean(out)

    def test_model_review(self):
        for argv in (["--env", self.tokenpath()], ["--env", self.tokenpath(f"{TOKEN}\n")],
                     ["--uri", "bolt://h", "--secret", TOKEN], ["--uri", "bolt://h", "--limit", TOKEN],
                     ["--uri", "bolt://h", "--query-timeout", TOKEN]):
            with self.subTest(argv=argv), mock.patch.dict(os.environ, {"NEO4J_PASSWORD": "pw"}):
                code, out = run_main(mr.main, argv)
                self.assertEqual(code, 2, out)
                self.clean(out)

    def test_load_verify(self):
        tmp = tempfile.mkdtemp()
        common = ["--bolt", "bolt://h", "--import-dir", tmp, "--merged", "m", "--loadable", "l", "--inferred", "i",
                  "--report", os.path.join(tmp, "r.json"), "--shapes", os.path.join(TEMPLATES, "library-shapes.ttl")]
        config = os.path.join(TEMPLATES, "projection-config.json")
        module = os.path.join(TEMPLATES, "library-module.ttl")
        for argv in (["--config", self.tokenpath(suffix=".json")] + common + [module],
                     ["--config", config, "--manual-cases", self.tokenpath("{}", ".json")] + common + [module],
                     ["--config", config, "--manual-cases", self.tokenpath(suffix=".json")] + common + [module],
                     ["--config", config, "--query-timeout", TOKEN] + common + [module],
                     ["--config", config] + common + [module, "--" + TOKEN]):
            with self.subTest(argv=argv[:3]), mock.patch.dict(os.environ, {"NEO4J_PASSWORD": "pw"}):
                code, out = run_main(lv.main, argv)
                self.assertEqual(code, 2, out)
                self.clean(out)

    def test_an_option_without_a_value_is_not_echoed(self):
        with self.assertRaises(ValueError) as caught:
            build.options(["--" + TOKEN])
        self.assertNotIn(TOKEN, str(caught.exception))


if __name__ == "__main__":
    unittest.main()
