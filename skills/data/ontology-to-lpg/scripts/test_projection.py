"""Tests for check_projection_rules.py and in_graph_shapes.py, on the library templates.

Run from this folder:
  uv run --no-project --with rdflib --with pyshacl python3 -m unittest test_projection

Each one-break test breaks a template in one way and asserts that exactly the named check fires
with its message, so a check that passes vacuously, or fires for the wrong reason, fails here.
No test needs Neo4j or Java.
"""
import contextlib
import io
import json
import os
import tempfile
import unittest

from pyshacl import validate
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import OWL, RDF, RDFS, SH, XSD

import check_projection_rules as cpr
import in_graph_shapes as igs

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = os.path.join(HERE, "..", "templates")
MODULE = os.path.join(TEMPLATES, "library-module.ttl")
SHAPES = os.path.join(TEMPLATES, "library-shapes.ttl")
CONFIG = os.path.join(TEMPLATES, "projection-config.json")
LIB = "https://id.example.org/library/"
AUTHORSHIP = URIRef(LIB + "authorship/W-0042-P-17")
WORK = URIRef(LIB + "work/W-0042")
COPY = URIRef(LIB + "copy/C-00420001")


def lib(name):
    return URIRef(LIB + name)


def module():
    return Graph().parse(MODULE, format="turtle")


def shapes():
    return Graph().parse(SHAPES, format="turtle")


def raw_config():
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f)


def config(change=None):
    raw = raw_config()
    if change:
        change(raw)
    return cpr.Config(raw)


def run_main(main, argv):
    """Call a script's main() and return (exit code, everything it printed)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = main(argv)
    return code, out.getvalue()


class OneBreak:
    """assertOnly: every failure has the expected check name, and one has the exact message."""

    def assertOnly(self, fails, name, message):
        self.assertTrue(fails, f"expected {name!r}: {message!r}, got no failure")
        self.assertEqual({n for n, _ in fails}, {name}, f"unexpected checks fired: {fails}")
        self.assertIn(message, [m for _, m in fails])


class Templates(unittest.TestCase):
    def test_templates_pass_every_rule(self):
        self.assertEqual(cpr.check(module(), shapes(), config()), [])

    def test_module_conforms_to_its_shapes(self):
        conforms, _, text = validate(module(), shacl_graph=shapes())
        self.assertTrue(conforms, text)

    def test_namespace_splits_as_rdf4j_does(self):
        self.assertEqual(cpr.namespace(LIB + "barcode"), LIB)
        self.assertEqual(cpr.namespace(LIB + "work/W-0042"), LIB + "work/")
        self.assertEqual(cpr.namespace("https://id.example.org/v#a/b"), "https://id.example.org/v#")
        self.assertEqual(cpr.namespace("urn:isbn:0451450523"), "urn:isbn:")


class Rules(OneBreak, unittest.TestCase):
    def broken(self, mutate_data=None, mutate_shapes=None, cfg=None):
        g, s = module(), shapes()
        if mutate_data:
            mutate_data(g)
        if mutate_shapes:
            mutate_shapes(s)
        return cpr.check(g, s, cfg or config())

    # Rule 1
    def test_two_kinds(self):
        self.assertOnly(self.broken(lambda g: g.add((lib("barcode"), RDF.type, OWL.AnnotationProperty))), "rule-1",
                        "Rule 1: lib:barcode has 2 kinds; it needs exactly one of owl:ObjectProperty, "
                        "owl:DatatypeProperty and owl:AnnotationProperty")

    def test_bare_rdf_property(self):
        def change(g):
            g.remove((lib("barcode"), RDF.type, OWL.DatatypeProperty))
            g.add((lib("barcode"), RDF.type, RDF.Property))
        self.assertOnly(self.broken(change), "rule-1",
                        "Rule 1: lib:barcode has 0 kinds; it needs exactly one of owl:ObjectProperty, "
                        "owl:DatatypeProperty and owl:AnnotationProperty")

    def test_undeclared_own_predicate(self):
        # Used in the data but never declared: no kind. Its shape exists, so only Rule 1 fires.
        def data(g):
            g.add((COPY, lib("loanCount"), Literal(3)))
        def shape(s):
            s.add((lib("CopyShape-loanCount"), SH.path, lib("loanCount")))
            s.add((lib("CopyShape-loanCount"), SH.maxCount, Literal(1)))
        self.assertOnly(self.broken(data, shape), "rule-1",
                        "Rule 1: lib:loanCount has 0 kinds; it needs exactly one of owl:ObjectProperty, "
                        "owl:DatatypeProperty and owl:AnnotationProperty")

    def test_no_range(self):
        self.assertOnly(self.broken(lambda g: g.remove((lib("copyOf"), RDFS.range, None))), "rule-1",
                        "Rule 1: lib:copyOf has no single concrete range")

    def test_two_ranges(self):
        self.assertOnly(self.broken(lambda g: g.add((lib("copyOf"), RDFS.range, lib("Copy")))), "rule-1",
                        "Rule 1: lib:copyOf has no single concrete range")

    def test_literal_range(self):
        self.assertOnly(self.broken(lambda g: g.set((lib("barcode"), RDFS.range, RDFS.Literal))), "rule-1",
                        "Rule 1: lib:barcode has no single concrete range")

    def test_datatype_property_with_class_range(self):
        self.assertOnly(self.broken(lambda g: g.set((lib("barcode"), RDFS.range, lib("Copy")))), "rule-1",
                        "Rule 1: lib:barcode is a datatype property but its range lib:Copy is not a datatype")

    def test_object_property_with_datatype_range(self):
        self.assertOnly(self.broken(lambda g: g.set((lib("copyOf"), RDFS.range, XSD.string))), "rule-1",
                        "Rule 1: lib:copyOf is an object property but its range xsd:string is a datatype")

    def test_annotation_property_needs_no_range(self):
        g = module()
        self.assertEqual(list(g.objects(lib("shelfNote"), RDFS.range)), [])
        self.assertEqual(cpr.check(g, shapes(), config()), [])

    # Rule 2
    def test_property_without_cardinality(self):
        def change(s):
            s.remove((lib("CopyShape-barcode"), SH.maxCount, None))
            s.remove((lib("CopyShape-barcode"), SH.minCount, None))
        self.assertOnly(self.broken(mutate_shapes=change), "rule-2", "Rule 2: no cardinality stated for lib:barcode")

    def test_annotation_property_without_cardinality(self):
        self.assertOnly(self.broken(mutate_shapes=lambda s: s.remove((lib("CopyShape-shelfNote"), SH.maxCount, None))),
                        "rule-2", "Rule 2: no cardinality stated for lib:shelfNote")

    def test_min_count_zero_states_an_optional_list(self):
        s = shapes()
        self.assertIn((lib("WorkShape-altTitle"), SH.minCount, Literal(0)), s)
        self.assertNotIn((lib("WorkShape-altTitle"), SH.maxCount, None), s)
        self.assertEqual(cpr.check(module(), s, config()), [])

    # Rule 3
    def test_blank_node(self):
        b = BNode("b1")
        self.assertOnly(self.broken(lambda g: g.add((COPY, lib("shelfNote"), b))), "rule-3",
                        f"Rule 3: blank node in {LIB}copy/C-00420001 lib:shelfNote _:b1")

    def test_unregistered_namespace(self):
        def change(g):
            g.add((COPY, URIRef("https://vocab.example.net/terms#condition"), Literal("good")))
        self.assertOnly(self.broken(change), "rule-3",
                        "Rule 3: no fixed prefix for the namespace https://vocab.example.net/terms#")

    def test_unregistered_type_namespace(self):
        self.assertOnly(self.broken(lambda g: g.add((COPY, RDF.type, URIRef("https://vocab.example.net/terms#Item")))),
                        "rule-3", "Rule 3: no fixed prefix for the namespace https://vocab.example.net/terms#")

    def test_own_namespace_without_prefix(self):
        cfg = config(lambda r: r["own_namespaces"].append("https://id.example.org/archive/"))
        self.assertOnly(self.broken(cfg=cfg), "rule-3",
                        "Rule 3: no fixed prefix for the own namespace https://id.example.org/archive/")

    def test_two_prefixes_for_one_namespace(self):
        cfg = config(lambda r: r["prefixes"].update({"library": LIB}))
        self.assertOnly(self.broken(cfg=cfg), "rule-3",
                        f"Rule 3: the namespace {LIB} has 2 prefixes: lib, library")

    # Rule 4a
    def test_two_values_for_an_end(self):
        self.assertOnly(self.broken(lambda g: g.add((AUTHORSHIP, lib("authorshipAgent"), lib("person/P-18")))),
                        "rule-4a", f"Rule 4a: {AUTHORSHIP} has 2 values of lib:authorshipAgent; "
                                   "it needs exactly one")

    def test_missing_end(self):
        # The shape would also fire; the rule check reports it without SHACL.
        self.assertOnly(self.broken(lambda g: g.remove((AUTHORSHIP, lib("authorshipAgent"), None))),
                        "rule-4a", f"Rule 4a: {AUTHORSHIP} has 0 values of lib:authorshipAgent; "
                                   "it needs exactly one")

    def test_two_inverse_links(self):
        self.assertOnly(self.broken(lambda g: g.add((lib("work/W-0099"), lib("hasAuthorship"), AUTHORSHIP))),
                        "rule-4a", f"Rule 4a: {AUTHORSHIP} is the object of 2 lib:hasAuthorship "
                                   "links; it needs exactly one")

    def test_no_inverse_link(self):
        self.assertOnly(self.broken(lambda g: g.remove((WORK, lib("hasAuthorship"), AUTHORSHIP))),
                        "rule-4a", f"Rule 4a: {AUTHORSHIP} is the object of 0 lib:hasAuthorship "
                                   "links; it needs exactly one")

    # Rule 5
    def test_shared_lpg_name(self):
        lpg = "https://id.example.org/lpg-mapping#"
        def cfg_change(r):
            r["prefixes"]["lpg"] = lpg
            r["lpg_name_property"] = "lpg:name"
        def change(g):
            g.add((lib("copyOf"), URIRef(lpg + "name"), Literal("OF")))
            g.add((lib("hasAuthorship"), URIRef(lpg + "name"), Literal("OF")))
        self.assertOnly(self.broken(change, cfg=config(cfg_change)), "rule-5",
                        "Rule 5: the name 'OF' is given to lib:copyOf, lib:hasAuthorship")

    def test_distinct_lpg_names_pass(self):
        lpg = "https://id.example.org/lpg-mapping#"
        def cfg_change(r):
            r["prefixes"]["lpg"] = lpg
            r["lpg_name_property"] = "lpg:name"
        def change(g):
            g.add((lib("copyOf"), URIRef(lpg + "name"), Literal("COPY_OF")))
            g.add((lib("hasAuthorship"), URIRef(lpg + "name"), Literal("HAS_AUTHORSHIP")))
        self.assertEqual(self.broken(change, cfg=config(cfg_change)), [])


class ReleaseExceptions(OneBreak, unittest.TestCase):
    GAP = "Rule 1: lib:copyOf has no single concrete range"

    def gap_data(self):
        g = module()
        g.remove((lib("copyOf"), RDFS.range, None))
        return g

    def test_listed_gap_passes(self):
        cfg = config(lambda r: r["release_exceptions"].update(
            {self.GAP: "lending 1.1.0 declares no range; the next lending release adds rdfs:range lib:Work"}))
        self.assertEqual(cpr.check(self.gap_data(), shapes(), cfg), [])

    def test_unlisted_gap_fails(self):
        self.assertOnly(cpr.check(self.gap_data(), shapes(), config()), "rule-1", self.GAP)

    def test_stale_exception_fails(self):
        cfg = config(lambda r: r["release_exceptions"].update({self.GAP: "closed by lending 1.1.0"}))
        self.assertOnly(cpr.check(module(), shapes(), cfg), "exceptions",
                        f"listed release exception no longer occurs: {self.GAP}")

    def test_exception_without_a_fix_fails(self):
        cfg = config(lambda r: r["release_exceptions"].update({self.GAP: " "}))
        self.assertOnly(cpr.check(self.gap_data(), shapes(), cfg), "exceptions",
                        f"listed release exception has no fix: {self.GAP}")

    def test_only_the_listed_message_is_excepted(self):
        # A second gap on another property is not covered by the first one's entry.
        cfg = config(lambda r: r["release_exceptions"].update({self.GAP: "the next lending release adds a range"}))
        g = self.gap_data()
        g.remove((lib("authorshipAgent"), RDFS.range, None))
        self.assertOnly(cpr.check(g, shapes(), cfg), "rule-1", "Rule 1: lib:authorshipAgent has no single concrete range")


class Packages(OneBreak, unittest.TestCase):
    def releases(self, layout):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for module_name, versions in layout.items():
            for v in versions:
                os.makedirs(os.path.join(tmp.name, module_name, v))
        return tmp.name

    def test_pin_at_newest_passes(self):
        folder = self.releases({"lending": ["1.0.0", "1.1.0", "1.2.0-rc.1"]})
        self.assertEqual(cpr.check(module(), shapes(), config(), folder), [])

    def test_newer_release_fails(self):
        folder = self.releases({"lending": ["1.0.0", "1.1.0", "1.10.0"]})
        self.assertOnly(cpr.check(module(), shapes(), config(), folder), "inputs",
                        "Inputs: lending is pinned at 1.1.0 but its newest release is 1.10.0")

    def test_unpinned_module_fails(self):
        folder = self.releases({"lending": ["1.1.0"], "catalogue": ["1.0.0"]})
        self.assertOnly(cpr.check(module(), shapes(), config(), folder), "inputs",
                        "Inputs: catalogue has a release (1.0.0) but no pin")

    def test_pin_without_folder_fails(self):
        folder = self.releases({"lending": ["1.0.0"]})
        self.assertOnly(cpr.check(module(), shapes(), config(), folder), "inputs",
                        "Inputs: lending is pinned at 1.1.0, which has no release folder")


class CommandLine(unittest.TestCase):
    def args(self, *extra):
        return ["--config", CONFIG, "--shapes", SHAPES, *extra, MODULE]

    def test_pass_is_0(self):
        code, out = run_main(cpr.main, self.args())
        self.assertEqual(code, 0, out)
        self.assertIn("all projection rules pass", out)

    def test_failure_is_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = raw_config()
            raw["release_exceptions"] = {"Rule 1: lib:copyOf has no single concrete range": "never closes"}
            path = os.path.join(tmp, "config.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(raw, f)
            code, out = run_main(cpr.main, ["--config", path, "--shapes", SHAPES, MODULE])
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL exceptions: listed release exception no longer occurs", out)

    def test_bad_arguments_are_2(self):
        self.assertEqual(run_main(cpr.main, [MODULE])[0], 2)
        self.assertEqual(run_main(cpr.main, ["--config", CONFIG])[0], 2)
        self.assertEqual(run_main(cpr.main, ["--bogus", MODULE])[0], 2)

    def test_bad_config_is_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = raw_config()
            raw["rule4"] = "4c"
            path = os.path.join(tmp, "config.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(raw, f)
            code, out = run_main(cpr.main, ["--config", path, MODULE])
        self.assertEqual(code, 2, out)
        self.assertIn('"rule4"', out)

    def test_unknown_prefix_in_config_is_2(self):
        with self.assertRaises(cpr.ConfigError):
            config(lambda r: r["qualified_relations"][0].update({"class": "nope:Authorship"}))

    def test_unreadable_file_is_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = os.path.join(tmp, "bad.ttl")
            with open(bad, "w", encoding="utf-8") as f:
                f.write("this is not turtle .")
            self.assertEqual(run_main(cpr.main, ["--config", CONFIG, bad])[0], 2)


class InGraphShapes(unittest.TestCase):
    def setUp(self):
        self.full = shapes()
        self.sub, self.dropped = igs.subset(self.full)

    def test_drops_what_n10s_cannot_run(self):
        for p in (SH.pattern, SH.languageIn, SH.message, SH.severity):
            self.assertNotIn((None, p, None), self.sub)
        self.assertNotIn((None, SH.datatype, RDF.langString), self.sub)

    def test_drops_a_literal_in_list_and_keeps_an_iri_list(self):
        lists = [list(Collection(self.sub, o)) for o in self.sub.objects(None, SH["in"])]
        self.assertEqual(lists, [[lib("author"), lib("illustrator")]])
        self.assertNotIn((lib("AuthorshipShape-position"), SH["in"], None), self.sub)

    def test_leaves_no_orphaned_list_cells(self):
        heads = set(self.sub.objects(None, SH["in"]))
        cells = set(heads)
        for h in heads:
            node = h
            while node != RDF.nil:
                node = self.sub.value(node, RDF.rest)
                cells.add(node)
        orphans = {s for s in self.sub.subjects(RDF.first, None)} - cells
        self.assertEqual(orphans, set())

    def test_keeps_cardinality_and_targets(self):
        self.assertIn((lib("CopyShape-barcode"), SH.maxCount, Literal(1)), self.sub)
        self.assertIn((lib("CopyShape"), SH.targetClass, lib("Copy")), self.sub)

    def test_records_each_drop_with_its_reason(self):
        reasons = {(str(s), str(p)): r for s, p, r in self.dropped}
        self.assertIn("whole string", reasons[(LIB + "CopyShape-barcode", str(SH.pattern))])
        self.assertIn("as strings", reasons[(LIB + "AuthorshipShape-position", str(SH["in"]))])
        self.assertIn((LIB + "WorkShape-title", str(SH.languageIn)), reasons)

    def test_drops_a_node_shape_without_a_target_class(self):
        full = shapes()
        full.add((lib("OrphanShape"), RDF.type, SH.NodeShape))
        full.add((lib("OrphanShape"), SH.targetSubjectsOf, lib("copyOf")))
        full.add((lib("OrphanShape"), SH.property, lib("OrphanShape-x")))
        full.add((lib("OrphanShape-x"), SH.path, lib("copyOf")))
        full.add((lib("OrphanShape-x"), SH.minCount, Literal(1)))
        sub, dropped = igs.subset(full)
        self.assertNotIn((lib("OrphanShape"), None, None), sub)
        self.assertNotIn((lib("OrphanShape-x"), None, None), sub)
        self.assertIn(lib("OrphanShape"), {s for s, _, _ in dropped})

    def test_the_subset_still_catches_a_mutant(self):
        # The in-graph check must be able to fail: remove a required value and expect a violation.
        data = module()
        conforms, _, _ = validate(data, shacl_graph=self.sub)
        self.assertTrue(conforms)
        data.remove((COPY, lib("barcode"), None))
        conforms, report, _ = validate(data, shacl_graph=self.sub)
        self.assertFalse(conforms)
        self.assertIn((None, SH.resultPath, lib("barcode")), report)

    def test_shacl_searches_an_unanchored_pattern(self):
        # SHACL (through SPARQL REGEX and fn:matches) searches the string, so "\S" passes a
        # multi-character value in pySHACL; n10s's full-string match would fail it. That is why
        # patterns stay in the pre-load check and are anchored.
        s = shapes()
        s.set((lib("PersonShape-name"), SH.pattern, Literal("\\S")))
        conforms, _, text = validate(module(), shacl_graph=s)
        self.assertTrue(conforms, text)

    def test_command_line_writes_turtle(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "shapes-in-graph.ttl")
            code, out = run_main(igs.main, ["--output", out_path, SHAPES])
            self.assertEqual(code, 0, out)
            self.assertIn("dropped lib:CopyShape-barcode sh:pattern", out)
            self.assertEqual(len(Graph().parse(out_path, format="turtle")), len(self.sub))
        self.assertEqual(run_main(igs.main, [SHAPES])[0], 2)


if __name__ == "__main__":
    unittest.main()
