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


def fake(labels=("Resource", "lib__Work", "lib__Person"), types=("lib__createdBy",),
         constraints=(GOOD_CONSTRAINT,), degrees=None, patterns=None):
    """run(statement) answering the review's five queries from the rows given."""
    degrees = degrees if degrees is not None else [
        {"uri": "w1", "labels": ["Resource", "lib__Work"], "degree": 1},
        {"uri": "p1", "labels": ["Resource", "lib__Person"], "degree": 1}]
    patterns = patterns if patterns is not None else [
        {"type": "lib__createdBy", "source": ["Resource", "lib__Work"], "target": ["Resource", "lib__Person"]}]
    answers = {mr.LABELS: [{"label": lb} for lb in labels], mr.TYPES: [{"type": t} for t in types],
               mr.CONSTRAINTS: list(constraints), mr.DEGREES: degrees, mr.PATTERNS: patterns}
    return lambda stmt: answers[stmt]


def rules(found):
    return [f["rule"] for f in found]


class Review(unittest.TestCase):
    def test_a_clean_projection_has_no_finding(self):
        self.assertEqual(mr.review(fake()), [])

    def test_missing_uri_constraint_is_an_error(self):
        found = mr.review(fake(constraints=()))
        self.assertEqual(rules(found), ["missing-key-constraint"])
        self.assertEqual(found[0]["severity"], "ERROR")

    def test_a_constraint_on_another_property_does_not_count(self):
        other = dict(GOOD_CONSTRAINT, properties=["lib__barcode"])
        self.assertEqual(rules(mr.review(fake(constraints=(other,)))), ["missing-key-constraint"])

    def test_a_node_key_constraint_counts(self):
        self.assertEqual(mr.review(fake(constraints=(dict(GOOD_CONSTRAINT, type="NODE_KEY"),))), [])

    def test_a_generic_label_is_a_warning(self):
        found = mr.review(fake(labels=("Resource", "lib__Work", "lib__Entity")))
        self.assertEqual([(f["severity"], f["rule"]) for f in found], [("WARNING", "generic-label")])

    def test_resource_and_schema_labels_are_not_generic(self):
        self.assertEqual(mr.review(fake(labels=("Resource", "_GraphConfig", "n4sch__Class", "lib__Work"))), [])

    def test_a_generic_relationship_type_is_a_warning_in_any_spelling(self):
        for name in ("lib__relatedTo", "lib__HAS", "RELATED_TO"):
            with self.subTest(name=name):
                self.assertEqual(rules(mr.review(fake(types=(name,)))), ["generic-type"])

    def test_a_node_over_the_limit_is_a_supernode(self):
        degrees = [{"uri": "w1", "labels": ["Resource", "lib__Work"], "degree": 11}]
        found = mr.review(fake(degrees=degrees), max_degree=10)
        self.assertEqual([(f["severity"], f["rule"]) for f in found], [("WARNING", "supernode")])

    def test_a_node_far_above_its_label_median_is_a_candidate(self):
        degrees = [{"uri": f"w{i}", "labels": ["Resource", "lib__Work"], "degree": 2} for i in range(5)]
        degrees.append({"uri": "hub", "labels": ["Resource", "lib__Work"], "degree": 60})
        found = mr.review(fake(degrees=degrees))
        self.assertEqual([(f["severity"], f["rule"]) for f in found], [("INFO", "supernode-candidate")])
        self.assertIn("hub", found[0]["message"])

    def test_a_busy_node_under_the_minimum_is_not_a_candidate(self):
        degrees = [{"uri": "w1", "labels": ["Resource", "lib__Work"], "degree": 1},
                   {"uri": "w2", "labels": ["Resource", "lib__Work"], "degree": 1},
                   {"uri": "w3", "labels": ["Resource", "lib__Work"], "degree": 49}]
        self.assertEqual(mr.review(fake(degrees=degrees)), [])

    def test_one_type_in_both_directions_is_a_warning(self):
        patterns = [{"type": "lib__about", "source": ["Resource", "lib__Work"], "target": ["Resource", "lib__Person"]},
                    {"type": "lib__about", "source": ["Resource", "lib__Person"], "target": ["Resource", "lib__Work"]}]
        self.assertEqual(rules(mr.review(fake(patterns=patterns))), ["both-directions"])

    def test_a_type_between_nodes_of_one_label_is_not_both_directions(self):
        patterns = [{"type": "skos__broader", "source": ["Resource", "skos__Concept"],
                     "target": ["Resource", "skos__Concept"]}]
        self.assertEqual(mr.review(fake(patterns=patterns)), [])

    def test_errors_come_first(self):
        found = mr.review(fake(constraints=(), labels=("Resource", "lib__Thing")))
        self.assertEqual(rules(found), ["missing-key-constraint", "generic-label"])

    def test_bad_flags_are_refused(self):
        for argv in ([], ["--uri"], ["--uri", "bolt://x", "--env", "f"], ["--uri", "bolt://x", "--factor", "0"],
                     ["--uri", "bolt://x", "--colour", "red"]):
            with self.subTest(argv=argv):
                self.assertEqual(mr.main(argv), 2)


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
        self.assertEqual(redact(f"neo4j+s://neo4j:{CANARY}@x.io:7687"), "neo4j+s://neo4j:***@x.io:7687")
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
        self.assertIn("bolt://neo4j:***@h:7687", out)

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

    def test_triplestore_reports_store_no_credential(self):
        for counts, name in ((None, ""), ({"urn:x": 1}, ".failed")):
            with self.subTest(report=name or "passed"):
                code, out, report = self.store_run(counts=counts)
                with open(report + name, encoding="utf-8") as f:
                    text = f.read()
                self.assertNotIn(CANARY, text + out)
                self.assertNotIn(CANARY2, text + out)


if __name__ == "__main__":
    unittest.main()
