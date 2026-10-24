"""Tests for the engine-readback gate, the fail-closed report and the add-ons (copy, GRAPH TYPE,
triple store). No test needs Neo4j, a triple store or Java: the engine's answers are given as rows.

Run from this folder:
  uv run --no-project --with rdflib --with pyshacl python3 -m unittest test_engine_gate
"""
import contextlib
import io
import json
import os
import shlex
import sys
import tempfile
import unittest
from unittest import mock

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import OWL, RDF, SH, XSD

import build
import copy_graph as cg
import in_graph_shapes as igs
import load_verify as lv
import triplestore as ts

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = os.path.join(HERE, "..", "templates")
MODULE = os.path.join(TEMPLATES, "library-module.ttl")
SHAPES = os.path.join(TEMPLATES, "library-shapes.ttl")
CONFIG = os.path.join(TEMPLATES, "projection-config.json")
LIB = "https://id.example.org/library/"


def lib(name):
    return URIRef(LIB + name)


def cfg():
    return build.load_config(CONFIG)


def run_main(main, argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = main(argv)
    return code, out.getvalue()


def shape_graph(*triples):
    g = Graph()
    g.bind("lib", LIB)
    g.add((lib("S"), RDF.type, SH.NodeShape))
    g.add((lib("S"), SH.targetClass, lib("Copy")))
    g.add((lib("S"), SH.property, lib("S-p")))
    g.add((lib("S-p"), SH.path, lib("barcode")))
    for t in triples:
        g.add(t)
    return g


def row(target, path, param, value):
    return {"target": target, "path": path, "param": param, "value": value}


class Sanitizer(unittest.TestCase):
    """in_graph_shapes.py leaves out only what would break n10s, and gates nothing."""

    def left_out_terms(self, g):
        return {str(t[1]) for t in igs.subset(g)[1]}

    def test_drops_the_terms_n10s_cannot_take(self):
        g = shape_graph((lib("S-p"), SH.datatype, RDF.langString), (lib("S-p"), SH.pattern, Literal("^a")))
        head = BNode()
        Collection(g, head, [Literal(1), Literal(2)])
        g.add((lib("S-p"), SH["in"], head))
        g.add((lib("S-p"), SH.hasValue, Literal("x")))
        self.assertEqual(self.left_out_terms(g), {str(SH.datatype), str(SH.pattern), str(SH["in"]), str(SH.hasValue)})

    def test_drops_a_deactivated_shape(self):
        g = shape_graph((lib("S-p"), SH.minCount, Literal(1)), (lib("S-p"), SH.deactivated, Literal(True)))
        safe, left = igs.subset(g)
        self.assertNotIn((lib("S-p"), SH.minCount, Literal(1)), safe)
        self.assertEqual([str(t[1]) for t in left], [str(SH.deactivated)])

    def test_drops_value_terms_on_an_inverse_path_but_keeps_counts(self):
        # n10s reads the inverse flag only for cardinality; a load showed sh:class checked forwards.
        g = shape_graph()
        g.remove((lib("S-p"), SH.path, lib("barcode")))
        inv = BNode()
        g.add((inv, SH.inversePath, lib("hasCopy")))
        g.add((lib("S-p"), SH.path, inv))
        g.add((lib("S-p"), SH["class"], lib("Work")))
        g.add((lib("S-p"), SH.minCount, Literal(1)))
        safe, left = igs.subset(g)
        self.assertEqual([str(t[1]) for t in left], [str(SH["class"])])
        self.assertIn((lib("S-p"), SH.minCount, Literal(1)), safe)

    def test_keeps_everything_else(self):
        g = shape_graph((lib("S-p"), SH.minCount, Literal(1)), (lib("S-p"), SH.maxLength, Literal(8)),
                        (lib("S-p"), SH.datatype, XSD.string), (lib("S"), SH.closed, Literal(True)))
        self.assertEqual(igs.subset(g)[1], [])

    def test_prediction_is_labelled_advisory(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = run_main(igs.main, ["--output", os.path.join(tmp, "s.ttl"), SHAPES])
        self.assertEqual(code, 0, out)
        lines = [line for line in out.splitlines() if line.startswith("PREDICTION")]
        self.assertTrue(lines)
        self.assertTrue(all("advisory" in line for line in lines))
        self.assertIn("gates nothing", igs.__doc__)

    def test_prediction_lists_node_level_class(self):
        g = shape_graph((lib("S"), SH["class"], lib("Copy")))
        self.assertIn(("lib:Copy", None, "sh:class"), igs.predict(g, lambda i: i.n3(g.namespace_manager)))


class FileAgainstEngine(unittest.TestCase):
    """The gate: every constraint the file states is matched to a listShapes row by value too."""

    def test_values_are_spelled_as_listShapes_lists_them(self):
        g = shape_graph((lib("S-p"), SH["class"], lib("Work")), (lib("S-p"), SH.maxCount, Literal(1)),
                        (lib("S-p"), SH.disjoint, lib("title")))
        head = BNode()
        Collection(g, head, [lib("a"), lib("b")])
        g.add((lib("S-p"), SH["in"], head))
        got = {c["term"]: c["value"] for c in lv.file_constraints(g, cfg())}
        self.assertEqual(got["sh:class"], "lib__Work")
        self.assertEqual(got["sh:maxCount"], 1)
        self.assertEqual(got["sh:in"], [LIB + "a", LIB + "b"])
        self.assertEqual(got["sh:hasValue"], [LIB + "title"])   # sh:disjoint, as n10s 2025.06.1 lists it

    def test_a_second_shape_with_another_value_is_not_compiled(self):
        # Before, the comparison ignored the value, so a ghost shape on the same key looked compiled.
        g = shape_graph((lib("S-p"), SH.maxLength, Literal(8)))
        ghost = BNode()
        g.add((lib("Ghost"), SH.targetClass, lib("Copy")))
        g.add((lib("Ghost"), SH.property, ghost))
        g.add((ghost, SH.path, lib("barcode")))
        g.add((ghost, SH.maxLength, Literal(9)))
        missing = lv.not_compiled(lv.file_constraints(g, cfg()), [row("lib__Copy", "lib__barcode", "sh:maxLength", 8)])
        self.assertEqual([(c["term"], c["value"]) for c in missing], [("sh:maxLength", 9)])

    def test_closed_matches_its_ignored_properties_row_exactly(self):
        # Review 8, #4: the file's ignore-list is compared with the compiled one, not skipped.
        g = shape_graph((lib("S"), SH.closed, Literal(True)))
        head = BNode()
        Collection(g, head, [RDF.type])
        g.add((lib("S"), SH.ignoredProperties, head))
        cons = lv.file_constraints(g, cfg())
        self.assertEqual(lv.not_compiled(cons, [row("lib__Copy", None, "sh:ignoredProperties", ["rdf__type"])]), [])
        wider = [row("lib__Copy", None, "sh:ignoredProperties", ["lib__extra", "rdf__type"])]
        self.assertEqual([c["term"] for c in lv.not_compiled(cons, wider)], ["sh:ignoredProperties"])
        planned = lv.plan_cases(wider, cons, set(), cfg())
        self.assertIn("mismatch", planned[0])
        self.assertEqual(lv.run_cases(None, planned)[0]["status"], "failed")
        bare = lv.file_constraints(shape_graph((lib("S"), SH.closed, Literal(True))), cfg())
        self.assertTrue(lv.not_compiled(bare, [row("lib__Copy", None, "sh:ignoredProperties", ["rdf__type"])]))

    def test_node_shape_reached_from_a_property_shape_has_no_class_target(self):
        g = shape_graph((lib("S-p"), SH.node, lib("Inner")), (lib("Inner"), RDF.type, SH.NodeShape),
                        (lib("Inner"), SH["class"], lib("Work")))
        inner = [c for c in lv.file_constraints(g, cfg()) if c["shape"] == "lib:Inner"]
        self.assertTrue(inner and all(c["target"].startswith("(no class target") for c in inner))

    def test_terms_n10s_never_compiles_are_reported(self):
        g = shape_graph((lib("S-p"), SH.lessThan, lib("other")))
        head = BNode()
        Collection(g, head, [Literal("en")])
        g.add((lib("S-p"), SH.languageIn, head))
        missing = lv.not_compiled(lv.file_constraints(g, cfg()), [])
        self.assertIn(("sh:languageIn", ["en"]), [(c["term"], c["value"]) for c in missing])
        self.assertIn("sh:lessThan", [c["term"] for c in missing])

    def test_value_key_reads_numbers_and_lists_alike(self):
        self.assertEqual(lv.value_key(8), lv.value_key(8.0))
        self.assertEqual(lv.value_key(["b", "a"]), lv.value_key(["a", "b"]))


class Cases(unittest.TestCase):
    """One generated case per compiled row; each makes its own node and names the path to report."""

    def constraints(self, *extra):
        g = shape_graph(*extra)
        return lv.file_constraints(g, cfg())

    def case(self, r, constraints=None, literal=()):
        return lv.case_for(r, constraints if constraints is not None else self.constraints(), set(literal), cfg(), 7)

    def test_every_case_makes_its_own_node(self):
        param, path, cypher = self.case(row("lib__Copy", "lib__barcode", "sh:minCount", 1))
        self.assertEqual((param, path), ("sh:minCount", LIB + "barcode"))
        self.assertTrue(cypher.startswith('CREATE (n:Resource:`lib__Copy` {uri: "urn:lpg-projection:fail-case:7"})'))
        self.assertNotIn("MATCH", cypher)

    def test_zero_minimums_are_no_ops(self):
        self.assertIsNone(self.case(row("lib__Copy", "lib__barcode", "sh:minCount", 0))[2])
        self.assertIsNone(self.case(row("lib__Copy", "lib__barcode", "sh:minLength", 0))[2])

    def test_max_count_on_a_dated_value_repeats_dates(self):
        cons = self.constraints((lib("S-p"), SH.datatype, XSD.date))
        cypher = self.case(row("lib__Copy", "lib__barcode", "sh:maxCount", 1), cons)[2]
        self.assertIn("[date('2020-01-01'), date('2020-01-02')]", cypher)
        cypher0 = self.case(row("lib__Copy", "lib__barcode", "sh:maxCount", 0), cons)[2]
        self.assertIn("SET n.`lib__barcode` = date('2020-01-01')", cypher0)

    def test_max_count_on_a_relationship_adds_one_too_many(self):
        cypher = self.case(row("lib__Copy", "lib__copyOf", "sh:maxCount", 1))[2]
        self.assertEqual(cypher.count("CREATE (n)-[:`lib__copyOf`]->"), 2)

    def test_inverse_paths(self):
        g = shape_graph()
        g.remove((lib("S-p"), SH.path, lib("barcode")))
        inv = BNode()
        g.add((inv, SH.inversePath, lib("hasCopy")))
        g.add((lib("S-p"), SH.path, inv))
        g.add((lib("S-p"), SH.maxCount, Literal(1)))
        cons = lv.file_constraints(g, cfg())
        self.assertEqual(self.case(row("lib__Copy", "lib__hasCopy", "sh:maxCount", 1), cons)[2].count("<-[:`lib__hasCopy`]-"), 2)
        self.assertNotIn("<-", self.case(row("lib__Copy", "lib__hasCopy", "sh:minCount", 1), cons)[2])
        self.assertEqual(self.case(row("lib__Copy", "lib__hasCopy", "sh:class", "lib__Work"), cons)[2], "")

    def test_disjoint_is_listed_as_has_value_and_gets_its_own_case(self):
        cons = self.constraints((lib("S-p"), SH.disjoint, lib("title")), (lib("S-p"), SH.datatype, XSD.string))
        param, path, cypher = self.case(row("lib__Copy", "lib__barcode", "sh:hasValue", [LIB + "title"]), cons)
        self.assertEqual(param, "sh:disjoint")
        self.assertIn("n.`lib__title` = 'value 1'", cypher)

    def test_closed_case_names_the_extra_property_as_its_path(self):
        param, path, cypher = self.case(row("lib__Copy", None, "sh:ignoredProperties", ["rdf__type"]))
        self.assertEqual(path, LIB + "notInTheShape")
        self.assertIn("lib__notInTheShape", cypher)

    def test_node_level_class(self):
        self.assertIsNone(self.case(row("lib__Copy", None, "sh:class", "lib__Copy"))[2])
        self.assertTrue(self.case(row("lib__Copy", None, "sh:class", "lib__Item"))[2])

    def test_node_kind(self):
        rel = self.constraints((lib("S-p"), SH["class"], lib("Work")))
        self.assertIn("'not an IRI'", self.case(row("lib__Copy", "lib__barcode", "sh:NodeKind", str(SH.IRI)), rel)[2])
        lit = self.constraints((lib("S-p"), SH.datatype, XSD.string))
        self.assertIn("CREATE (n)-[:`lib__barcode`]->",
                      self.case(row("lib__Copy", "lib__barcode", "sh:NodeKind", str(SH.Literal)), lit)[2])
        self.assertEqual(self.case(row("lib__Copy", "lib__barcode", "sh:NodeKind", str(SH.BlankNode)), lit)[2], "")

    def test_shapes_decide_property_or_relationship_before_the_data(self):
        lit = self.constraints((lib("S-p"), SH.datatype, XSD.date))
        self.assertTrue(lv.is_literal("lib__Copy", "lib__barcode", lit, set(), cfg()))
        rel = self.constraints((lib("S-p"), SH["class"], lib("Work")))
        self.assertFalse(lv.is_literal("lib__Copy", "lib__barcode", rel, {lib("barcode")}, cfg()))

    def test_a_row_without_a_case_needs_a_manual_case(self):
        rows = [row("lib__Copy", "lib__barcode", "sh:NodeKind", str(SH.BlankNode))]
        cons = self.constraints((lib("S-p"), SH.datatype, XSD.string))
        self.assertEqual(lv.plan_cases(rows, cons, set(), cfg())[0]["cypher"], "")
        manual = [{"target": "lib__Copy", "path": "lib__barcode", "param": "sh:NodeKind", "cypher": "RETURN 'x' AS focus"}]
        planned = lv.plan_cases(rows, cons, set(), cfg(), manual)[0]
        self.assertEqual((planned["source"], planned["expected_path"]), ("manual", None))

    def test_a_case_passes_only_on_its_focus_path_and_component(self):
        case = {"expected_param": "sh:minCount", "expected_path": LIB + "barcode"}
        hit = {"focusNode": "f", "propertyShape": str(SH) + "CountConstraintComponent", "resultPath": LIB + "barcode"}
        self.assertEqual(lv.case_result(case, "f", [hit])[1], "passed")
        self.assertEqual(lv.case_result(case, "f", [dict(hit, resultPath=LIB + "title")])[1], "failed")
        self.assertEqual(lv.case_result(case, "f", [dict(hit, focusNode="g")])[1], "failed")
        self.assertEqual(lv.case_result(case, "f", [dict(hit, propertyShape=str(SH) + "ClassConstraintComponent")])[1],
                         "failed")

    def test_no_case_fails_the_run(self):
        report = {"shacl_violations_in_graph": 0, "in_graph_mutant_violations": 1, "mutant": {"after_restore": 0},
                  "roundtrip_lost": 0, "roundtrip_added": 0, "determinism_hash_sorted": "h",
                  "determinism_hash_shuffled": "h", "compiled": [ROW],
               "fail_cases": [dict(ROW, status="passed"), {"status": "no-op"}]}
        self.assertTrue(lv.passed(report))
        report["fail_cases"].append({"status": "no case"})
        self.assertFalse(lv.passed(report))

    def test_a_manual_case_for_another_row_is_not_used(self):
        # Review 8, #20: a behavioural check in place of the vacuous one.
        rows = [row("lib__Copy", "lib__barcode", "sh:NodeKind", str(SH.BlankNode))]
        cons = self.constraints((lib("S-p"), SH.datatype, XSD.string))
        other = [{"target": "lib__Copy", "path": "lib__title", "param": "sh:NodeKind", "cypher": "RETURN 'x' AS focus"}]
        self.assertEqual(lv.plan_cases(rows, cons, set(), cfg(), other)[0]["cypher"], "")


class FailClosedReport(unittest.TestCase):
    """The report exists only after a run that passed every check."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp))
        self.path = os.path.join(self.tmp, "my report.json")
        for name in (self.path, self.path + ".failed"):
            with open(name, "w", encoding="utf-8") as f:
                f.write('{"passed": true, "manual_cases": [{"cypher": "old"}]}')

    def main(self, run_result=None, run_error=None, extra=()):
        args = ["--config", CONFIG, "--shapes", SHAPES, "--bolt", "bolt://127.0.0.1:1", "--import-dir", self.tmp,
                "--merged", MODULE, "--loadable", MODULE, "--inferred", MODULE, "--report", self.path, *extra, MODULE]
        patch = mock.patch.object(lv, "run", side_effect=run_error) if run_error else \
            mock.patch.object(lv, "run", return_value=run_result)
        with mock.patch.dict(os.environ, {"NEO4J_PASSWORD": "x"}), \
                mock.patch.dict(sys.modules, {"neo4j": mock.MagicMock()}), patch as run:
            code, out = run_main(lv.main, args)
        return code, out, run

    def report(self, passed):
        return {"shapes_import_rows": 1, "in_graph_shape_constraints": 1, "shacl_violations_in_graph": 0,
                "in_graph_mutant_violations": 1, "roundtrip_lost": 0, "roundtrip_added": 0, "nodes": 1,
                "relationships": 0, "determinism_hash_sorted": "h", "determinism_hash_shuffled": "h",
                "fail_cases": [{"status": "passed" if passed else "no case"}], "not_compiled": [], "passed": passed}

    def test_a_bad_flag_leaves_no_report(self):
        # Review 8, #20: a flag value that is really bad (a missing manual-cases file), with valid data.
        code, out, _ = self.main(extra=["--manual-cases", os.path.join(self.tmp, "missing.json")])
        self.assertEqual(code, 2, out)
        self.assertFalse(os.path.exists(self.path))
        self.assertFalse(os.path.exists(self.path + ".failed"))

    def test_a_driver_error_leaves_no_report(self):
        code, out, _ = self.main(run_error=OSError("connection refused"))
        self.assertEqual(code, 1, out)
        self.assertFalse(os.path.exists(self.path))

    def test_a_failed_check_writes_only_the_failed_file(self):
        code, out, _ = self.main(run_result=self.report(False))
        self.assertEqual(code, 1, out)
        self.assertFalse(os.path.exists(self.path))
        with open(self.path + ".failed", encoding="utf-8") as f:
            self.assertFalse(json.load(f)["passed"])

    def test_a_pass_writes_the_report_and_no_leftovers(self):
        code, out, run = self.main(run_result=self.report(True))
        self.assertEqual(code, 0, out)
        with open(self.path, encoding="utf-8") as f:
            self.assertTrue(json.load(f)["passed"])
        self.assertFalse(os.path.exists(self.path + ".failed"))
        self.assertEqual([n for n in os.listdir(self.tmp) if n.endswith(".tmp")], [])
        import inspect
        bound = inspect.signature(lv.run).bind(*run.call_args.args, **run.call_args.kwargs)
        self.assertEqual(list(bound.arguments.get("manual", ())), [])   # nothing carried from the old report
        self.assertIn(shlex.quote(self.path), out)

    def test_check_report_requires_passed_and_cases(self):
        man = {"input_fingerprint": "f", "shapes_fingerprint": "s"}
        rep = {"input_fingerprint": "f", "shapes_fingerprint": "s", "shacl_violations_in_graph": 0,
               "in_graph_mutant_violations": 1, "roundtrip_lost": 0, "roundtrip_added": 0,
               "determinism_hash_sorted": "h", "determinism_hash_shuffled": "h", "in_graph_shape_constraints": 1,
               "shapes_import_rows": 1, "mutant": {"violations": 1, "after_restore": 0},
               "compiled": [ROW], "fail_cases": [dict(ROW, status="passed")], "passed": True}
        self.assertEqual(build.check_report(man, rep), [])
        self.assertTrue(build.check_report(man, dict(rep, passed=False)))
        self.assertTrue(build.check_report(man, dict(rep, fail_cases=[])))
        self.assertTrue(build.check_report(man, dict(rep, fail_cases=[{"status": "no case"}])))
        # Review 8, #20: an old report's fields no longer satisfy the gate on their own.
        self.assertTrue(build.check_report(man, {"kinds_without_case": [], "manual_cases": [], "invalidated": False}))


class StrictSerialised(unittest.TestCase):
    def test_a_line_is_one_triple_and_nothing_else(self):
        a = f"<{LIB}a> <{RDF.type}> <{LIB}Work> .".encode()
        self.assertEqual(build.check_serialised(a + b"\n", b""), [])
        self.assertTrue(build.check_serialised(a + b" # note\n", b""))
        self.assertTrue(build.check_serialised(a + b"\n#\n", b""))


class GraphType(unittest.TestCase):
    def test_library_graph_type(self):
        text, left = build.graph_type(cfg(), Graph().parse(SHAPES, format="turtle"), Graph().parse(MODULE))
        self.assertTrue(text.startswith("CYPHER 25\nALTER CURRENT GRAPH TYPE SET {"))
        self.assertIn("(:`lib__Person` => {`lib__name` :: STRING NOT NULL})", text)
        self.assertIn("(:`lib__Copy`)-[:`lib__copyOf` =>]->(:`lib__Work`)", text)
        self.assertTrue(any("sh:pattern" in line for line in left))
        self.assertTrue(any("non-predicate path" in line for line in left))


ROW = {"target": "lib__Copy", "path": "lib__barcode", "param": "sh:minCount", "value": 1}


def earned_report(**change):
    """A projection report that earns its pass (build.report_earned is empty), changed by **change."""
    return dict({"shacl_violations_in_graph": 0, "in_graph_mutant_violations": 1, "roundtrip_lost": 0,
                 "roundtrip_added": 0, "determinism_hash_sorted": "h", "determinism_hash_shuffled": "h",
                 "in_graph_shape_constraints": 1, "shapes_import_rows": 1, "compiled": [ROW],
                 "fail_cases": [dict(ROW, status="passed")], "mutant": {"violations": 1, "after_restore": 0},
                 "passed": True}, **change)


def passing_report(case, **change):
    """A temporary projection report that earns its pass, with hash h, changed by **change."""
    rep = earned_report(**change)
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump(rep, f)
    f.close()
    case.addCleanup(os.remove, f.name)
    return f.name


class CopyGraph(unittest.TestCase):
    def env(self, text):
        f = tempfile.NamedTemporaryFile("w", suffix=".env", delete=False)
        f.write(text)
        f.close()
        self.addCleanup(os.remove, f.name)
        return f.name

    def test_env_file_and_no_password_printed(self):
        path = self.env("# Aura\nNEO4J_URI=neo4j+s://x.databases.neo4j.io\nNEO4J_USERNAME=neo4j\n"
                        "NEO4J_PASSWORD='s3cret'\nNEO4J_DATABASE=neo4j\n")
        values = cg.read_env_file(path)
        self.assertEqual(values["NEO4J_PASSWORD"], "s3cret")
        self.assertNotIn("s3cret", cg.describe_target(values))

    def test_missing_keys_stop_without_printing_secrets(self):
        path = self.env("NEO4J_URI=bolt://h\nNEO4J_PASSWORD=s3cret\n")
        with mock.patch.dict(os.environ, {"NEO4J_PASSWORD": "local"}):
            code, out = run_main(cg.main, ["--source", "bolt://127.0.0.1:1", "--target-env", path,
                                           "--report", passing_report(self)])
        self.assertEqual(code, 2)
        self.assertIn("NEO4J_USERNAME", out)
        self.assertNotIn("s3cret", out)

    def test_refuses_a_target_that_holds_nodes(self):
        path = self.env("NEO4J_URI=bolt://h\nNEO4J_USERNAME=neo4j\nNEO4J_PASSWORD=s3cret\n")
        fake = mock.MagicMock()
        session = fake.GraphDatabase.driver.return_value.__enter__.return_value.session.return_value.__enter__.return_value
        with mock.patch.dict(os.environ, {"NEO4J_PASSWORD": "local"}), mock.patch.dict(sys.modules, {"neo4j": fake}), \
                mock.patch.object(cg, "graph_hash", return_value="h"), \
                mock.patch.object(cg, "database_identity", side_effect=["source-db", "target-db"], create=True), \
                mock.patch.object(cg, "count_nodes", return_value=5), mock.patch.object(cg, "copy") as copy:
            code, out = run_main(cg.main, ["--source", "bolt://127.0.0.1:1", "--target-env", path,
                                           "--report", passing_report(self)])
        self.assertEqual(code, 1, out)
        self.assertIn("holds 5 nodes", out)
        self.assertNotIn("s3cret", out)
        copy.assert_not_called()
        self.assertIsNotNone(session)


class TripleStore(unittest.TestCase):
    def test_graph_names(self):
        g = Graph()
        g.add((lib("onto"), RDF.type, OWL.Ontology))
        self.assertEqual(ts.graph_iri(g, "x/a.ttl", "urn:b:"), LIB + "onto")
        g.add((lib("onto"), OWL.versionIRI, lib("onto/1.0.0")))
        self.assertEqual(ts.graph_iri(g, "x/a.ttl", "urn:b:"), LIB + "onto/1.0.0")
        self.assertEqual(ts.graph_iri(Graph(), "x/a.ttl", "urn:b:"), "urn:b:a")
        self.assertFalse(ts.DEFAULT_BASE.startswith("urn:x-"))

    def test_counts_and_comparison(self):
        a, b = Graph(), Graph()
        a.add((lib("s"), lib("p"), Literal("1")))
        b.add((lib("s"), lib("p"), Literal("1")))           # the same triple in two files counts once
        b.add((lib("s"), lib("q"), lib("o")))
        counts = ts.predicate_counts([a, b])
        self.assertEqual(counts, {LIB + "p": 1, LIB + "q": 1})
        self.assertEqual(ts.compare("x", counts, counts), [])
        self.assertEqual(len(ts.compare("x", counts, {LIB + "p": 2})), 2)

    def test_queries_and_put_url(self):
        self.assertIn("GRAPH <urn:g>", ts.graph_count_query("urn:g"))
        self.assertIn("FILTER(?g IN (<urn:a>, <urn:b>))", ts.predicate_count_query(["urn:a", "urn:b"]))
        store = ts.Store("http://127.0.0.1:1/ds", "http://127.0.0.1:1/ds/query", "u", "p")
        with mock.patch.object(store, "_request", return_value=(201, b"")) as req:
            store.put_graph("urn:a b", b"")
        self.assertEqual(req.call_args[0][:2], ("http://127.0.0.1:1/ds?graph=urn%3Aa+b", "PUT"))

    def test_two_files_on_one_graph_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            nt = os.path.join(tmp, "inferred.nt")
            open(nt, "w").close()
            code, out = run_main(ts.main, ["--gsp", "http://h/ds", "--query", "http://h/q", "--inferred", nt,
                                           "--report", os.path.join(tmp, "r.json"), MODULE, MODULE])
        self.assertEqual(code, 2, out)
        self.assertIn("one graph IRI", out)

    def test_password_is_never_printed(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.path.join(tmp, "store.env")
            with open(env, "w") as f:
                f.write("SPARQL_GSP=http://127.0.0.1:1/ds\nSPARQL_QUERY=http://127.0.0.1:1/q\n"
                        "SPARQL_USER=u\nSPARQL_PASSWORD=s3cret\n")
            nt = os.path.join(tmp, "inferred.nt")
            open(nt, "w").close()
            code, out = run_main(ts.main, ["--env", env, "--inferred", nt, "--report", os.path.join(tmp, "r.json"), MODULE])
        self.assertEqual(code, 1)
        self.assertNotIn("s3cret", out)


class DockerPins(unittest.TestCase):
    """docker/compose.yaml and docker/fuseki/Dockerfile use the pins the references give."""

    def read(self, *parts):
        with open(os.path.join(HERE, "..", *parts), encoding="utf-8") as f:
            return f.read()

    def test_neo4j_and_n10s_pins_match_running_md(self):
        import re
        running, compose = self.read("references", "running.md"), self.read("docker", "compose.yaml")
        digest = re.search(r"it was `(sha256:[0-9a-f]{64})`", running).group(1)
        self.assertIn(f"neo4j:2025.06.2@{digest}", compose)
        row = next(line for line in running.splitlines() if line.startswith("   | n10s 2025.06.1 |"))
        url, sha = re.findall(r"(https://\S+\.jar)", row)[0], re.findall(r"`([0-9a-f]{64})`", row)[0]
        self.assertIn(f"N10S_URL: {url}", compose)
        self.assertIn(f"N10S_SHA256: {sha}", compose)

    def test_fuseki_pin_matches_add_on_j(self):
        import re
        sha = re.search(r"SHA-256 `([0-9a-f]{64})`", self.read("references", "add-ons.md")).group(1)
        self.assertIn(f"PACKAGE_SHA256={sha}", self.read("docker", "fuseki", "Dockerfile"))

    def test_every_download_and_base_image_is_pinned(self):
        # Review 8, #12: the JDK layer, the server jar and the manual Neo4j recipe are pinned too.
        docker = self.read("docker", "fuseki", "Dockerfile")
        self.assertRegex(docker, r"TEMURIN_IMAGE=eclipse-temurin:21-alpine@sha256:[0-9a-f]{64}")
        self.assertRegex(docker, r"FUSEKI_JAR_SHA256=[0-9a-f]{64}")
        self.assertEqual(docker.count("sha256sum -c"), 2)
        self.assertNotIn("download.sh", docker)
        self.assertTrue(all("@sha256:" in line for line in docker.splitlines() if line.startswith("FROM ") and "$" not in line))
        self.assertIn("sha256sum -c", self.read("docker", "compose.yaml"))
        running = self.read("references", "running.md")
        self.assertRegex(running, r"neo4j:2025\.06\.2@sha256:[0-9a-f]{64}\n")

    def test_ports_are_local_and_no_password_is_written(self):
        compose = self.read("docker", "compose.yaml")
        ports = [line.strip() for line in compose.splitlines() if line.strip().startswith('- "') and ":" in line]
        self.assertTrue(ports and all(p.startswith('- "127.0.0.1:') for p in ports))
        self.assertIn("NEO4J_AUTH: neo4j/${NEO4J_PASSWORD:-}", compose)


GOOD_REPORT = {"shacl_violations_in_graph": 0, "in_graph_mutant_violations": 1,
               "mutant": {"focus": "u", "removed": "k", "violations": 1, "after_restore": 0},
               "roundtrip_lost": 0, "roundtrip_added": 0, "determinism_hash_sorted": "h",
               "determinism_hash_shuffled": "h", "compiled": [ROW],
               "fail_cases": [dict(ROW, status="passed"), {"status": "no-op"}]}
# One failing value per clause of the gate: (name, change).
GATE_BREAKS = [
    ("a failed case", {"fail_cases": [{"status": "failed"}]}),
    ("a row without a case", {"fail_cases": [{"status": "no case"}]}),
    ("a violation in the graph", {"shacl_violations_in_graph": 1}),
    ("a mutant nothing caught", {"in_graph_mutant_violations": 0}),
    ("a mutant not restored", {"mutant": {"focus": "u", "removed": "k", "violations": 1, "after_restore": 1}}),
    ("a lost triple", {"roundtrip_lost": 1}),
    ("an added triple", {"roundtrip_added": 1}),
    ("two hashes", {"determinism_hash_shuffled": "other"}),
]


class GateClauses(unittest.TestCase):
    """Review 8, #8 and #2: every clause of passed() and of check_report is seen to fail on its own."""

    def test_passed_fails_on_each_clause(self):
        self.assertTrue(lv.passed(dict(GOOD_REPORT)))
        for name, change in GATE_BREAKS:
            with self.subTest(name):
                self.assertFalse(lv.passed(dict(GOOD_REPORT, **change)))

    def test_check_report_fails_on_each_field(self):
        man = {"input_fingerprint": "f", "shapes_fingerprint": "s"}
        good = dict(GOOD_REPORT, input_fingerprint="f", shapes_fingerprint="s", in_graph_shape_constraints=3,
                    shapes_import_rows=3, passed=True)
        self.assertEqual(build.check_report(man, good), [])
        breaks = GATE_BREAKS + [
            ("a stale input fingerprint", {"input_fingerprint": "old"}),
            ("a stale shapes fingerprint", {"shapes_fingerprint": "old"}),
            ("shape counts that differ", {"shapes_import_rows": 2}),
            ("no shape count", {"in_graph_shape_constraints": 0, "shapes_import_rows": 0}),
            ("not passed", {"passed": False}),
            ("no fail cases", {"fail_cases": []}),
            ("no mutant", {"mutant": None}),
            ("a compiled row without a case", {"compiled": [{"target": "T", "path": "p", "param": "sh:minCount", "value": 1}]}),
            ("no compiled rows", {"compiled": []}),
            ("no compiled key", {"compiled": None}),
        ]
        for name, change in breaks:
            with self.subTest(name):
                self.assertTrue(build.check_report(man, dict(good, **change)))


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def data(self):
        return list(self.rows)

    def single(self):
        return self.rows[0] if self.rows else None

    def value(self):
        return [next(iter(r.values())) for r in self.rows]

    def consume(self):
        return None


class FakeEngine:
    """A session that answers run()'s queries from canned rows, keyed by the query text."""

    def __init__(self, listed, export_rows, fire=True):
        self.listed, self.export_rows, self.fire = listed, export_rows, fire
        self.rollbacks, self.removed = 0, False
        self.paths = sorted({LIB + local for local in ("notInTheShape",)} |
                            {str(lv.iri_of(r["path"], cfg())) for r in listed if r["path"]})

    def session(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def begin_transaction(self):
        engine = self

        class Tx:
            focus = None

            def run(self, query, **_):
                if query == lv.VALIDATE:
                    if not engine.fire or not self.focus:
                        return FakeResult([])
                    return FakeResult([{"focusNode": self.focus, "propertyShape": str(SH) + comp, "resultPath": p,
                                        "resultMessage": ""}
                                       for comp in sorted(set().union(*lv.EXPECTED.values())) for p in engine.paths])
                import re
                self.focus = re.search(r'uri: "([^"]+)"', query).group(1)
                return FakeResult([{"focus": self.focus}])

            def rollback(self):
                engine.rollbacks += 1
        return Tx()

    def run(self, query, **_):
        if query == lv.VALIDATE:
            return FakeResult([{"focusNode": "u", "propertyShape": str(SH) + "CountConstraintComponent",
                                "resultPath": "", "resultMessage": ""}] if self.removed else [])
        if "RETURN n.uri AS uri, labels(n)" in query:
            return FakeResult([{"uri": "u", "labels": ["Resource"], "props": {"uri": "u"}}])
        if "RETURN n.uri AS uri" in query:
            return FakeResult([{"uri": "u", "value": "v"}])
        if " REMOVE n." in query:
            self.removed = True
            return FakeResult([])
        if "SET n.`" in query and "$value" in query:
            self.removed = False
            return FakeResult([])
        if "count(n) AS n" in query or "count(*) AS n" in query and "SHOW CONSTRAINTS" in query:
            return FakeResult([{"n": 0}])
        if "listShapes() YIELD target" in query:
            return FakeResult([{"n": len(self.listed)}])
        if "listShapes()" in query:
            return FakeResult([{"target": r["target"], "propertyOrRelationshipPath": r["path"], "param": r["param"],
                                "value": r["value"]} for r in self.listed])
        if "shacl.import" in query:
            return FakeResult([{"target": "x"}] * len(self.listed))
        if "rdf.import" in query or "onto.import" in query:
            return FakeResult([{"terminationStatus": "OK"}])
        if query.startswith("CALL n10s.rdf.export"):
            return FakeResult(self.export_rows)
        if "RETURN n.uri AS uri, labels(n)" in query:
            return FakeResult([{"uri": "u", "labels": ["Resource"], "props": {"uri": "u"}}])
        if "type(r) AS t" in query:
            return FakeResult([])
        return FakeResult([])


class RunWiring(unittest.TestCase):
    """Review 8, #7: run() itself, with a fake engine, not a patched-out run()."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp))
        loadable, self.inferred = os.path.join(self.tmp, "l.nt"), os.path.join(self.tmp, "i.nt")
        with open(loadable, "w", encoding="utf-8") as f:
            f.write(build.sorted_nt(build.parse([MODULE])))
        open(self.inferred, "w").close()
        self.loadable = loadable
        safe, _ = igs.subset(Graph().parse(SHAPES))
        cons = [c for c in lv.file_constraints(safe, cfg()) if not c["target"].startswith("(")]
        rows, seen = [], set()
        for c in cons:
            r = row(c["target"], c["path"], c["term"], c["value"])
            if lv.row_key(r) not in seen:
                seen.add(lv.row_key(r))
                rows.append(r)
        self.dropped = rows.pop()                      # one constraint n10s "did not compile"
        self.rows = rows
        g = Graph().parse(data=open(loadable).read(), format="nt")
        self.export = [{"subject": str(s), "predicate": str(p), "object": str(o), "isLiteral": isinstance(o, Literal),
                        "literalType": str(o.datatype) if isinstance(o, Literal) and o.datatype else None,
                        "literalLang": o.language if isinstance(o, Literal) else None} for s, p, o in g]

    def run_with(self, engine):
        return lv.run(engine, cfg(), [MODULE], [SHAPES], self.tmp, MODULE, self.loadable, self.inferred)

    def test_run_reads_the_engine_and_tests_every_row(self):
        engine = FakeEngine(self.rows, self.export)
        report = self.run_with(engine)
        self.assertEqual(report["compiled"], self.rows)
        self.assertIn((self.dropped["target"], self.dropped["path"], self.dropped["param"]),
                      [(c["target"], c["path"], c["term"]) for c in report["not_compiled"]])
        self.assertEqual(len(report["fail_cases"]), len(self.rows))
        tested = [c for c in report["fail_cases"] if c["status"] in ("passed", "failed")]
        self.assertEqual(engine.rollbacks, len(tested))
        self.assertEqual((report["roundtrip_lost"], report["roundtrip_added"]), (0, 0))
        self.assertTrue(report["passed"], [c for c in report["fail_cases"] if c["status"] != "passed"][:3])

    def test_run_fails_when_a_case_does_not_fire(self):
        report = self.run_with(FakeEngine(self.rows, self.export, fire=False))
        self.assertFalse(report["passed"])


class RoundEight(unittest.TestCase):
    """Full review 8 of 3bf17ed..8abb44b: one test per behaviour change; each fails on 8648028."""

    def tmp(self):
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(d))
        return d

    # 1: printed values are quoted, and the next step has no redirection token
    def test_not_compiled_line_is_one_quoted_line(self):
        d = self.tmp()
        path = os.path.join(d, "r.json")
        bad = {"target": "lib__Copy", "path": None, "term": "sh:sparql", "file_term": "sh:sparql",
               "raw": "x\n$(touch pwned)", "shape": "lib:S"}
        rep = dict(GOOD_REPORT, shapes_import_rows=1, in_graph_shape_constraints=1, nodes=1, relationships=0,
                   not_compiled=[bad], passed=True)
        args = ["--config", CONFIG, "--shapes", SHAPES, "--bolt", "bolt://x", "--import-dir", d, "--merged", MODULE,
                "--loadable", MODULE, "--inferred", MODULE, "--report", path, MODULE]
        with mock.patch.dict(os.environ, {"NEO4J_PASSWORD": "x"}), \
                mock.patch.dict(sys.modules, {"neo4j": mock.MagicMock()}), mock.patch.object(lv, "run", return_value=rep):
            code, out = run_main(lv.main, args)
        self.assertEqual(code, 0, out)
        line = [x for x in out.splitlines() if x.startswith("NOT COMPILED")]
        self.assertEqual(len(line), 1)
        self.assertNotIn("\n$(touch", out)
        payload = line[0].split(": ", 1)[1]
        self.assertEqual(json.loads(shlex.split(payload)[0])["raw"], "x\n$(touch pwned)")
        self.assertNotIn("<", lv.check_report_command(path))
        self.assertNotIn(">", lv.check_report_command(path))

    def test_in_graph_shapes_quotes_what_it_prints(self):
        d = self.tmp()
        out_path = os.path.join(d, "a b;$(x).ttl")
        code, out = run_main(igs.main, ["--output", out_path, SHAPES])
        self.assertEqual(code, 0, out)
        self.assertIn("wrote " + shlex.quote(out_path), out)
        for line in out.splitlines():
            if line.startswith("PREDICTION"):
                self.assertEqual(len(shlex.split(line.split(": ", 1)[1])), 3)

    def test_copy_target_is_quoted(self):
        self.assertIn("'bolt://h;rm -rf x'", cg.describe_target(
            {"NEO4J_URI": "bolt://h;rm -rf x", "NEO4J_USERNAME": "n", "NEO4J_PASSWORD": "p"}))

    def test_graph_type_left_out_lines_cannot_break_the_comment(self):
        # Review 9, #1: the statement goes to a file; each comment is one quoted word on one line.
        out_path = os.path.join(self.tmp(), "gt.cypher")
        bad = "a\n`MATCH (n) DETACH DELETE n` $(touch x) <y>"
        with mock.patch.object(build, "graph_type", return_value=("CYPHER 25", [bad])):
            code, out = run_main(build.main, ["graph-type", "--config", CONFIG, "--shapes", SHAPES,
                                              "--output", out_path, MODULE])
        self.assertEqual(code, 0, out)
        self.assertEqual(len(out.splitlines()), 1)                 # only the quoted "wrote" line
        with open(out_path) as f:
            lines = f.read().splitlines()
        self.assertEqual(lines[0], "CYPHER 25")
        self.assertEqual(len(lines), 2)
        word = lines[1][len("// "):]
        self.assertEqual(len(shlex.split(word)), 1)
        self.assertIn("$(touch x)", shlex.split(word)[0])

    # 9: every exit 2 that names a report path deletes it
    def test_report_named_with_equals_or_last_is_deleted(self):
        d = self.tmp()
        for argv in (lambda p: ["--report=" + p], lambda p: ["--config", "nope", "--report", p]):
            path = os.path.join(d, "r.json")
            with open(path, "w") as f:
                f.write('{"passed": true}')
            code, _ = run_main(lv.main, argv(path))
            self.assertEqual(code, 2)
            self.assertFalse(os.path.exists(path))
        self.assertEqual(build.named_paths(["--report=a", "--x", "--report", "b"], "--report"), ["a", "b"])

    # 11: the store report is deleted first and written only on a pass
    def store_main(self, d, put=None, counts=None, projection=None):
        nt = os.path.join(d, "inferred.nt")
        open(nt, "w").close()
        path = os.path.join(d, "ts.json")
        with open(path, "w") as f:
            f.write('{"passed": true}')
        args = ["--gsp", "http://127.0.0.1:1/ds", "--query", "http://127.0.0.1:1/q", "--inferred", nt,
                "--report", path, MODULE]
        if projection:
            args[0:0] = ["--projection-report", projection]
        graph = ts.graph_iri(Graph().parse(MODULE), MODULE, ts.DEFAULT_BASE)
        n = len(Graph().parse(MODULE))

        def select(store, sparql, default_graphs=()):
            if "GROUP BY ?p" in sparql:
                return [{"p": {"value": p}, "n": {"value": str(c)}}
                        for p, c in (counts or ts.predicate_counts([Graph().parse(MODULE)])).items()]
            return [{"n": {"value": str(n if graph in sparql else 0)}}]
        with mock.patch.object(ts.Store, "put_graph", side_effect=put or (lambda *a: 201)), \
                mock.patch.object(ts.Store, "select", select):
            code, out = run_main(ts.main, args)
        return code, out, path

    def test_store_request_failure_leaves_no_report(self):
        import urllib.error
        code, out, path = self.store_main(self.tmp(), put=urllib.error.URLError("refused"))
        self.assertEqual(code, 1, out)
        self.assertFalse(os.path.exists(path))

    def test_store_count_mismatch_writes_only_the_failed_file(self):
        code, out, path = self.store_main(self.tmp(), counts={LIB + "x": 1})
        self.assertEqual(code, 1, out)
        self.assertFalse(os.path.exists(path))
        self.assertTrue(os.path.exists(path + ".failed"))

    def test_store_pass_writes_the_report(self):
        code, out, path = self.store_main(self.tmp())
        self.assertEqual(code, 0, out)
        with open(path) as f:
            self.assertTrue(json.load(f)["passed"])

    # 3: copy only a verified graph, and never touch the target otherwise
    def copy_main(self, report_args, source_hash="h", present=5):
        env = tempfile.NamedTemporaryFile("w", suffix=".env", delete=False)
        env.write("NEO4J_URI=bolt://h\nNEO4J_USERNAME=neo4j\nNEO4J_PASSWORD=s3cret\n")
        env.close()
        self.addCleanup(os.remove, env.name)
        with mock.patch.dict(os.environ, {"NEO4J_PASSWORD": "local"}), \
                mock.patch.dict(sys.modules, {"neo4j": mock.MagicMock()}), \
                mock.patch.object(cg, "graph_hash", return_value=source_hash), \
                mock.patch.object(cg, "database_identity", side_effect=["source-db", "target-db"], create=True), \
                mock.patch.object(cg, "count_nodes", return_value=present), \
                mock.patch.object(cg, "empty_target") as empty, mock.patch.object(cg, "copy") as copy:
            code, out = run_main(cg.main, ["--source", "bolt://x", "--target-env", env.name, "--replace", *report_args])
        return code, out, empty, copy

    def test_copy_needs_a_passing_report(self):
        for args in ([], ["--report", passing_report(self, passed=False)],
                     ["--report", passing_report(self, determinism_hash_shuffled="other")]):
            code, out, empty, copy = self.copy_main(args)
            self.assertEqual(code, 2, out)
            empty.assert_not_called()
            copy.assert_not_called()

    def test_copy_of_an_unverified_source_deletes_nothing(self):
        code, out, empty, copy = self.copy_main(["--report", passing_report(self)], source_hash="changed")
        self.assertEqual(code, 1, out)
        empty.assert_not_called()
        copy.assert_not_called()

    def test_copy_of_the_verified_source_runs(self):
        code, out, empty, copy = self.copy_main(["--report", passing_report(self)])
        self.assertEqual(code, 0, out)
        empty.assert_called_once()
        copy.assert_called_once()

    # 26: a date and the string of its text do not hash alike
    def test_typed_values_hash_with_their_type(self):
        import datetime
        nodes = lambda v: [{"uri": "u", "labels": ["Resource"], "props": {"d": v}}]
        self.assertNotEqual(lv.graph_hash(nodes(datetime.date(2020, 1, 1)), []), lv.graph_hash(nodes("2020-01-01"), []))

    # 27: qualified cardinality is reported as not compiled
    def test_qualified_cardinality_is_reported(self):
        g = shape_graph((lib("S-p"), SH.qualifiedMinCount, Literal(1)), (lib("S-p"), SH.qualifiedMaxCount, Literal(2)),
                        (lib("S-p"), SH.qualifiedValueShapesDisjoint, Literal(True)))
        terms = {c["term"] for c in lv.not_compiled(lv.file_constraints(g, cfg()), [])}
        self.assertTrue({"sh:qualifiedMinCount", "sh:qualifiedMaxCount", "sh:qualifiedValueShapesDisjoint"} <= terms)

    # 29: a minimum is tested one value short
    def test_minimum_cases_are_near_misses(self):
        lit = lv.file_constraints(shape_graph((lib("S-p"), SH.datatype, XSD.integer)), cfg())
        cypher = lv.case_for(row("lib__Copy", "lib__barcode", "sh:minCount", 3), lit, set(), cfg())[2]
        self.assertIn("SET n.`lib__barcode` = [1, 2]", cypher)
        rel = lv.file_constraints(shape_graph((lib("S-p"), SH["class"], lib("Work"))), cfg())
        cypher = lv.case_for(row("lib__Copy", "lib__barcode", "sh:minCount", 3), rel, set(), cfg())[2]
        self.assertEqual(cypher.count("CREATE (n)-[:`lib__barcode`]->"), 2)
        strs = lv.file_constraints(shape_graph((lib("S-p"), SH.datatype, XSD.string)), cfg())
        self.assertIn('"xxxx"', lv.case_for(row("lib__Copy", "lib__barcode", "sh:minLength", 5), strs, set(), cfg())[2])

    # 31: the clean-up line matches a compose start
    def test_compose_project_cleanup(self):
        self.assertEqual(lv.remove_command({"--compose-project": "p q"}),
                         "docker compose -p 'p q' --profile neo4j --profile fuseki down -v")

    # 15 and the two Aura findings: GRAPH TYPE
    def test_graph_type_omits_empty_node_types_and_keeps_endpoints(self):
        g = shape_graph()
        g.remove((lib("S-p"), SH.path, lib("barcode")))
        g.add((lib("S-p"), SH.path, lib("copyOf")))
        g.add((lib("S-p"), SH["class"], lib("Work")))
        text, left = build.graph_type(cfg(), g, Graph())
        self.assertNotIn("=>)", text)
        self.assertIn("(:`lib__Copy`)-[:`lib__copyOf` =>]->(:`lib__Work`)", text)
        self.assertIn("lib__Copy: no typed property, so no node element type", left)

    def test_graph_type_follows_the_loads_multivalued_list(self):
        g = shape_graph((lib("S-p"), SH.datatype, XSD.string), (lib("S-p"), SH.maxCount, Literal(1)))
        data = Graph()
        data.add((lib("c1"), lib("barcode"), Literal("a")))
        data.add((lib("c1"), lib("barcode"), Literal("b")))       # two values: the load stores a list
        self.assertIn("`lib__barcode` :: LIST<STRING NOT NULL>", build.graph_type(cfg(), g, data)[0])
        single = Graph()
        single.add((lib("c1"), lib("barcode"), Literal("a")))
        self.assertIn("`lib__barcode` :: STRING", build.graph_type(cfg(), g, single)[0])

    def test_graph_type_lists_a_second_mapping_and_terms_after_an_unknown_datatype(self):
        g = shape_graph((lib("S-p"), SH.datatype, XSD.string), (lib("S"), SH.property, lib("S-q")),
                        (lib("S-q"), SH.path, lib("barcode")), (lib("S-q"), SH.datatype, XSD.integer),
                        (lib("S"), SH.property, lib("S-r")), (lib("S-r"), SH.path, lib("note")),
                        (lib("S-r"), SH.datatype, XSD.gYear), (lib("S-r"), SH.pattern, Literal("^1")),
                        (lib("S"), SH.property, lib("S-s")), (lib("S-s"), SH.path, lib("copyOf")),
                        (lib("S-s"), SH.datatype, XSD.string), (lib("S-s"), SH["class"], lib("Work")))
        text, left = build.graph_type(cfg(), g, Graph())
        self.assertTrue(any("a second property shape maps it" in x for x in left), left)
        self.assertIn("lib__Copy.lib__note: sh:pattern (no GRAPH TYPE form)", left)
        self.assertTrue(any("beside sh:datatype" in x for x in left), left)
        self.assertNotIn("lib__copyOf =>", text)


class PrintedValues(unittest.TestCase):
    """Review 9 and quick check 10: every value any script prints goes through shell.q or
    shell.comment. This reads the syntax tree of every script in scripts/ and fails on a call to
    print, or to a write or print attribute aimed at stdout or stderr, any of whose positional or
    keyword arguments is not a string or number literal, a q() or comment() call, an f-string or a +
    of those, or a call to one of the helpers below whose every return value obeys the same rule.
    print's file= may only name sys.stdout or sys.stderr."""

    # Helpers that build a printed line; each one's return values are checked by the same rule.
    HELPERS = ("describe_target", "remove_command", "check_report_command")

    @staticmethod
    def safe(node, helpers=()):
        import ast
        if isinstance(node, ast.Constant):
            return isinstance(node.value, (str, int, float)) and not isinstance(node.value, bool)
        if isinstance(node, ast.JoinedStr):
            return all(isinstance(v, ast.Constant) or (v.format_spec is None and PrintedValues.safe(v.value, helpers))
                       for v in node.values)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return PrintedValues.safe(node.left, helpers) and PrintedValues.safe(node.right, helpers)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            return node.func.id in ("q", "comment") + tuple(helpers)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and \
                isinstance(node.func.value, ast.Name) and node.func.value.id in ("shell", "lv", "build", "cg"):
            return node.func.attr in ("q", "comment") + tuple(helpers)
        return False

    @staticmethod
    def std_stream(node):
        import ast
        return isinstance(node, ast.Attribute) and node.attr in ("stdout", "stderr") and \
            isinstance(node.value, ast.Name) and node.value.id == "sys"

    @classmethod
    def unsafe_prints(cls, source, name="<source>", helpers=HELPERS):
        import ast
        bad = []
        for n in ast.walk(ast.parse(source)):
            if not isinstance(n, ast.Call):
                continue
            f = n.func
            is_print = isinstance(f, ast.Name) and f.id == "print"
            is_stream = isinstance(f, ast.Attribute) and f.attr in ("write", "print") and cls.std_stream(f.value)
            if not (is_print or is_stream):
                continue
            for a in n.args:
                if not cls.safe(a, helpers):
                    bad.append(f"{name}:{n.lineno}: {ast.unparse(a)[:90]}")
            for k in n.keywords:
                if is_print and k.arg == "file" and cls.std_stream(k.value):
                    continue
                if not cls.safe(k.value, helpers):
                    bad.append(f"{name}:{n.lineno}: {k.arg}={ast.unparse(k.value)[:80]}")
        return bad

    def scripts(self):
        import glob
        for path in sorted(glob.glob(os.path.join(HERE, "*.py"))):
            if not os.path.basename(path).startswith("test_"):
                with open(path, encoding="utf-8") as f:
                    yield os.path.basename(path), f.read()

    def test_every_printed_value_goes_through_the_helper(self):
        bad = []
        for name, source in self.scripts():
            bad += self.unsafe_prints(source, name)
        self.assertEqual(bad, [])

    def test_the_helpers_build_only_quoted_text(self):
        import ast
        found = set()
        for name, source in self.scripts():
            for n in ast.walk(ast.parse(source)):
                if isinstance(n, ast.FunctionDef) and n.name in self.HELPERS:
                    found.add(n.name)
                    returns = [r.value for r in ast.walk(n) if isinstance(r, ast.Return)]
                    self.assertTrue(returns, n.name)
                    for r in returns:
                        self.assertTrue(self.safe(r, ()), f"{name}: {n.name} returns {ast.unparse(r)[:90]}")
        self.assertEqual(found, set(self.HELPERS))

    def test_the_checker_flags_the_known_escapes(self):
        escapes = ['print(MSG)', 'print("ok", end=user)', 'print(f"{user.count(user)}")', 'print(f"{len(user)}")',
                   'sys.stderr.write(user)', 'sys.stdout.print(user)', 'print("x", file=user_file)',
                   'print(f"{user:>{width}}")', 'print(USAGE)', 'print(RULE.format(script=x))']
        for src in escapes:
            with self.subTest(src):
                self.assertTrue(self.unsafe_prints(src), src)
        for src in ['print("ok")', 'print(q(user))', 'print(f"a {q(user)}", file=sys.stderr)', 'print(q(USAGE))',
                    'print(comment(x) + "\\n")']:
            with self.subTest(src):
                self.assertEqual(self.unsafe_prints(src), [], src)

    def test_the_quoting_helpers_quote(self):
        import shell
        hostile = "a b;$(touch x)`y`<z>\n"
        self.assertEqual(shell.q("a b"), "'a b'")
        self.assertEqual(len(shlex.split(shell.comment("x\n`y` $(z) <w>")[3:])), 1)
        self.assertEqual(shlex.split(lv.remove_command({"--compose-project": hostile})),
                         ["docker", "compose", "-p", hostile, "--profile", "neo4j", "--profile", "fuseki", "down", "-v"])
        self.assertEqual(shlex.split(lv.remove_command({"--container": hostile})), ["docker", "rm", "-f", "-v", hostile])
        self.assertEqual(shlex.split(lv.check_report_command(hostile))[-1], hostile)
        described = cg.describe_target({"NEO4J_URI": hostile, "NEO4J_USERNAME": hostile, "NEO4J_DATABASE": hostile,
                                        "NEO4J_PASSWORD": "s3cret"})
        self.assertEqual(shlex.split(described), [hostile, "as", hostile, "(database", hostile + ")"])
        self.assertNotIn("s3cret", described)

class RoundNine(unittest.TestCase):
    """Review 9 of 8648028 and cb6c005: one test per behaviour change; each fails on cb6c005."""

    def tmp(self):
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(d))
        return d

    # 3: a report with no compiled key fails check-report
    def test_missing_compiled_fails(self):
        rep = earned_report()
        self.assertEqual(build.report_earned(rep), [])
        del rep["compiled"]
        self.assertIn("report lists no compiled rows (pipeline.md, rule 13)", build.report_earned(rep))

    # 4: copy and the store recompute the gate rather than trust passed
    def test_copy_refuses_a_passed_report_with_a_failed_case(self):
        report = passing_report(self, fail_cases=[dict(ROW, status="failed")])
        code, out, empty, copy = RoundEight.copy_main(self, ["--report", report])
        self.assertEqual(code, 2, out)
        self.assertIn("not a verified projection report", out)
        empty.assert_not_called()
        copy.assert_not_called()

    def test_store_refuses_a_passed_report_without_compiled_rows(self):
        export = ts.predicate_counts([Graph().parse(MODULE)])
        code, out, path = RoundEight.store_main(self, self.tmp(), projection=passing_report(
            self, compiled=[], export_predicate_counts=export))
        self.assertEqual(code, 2, out)
        self.assertIn("lists no compiled rows", out)

    def test_copy_refuses_old_flags(self):
        code, out, _, _ = RoundEight.copy_main(self, ["--report", passing_report(self), "--expect-hash", "h"])
        self.assertEqual(code, 2, out)
        self.assertIn("--expect-hash", out)

    # 5: a wider compiled ignore-list beside a stricter file list fails, whichever matches
    def test_a_stricter_closed_shape_with_no_equal_row_fails_the_case(self):
        g = shape_graph((lib("S"), SH.closed, Literal(True)))
        wide, strict = BNode(), BNode()
        Collection(g, wide, [RDF.type, lib("extra")])
        g.add((lib("S"), SH.ignoredProperties, wide))
        g.add((lib("T"), RDF.type, SH.NodeShape))
        g.add((lib("T"), SH.targetClass, lib("Copy")))
        g.add((lib("T"), SH.closed, Literal(True)))
        Collection(g, strict, [RDF.type])
        g.add((lib("T"), SH.ignoredProperties, strict))
        cons = lv.file_constraints(g, cfg())
        rows = [row("lib__Copy", None, "sh:ignoredProperties", ["lib__extra", "rdf__type"])]
        self.assertIn("mismatch", lv.plan_cases(rows, cons, set(), cfg())[0])
        both = rows + [row("lib__Copy", None, "sh:ignoredProperties", ["rdf__type"])]
        self.assertTrue(all("mismatch" not in c for c in lv.plan_cases(both, cons, set(), cfg())))

    # 10: an unmappable datatype beside sh:class says both are left out, never "typed"
    def test_unmappable_datatype_beside_a_class_is_recorded_truthfully(self):
        g = shape_graph((lib("S-p"), SH.datatype, XSD.gYear), (lib("S-p"), SH["class"], lib("Work")),
                        (lib("S"), SH.property, lib("S-q")), (lib("S-q"), SH.path, lib("name")),
                        (lib("S-q"), SH.datatype, XSD.string))
        _, left = build.graph_type(cfg(), g, Graph())
        self.assertFalse(any("the property is typed" in x for x in left), left)
        self.assertTrue(any("gYear" in x and "its sh:class" in x for x in left), left)

    def test_a_statement_with_no_element_is_refused(self):
        g = shape_graph((lib("S-p"), SH.datatype, XSD.gYear))
        with self.assertRaises(ValueError):
            build.graph_type(cfg(), g, Graph())

    def test_a_report_path_that_cannot_be_deleted_stops(self):
        d = self.tmp()
        path = os.path.join(d, "r.json")
        os.mkdir(path)
        code, out = run_main(lv.main, ["--report", path])
        self.assertEqual(code, 2, out)
        self.assertIn("cannot delete the earlier report", out)

    # W5: the printed next step names the skill's manifest file
    def test_next_step_names_the_manifest(self):
        self.assertIn("--manifest projection-manifest.json", lv.check_report_command("r.json"))


class AddedCoverage(unittest.TestCase):
    """Tests that lock behaviour the code already had: each passes on cb6c005 and on 88a8510.
    test_store_refuses_a_projection_report_that_did_not_pass also passes on cb6c005 (it fails on
    8648028, which left the stale store report in place)."""

    def tmp(self):
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(d))
        return d

    def store_main(self, *a, **kw):
        return RoundEight.store_main(self, *a, **kw)

    # 11: the mutant walks to the next candidate, and stops when none has a holder
    def test_the_mutant_takes_the_next_candidate(self):
        wiring = RunWiring()
        wiring.setUp = RunWiring.setUp.__get__(wiring)
        wiring.addCleanup = self.addCleanup
        wiring.setUp()
        safe, _ = igs.subset(Graph().parse(SHAPES))
        literal = {p for _, p, o in Graph().parse(MODULE) if isinstance(o, Literal)}
        targets = lv.mutant_targets(wiring.rows, lv.file_constraints(safe, cfg()), literal, cfg())
        self.assertGreater(len(targets), 1)

        class Picky(FakeEngine):
            def __init__(self, empty_keys, *a, **kw):
                super().__init__(*a, **kw)
                self.empty_keys = empty_keys

            def run(self, query, **kw):
                if "RETURN n.uri AS uri, n.`" in query and any(f"n.`{k}` IS NOT NULL" in query for k in self.empty_keys):
                    return FakeResult([])
                return super().run(query, **kw)
        report = wiring.run_with(Picky({targets[0][1]}, wiring.rows, wiring.export))
        self.assertEqual(report["mutant"]["removed"], targets[1][1])
        with self.assertRaises(lv.Failed):
            wiring.run_with(Picky({k for _, k in targets}, wiring.rows, wiring.export))
        self.assertIsNone(lv.mutant(FakeResultSession(), "T", "k"))

    # tests the review listed as gaps
    def test_an_http_exception_leaves_no_store_report(self):
        import http.client
        code, out, path = RoundEight.store_main(self, self.tmp(), put=http.client.IncompleteRead(b""))
        self.assertEqual(code, 1, out)
        self.assertFalse(os.path.exists(path))

    def test_store_refuses_a_projection_report_that_did_not_pass(self):
        # Review 9, #12: export counts present and equal, so only the passed check can reject it.
        export = ts.predicate_counts([Graph().parse(MODULE)])
        code, out, path = self.store_main(self.tmp(), projection=passing_report(self, passed=False,
                                                                             export_predicate_counts=export))
        self.assertEqual(code, 2, out)
        self.assertIn("does not say passed: true", out)
        self.assertFalse(os.path.exists(path))
        code, out, _ = self.store_main(self.tmp(), projection=passing_report(self, export_predicate_counts=export))
        self.assertEqual(code, 0, out)

class QuickCheckTen(unittest.TestCase):
    """Quick check 10 of 88a8510: each test here fails on 88a8510."""

    def test_copy_refuses_the_source_database_under_another_uri(self):
        # Quick check 10, #3: one server reached as bolt://127.0.0.1 and as bolt://localhost.
        class Server:
            def run(self, query, **_):
                return FakeResult([{"id": "one-database"}] if "db.info()" in query else [{"n": 5}])

        env = tempfile.NamedTemporaryFile("w", suffix=".env", delete=False)
        env.write("NEO4J_URI=bolt://localhost:7687\nNEO4J_USERNAME=neo4j\nNEO4J_PASSWORD=p\n")
        env.close()
        self.addCleanup(os.remove, env.name)
        fake = mock.MagicMock()
        fake.GraphDatabase.driver.return_value.__enter__.return_value.session.return_value.__enter__.return_value = Server()
        with mock.patch.dict(os.environ, {"NEO4J_PASSWORD": "local"}), mock.patch.dict(sys.modules, {"neo4j": fake}), \
                mock.patch.object(cg, "graph_hash", return_value="h"), \
                mock.patch.object(cg, "empty_target") as empty, mock.patch.object(cg, "copy") as copy:
            code, out = run_main(cg.main, ["--source", "bolt://127.0.0.1:7687", "--target-env", env.name,
                                           "--report", passing_report(self), "--replace"])
        self.assertEqual(code, 1, out)
        self.assertIn("the target is the source database", out)
        empty.assert_not_called()
        copy.assert_not_called()


class FakeResultSession:
    def run(self, *a, **kw):
        return FakeResult([])


if __name__ == "__main__":
    unittest.main()
