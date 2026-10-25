#!/usr/bin/env python3
"""Tests of model_review.py (the anti-pattern review) and build.py data-model (the Data Modeling MCP
format). No database: the review runs on a fake query layer, one break per rule."""
import json
import os
import unittest

from rdflib import Graph

import build
import model_review as mr

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


class DataModel(unittest.TestCase):
    def test_the_library_model_has_its_nodes_and_relationships(self):
        model = build.data_model(*library())
        self.assertEqual([n["label"] for n in model["nodes"]],
                         ["lib__Authorship", "lib__Copy", "lib__Person", "lib__Work"])
        self.assertEqual([(r["start_node_label"], r["type"], r["end_node_label"]) for r in model["relationships"]],
                         [("lib__Authorship", "lib__authorshipAgent", "lib__Person"),
                          ("lib__Copy", "lib__copyOf", "lib__Work"),
                          ("lib__Work", "lib__hasAuthorship", "lib__Authorship")])
        self.assertEqual(build.data_model_problems(model), [])

    def test_every_node_is_keyed_on_the_uri(self):
        model = build.data_model(*library())
        self.assertEqual({n["key_property"]["name"] for n in model["nodes"]}, {"uri"})

    def test_a_list_property_is_typed_list_with_its_element_type(self):
        work = next(n for n in build.data_model(*library())["nodes"] if n["label"] == "lib__Work")
        alt = next(p for p in work["properties"] if p["name"] == "lib__altTitle")
        self.assertEqual((alt["type"], alt["description"]), ("LIST", "LIST<STRING NOT NULL>"))

    def test_a_required_scalar_says_not_null(self):
        copy = next(n for n in build.data_model(*library())["nodes"] if n["label"] == "lib__Copy")
        self.assertEqual({p["name"]: (p["type"], p["description"]) for p in copy["properties"]},
                         {"lib__barcode": ("STRING", "NOT NULL"), "lib__shelfNote": ("STRING", None)})

    def test_it_matches_the_graph_type_element_for_element(self):
        statement, left_out = build.graph_type(*library())
        model = build.data_model(*library())
        for node in model["nodes"]:
            if node["properties"]:
                self.assertIn(f"(:`{node['label']}` =>", statement)
        self.assertEqual(model["metadata"]["left_out"], left_out)

    def test_each_mcp_rule_breaks_once(self):
        good = build.data_model(*library())
        breaks = {
            "empty label": lambda m: m["nodes"][0].update(label=""),
            "no key": lambda m: m["nodes"][0].pop("key_property"),
            "repeated property": lambda m: m["nodes"][1]["properties"].append(dict(m["nodes"][1]["properties"][0])),
            "repeated label": lambda m: m["nodes"].append(json.loads(json.dumps(m["nodes"][0]))),
            "empty type": lambda m: m["relationships"][0].update(type=""),
            "unknown end": lambda m: m["relationships"][0].update(end_node_label="lib__Nobody"),
        }
        for name, change in breaks.items():
            with self.subTest(name=name):
                model = json.loads(json.dumps(good))
                change(model)
                self.assertTrue(build.data_model_problems(model))

    def test_the_command_writes_the_model(self):
        import tempfile
        out = os.path.join(tempfile.mkdtemp(), "data-model.json")
        code = build.main(["data-model", "--config", os.path.join(TEMPLATES, "projection-config.json"),
                           "--shapes", os.path.join(TEMPLATES, "library-shapes.ttl"), "--output", out,
                           os.path.join(TEMPLATES, "library-module.ttl")])
        self.assertEqual(code, 0)
        with open(out, encoding="utf-8") as f:
            self.assertEqual(len(json.load(f)["nodes"]), 4)


if __name__ == "__main__":
    unittest.main()
