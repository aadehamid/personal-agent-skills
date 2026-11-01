"""Tests for run_regression.py, check_shapes.py, check_cardinality.py, check_packages.py and check_code_lists.py.

Run from this folder:
  uv run --no-project --with rdflib --with pyyaml --with pyshacl python3 -m unittest test_validation

Each check gets a clean case that passes and one planted error per failure it claims, asserting the
failure names what was planted, so a check that passes vacuously, or fails for another reason, fails here.
The fixtures are a small library ontology, as in the templates.
"""
import contextlib
import hashlib
import importlib
import io
import json
import os
import shutil
import sys
import tempfile
import textwrap
import unittest

from rdflib import Graph

import check_cardinality
import check_code_lists
import check_packages
import check_shapes
import run_regression

PREFIXES = textwrap.dedent("""\
    @prefix lib: <https://id.example.org/library/> .
    @prefix skos: <http://www.w3.org/2004/02/skos/core#> .
    @prefix sh: <http://www.w3.org/ns/shacl#> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
    """)


def run_main(main, argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = main(argv)
    return code, out.getvalue()


class Files(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def write(self, name, text, prefixes=True):
        path = os.path.join(self.dir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write((PREFIXES if prefixes else "") + textwrap.dedent(text))
        return path


BOOKS = """\
    lib:dune a lib:Book ; rdfs:label "Dune"@en ; lib:genre lib:fiction .
    lib:fiction a skos:Concept ; skos:inScheme lib:Genre .
    lib:Genre a skos:ConceptScheme .
    """


class Regression(Files):
    def setUp(self):
        super().setUp()
        self.data = self.write("books.ttl", BOOKS)
        self.queries = os.path.join(self.dir, "queries")
        self.write("queries/q1-books.rq", "SELECT ?b WHERE { ?b a <https://id.example.org/library/Book> }\n", False)
        self.write("queries/q2-unlabelled.rq",
                   "# Books without a label (must be none)\nSELECT ?b WHERE { ?b a <https://id.example.org/library/Book> "
                   "FILTER NOT EXISTS { ?b <http://www.w3.org/2000/01/rdf-schema#label> ?l } }\n", False)

    def run_rows(self, *rows, files=None):
        expected = self.write("expected.csv", "question,status,queries,waits_for\n" + "".join(r + "\n" for r in rows), False)
        return run_main(run_regression.main, ["--expected", expected, "--queries", self.queries, *(files or [self.data])])

    def test_clean_questions_pass(self):
        code, out = self.run_rows("1,answerable,q1-books.rq;q2-unlabelled.rq,", "2,partial,q1-books.rq,the catalog page",
                                  "3,waiting:Step 7,,", "4,parked:DEC-12,,", "5,drafted,,")
        self.assertEqual(code, 0, out)
        self.assertIn("answerable 1, partial 1, waiting 1, parked 1, drafted 1", out)

    def test_a_query_with_no_rows_fails(self):
        empty = self.write("empty.ttl", "")
        code, out = self.run_rows("1,answerable,q1-books.rq,", files=[empty])
        self.assertEqual(code, 1)
        self.assertIn("Q1 q1-books.rq: no rows", out)

    def test_a_must_be_none_query_with_rows_fails(self):
        unlabelled = self.write("unlabelled.ttl", "lib:emma a lib:Book .\n")
        code, out = self.run_rows("1,answerable,q2-unlabelled.rq,", files=[self.data, unlabelled])
        self.assertEqual(code, 1)
        self.assertIn("Q1 q2-unlabelled.rq: 1 row(s), expected none", out)

    def test_the_marker_counts_only_on_the_first_comment_line(self):
        self.write("queries/q3.rq", "SELECT ?b WHERE { ?b a <https://id.example.org/library/Magazine> }\n"
                                    "# (must be none)\n", False)
        code, out = self.run_rows("1,answerable,q3.rq,")
        self.assertEqual(code, 1)
        self.assertIn("Q1 q3.rq: no rows", out)

    def test_each_status_rule_fails_when_broken(self):
        cases = {
            "1,partial,q1-books.rq,": "Q1: partial must name what the rest waits for",
            "1,answerable,,": "Q1: answerable with no query",
            "1,answerable,q1-books.rq,the portal": "Q1: answerable but names something it waits for",
            "1,waiting:,,": "Q1: waiting must name what it waits for",
            "1,parked:,,": "Q1: parked must name what it was parked by",
            "1,parked:DEC-1,q1-books.rq,": "Q1: parked but lists queries",
            "1,waiting:Step 7,q1-books.rq,": "Q1: waiting but lists queries",
            "1,done,,": "Q1: unknown status 'done'",
            "1,answerable,missing.rq,": "Q1 missing.rq: cannot run",
        }
        for row, message in cases.items():
            with self.subTest(row=row):
                code, out = self.run_rows(row)
                self.assertEqual(code, 1, out)
                self.assertIn(message, out)

    def test_a_question_listed_twice_fails(self):
        code, out = self.run_rows("1,answerable,q1-books.rq,", "1,drafted,,")
        self.assertEqual(code, 1)
        self.assertIn("Q1: listed twice", out)

    def test_the_template_expected_file_runs(self):
        template = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates", "regression-expected.csv")
        code, out = run_main(run_regression.main, ["--expected", template, "--queries", self.queries, self.data])
        self.assertEqual(code, 0, out)
        self.assertIn("2 questions; answerable 0, partial 0, waiting 0, parked 0, drafted 2", out)

    def test_wrong_columns_or_no_questions_is_a_usage_error(self):
        bad = self.write("bad.csv", "question,status\n1,answerable\n", False)
        self.assertEqual(run_main(run_regression.main, ["--expected", bad, "--queries", self.queries, self.data])[0], 2)
        self.assertEqual(self.run_rows()[0], 2)

    def test_a_later_query_with_no_rows_fails(self):
        self.write("queries/q3-magazines.rq", "SELECT ?m WHERE { ?m a <https://id.example.org/library/Magazine> }\n", False)
        code, out = self.run_rows("1,answerable,q1-books.rq;q3-magazines.rq,")
        self.assertEqual(code, 1)
        self.assertIn("Q1 q3-magazines.rq: no rows", out)

    def test_the_marker_after_blank_lines_still_counts(self):
        self.write("queries/q3.rq", "\n\n# none unlabelled (must be none)\nSELECT ?b WHERE { ?b a <https://id.example.org/library/Magazine> }\n", False)
        self.assertEqual(self.run_rows("1,answerable,q3.rq,")[0], 0)

    def test_a_plain_comment_is_not_the_marker(self):
        self.write("queries/q3.rq", "# magazines\nSELECT ?m WHERE { ?m a <https://id.example.org/library/Magazine> }\n", False)
        code, out = self.run_rows("1,answerable,q3.rq,")
        self.assertEqual(code, 1)
        self.assertIn("Q1 q3.rq: no rows", out)

    def test_ask_counts_true_as_a_row_and_false_as_none(self):
        self.write("queries/ask-yes.rq", "ASK { ?b a <https://id.example.org/library/Book> }\n", False)
        self.write("queries/ask-no.rq", "ASK { ?b a <https://id.example.org/library/Magazine> }\n", False)
        self.write("queries/ask-yes-none.rq", "# (must be none)\nASK { ?b a <https://id.example.org/library/Book> }\n", False)
        self.assertEqual(self.run_rows("1,answerable,ask-yes.rq,")[0], 0)
        code, out = self.run_rows("1,answerable,ask-no.rq,")
        self.assertEqual(code, 1)
        self.assertIn("Q1 ask-no.rq: no rows", out)
        code, out = self.run_rows("1,answerable,ask-yes-none.rq,")
        self.assertEqual(code, 1)
        self.assertIn("Q1 ask-yes-none.rq: 1 row(s), expected none", out)

    def test_more_status_rules_fail_when_broken(self):
        cases = {"1,partial,,the portal": "Q1: partial with no query",
                 "1,waiting:   ,,": "Q1: waiting must name what it waits for",
                 "1,parked: ,,": "Q1: parked must name what it was parked by"}
        for row, message in cases.items():
            with self.subTest(row=row):
                code, out = self.run_rows(row)
                self.assertEqual(code, 1, out)
                self.assertIn(message, out)

    def test_the_coverage_line_counts_every_question(self):
        code, out = self.run_rows("1,answerable,q1-books.rq,", "2,drafted,,", "3,parked:DEC-1,,")
        self.assertEqual(code, 0, out)
        self.assertIn("competency coverage: 3 questions; answerable 1, partial 0, waiting 0, parked 1, drafted 1", out)

    def test_an_unreadable_data_file_is_a_usage_error(self):
        bad = self.write("bad.ttl", "lib:dune a .\n")
        self.assertEqual(self.run_rows("1,answerable,q1-books.rq,", files=[bad])[0], 2)


SHAPES = """\
    lib:BookShape a sh:NodeShape ; sh:targetClass lib:Book ;
        sh:property [ sh:path rdfs:label ; sh:minCount 1 ] .
    """


class WholeGraph(Files):
    def gate(self, data, shapes, *extra):
        return run_main(check_shapes.main, ["--shapes", *shapes, "--data", *data, *extra])

    def test_a_conforming_graph_passes(self):
        code, out = self.gate([self.write("books.ttl", BOOKS)], [self.write("shapes.ttl", SHAPES)])
        self.assertEqual(code, 0, out)

    def test_a_violation_fails_and_names_its_focus_node(self):
        code, out = self.gate([self.write("books.ttl", BOOKS + "lib:emma a lib:Book .\n")],
                              [self.write("shapes.ttl", SHAPES)])
        self.assertEqual(code, 1)
        self.assertIn("Violation on https://id.example.org/library/emma path http://www.w3.org/2000/01/rdf-schema#label", out)

    def test_a_warning_fails_too(self):
        shapes = SHAPES.replace("sh:minCount 1 ]", "sh:minCount 1 ; sh:severity sh:Warning ]")
        code, out = self.gate([self.write("books.ttl", BOOKS + "lib:emma a lib:Book .\n")],
                              [self.write("shapes.ttl", shapes)])
        self.assertEqual(code, 1)
        self.assertIn("Warning on https://id.example.org/library/emma", out)

    def test_a_cross_module_break_fails(self):
        # Each module conforms alone; together, the loans module points at a book the catalog never defines.
        catalog = self.write("catalog/catalog.ttl", BOOKS)
        loans = self.write("loans/loans.ttl", "lib:loan1 a lib:Loan ; lib:item lib:no-such-book .\n")
        shapes = self.write("loans/shapes.ttl", "lib:LoanShape a sh:NodeShape ; sh:targetClass lib:Loan ;\n"
                                                "    sh:property [ sh:path lib:item ; sh:class lib:Book ] .\n")
        code, out = self.gate([catalog, loans], [shapes])
        self.assertEqual(code, 1)
        self.assertIn("Violation on https://id.example.org/library/loan1 path https://id.example.org/library/item", out)

    def test_a_shapes_file_left_out_of_the_gate_fails(self):
        listed = self.write("modules/catalog/catalog-shapes.ttl", SHAPES)
        self.write("modules/catalog/shapes.ttl", "")  # not *-shapes.ttl, so not required
        self.write("modules/catalog/reshapes.ttl", "")
        left_out = self.write("modules/loans/loans-shapes.ttl", "")
        data = self.write("books.ttl", BOOKS)
        code, out = self.gate([data], [listed], "--every-shapes-file-under", os.path.join(self.dir, "modules"))
        self.assertEqual(code, 1)
        self.assertIn(f"shapes file not in the gate: {left_out}", out)
        code, out = self.gate([data], [listed, left_out], "--every-shapes-file-under", os.path.join(self.dir, "modules"))
        self.assertEqual(code, 0, out)

    def test_an_unreadable_file_is_a_usage_error(self):
        bad = self.write("bad.ttl", "lib:dune a .\n")
        self.assertEqual(self.gate([bad], [self.write("shapes.ttl", SHAPES)])[0], 2)

    def test_an_info_result_fails_too(self):
        shapes = SHAPES.replace("sh:minCount 1 ]", "sh:minCount 1 ; sh:severity sh:Info ]")
        code, out = self.gate([self.write("books.ttl", BOOKS + "lib:emma a lib:Book .\n")], [self.write("shapes.ttl", shapes)])
        self.assertEqual(code, 1)
        self.assertIn("Info on https://id.example.org/library/emma", out)

    def test_a_rule_that_supplies_a_missing_value_fails(self):
        # The rule would add the label the shape requires; the gate refuses rules instead of running them.
        rule = SHAPES + ("lib:LabelRule a sh:NodeShape ; sh:targetClass lib:Book ;\n"
                         "    sh:rule [ a sh:TripleRule ; sh:subject sh:this ; sh:predicate rdfs:label ; sh:object \"x\"@en ] .\n")
        code, out = self.gate([self.write("books.ttl", BOOKS + "lib:emma a lib:Book .\n")], [self.write("shapes.ttl", rule)])
        self.assertEqual(code, 1)
        self.assertIn("FAIL Rule on https://id.example.org/library/LabelRule: sh:rule is not allowed", out)

    def test_a_shapes_root_that_is_not_a_directory_is_a_usage_error(self):
        data, shapes = self.write("books.ttl", BOOKS), self.write("shapes.ttl", SHAPES)
        code, out = self.gate([data], [shapes], "--every-shapes-file-under", os.path.join(self.dir, "no-such-dir"))
        self.assertEqual(code, 2)
        self.assertIn("ERROR not a directory", out)
        self.assertEqual(self.gate([data], [shapes], "--every-shapes-file-under", data)[0], 2)

    def test_a_malformed_shape_is_a_usage_error(self):
        bad = SHAPES.replace("sh:minCount 1", 'sh:minCount "one"')
        self.assertEqual(self.gate([self.write("books.ttl", BOOKS)], [self.write("shapes.ttl", bad)])[0], 2)


DECLARED = """\
    @prefix owl: <http://www.w3.org/2002/07/owl#> .
    lib:Book a owl:Class . lib:Copy a owl:Class .
    lib:genre a owl:ObjectProperty ; rdfs:domain lib:Book ; rdfs:range skos:Concept .
    lib:pages a owl:DatatypeProperty ; rdfs:domain lib:Book ; rdfs:range xsd:integer .
    lib:note a owl:AnnotationProperty .
    """
CARDINALITIES = """\
    lib:BookShape a sh:NodeShape ; sh:targetClass lib:Book ; sh:property lib:BookShape-genre, lib:BookShape-pages .
    lib:BookShape-genre a sh:PropertyShape ; sh:path lib:genre ; sh:minCount 1 .
    lib:BookShape-pages a sh:PropertyShape ; sh:path lib:pages ; sh:maxCount 1 .
    lib:NoteShape a sh:NodeShape ; sh:targetSubjectsOf lib:note ; sh:property [ sh:path lib:note ; sh:maxCount 1 ] .
    """


class Cardinality(Files):
    def check(self, data, shapes):
        return run_main(check_cardinality.main, ["--shapes", self.write("shapes.ttl", shapes),
                                                 "--data", self.write("data.ttl", data)])

    def test_every_property_shaped_passes(self):
        code, out = self.check(DECLARED, CARDINALITIES)
        self.assertEqual(code, 0, out)
        self.assertIn("(3 properties)", out)

    def test_the_skill_skeletons_pass(self):
        templates = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates")
        code, out = run_main(check_cardinality.main, ["--shapes", os.path.join(templates, "shapes-skeleton.ttl"),
                                                      "--data", os.path.join(templates, "ontology-skeleton.ttl")])
        self.assertEqual(code, 0, out)
        self.assertIn("(5 properties)", out)

    def test_a_property_with_no_cardinality_fails(self):
        shapes = CARDINALITIES.replace("sh:path lib:pages ; sh:maxCount 1", "sh:path lib:pages ; sh:datatype xsd:integer")
        code, out = self.check(DECLARED, shapes)
        self.assertEqual(code, 1)
        self.assertIn("FAIL cardinality: https://id.example.org/library/pages has no applied property shape", out)
        self.assertNotIn("library/genre", out)

    def test_a_declared_unused_property_still_needs_one(self):
        shapes = CARDINALITIES.replace("lib:NoteShape a sh:NodeShape ; sh:targetSubjectsOf lib:note ; sh:property [ sh:path lib:note ; sh:maxCount 1 ] .\n", "")
        code, out = self.check(DECLARED, shapes)
        self.assertEqual(code, 1)
        self.assertIn("FAIL cardinality: https://id.example.org/library/note has no applied property shape", out)

    def test_a_shape_for_another_class_does_not_count(self):
        # pages has domain Book; its only cardinality sits under a shape that targets Copy, so no Book is checked.
        shapes = CARDINALITIES.replace("sh:property lib:BookShape-genre, lib:BookShape-pages", "sh:property lib:BookShape-genre") \
            + "lib:CopyShape a sh:NodeShape ; sh:targetClass lib:Copy ; sh:property lib:BookShape-pages .\n"
        code, out = self.check(DECLARED, shapes)
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL cardinality: https://id.example.org/library/pages", out)

    def test_a_shape_for_a_superclass_of_the_domain_counts(self):
        data = DECLARED + "lib:Item a owl:Class . lib:Book rdfs:subClassOf lib:Item .\n"
        shapes = CARDINALITIES.replace("sh:targetClass lib:Book", "sh:targetClass lib:Item")
        self.assertEqual(self.check(data, shapes)[0], 0)
        shapes = CARDINALITIES.replace("sh:targetClass lib:Book", "sh:targetClass lib:Copy")
        self.assertEqual(self.check(data, shapes)[0], 1)

    def test_an_implicit_class_target_counts(self):
        shapes = "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n" + CARDINALITIES.replace(
            "lib:BookShape a sh:NodeShape ; sh:targetClass lib:Book ;", "lib:Book a sh:NodeShape, owl:Class ;")
        code, out = self.check(DECLARED, shapes)
        self.assertEqual(code, 0, out)

    def test_a_shape_reached_through_node_and_or_counts(self):
        # The cardinalities sit in shapes nothing targets; the targeted shape reaches them through sh:node and sh:and.
        for reuse in ("sh:node lib:Inner", "sh:and ( lib:Inner )", "sh:or ( lib:Inner )", "sh:xone ( lib:Inner )"):
            with self.subTest(reuse=reuse):
                shapes = CARDINALITIES.replace("lib:BookShape a sh:NodeShape ; sh:targetClass lib:Book ; sh:property lib:BookShape-genre, lib:BookShape-pages .",
                                               f"lib:BookShape a sh:NodeShape ; sh:targetClass lib:Book ; {reuse} .\n"
                                               "lib:Inner a sh:NodeShape ; sh:property lib:BookShape-genre, lib:BookShape-pages .")
                code, out = self.check(DECLARED, shapes)
                self.assertEqual(code, 0, out)

    def test_a_shape_below_a_property_shape_does_not_count(self):
        # Inner applies to the values of genre, not to books, so it says nothing about a book's genre or pages.
        shapes = CARDINALITIES.replace("sh:property lib:BookShape-genre, lib:BookShape-pages .",
                                       "sh:property [ sh:path lib:other ; sh:node lib:Inner ] .\n"
                                       "lib:Inner a sh:NodeShape ; sh:property lib:BookShape-genre, lib:BookShape-pages .")
        code, out = self.check(DECLARED, shapes)
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL cardinality: https://id.example.org/library/genre", out)
        self.assertIn("FAIL cardinality: https://id.example.org/library/pages", out)

    def test_a_sparql_target_counts_for_no_property(self):
        # The query selects copies here; the check does not run queries, so neither query can count.
        for cls in ("Book", "Copy"):
            with self.subTest(cls=cls):
                shapes = CARDINALITIES.replace("sh:targetClass lib:Book", "sh:target [ a sh:SPARQLTarget ; sh:select "
                                               f"\"SELECT ?this WHERE {{ ?this a <https://id.example.org/library/{cls}> }}\" ]")
                code, out = self.check(DECLARED, shapes)
                self.assertEqual(code, 1, out)
                self.assertIn("FAIL cardinality: https://id.example.org/library/pages", out)

    def test_an_instance_target_counts_only_for_its_own_class(self):
        target = CARDINALITIES.replace("sh:targetClass lib:Book", "sh:targetNode lib:dune")
        self.assertEqual(self.check(DECLARED + "lib:dune a lib:Book .\n", target)[0], 0)
        code, out = self.check(DECLARED + "lib:dune a lib:Copy .\n", target)
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL cardinality: https://id.example.org/library/pages", out)
        self.assertEqual(self.check(DECLARED, target)[0], 1)  # a node the data does not type shows nothing
        # One paperback does not stand in for every book, as sh:targetClass lib:Paperback does not.
        paperback = DECLARED + "lib:Paperback a owl:Class ; rdfs:subClassOf lib:Book .\nlib:dune a lib:Paperback .\n"
        code, out = self.check(paperback, target)
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL cardinality: https://id.example.org/library/pages", out)

    def test_an_objects_or_subjects_target_counts_only_for_its_own_class(self):
        for kind, good, bad in (("sh:targetObjectsOf", {"d": "Copy", "r": "Book"}, {"d": "Book", "r": "Copy"}),
                                ("sh:targetSubjectsOf", {"d": "Book", "r": "Copy"}, {"d": "Copy", "r": "Book"})):
            with self.subTest(kind=kind):
                target = CARDINALITIES.replace("sh:targetClass lib:Book", f"{kind} lib:shelved")
                declared = DECLARED + "lib:shelved a owl:ObjectProperty ; rdfs:domain lib:{d} ; rdfs:range lib:{r} .\n"
                shelved = "lib:ShelvedShape a sh:NodeShape ; sh:targetSubjectsOf lib:shelved ; sh:property [ sh:path lib:shelved ; sh:maxCount 1 ] .\n"
                code, out = self.check(declared.format(**good), target + shelved)
                self.assertEqual(code, 0, out)
                for wrong in (bad, {**good, "r" if kind == "sh:targetObjectsOf" else "d": "Paperback"}):
                    subclass = "lib:Paperback a owl:Class ; rdfs:subClassOf lib:Book .\n"
                    code, out = self.check(declared.format(**wrong) + subclass, target + shelved)
                    self.assertEqual(code, 1, out)
                    self.assertIn("FAIL cardinality: https://id.example.org/library/pages", out)

    def test_a_property_with_no_domain_needs_its_subjects_targeted(self):
        # The annotation is used on a book and its only cardinality sits under a shape on copies.
        shapes = CARDINALITIES.replace("lib:NoteShape a sh:NodeShape ; sh:targetSubjectsOf lib:note ;",
                                       "lib:NoteShape a sh:NodeShape ; sh:targetClass lib:Copy ;")
        code, out = self.check(DECLARED + 'lib:dune a lib:Book ; lib:note "x"@en, "y"@en .\n', shapes)
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL cardinality: https://id.example.org/library/note", out)

    def test_an_empty_node_shape_fails(self):
        # A class with no properties gets no node shape (shapes-skeleton.ttl); one that holds nothing can never fail.
        code, out = self.check(DECLARED, CARDINALITIES + "lib:CopyShape a sh:NodeShape ; sh:targetClass lib:Copy .\n")
        self.assertEqual(code, 1)
        self.assertIn("FAIL empty-shape: https://id.example.org/library/CopyShape holds no property shape and no constraint", out)

    def test_a_node_shape_with_a_constraint_but_no_property_shape_passes(self):
        code, out = self.check(DECLARED, CARDINALITIES + "lib:CopyShape a sh:NodeShape ; sh:targetClass lib:Copy ; sh:closed true .\n")
        self.assertEqual(code, 0, out)

    def test_a_deactivated_shape_is_not_applied(self):
        for dead in ("lib:BookShape-pages a sh:PropertyShape ; sh:deactivated true ;",
                     "lib:BookShape a sh:NodeShape ; sh:deactivated true ;"):
            with self.subTest(dead=dead):
                shapes = CARDINALITIES.replace(dead.replace(" sh:deactivated true ;", ""), dead)
                code, out = self.check(DECLARED, shapes)
                self.assertEqual(code, 1, out)
                self.assertIn("FAIL cardinality: https://id.example.org/library/pages", out)

    def test_a_property_shape_nothing_targets_is_not_applied(self):
        shapes = CARDINALITIES.replace("sh:property lib:BookShape-genre, lib:BookShape-pages", "sh:property lib:BookShape-genre")
        code, out = self.check(DECLARED, shapes)
        self.assertEqual(code, 1)
        self.assertIn("FAIL cardinality: https://id.example.org/library/pages", out)

    def test_a_property_shape_with_its_own_target_is_applied(self):
        loose = CARDINALITIES.replace("sh:property lib:BookShape-genre, lib:BookShape-pages", "sh:property lib:BookShape-genre")
        own = loose.replace("lib:BookShape-pages a sh:PropertyShape ;", "lib:BookShape-pages a sh:PropertyShape ; sh:targetClass lib:Book ;")
        self.assertEqual(self.check(DECLARED, own)[0], 0)
        other = loose.replace("lib:BookShape-pages a sh:PropertyShape ;", "lib:BookShape-pages a sh:PropertyShape ; sh:targetClass lib:Copy ;")
        self.assertEqual(self.check(DECLARED, other)[0], 1)

    def test_an_unreadable_file_is_a_usage_error(self):
        self.assertEqual(self.check("lib:x a .\n", CARDINALITIES)[0], 2)
        self.assertEqual(run_main(check_cardinality.main, ["--shapes", os.path.join(self.dir, "none.ttl"),
                                                           "--data", self.write("d.ttl", DECLARED)])[0], 2)


class AppliedShapeParity(Files):
    """check_cardinality.py and ontology-to-lpg's check_projection_rules.py read the same shapes as applied.
    The two stay separate code because a project copies this skill's scripts without the other skill."""

    @classmethod
    def setUpClass(cls):
        folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "ontology-to-lpg", "scripts")
        sys.path.append(folder)
        try:
            cls.projection = importlib.import_module("check_projection_rules")
        finally:
            sys.path.remove(folder)

    def paths(self, shapes):
        g = Graph().parse(data=PREFIXES + "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n" + textwrap.dedent(shapes), format="turtle")
        return ({str(p).rsplit("/", 1)[-1] for p, _ in check_cardinality.applied_property_shapes(g)},
                {str(p).rsplit("/", 1)[-1] for p, _ in self.projection.applied_property_shapes(g)})

    def test_both_read_the_same_shapes_as_applied(self):
        inner = "lib:Inner a sh:NodeShape ; sh:property [ sh:path lib:pages ; sh:maxCount 1 ] .\n"
        own = "sh:property [ sh:path lib:pages ; sh:maxCount 1 ]"
        cases = {
            "class target": (f"lib:S a sh:NodeShape ; sh:targetClass lib:Book ; {own} .", {"pages"}),
            "instance target": (f"lib:S a sh:NodeShape ; sh:targetNode lib:dune ; {own} .", {"pages"}),
            "subjects target": (f"lib:S a sh:NodeShape ; sh:targetSubjectsOf lib:pages ; {own} .", {"pages"}),
            "objects target": (f"lib:S a sh:NodeShape ; sh:targetObjectsOf lib:item ; {own} .", {"pages"}),
            "implicit class": (f"lib:Book a sh:NodeShape, owl:Class ; {own} .", {"pages"}),
            "no target": (f"lib:S a sh:NodeShape ; {own} .", set()),
            "deactivated root": (f"lib:S a sh:NodeShape ; sh:targetClass lib:Book ; sh:deactivated true ; {own} .", set()),
            "deactivated property shape": ("lib:S a sh:NodeShape ; sh:targetClass lib:Book ; "
                                           "sh:property [ sh:path lib:pages ; sh:maxCount 1 ; sh:deactivated true ] .", set()),
            "sh:node": ("lib:S a sh:NodeShape ; sh:targetClass lib:Book ; sh:node lib:Inner .\n" + inner, {"pages"}),
            "sh:and": ("lib:S a sh:NodeShape ; sh:targetClass lib:Book ; sh:and ( lib:Inner ) .\n" + inner, {"pages"}),
            "sh:or": ("lib:S a sh:NodeShape ; sh:targetClass lib:Book ; sh:or ( lib:Inner ) .\n" + inner, {"pages"}),
            "sh:xone": ("lib:S a sh:NodeShape ; sh:targetClass lib:Book ; sh:xone ( lib:Inner ) .\n" + inner, {"pages"}),
            "deactivated sh:node": ("lib:S a sh:NodeShape ; sh:targetClass lib:Book ; sh:node lib:Inner .\n"
                                    + inner.replace("sh:NodeShape ;", "sh:NodeShape ; sh:deactivated true ;"), set()),
        }
        for name, (shapes, expected) in cases.items():
            with self.subTest(name):
                self.assertEqual(self.paths(shapes), (expected, expected))

    def test_the_two_recorded_differences(self):
        # Rule 2 asks whether any node's value is checked, and the loader's list reads that, so a shape below a
        # property shape counts there; here it says nothing about the root's own nodes.
        below = ("lib:S a sh:NodeShape ; sh:targetClass lib:Book ; sh:property [ sh:path lib:item ; sh:node lib:Inner ] .\n"
                 "lib:Inner a sh:NodeShape ; sh:property [ sh:path lib:pages ; sh:maxCount 1 ] .\n")
        self.assertEqual(self.paths(below), ({"item"}, {"item", "pages"}))
        # A property shape with its own target applies to its target's nodes; the projection reads property shapes
        # only through a node shape's sh:property.
        self.assertEqual(self.paths("lib:P a sh:PropertyShape ; sh:path lib:pages ; sh:maxCount 1 ; sh:targetClass lib:Book .\n"),
                         ({"pages"}, set()))


CORE_V1 = """\
    lib:dune a lib:Book ; rdfs:label "Dune"@en .
    """
LOANS = """\
    lib:loan1 a lib:Loan ; lib:item lib:dune .
    """
LOAN_SHAPES = """\
    lib:LoanShape a sh:NodeShape ; sh:targetClass lib:Loan ;
        sh:property [ sh:path lib:item ; sh:class lib:Book ; sh:minCount 1 ] .
    """


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

TYPES = """\
    lib:dune a lib:Classic .
    """
NEEDS_BOOK = """\
    lib:Shelf a sh:NodeShape ; sh:targetNode lib:dune ; sh:property [ sh:path rdf:type ; sh:hasValue lib:Classic ] .
    """


class Packages(Files):
    def package(self, module, version, data, shapes="", depends_on=None):
        folder = os.path.join("releases", module, version)
        files = {f"{module}.ttl": self.write(os.path.join(folder, f"{module}.ttl"), data),
                 "shapes.ttl": self.write(os.path.join(folder, "shapes.ttl"), shapes)}
        manifest = {"module": module, "version": version, "depends_on": depends_on or {},
                    "files": {n: sha256(p) for n, p in files.items()}}
        with open(os.path.join(self.dir, folder, "manifest.json"), "w") as f:
            json.dump(manifest, f)
        return os.path.join(self.dir, folder)

    def check(self, pins):
        expect = self.write("packages.txt", "# pinned by hand\n" + "".join(p + "\n" for p in pins), False)
        return run_main(check_packages.main, ["--releases", os.path.join(self.dir, "releases"), "--expect", expect])

    def setUp(self):
        super().setUp()
        self.package("catalog", "1.0.0", CORE_V1)
        self.loans = self.package("loans", "1.0.0", LOANS, LOAN_SHAPES, {"catalog": "1.0.0"})
        self.pins = ["catalog 1.0.0", "loans 1.0.0"]

    def test_clean_packages_pass(self):
        code, out = self.check(self.pins)
        self.assertEqual(code, 0, out)
        self.assertIn("2 release packages", out)

    def test_a_package_without_its_closure_fails(self):
        self.package("loans", "1.0.0", LOANS, LOAN_SHAPES, {})
        code, out = self.check(self.pins)
        self.assertEqual(code, 1)
        self.assertIn("loans 1.0.0: Violation on https://id.example.org/library/loan1", out)

    def test_a_changed_file_fails(self):
        with open(os.path.join(self.loans, "loans.ttl"), "a") as f:
            f.write("lib:loan2 a lib:Loan ; lib:item lib:dune .\n")
        code, out = self.check(self.pins)
        self.assertEqual(code, 1)
        self.assertIn("loans 1.0.0: loans.ttl does not match its manifest hash", out)

    def test_a_file_outside_the_manifest_fails(self):
        self.write("releases/loans/1.0.0/notes.md", "", False)
        code, out = self.check(self.pins)
        self.assertEqual(code, 1)
        self.assertIn("loans 1.0.0: notes.md is not in the manifest", out)

    def test_an_unpinned_or_missing_package_fails(self):
        code, out = self.check(["catalog 1.0.0", "loans 2.0.0"])
        self.assertEqual(code, 1)
        self.assertIn("loans 1.0.0: package folder not pinned", out)
        self.assertIn("loans 2.0.0: pinned but no package folder", out)

    def test_a_required_version_that_does_not_exist_fails(self):
        self.package("loans", "1.0.0", LOANS, LOAN_SHAPES, {"catalog": "9.0.0"})
        code, out = self.check(self.pins)
        self.assertEqual(code, 1)
        self.assertIn("loans 1.0.0: cannot load the package or its closure", out)

    def test_the_highest_release_of_a_dependency_is_loaded(self):
        # loans needs catalog 1.0.0 directly and 1.10.0 through reviews; only 1.10.0 is loaded.
        self.package("catalog", "1.10.0", CORE_V1)
        self.package("reviews", "1.0.0", "", "", {"catalog": "1.10.0"})
        releases = os.path.join(self.dir, "releases")
        # Both orders: the lower release reached first, and the higher reached first.
        for order in ({"catalog": "1.0.0", "reviews": "1.0.0"}, {"reviews": "1.0.0", "catalog": "1.0.0"}):
            with self.subTest(order=list(order)):
                self.assertEqual(check_packages.closure(releases, order), {"catalog": "1.10.0", "reviews": "1.0.0"})

    def test_a_release_candidate_sorts_before_its_release(self):
        self.assertLess(check_packages.version_key("1.0.0-rc.1"), check_packages.version_key("1.0.0"))
        self.assertLess(check_packages.version_key("1.9.0"), check_packages.version_key("1.10.0"))

    def test_a_losing_release_brings_no_dependencies(self):
        # catalog 1.0.0 needs types 1.0.0, which types the book; catalog 1.1.0 does not. reviews needs
        # catalog 1.1.0, so 1.1.0 wins and types must not be loaded, in either order of the requirements.
        self.package("types", "1.0.0", TYPES)
        self.package("catalog", "1.0.0", CORE_V1, depends_on={"types": "1.0.0"})
        self.package("catalog", "1.1.0", CORE_V1)
        self.package("reviews", "1.0.0", "", depends_on={"catalog": "1.1.0"})
        releases = os.path.join(self.dir, "releases")
        for order in ({"catalog": "1.0.0", "reviews": "1.0.0"}, {"reviews": "1.0.0", "catalog": "1.0.0"}):
            with self.subTest(order=list(order)):
                self.assertEqual(check_packages.closure(releases, order), {"catalog": "1.1.0", "reviews": "1.0.0"})
        self.package("shelf", "1.0.0", "", "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n" + NEEDS_BOOK,
                             {"reviews": "1.0.0", "catalog": "1.0.0"})
        fails = check_packages.check_package(releases, "shelf", "1.0.0")
        self.assertTrue(any("Violation on https://id.example.org/library/dune" in f for f in fails), fails)

    def test_pre_releases_follow_semver_precedence(self):
        k = check_packages.version_key
        self.assertLess(k("1.0.0-rc.2"), k("1.0.0-rc.10"))
        self.assertLess(k("1.0.0-rc.10"), k("1.0.0"))
        self.assertLess(k("1.0.0-alpha"), k("1.0.0-alpha.1"))
        self.assertLess(k("1.0.0-1"), k("1.0.0-alpha"))
        self.package("catalog", "1.0.0-rc.2", CORE_V1)
        self.package("catalog", "1.0.0-rc.10", CORE_V1)
        releases = os.path.join(self.dir, "releases")
        self.assertEqual(check_packages.closure(releases, {"catalog": "1.0.0-rc.2"}), {"catalog": "1.0.0-rc.2"})
        self.package("bridge", "1.0.0", "", depends_on={"catalog": "1.0.0-rc.10"})
        self.assertEqual(check_packages.closure(releases, {"catalog": "1.0.0-rc.2", "bridge": "1.0.0"}),
                         {"catalog": "1.0.0-rc.10", "bridge": "1.0.0"})

    def test_a_closure_is_numeric_not_textual(self):
        self.package("catalog", "1.9.0", CORE_V1)
        self.package("catalog", "1.10.0", CORE_V1)
        self.package("bridge", "1.0.0", "", depends_on={"catalog": "1.10.0"})
        releases = os.path.join(self.dir, "releases")
        self.assertEqual(check_packages.closure(releases, {"catalog": "1.9.0", "bridge": "1.0.0"})["catalog"], "1.10.0")

    def test_each_broken_manifest_or_file_fails(self):
        def manifest(**kw):
            path = os.path.join(self.loans, "manifest.json")
            with open(path) as f:
                m = json.load(f)
            m.update(kw)
            with open(path, "w") as f:
                json.dump(m, f)
        cases = [
            (lambda: manifest(files=["loans.ttl"]), 'no readable manifest.json: manifest "files" is not an object'),
            (lambda: manifest(depends_on=["catalog"]), 'no readable manifest.json: manifest "depends_on" is not an object'),
            (lambda: open(os.path.join(self.loans, "manifest.json"), "w").write("{not json"), "no readable manifest.json"),
            (lambda: os.remove(os.path.join(self.loans, "shapes.ttl")), "shapes.ttl is in the manifest but missing"),
        ]
        for i, (breakit, message) in enumerate(cases):
            with self.subTest(case=i):
                self.loans = self.package("loans", "1.0.0", LOANS, LOAN_SHAPES, {"catalog": "1.0.0"})
                breakit()
                code, out = self.check(self.pins)
                self.assertEqual(code, 1, out)
                self.assertIn("loans 1.0.0: " + message, out)

    def test_a_package_without_its_turtle_or_with_bad_turtle_fails(self):
        self.package("loans", "1.0.0", LOANS, LOAN_SHAPES, {"catalog": "1.0.0"})
        os.rename(os.path.join(self.loans, "loans.ttl"), os.path.join(self.loans, "other.ttl"))
        code, out = self.check(self.pins)
        self.assertIn("loans 1.0.0: no loans.ttl", out)
        self.package("loans", "1.0.0", "lib:loan1 a .\n", LOAN_SHAPES, {"catalog": "1.0.0"})
        os.remove(os.path.join(self.loans, "other.ttl"))
        code, out = self.check(self.pins)
        self.assertEqual(code, 1)
        self.assertIn("loans 1.0.0: cannot parse or apply the package or its closure", out)

    def test_a_rule_in_package_shapes_fails(self):
        rule = LOAN_SHAPES + ("lib:Fix a sh:NodeShape ; sh:targetClass lib:Loan ;\n"
                              "    sh:rule [ a sh:TripleRule ; sh:subject sh:this ; sh:predicate lib:item ; sh:object lib:dune ] .\n")
        self.package("loans", "1.0.0", LOANS, rule, {"catalog": "1.0.0"})
        code, out = self.check(self.pins)
        self.assertEqual(code, 1)
        self.assertIn("loans 1.0.0: Rule on https://id.example.org/library/Fix: sh:rule is not allowed", out)

    def test_an_empty_releases_folder_fails(self):
        empty = os.path.join(self.dir, "empty")
        os.makedirs(empty)
        code, out = run_main(check_packages.main, ["--releases", empty, "--expect", self.write("p.txt", "", False)])
        self.assertEqual(code, 1)
        self.assertIn("FAIL no release package under", out)

    def test_a_closure_that_never_settles_fails(self):
        # a 1.0.0 needs b 1.0.0, which needs a 2.0.0; a 2.0.0 needs nothing, so b drops and a 1.0.0 returns.
        self.package("a", "1.0.0", "", depends_on={"b": "1.0.0"})
        self.package("b", "1.0.0", "", depends_on={"a": "2.0.0"})
        self.package("a", "2.0.0", "")
        with self.assertRaisesRegex(ValueError, "does not settle"):
            check_packages.closure(os.path.join(self.dir, "releases"), {"a": "1.0.0"})

    def test_bad_arguments_are_usage_errors(self):
        self.assertEqual(run_main(check_packages.main, ["--releases", os.path.join(self.dir, "nope"),
                                                        "--expect", self.write("p.txt", "", False)])[0], 2)
        bad = self.write("bad.txt", "loans one\n", False)
        self.assertEqual(run_main(check_packages.main, ["--releases", os.path.join(self.dir, "releases"), "--expect", bad])[0], 2)


CODED = """\
    lib:dune a lib:Book ; lib:genre lib:fiction ; lib:format lib:hardback .
    lib:Genre a skos:ConceptScheme .
    lib:Format a skos:ConceptScheme .
    lib:fiction a skos:Concept ; skos:inScheme lib:Genre .
    lib:poetry a skos:Concept ; skos:inScheme lib:Genre .
    lib:hardback a skos:Concept ; skos:inScheme lib:Format .
    """
GENRE_SHAPE = """\
    lib:GenreValue a sh:NodeShape ; sh:targetObjectsOf lib:genre ;
        sh:property [ sh:path skos:inScheme ; sh:hasValue lib:Genre ] .
    """
FORMAT_SHAPE = """\
    lib:BookFormat a sh:NodeShape ; sh:targetClass lib:Book ;
        sh:property [ sh:path lib:format ; sh:node lib:InFormat ] .
    lib:InFormat a sh:NodeShape ; sh:property [ sh:path skos:inScheme ; sh:hasValue lib:Format ] .
    """


class CodeLists(Files):
    def check(self, data, shapes, *extra):
        return run_main(check_code_lists.main, ["--shapes", self.write("shapes.ttl", shapes),
                                                "--data", self.write("data.ttl", data), *extra])

    def test_both_shape_forms_pass(self):
        code, out = self.check(CODED, GENRE_SHAPE + FORMAT_SHAPE)
        self.assertEqual(code, 0, out)
        self.assertIn("(2 properties)", out)

    def test_a_property_with_no_shape_fails(self):
        code, out = self.check(CODED, GENRE_SHAPE)
        self.assertEqual(code, 1)
        self.assertIn("FAIL covered: https://id.example.org/library/format takes values from", out)

    def test_class_skos_concept_is_not_a_membership_shape(self):
        shape = FORMAT_SHAPE.replace("sh:node lib:InFormat", "sh:class skos:Concept")
        code, out = self.check(CODED, GENRE_SHAPE + shape)
        self.assertEqual(code, 1)
        self.assertIn("FAIL covered: https://id.example.org/library/format", out)

    def test_a_shape_on_another_path_is_not_a_membership_shape(self):
        shape = FORMAT_SHAPE.replace("sh:path skos:inScheme ; sh:hasValue lib:Format", "sh:path skos:broader ; sh:hasValue lib:Format")
        code, out = self.check(CODED, GENRE_SHAPE + shape)
        self.assertEqual(code, 1)
        self.assertIn("FAIL covered: https://id.example.org/library/format", out)

    def test_a_value_in_another_list_fails(self):
        data = CODED + "lib:emma a lib:Book ; lib:genre lib:hardback .\n"
        code, out = self.check(data, GENRE_SHAPE + FORMAT_SHAPE)
        self.assertEqual(code, 1)
        self.assertIn("FAIL same-list: https://id.example.org/library/genre on https://id.example.org/library/emma", out)

    def test_a_shape_that_cannot_fail_fails(self):
        shape = GENRE_SHAPE.replace("sh:targetObjectsOf lib:genre ;", "sh:targetObjectsOf lib:genre ; sh:deactivated true ;")
        code, out = self.check(CODED, shape + FORMAT_SHAPE)
        self.assertEqual(code, 1)
        self.assertIn("FAIL bites: https://id.example.org/library/genre: moving https://id.example.org/library/dune's value to "
                      "https://id.example.org/library/hardback does not fire the shape for https://id.example.org/library/Genre", out)

    def test_one_code_list_cannot_test_its_shape(self):
        data = CODED.replace("lib:format lib:hardback ", "").replace("lib:Format a skos:ConceptScheme .\n", "") \
            .replace("lib:hardback a skos:Concept ; skos:inScheme lib:Format .\n", "")
        code, out = self.check(data, GENRE_SHAPE)
        self.assertEqual(code, 1)
        self.assertIn("FAIL bites: https://id.example.org/library/genre: no concept of another code list to test its shapes with", out)

    def test_a_scheme_left_out_is_not_a_code_list(self):
        code, out = self.check(CODED, GENRE_SHAPE, "--not-code-list=https://id.example.org/library/Format")
        self.assertEqual(code, 1)  # genre can no longer be tested against another list
        self.assertNotIn("library/format", out)

    def test_a_literal_value_fails_same_list(self):
        code, out = self.check(CODED + 'lib:emma a lib:Book ; lib:genre "prose" .\n', GENRE_SHAPE + FORMAT_SHAPE)
        self.assertEqual(code, 1)
        self.assertIn("FAIL same-list: https://id.example.org/library/genre on https://id.example.org/library/emma is prose", out)

    def test_a_value_with_no_list_fails_same_list(self):
        code, out = self.check(CODED + "lib:emma a lib:Book ; lib:genre lib:unlisted .\n", GENRE_SHAPE + FORMAT_SHAPE)
        self.assertEqual(code, 1)
        self.assertIn("is https://id.example.org/library/unlisted, which is not in https://id.example.org/library/Genre", out)

    def test_a_blank_node_concept_makes_a_code_list_property(self):
        data = CODED + "lib:emma a lib:Book ; lib:shelf [ a skos:Concept ; skos:inScheme lib:Format ] .\n"
        code, out = self.check(data, GENRE_SHAPE + FORMAT_SHAPE)
        self.assertEqual(code, 1)
        self.assertIn("FAIL covered: https://id.example.org/library/shelf", out)

    def test_two_pinned_lists_both_apply(self):
        second = "lib:GenreAlso a sh:NodeShape ; sh:targetObjectsOf lib:genre ;\n    sh:property [ sh:path skos:inScheme ; sh:hasValue lib:Format ] .\n"
        code, out = self.check(CODED, GENRE_SHAPE + second + FORMAT_SHAPE)
        self.assertEqual(code, 1)
        self.assertIn("FAIL same-list: https://id.example.org/library/genre on https://id.example.org/library/dune is "
                      "https://id.example.org/library/fiction, which is not in https://id.example.org/library/Format", out)

    def test_the_test_value_leaves_every_named_list(self):
        # fiction is in Genre and in Format; it sorts first but meets the genre pin, so it is never the witness.
        data = CODED + "lib:fiction skos:inScheme lib:Format .\nlib:afterword a skos:Concept ; skos:inScheme lib:Format .\n"
        code, out = self.check(data, GENRE_SHAPE + FORMAT_SHAPE)
        self.assertEqual(code, 0, out)

    def test_another_shape_firing_is_not_a_bite(self):
        # The genre pin is deactivated; a class constraint fires on the moved value instead. Not proof.
        dead = GENRE_SHAPE.replace("sh:targetObjectsOf lib:genre ;", "sh:targetObjectsOf lib:genre ; sh:deactivated true ;")
        other = "lib:GenreClass a sh:NodeShape ; sh:targetObjectsOf lib:genre ; sh:class lib:GenreTerm .\n"
        data = CODED + "lib:fiction a lib:GenreTerm .\nlib:poetry a lib:GenreTerm .\n"
        code, out = self.check(data, dead + other + FORMAT_SHAPE)
        self.assertEqual(code, 1)
        self.assertIn("does not fire the shape for https://id.example.org/library/Genre", out)

    def test_another_constraint_on_the_carrier_is_not_a_bite(self):
        # The nested pin is deactivated; sh:class on the same property shape fires on the moved value instead.
        carrier = FORMAT_SHAPE.replace("sh:node lib:InFormat ]", "sh:node lib:InFormat ; sh:class lib:FormatTerm ]") \
            .replace("lib:InFormat a sh:NodeShape ;", "lib:InFormat a sh:NodeShape ; sh:deactivated true ;")
        data = CODED + "lib:hardback a lib:FormatTerm .\n"
        code, out = self.check(data, GENRE_SHAPE + carrier)
        self.assertEqual(code, 1)
        self.assertIn("does not fire the shape for https://id.example.org/library/Format", out)

    def test_a_result_the_shape_already_gave_is_not_a_bite(self):
        # The sh:in shape targets only emma, whose genre is already wrong; moving dune's value reaches no
        # shape, so the result the shape already reports for emma must not count as the bite.
        only_emma = ("lib:EmmaGenre a sh:NodeShape ; sh:targetNode lib:emma ;\n"
                     "    sh:property [ sh:path lib:genre ; sh:in ( lib:fiction lib:poetry ) ] .\n")
        data = CODED + "lib:emma a lib:Book ; lib:genre lib:hardback .\n"
        code, out = self.check(data, only_emma + FORMAT_SHAPE)
        self.assertEqual(code, 1)
        self.assertIn("FAIL bites: https://id.example.org/library/genre: moving https://id.example.org/library/dune's value", out)

    def test_a_rule_in_the_shapes_fails(self):
        rule = ("lib:Fix a sh:NodeShape ; sh:targetClass lib:Book ;\n"
                "    sh:rule [ a sh:TripleRule ; sh:subject sh:this ; sh:predicate lib:genre ; sh:object lib:fiction ] .\n")
        code, out = self.check(CODED, GENRE_SHAPE + FORMAT_SHAPE + rule)
        self.assertEqual(code, 1)
        self.assertIn("FAIL bites: the shapes hold a sh:rule", out)

    def test_an_in_list_is_a_membership_constraint(self):
        in_list = ("lib:BookGenre a sh:NodeShape ; sh:targetClass lib:Book ;\n"
                   "    sh:property [ sh:path lib:genre ; sh:in ( lib:fiction lib:poetry ) ] .\n")
        self.assertEqual(self.check(CODED, in_list + FORMAT_SHAPE)[0], 0)
        code, out = self.check(CODED + "lib:emma a lib:Book ; lib:genre lib:hardback .\n", in_list + FORMAT_SHAPE)
        self.assertEqual(code, 1)
        self.assertIn("which is not in sh:in (https://id.example.org/library/fiction https://id.example.org/library/poetry)", out)

    def test_every_value_already_wrong_reports_same_list_only(self):
        data = CODED.replace("lib:genre lib:fiction", "lib:genre lib:hardback")
        code, out = self.check(data, GENRE_SHAPE + FORMAT_SHAPE)
        self.assertEqual(code, 1)
        self.assertIn("FAIL same-list", out)
        self.assertNotIn("FAIL bites", out)

    def test_the_skill_skeletons_pass(self):
        # A loan with a state from the skeleton's loan-state list, so the sh:in shape is exercised, and a
        # second code list, so the bite check has a concept from another list to move the state to.
        templates = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates")
        loan = self.write("loan.ttl", "lib:loan1 a lib:Loan ; lib:loanState lib:on-loan .\n"
                                      "lib:Format a skos:ConceptScheme .\n"
                                      "lib:hardback a skos:Concept ; skos:inScheme lib:Format .\n")
        code, out = run_main(check_code_lists.main, ["--shapes", os.path.join(templates, "shapes-skeleton.ttl"),
                                                      "--data", os.path.join(templates, "ontology-skeleton.ttl"), loan,
                                                      "--not-code-list=https://id.example.org/library/lending"])
        self.assertEqual(code, 0, out)
        self.assertIn("(1 properties)", out)

    def test_an_unreadable_file_is_a_usage_error(self):
        self.assertEqual(run_main(check_code_lists.main, ["--shapes", self.write("s.ttl", GENRE_SHAPE),
                                                          "--data", self.write("d.ttl", "lib:x a .\n")])[0], 2)

    def test_definitions_alone_do_not_pass(self):
        # The module declares its lists and no instance (domain-model.md, rule 9), so no property takes a value:
        # the run must fail, not pass over nothing.
        definitions = "\n".join(l for l in CODED.split("\n") if "lib:dune" not in l)
        code, out = self.check(definitions, GENRE_SHAPE + FORMAT_SHAPE)
        self.assertEqual(code, 1)
        self.assertIn("FAIL covered: no property takes a value from any code list (https://id.example.org/library/Format, "
                      "https://id.example.org/library/Genre); pass the shapes tests' illustration file as --data too", out)

    def test_the_skeleton_alone_does_not_pass(self):
        templates = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates")
        code, out = run_main(check_code_lists.main, ["--shapes", os.path.join(templates, "shapes-skeleton.ttl"),
                                                      "--data", os.path.join(templates, "ontology-skeleton.ttl"),
                                                      "--not-code-list=https://id.example.org/library/lending"])
        self.assertEqual(code, 1)
        self.assertIn("FAIL covered: no property takes a value from any code list (https://id.example.org/library/loan-state)", out)

    def test_a_shaped_property_no_value_exercises_fails(self):
        # genre is illustrated; format has a membership shape (deactivated, so it would never bite) and no value.
        data = CODED.replace(" ; lib:format lib:hardback", "")
        dead = FORMAT_SHAPE.replace("lib:InFormat a sh:NodeShape ;", "lib:InFormat a sh:NodeShape ; sh:deactivated true ;")
        code, out = self.check(data, GENRE_SHAPE + dead)
        self.assertEqual(code, 1)
        self.assertIn("FAIL unexercised: https://id.example.org/library/format has a membership shape but no value in the data takes it", out)
        self.assertNotIn("library/genre", out)
        self.assertEqual(self.check(data, GENRE_SHAPE + FORMAT_SHAPE)[0], 1)

    def test_a_shaped_property_whose_value_is_in_no_list_fails_same_list(self):
        # The value exists, so this is not "unexercised": same-list must name it.
        data = CODED.replace("lib:format lib:hardback", "lib:format lib:notAConcept")
        code, out = self.check(data, GENRE_SHAPE + FORMAT_SHAPE)
        self.assertEqual(code, 1)
        self.assertIn("FAIL same-list: https://id.example.org/library/format on https://id.example.org/library/dune is "
                      "https://id.example.org/library/notAConcept", out)
        self.assertNotIn("unexercised", out)

    def test_with_no_code_list_declared_same_list_and_unexercised_still_run(self):
        in_list = ("lib:BookGenre a sh:NodeShape ; sh:targetClass lib:Book ;\n"
                   "    sh:property [ sh:path lib:genre ; sh:in ( lib:fiction lib:poetry ) ] .\n")
        code, out = self.check("lib:dune a lib:Book ; lib:genre lib:notAConcept .\n", in_list)
        self.assertEqual(code, 1)
        self.assertIn("FAIL same-list: https://id.example.org/library/genre on https://id.example.org/library/dune is "
                      "https://id.example.org/library/notAConcept", out)
        code, out = self.check("lib:dune a lib:Book .\n", in_list)
        self.assertEqual(code, 1)
        self.assertIn("FAIL unexercised: https://id.example.org/library/genre", out)
        code, out = self.check("lib:dune a lib:Book ; lib:genre lib:fiction .\n", in_list)
        self.assertEqual(code, 0, out)  # a good value: no second list exists, so no bite test applies

    def test_a_module_with_no_code_list_passes_with_no_property(self):
        code, out = self.check("lib:dune a lib:Book ; rdfs:label \"Dune\"@en .\n", "")
        self.assertEqual(code, 0, out)
        self.assertIn("(0 properties)", out)
        code, out = self.check(CODED.replace("lib:genre lib:fiction ; lib:format lib:hardback", "rdfs:label \"Dune\"@en"), "",
                               "--not-code-list=https://id.example.org/library/Genre", "--not-code-list=https://id.example.org/library/Format")
        self.assertEqual(code, 0, out)


if __name__ == "__main__":
    unittest.main()
