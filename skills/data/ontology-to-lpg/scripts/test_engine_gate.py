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

    def test_closed_matches_its_ignored_properties_row(self):
        g = shape_graph((lib("S"), SH.closed, Literal(True)))
        rows = [row("lib__Copy", None, "sh:ignoredProperties", ["rdf__type"])]
        self.assertEqual(lv.not_compiled(lv.file_constraints(g, cfg()), rows), [])

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
                  "determinism_hash_shuffled": "h", "fail_cases": [{"status": "passed"}, {"status": "no-op"}]}
        self.assertTrue(lv.passed(report))
        report["fail_cases"].append({"status": "no case"})
        self.assertFalse(lv.passed(report))

    def test_nothing_is_carried_from_an_earlier_report(self):
        self.assertFalse(hasattr(lv, "CARRY_KEYS"))
        self.assertFalse(hasattr(lv, "read_previous_report"))
        self.assertNotIn("manual_cases", json.dumps(lv.plan_cases([], [], set(), cfg())))


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
        code, out, _ = self.main(extra=["--manual-cases"])
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
        self.assertEqual(run.call_args[0][-1], [])              # no manual cases carried from the old report
        self.assertIn(shlex.quote(self.path), out)

    def test_check_report_requires_passed_and_cases(self):
        man = {"input_fingerprint": "f", "shapes_fingerprint": "s"}
        rep = {"input_fingerprint": "f", "shapes_fingerprint": "s", "shacl_violations_in_graph": 0,
               "in_graph_mutant_violations": 1, "roundtrip_lost": 0, "roundtrip_added": 0,
               "determinism_hash_sorted": "h", "determinism_hash_shuffled": "h", "in_graph_shape_constraints": 1,
               "shapes_import_rows": 1, "mutant": {"violations": 1, "after_restore": 0},
               "fail_cases": [{"status": "passed"}], "passed": True}
        self.assertEqual(build.check_report(man, rep), [])
        self.assertTrue(build.check_report(man, dict(rep, passed=False)))
        self.assertTrue(build.check_report(man, dict(rep, fail_cases=[])))
        self.assertTrue(build.check_report(man, dict(rep, fail_cases=[{"status": "no case"}])))
        for gone in ("invalidated", "kinds_without_case", "manual_cases"):
            self.assertNotIn(gone, build.check_report.__code__.co_consts)


class StrictSerialised(unittest.TestCase):
    def test_a_line_is_one_triple_and_nothing_else(self):
        a = f"<{LIB}a> <{RDF.type}> <{LIB}Work> .".encode()
        self.assertEqual(build.check_serialised(a + b"\n", b""), [])
        self.assertTrue(build.check_serialised(a + b" # note\n", b""))
        self.assertTrue(build.check_serialised(a + b"\n#\n", b""))


class GraphType(unittest.TestCase):
    def test_library_graph_type(self):
        text, left = build.graph_type(cfg(), Graph().parse(SHAPES, format="turtle"))
        self.assertTrue(text.startswith("CYPHER 25\nALTER CURRENT GRAPH TYPE SET {"))
        self.assertIn("(:`lib__Person` => {`lib__name` :: STRING NOT NULL})", text)
        self.assertIn("(:`lib__Copy`)-[:`lib__copyOf` =>]->(:`lib__Work`)", text)
        self.assertTrue(any("sh:pattern" in line for line in left))
        self.assertTrue(any("non-predicate path" in line for line in left))


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
            code, out = run_main(cg.main, ["--source", "bolt://127.0.0.1:1", "--target-env", path])
        self.assertEqual(code, 2)
        self.assertIn("NEO4J_USERNAME", out)
        self.assertNotIn("s3cret", out)

    def test_refuses_a_target_that_holds_nodes(self):
        path = self.env("NEO4J_URI=bolt://h\nNEO4J_USERNAME=neo4j\nNEO4J_PASSWORD=s3cret\n")
        fake = mock.MagicMock()
        session = fake.GraphDatabase.driver.return_value.__enter__.return_value.session.return_value.__enter__.return_value
        with mock.patch.dict(os.environ, {"NEO4J_PASSWORD": "local"}), mock.patch.dict(sys.modules, {"neo4j": fake}), \
                mock.patch.object(cg, "graph_hash", return_value="h"), \
                mock.patch.object(cg, "count_nodes", return_value=5), mock.patch.object(cg, "copy") as copy:
            code, out = run_main(cg.main, ["--source", "bolt://127.0.0.1:1", "--target-env", path])
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

    def test_ports_are_local_and_no_password_is_written(self):
        compose = self.read("docker", "compose.yaml")
        ports = [line.strip() for line in compose.splitlines() if line.strip().startswith('- "') and ":" in line]
        self.assertTrue(ports and all(p.startswith('- "127.0.0.1:') for p in ports))
        self.assertIn("NEO4J_AUTH: neo4j/${NEO4J_PASSWORD:-}", compose)


if __name__ == "__main__":
    unittest.main()
