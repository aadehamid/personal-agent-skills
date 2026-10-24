"""Tests for run_regression.py, check_shapes.py, check_packages.py and check_code_lists.py.

Run from this folder:
  uv run --no-project --with rdflib --with pyyaml --with pyshacl python3 -m unittest test_validation

Each check gets a clean case that passes and one planted error per failure it claims, asserting the
failure names what was planted, so a check that passes vacuously, or fails for another reason, fails here.
The fixtures are a small library ontology, as in the templates.
"""
import contextlib
import hashlib
import io
import json
import os
import shutil
import tempfile
import textwrap
import unittest

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


if __name__ == "__main__":
    unittest.main()
