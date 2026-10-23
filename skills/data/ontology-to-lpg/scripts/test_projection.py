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
import shutil
import tempfile
import unittest

from pyshacl import validate
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import OWL, RDF, RDFS, SH, XSD

import build
import check_projection_rules as cpr
import in_graph_shapes as igs
import load_verify as lv
import validate_data as vd

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
    """assertOnly: the break produces exactly one failure, with this check name and this message."""

    def assertOnly(self, fails, name, message):
        self.assertEqual(fails, [(name, message)])


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
            s.add((lib("CopyShape"), SH.property, lib("CopyShape-loanCount")))
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
                        "Rule 1: lib:barcode is a datatype property but its range lib:Copy is not a datatype the XSD to Cypher table maps")

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


class ReviewRoundOne(OneBreak, unittest.TestCase):
    """One test per finding of the first independent review; each failed on commit a056da9."""

    def broken(self, mutate_data=None, mutate_shapes=None, cfg=None):
        g, s = module(), shapes()
        if mutate_data:
            mutate_data(g)
        if mutate_shapes:
            mutate_shapes(s)
        return cpr.check(g, s, cfg or config())

    # 1: a property known only from its domain and range is still checked
    def test_domain_only_property_is_checked(self):
        def change(g):
            g.add((lib("secretLink"), RDFS.domain, lib("Copy")))
            g.add((lib("secretLink"), RDFS.range, lib("Work")))
        # Rule 1 checks it; Rule 2 does not, because the data never uses it (round-two decision).
        self.assertEqual(self.broken(change), [
            ("rule-1", "Rule 1: lib:secretLink has 0 kinds; it needs exactly one of owl:ObjectProperty, "
                       "owl:DatatypeProperty and owl:AnnotationProperty")])

    # 2: a datatype range must be a row of the XSD to Cypher table
    def test_unknown_xsd_range(self):
        self.assertOnly(self.broken(lambda g: g.set((lib("barcode"), RDFS.range, XSD.notARealType))), "rule-1",
                        "Rule 1: lib:barcode is a datatype property but its range xsd:notARealType is not a "
                        "datatype the XSD to Cypher table maps")

    def test_rdf_html_range(self):
        self.assertOnly(self.broken(lambda g: g.set((lib("barcode"), RDFS.range, RDF.HTML))), "rule-1",
                        "Rule 1: lib:barcode is a datatype property but its range rdf:HTML is not a "
                        "datatype the XSD to Cypher table maps")

    def test_custom_datatype_range(self):
        def change(g):
            g.add((lib("Barcode"), RDF.type, RDFS.Datatype))
            g.set((lib("barcode"), RDFS.range, lib("Barcode")))
        self.assertOnly(self.broken(change), "rule-1",
                        "Rule 1: lib:barcode is a datatype property but its range lib:Barcode is not a "
                        "datatype the XSD to Cypher table maps")

    def test_zoned_timestamp_range_passes(self):
        self.assertEqual(self.broken(lambda g: g.set((lib("barcode"), RDFS.range, XSD.dateTimeStamp))), [])

    # 3: only a shape that a targeted node shape uses states a cardinality
    def test_unattached_shape_does_not_state_cardinality(self):
        def change(s):
            s.remove((lib("CopyShape-barcode"), SH.minCount, None))
            s.remove((lib("CopyShape-barcode"), SH.maxCount, None))
            decoy = BNode()
            s.add((decoy, SH.path, lib("barcode")))
            s.add((decoy, SH.minCount, Literal(0)))
        self.assertOnly(self.broken(mutate_shapes=change), "rule-2", "Rule 2: no cardinality stated for lib:barcode")

    # 4: every namespace a class uses needs a prefix, wherever the class appears
    def test_superclass_namespace(self):
        self.assertOnly(self.broken(lambda g: g.add((lib("Work"), RDFS.subClassOf,
                                                     URIRef("https://vocab.example.net/terms#Item")))),
                        "rule-3", "Rule 3: no fixed prefix for the namespace https://vocab.example.net/terms#")

    def test_declared_class_namespace(self):
        self.assertOnly(self.broken(lambda g: g.add((URIRef("https://vocab.example.net/terms#Widget"), RDF.type,
                                                     OWL.Class))),
                        "rule-3", "Rule 3: no fixed prefix for the namespace https://vocab.example.net/terms#")

    def test_shape_class_namespace(self):
        self.assertOnly(self.broken(mutate_shapes=lambda s: s.set((lib("CopyShape-copyOf"), SH["class"],
                                                                   URIRef("https://vocab.example.net/terms#Work")))),
                        "rule-3", "Rule 3: no fixed prefix for the namespace https://vocab.example.net/terms#")

    # 7: the round-trip refusals
    def test_string_ending_like_a_tag_is_refused(self):
        self.assertOnly(self.broken(lambda g: g.set((lib("person/P-17"), lib("name"), Literal("Spine@en")))),
                        "refusal", f'Refused: {LIB}person/P-17 lib:name "Spine@en" ends like a language tag')

    def test_inexact_decimal_is_refused(self):
        def change(g):
            g.set((lib("position"), RDFS.range, XSD.decimal))
            g.set((AUTHORSHIP, lib("position"), Literal("0.1000000000000000055", datatype=XSD.decimal)))
        fails = cpr.roundtrip_refusals(self.mutated(change), config())
        self.assertEqual(len(fails), 1)
        self.assertIn("does not survive as a double", fails[0][1])

    def mutated(self, change):
        g = module()
        change(g)
        return g

    def test_exact_decimals_survive(self):
        for lexical in ("1", "0.64", "12.5", "-3"):
            self.assertTrue(cpr.decimal_survives(lexical), lexical)
        self.assertFalse(cpr.decimal_survives("0.1000000000000000055"))

    def test_tagged_literal_is_not_refused(self):
        self.assertEqual(cpr.roundtrip_refusals(module(), config()), [])

    # 8: release exceptions cannot waive data errors
    def test_exception_cannot_waive_a_blank_node(self):
        message = f"Rule 3: blank node in {LIB}copy/C-00420001 lib:shelfNote _:b1"
        cfg = config(lambda r: r["release_exceptions"].update({message: "the next release removes it"}))
        fails = self.broken(lambda g: g.add((COPY, lib("shelfNote"), BNode("b1"))), cfg=cfg)
        self.assertEqual(fails, [("rule-3", message),
                                 ("exceptions", "a release exception cannot waive a blank node, a missing prefix, a "
                                                f"broken qualified relation, a refused value or a package pin: {message}")])

    def test_exception_cannot_waive_a_broken_qualified_relation(self):
        message = f"Rule 4a: {AUTHORSHIP} has 2 values of lib:authorshipAgent; it needs exactly one"
        cfg = config(lambda r: r["release_exceptions"].update({message: "the next release fixes it"}))
        fails = self.broken(lambda g: g.add((AUTHORSHIP, lib("authorshipAgent"), lib("person/P-18"))), cfg=cfg)
        self.assertEqual([n for n, _ in fails], ["rule-4a", "exceptions"])

    # 14: the end shapes themselves must say exactly one
    def test_end_shape_must_be_exactly_one(self):
        def change(s):
            s.remove((lib("AuthorshipShape-agent"), SH.maxCount, None))
            s.set((lib("AuthorshipShape-agent"), SH.minCount, Literal(0)))
        self.assertOnly(self.broken(mutate_shapes=change), "rule-4a",
                        "Rule 4a: no shape on lib:Authorship gives lib:authorshipAgent sh:minCount 1 and sh:maxCount 1")

    def test_inverse_end_shape_must_exist(self):
        def change(s):
            s.remove((lib("AuthorshipShape"), SH.property, lib("AuthorshipShape-work")))
        self.assertOnly(self.broken(mutate_shapes=change), "rule-4a",
                        "Rule 4a: no shape on lib:Authorship gives the inverse of lib:hasAuthorship sh:minCount 1 "
                        "and sh:maxCount 1")

    # 15: the Rule 4 choice is read, and needs its reason
    def test_rule_4b_stops_the_checker(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = raw_config()
            raw["rule4"] = "4b"
            path = os.path.join(tmp, "config.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(raw, f)
            code, out = run_main(cpr.main, ["--config", path, "--shapes", SHAPES, MODULE])
        self.assertEqual(code, 2, out)
        self.assertIn("Jena 6.1.0+ or RDF4J 6.0.0+", out)

    def test_rule_4_reason_is_required(self):
        with self.assertRaises(cpr.ConfigError):
            config(lambda r: r.pop("rule4_reason"))

    # testing gaps the review listed
    def test_blank_subject(self):
        b = BNode("s1")
        fails = self.broken(lambda g: g.add((b, RDF.type, lib("Copy"))))
        self.assertIn(("rule-3", f"Rule 3: blank node in _:s1 rdf:type lib:Copy"), fails)

    def test_resource_range(self):
        self.assertOnly(self.broken(lambda g: g.set((lib("copyOf"), RDFS.range, RDFS.Resource))), "rule-1",
                        "Rule 1: lib:copyOf has no single concrete range")

    def test_blank_range(self):
        self.assertEqual(self.broken(lambda g: g.set((lib("copyOf"), RDFS.range, BNode("u")))), [
            ("rule-1", "Rule 1: lib:copyOf has no single concrete range"),
            ("rule-3", "Rule 3: blank node in lib:copyOf rdfs:range _:u")])

    def test_second_own_namespace_is_checked(self):
        arc = "https://id.example.org/archive/"
        cfg = config(lambda r: (r["own_namespaces"].append(arc), r["prefixes"].update({"arc": arc})))
        fails = self.broken(lambda g: g.add((COPY, URIRef(arc + "boxNumber"), Literal("7"))), cfg=cfg)
        self.assertEqual([n for n, _ in fails], ["rule-1", "rule-2"])

    def test_pin_order_is_numeric(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for v in ("1.1.0", "1.9.0", "1.10.0"):
            os.makedirs(os.path.join(tmp.name, "lending", v))
        fails = cpr.check(module(), shapes(), config(lambda r: r["packages"].update({"lending": "1.9.0"})), tmp.name)
        self.assertEqual(fails, [("inputs", "Inputs: lending is pinned at 1.9.0 but its newest release is 1.10.0")])


def minimal_shape(predicate, obj):
    """A targeted node shape whose one property shape carries predicate -> obj."""
    g = Graph()
    g.add((lib("S"), RDF.type, SH.NodeShape))
    g.add((lib("S"), SH.targetClass, lib("Copy")))
    g.add((lib("S"), SH.property, lib("S-p")))
    g.add((lib("S-p"), SH.path, lib("barcode")))
    g.add((lib("S-p"), SH.minCount, Literal(1)))
    g.add((lib("S-p"), predicate, obj))
    return g


class InGraphReviewRoundOne(unittest.TestCase):
    """One test per in-graph finding of the first independent review; each failed on commit a056da9."""

    # 9: datatypes n10s throws on are dropped
    def test_datatypes_outside_the_n10s_list_are_dropped(self):
        for dt in (XSD.dateTimeStamp, XSD.long, XSD.double, XSD.token, XSD.duration):
            sub, dropped = igs.subset(minimal_shape(SH.datatype, dt))
            self.assertNotIn((lib("S-p"), SH.datatype, dt), sub, dt)
            self.assertIn((lib("S-p"), SH.datatype), {(s, p) for s, p, _ in dropped})

    def test_supported_datatypes_stay(self):
        for dt in (XSD.integer, XSD.string, XSD.date, XSD.dateTime, XSD.boolean):
            sub, _ = igs.subset(minimal_shape(SH.datatype, dt))
            self.assertIn((lib("S-p"), SH.datatype, dt), sub, dt)

    # 10: a property shape a kept node shape uses survives; sh:and is dropped and recorded
    def test_shared_property_shape_survives_an_untargeted_node(self):
        full = shapes()
        full.add((lib("Untargeted"), RDF.type, SH.NodeShape))
        full.add((lib("Untargeted"), SH.property, lib("CopyShape-barcode")))
        sub, _ = igs.subset(full)
        self.assertIn((lib("CopyShape-barcode"), SH.minCount, Literal(1)), sub)
        data = module()
        data.remove((COPY, lib("barcode"), None))
        conforms, _, _ = validate(data, shacl_graph=sub)
        self.assertFalse(conforms)

    def test_sh_and_is_dropped_and_recorded(self):
        g = minimal_shape(SH.minCount, Literal(1))
        inner = lib("Inner")
        g.add((inner, RDF.type, SH.NodeShape))
        g.add((inner, SH.property, lib("Inner-p")))
        g.add((lib("Inner-p"), SH.path, lib("copyOf")))
        g.add((lib("Inner-p"), SH.minCount, Literal(1)))
        head = BNode()
        Collection(g, head, [inner])
        g.add((lib("S"), SH["and"], head))
        sub, dropped = igs.subset(g)
        self.assertNotIn((None, SH["and"], None), sub)
        self.assertIn((lib("S"), SH["and"]), {(s, p) for s, p, _ in dropped})

    # 11: every entry of the drop list is exercised on its own
    # Written out, not read from igs.UNSUPPORTED, so deleting an entry there fails this test.
    DROPPED = (SH["not"], SH.languageIn, SH.node, SH.targetSubjectsOf, SH.targetObjectsOf, SH["and"], SH["or"],
               SH.xone, SH.target, SH.sparql, SH.pattern, SH.flags)

    def test_each_unsupported_predicate_is_dropped(self):
        for predicate in self.DROPPED:
            sub, dropped = igs.subset(minimal_shape(predicate, Literal("x")))
            self.assertNotIn((None, predicate, None), sub, predicate)
            self.assertIn((lib("S-p"), predicate), {(s, p) for s, p, _ in dropped}, predicate)
            self.assertIn((lib("S-p"), SH.minCount, Literal(1)), sub, predicate)

    def test_each_non_constraint_is_removed(self):
        for predicate in (SH.message, SH.severity):
            sub, _ = igs.subset(minimal_shape(predicate, Literal("x")))
            self.assertNotIn((None, predicate, None), sub, predicate)

    def test_targets_on_a_node_shape_are_dropped(self):
        for predicate in (SH.targetSubjectsOf, SH.targetObjectsOf):
            g = minimal_shape(SH.minCount, Literal(1))
            g.add((lib("S"), predicate, lib("copyOf")))
            sub, dropped = igs.subset(g)
            self.assertNotIn((lib("S"), predicate, None), sub)
            self.assertIn((lib("S"), predicate), {(s, p) for s, p, _ in dropped})
            self.assertIn((lib("S"), SH.targetClass, lib("Copy")), sub)

    # 13: a literal sh:hasValue is dropped; an IRI one stays
    def test_literal_has_value_is_dropped(self):
        sub, dropped = igs.subset(minimal_shape(SH.hasValue, Literal(True)))
        self.assertNotIn((None, SH.hasValue, None), sub)
        self.assertIn((lib("S-p"), SH.hasValue), {(s, p) for s, p, _ in dropped})

    def test_iri_has_value_stays(self):
        sub, _ = igs.subset(minimal_shape(SH.hasValue, lib("author")))
        self.assertIn((lib("S-p"), SH.hasValue, lib("author")), sub)

    # 23: the pattern reason says where patterns are checked
    def test_pattern_reason_names_the_pre_load_check(self):
        _, dropped = igs.subset(shapes())
        reasons = {(str(s), str(p)): r for s, p, r in dropped}
        self.assertIn("checked before the load only", reasons[(LIB + "CopyShape-barcode", str(SH.pattern))])

    def test_a_class_typed_node_shape_is_kept(self):
        # rdfs:Class, the implicit target n10s reads (review round 2, #10: owl:Class alone is not one).
        g = Graph()
        g.add((lib("Copy"), RDF.type, RDFS.Class))
        g.add((lib("Copy"), RDF.type, SH.NodeShape))
        g.add((lib("Copy"), SH.property, lib("C-p")))
        g.add((lib("C-p"), SH.path, lib("barcode")))
        g.add((lib("C-p"), SH.minCount, Literal(1)))
        sub, _ = igs.subset(g)
        self.assertIn((lib("C-p"), SH.minCount, Literal(1)), sub)


class Build(unittest.TestCase):
    def test_sorted_nt_is_byte_ordered_and_unique(self):
        g = Graph()
        g.add((lib("b"), lib("p"), Literal("Z")))
        g.add((lib("a"), lib("p"), Literal("é")))
        g.add((lib("a"), lib("p"), Literal("a")))
        lines = build.sorted_nt(g).splitlines()
        self.assertEqual(lines, sorted(set(lines), key=lambda x: x.encode("utf-8")))
        self.assertEqual(len(lines), 3)

    def test_inferred_keeps_domain_types_and_drops_declarations(self):
        given = module()
        reasoned = module()
        w43 = lib("work/W-0043")
        reasoned.add((w43, RDF.type, lib("Work")))
        reasoned.add((w43, RDF.type, OWL.NamedIndividual))
        reasoned.add((w43, RDF.type, OWL.Thing))
        reasoned.add((lib("Book"), RDFS.subClassOf, OWL.Thing))
        reasoned.add((BNode(), RDF.type, OWL.Restriction))
        self.assertEqual(set(build.inferred(given, reasoned)), {(w43, RDF.type, lib("Work"))})

    def test_template_has_an_inference_to_keep(self):
        g = module()
        self.assertIn((lib("Book"), RDFS.subClassOf, lib("Work")), g)
        self.assertIn((lib("work/W-0043"), RDF.type, lib("Book")), g)
        self.assertNotIn((lib("work/W-0043"), RDF.type, lib("Work")), g)

    def test_fingerprint_is_the_hash_of_both_files_concatenated(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = os.path.join(tmp, "loadable.nt"), os.path.join(tmp, "inferred.nt")
            with open(a, "wb") as f:
                f.write(b"<x> <y> <z> .\n")
            with open(b, "wb") as f:
                f.write(b"")
            man = build.manifest(config(), [MODULE], [SHAPES], a, b)
        import hashlib
        self.assertEqual(man["input_fingerprint"], hashlib.sha256(b"<x> <y> <z> .\n").hexdigest())
        self.assertEqual(man["shapes_fingerprint"], hashlib.sha256(open(SHAPES, "rb").read()).hexdigest())
        self.assertEqual(man["rule4"], "4a")

    def test_manifest_verify_fails_when_an_input_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            loadable, inferred_path = os.path.join(tmp, "loadable.nt"), os.path.join(tmp, "inferred.nt")
            out = os.path.join(tmp, "manifest.json")
            self.assertEqual(run_main(build.main, ["loadable", "--output", loadable, MODULE])[0], 0)
            open(inferred_path, "w").close()
            args = ["manifest", "--config", CONFIG, "--shapes", SHAPES, "--loadable", loadable,
                    "--inferred", inferred_path, "--output", out, MODULE]
            self.assertEqual(run_main(build.main, args)[0], 0)
            self.assertEqual(run_main(build.main, args + ["--verify"])[0], 0)
            with open(inferred_path, "w") as f:
                f.write(f"<{LIB}work/W-0043> <{RDF.type}> <{LIB}Work> .\n")
            code, text = run_main(build.main, args + ["--verify"])
            self.assertEqual(code, 1, text)
            self.assertIn("is not current", text)

    def good_report(self, man):
        return {"input_fingerprint": man["input_fingerprint"], "shapes_fingerprint": man["shapes_fingerprint"],
                "shacl_violations_in_graph": 0, "in_graph_mutant_violations": 1, "roundtrip_lost": 0,
                "roundtrip_added": 0, "determinism_hash_sorted": "h", "determinism_hash_shuffled": "h",
                "in_graph_shape_constraints": 9, "shapes_import_rows": 9,
                "mutant": {"focus": "x", "removed": "k", "violations": 1, "after_restore": 0}}

    def test_check_report(self):
        man = {"input_fingerprint": "f", "shapes_fingerprint": "s"}
        self.assertEqual(build.check_report(man, self.good_report(man)), [])
        for key, value in (("shapes_fingerprint", "old"), ("in_graph_mutant_violations", 0), ("roundtrip_added", 3),
                           ("determinism_hash_shuffled", "other"), ("shapes_import_rows", 8)):
            rep = self.good_report(man)
            rep[key] = value
            self.assertTrue(build.check_report(man, rep), key)

    def test_check_report_reads_fail_cases_and_the_restore(self):
        man = {"input_fingerprint": "f", "shapes_fingerprint": "s"}
        rep = self.good_report(man)
        rep["fail_cases"] = [{"kind": "class", "passed": True}, {"kind": "in", "passed": False}]
        self.assertTrue(any("in" in f for f in build.check_report(man, rep)))
        rep = self.good_report(man)
        rep["mutant"] = {"after_restore": 1}
        self.assertTrue(build.check_report(man, rep))

    def test_report_template_cannot_pass(self):
        with open(os.path.join(TEMPLATES, "projection-report.json"), encoding="utf-8") as f:
            rep = json.load(f)
        self.assertTrue(build.check_report({"input_fingerprint": "f", "shapes_fingerprint": "s"}, rep))

    def test_multivalued_rule(self):
        multival = build.multivalued(module(), shapes())
        self.assertIn(LIB + "altTitle", multival)          # sh:minCount 0, no maximum
        self.assertIn(str(RDFS.label), multival)            # no shape at all
        self.assertNotIn(LIB + "barcode", multival)         # sh:maxCount 1
        self.assertNotIn(LIB + "copyOf", multival)          # IRI-valued

    def test_cypher_sorts_only_resource_arrays(self):
        script = build.cypher(config(), module(), shapes())
        sorts = [line for line in script.splitlines() if "apoc.coll.sort" in line]
        self.assertTrue(sorts)
        self.assertTrue(all(line.startswith("MATCH (n:Resource) WHERE n.`") for line in sorts))
        self.assertIn("handleVocabUris: 'SHORTEN'", script)
        self.assertIn("lib__altTitle", script)
        prefixes = [line for line in script.splitlines() if "nsprefixes.add" in line]
        self.assertEqual(len(prefixes), len(raw_config()["prefixes"]))

    def test_merge_holds_the_data_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "merged.ttl")
            self.assertEqual(run_main(build.main, ["merge", "--output", out, MODULE])[0], 0)
            merged = Graph().parse(out, format="turtle")
        self.assertEqual(len(merged), len(module()))
        self.assertNotIn((None, SH.path, None), merged)


class ValidateData(unittest.TestCase):
    def test_template_passes(self):
        code, out = run_main(vd.main, ["--config", CONFIG, "--shapes", SHAPES, MODULE])
        self.assertEqual(code, 0, out)

    def test_refused_value_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = os.path.join(tmp, "bad.ttl")
            g = module()
            g.set((lib("person/P-17"), lib("name"), Literal("Spine@en")))
            g.serialize(bad, format="turtle")
            code, out = run_main(vd.main, ["--config", CONFIG, "--shapes", SHAPES, bad])
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL refusal", out)

    def test_shape_violation_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = os.path.join(tmp, "bad.ttl")
            g = module()
            g.remove((COPY, lib("barcode"), None))
            g.serialize(bad, format="turtle")
            self.assertEqual(run_main(vd.main, ["--config", CONFIG, "--shapes", SHAPES, bad])[0], 1)


class RoundTwo(OneBreak, unittest.TestCase):
    """One test per code change asked for by the second pair of test runs; each failed on 628a2d7."""

    def broken(self, mutate_data=None, mutate_shapes=None, cfg=None):
        g, s = module(), shapes()
        if mutate_data:
            mutate_data(g)
        if mutate_shapes:
            mutate_shapes(s)
        return cpr.check(g, s, cfg or config())

    @staticmethod
    def retarget(s, predicate, obj):
        """Move the copy shape's target from sh:targetClass to another target kind."""
        s.remove((lib("CopyShape"), SH.targetClass, None))
        s.add((lib("CopyShape"), predicate, obj))

    # Rule 2 counts every target kind (test b, 2)
    def test_subjects_of_target_states_cardinality(self):
        self.assertEqual(self.broken(mutate_shapes=lambda s: self.retarget(s, SH.targetSubjectsOf, lib("barcode"))), [])

    def test_sparql_target_states_cardinality(self):
        self.assertEqual(self.broken(mutate_shapes=lambda s: self.retarget(s, SH.target, BNode())), [])

    def test_target_node_states_cardinality(self):
        self.assertEqual(self.broken(mutate_shapes=lambda s: self.retarget(s, SH.targetNode, COPY)), [])

    def test_shape_reused_through_sh_node_states_cardinality(self):
        def change(s):
            s.remove((lib("CopyShape"), SH.targetClass, None))
            s.add((lib("CopyHolder"), RDF.type, SH.NodeShape))
            s.add((lib("CopyHolder"), SH.targetClass, lib("Copy")))
            s.add((lib("CopyHolder"), SH.node, lib("CopyShape")))
        self.assertEqual(self.broken(mutate_shapes=change), [])

    def test_untargeted_shape_still_states_nothing(self):
        self.assertOnly(self.broken(mutate_shapes=lambda s: s.remove((lib("PersonShape"), SH.targetClass, None))),
                        "rule-2", "Rule 2: no cardinality stated for lib:name")

    def test_single_value_under_subjects_of_target_is_not_an_array(self):
        s = shapes()
        self.retarget(s, SH.targetSubjectsOf, lib("barcode"))
        self.assertNotIn(LIB + "barcode", build.multivalued(module(), s))

    # declared but unused properties skip Rule 2 (test b, 3)
    def test_declared_unused_property_skips_rule_2(self):
        def change(g):
            g.add((lib("shelfmark"), RDF.type, OWL.DatatypeProperty))
            g.add((lib("shelfmark"), RDFS.range, XSD.string))
        self.assertEqual(self.broken(change), [])

    def test_used_property_still_needs_a_shape(self):
        def change(g):
            g.add((lib("shelfmark"), RDF.type, OWL.DatatypeProperty))
            g.add((lib("shelfmark"), RDFS.range, XSD.string))
            g.add((COPY, lib("shelfmark"), Literal("A-12")))
        self.assertOnly(self.broken(change), "rule-2", "Rule 2: no cardinality stated for lib:shelfmark")

    # exception keys may use full IRIs (test b, 4)
    def test_full_iri_exception_key(self):
        key = f"Rule 1: {LIB}copyOf has no single concrete range"
        cfg = config(lambda r: r["release_exceptions"].update({key: "the next lending release adds the range"}))
        self.assertEqual(self.broken(lambda g: g.remove((lib("copyOf"), RDFS.range, None)), cfg=cfg), [])

    def test_bracketed_iri_exception_key(self):
        key = f"Rule 1: <{LIB}copyOf> has no single concrete range"
        cfg = config(lambda r: r["release_exceptions"].update({key: "the next lending release adds the range"}))
        self.assertEqual(self.broken(lambda g: g.remove((lib("copyOf"), RDFS.range, None)), cfg=cfg), [])

    # the in-graph subset (test b, 7 and 8)
    def test_comparison_constraints_n10s_ignores_are_dropped(self):
        for predicate in (SH.lessThan, SH.lessThanOrEquals, SH.equals, SH.uniqueLang, SH.qualifiedValueShape):
            sub, dropped = igs.subset(minimal_shape(predicate, lib("copyOf")))
            self.assertNotIn((None, predicate, None), sub, predicate)
            self.assertIn((lib("S-p"), predicate), {(x, p) for x, p, _ in dropped}, predicate)

    def test_disjoint_stays(self):
        sub, _ = igs.subset(minimal_shape(SH.disjoint, lib("copyOf")))
        self.assertIn((lib("S-p"), SH.disjoint, lib("copyOf")), sub)

    def test_iri_named_sparql_constraint_is_removed(self):
        g = minimal_shape(SH.minCount, Literal(1))
        c = lib("NoSelfCopy")
        g.add((lib("S"), SH.sparql, c))
        g.add((c, RDF.type, SH.SPARQLConstraint))
        g.add((c, SH.select, Literal("SELECT $this WHERE { $this ?p $this }")))
        g.add((c, SH.prefixes, lib("lending")))
        sub, dropped = igs.subset(g)
        self.assertNotIn((c, None, None), sub)
        self.assertIn(c, {x for x, _, _ in dropped})

    def test_deactivated_shape_is_removed(self):
        g = minimal_shape(SH.minCount, Literal(1))
        g.add((lib("S-p"), SH.deactivated, Literal(True)))
        sub, dropped = igs.subset(g)
        self.assertNotIn((lib("S-p"), None, None), sub)
        self.assertNotIn((lib("S"), SH.property, lib("S-p")), sub)

    # the manifest does not depend on where the tree sits (test a2, 14; test b, 11)
    def test_manifest_survives_moving_the_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = os.path.join(tmp, "a")
            os.makedirs(os.path.join(a, "data"))
            for src in (MODULE, SHAPES, CONFIG):
                shutil.copy(src, os.path.join(a, "data"))
            loadable, inferred_path = os.path.join(a, "loadable.nt"), os.path.join(a, "inferred.nt")
            open(loadable, "w").close()
            open(inferred_path, "w").close()

            def args(root):
                return ["manifest", "--config", os.path.join(root, "data", "projection-config.json"),
                        "--shapes", os.path.join(root, "data", "library-shapes.ttl"),
                        "--loadable", os.path.join(root, "loadable.nt"), "--inferred", os.path.join(root, "inferred.nt"),
                        "--output", os.path.join(root, "manifest.json"), os.path.join(root, "data", "library-module.ttl")]
            self.assertEqual(run_main(build.main, args(a))[0], 0)
            b = os.path.join(tmp, "b")
            shutil.copytree(a, b)
            code, out = run_main(build.main, args(b) + ["--verify"])
            self.assertEqual(code, 0, out)
            with open(os.path.join(b, "manifest.json"), encoding="utf-8") as f:
                self.assertIn("data/library-module.ttl", json.load(f)["inputs"])

    def test_merge_reports_what_it_wrote(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = run_main(build.main, ["merge", "--output", os.path.join(tmp, "m.ttl"), MODULE])
        self.assertEqual(code, 0)
        self.assertIn("triples from 1 file(s)", out)

    # the release-folder fixture the docs describe (test a2, 5)
    def test_release_folder_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = os.path.join(tmp, "releases", "lending", "1.1.0")
            os.makedirs(folder)
            shutil.copy(MODULE, os.path.join(folder, "lending.ttl"))
            shutil.copy(SHAPES, os.path.join(folder, "shapes.ttl"))
            code, out = run_main(cpr.main, ["--config", CONFIG, "--shapes", os.path.join(folder, "shapes.ttl"),
                                            "--releases", os.path.join(tmp, "releases"), os.path.join(folder, "lending.ttl")])
        self.assertEqual(code, 0, out)


class LoadVerifyPure(unittest.TestCase):
    """The parts of load_verify.py that need no Neo4j."""

    def row(self, obj, literal=True, dtype=str(XSD.string), lang="", subject=None, predicate=None):
        return {"subject": subject or LIB + "work/W-0042", "predicate": predicate or LIB + "title", "object": obj,
                "isLiteral": literal, "literalType": dtype, "literalLang": lang}

    # test b, 1: a multi-line tagged string comes back as xsd:string "text@en"
    def test_multi_line_tagged_text_is_rebuilt(self):
        self.assertEqual(lv.row_object(self.row("line one\nline two@en")), Literal("line one\nline two", lang="en"))

    def test_lang_column_is_used(self):
        self.assertEqual(lv.row_object(self.row("Lending", dtype=str(RDF.langString), lang="en")),
                         Literal("Lending", lang="en"))

    def test_plain_text_stays_plain(self):
        self.assertEqual(lv.row_object(self.row("00420001")), Literal("00420001"))

    def test_schema_rows_are_left_out(self):
        rows = [self.row("x"), self.row("Work", predicate="neo4j://graph.schema#name"),
                self.row("neo4j://graph.schema#Class", literal=False, predicate=str(RDF.type))]
        g, skipped = lv.rows_to_graph(rows)
        self.assertEqual((len(g), skipped), (1, 2))

    def test_round_trip_compares_values(self):
        source, exported = Graph(), Graph()
        source.add((COPY, lib("position"), Literal("2", datatype=XSD.integer)))
        exported.add((COPY, lib("position"), Literal("2", datatype=XSD.long)))
        self.assertEqual(lv.diff(source, exported), ([], []))

    # test a2, 11: the hash specification
    def nodes_edges(self):
        nodes = [{"uri": "b", "labels": ["Resource", "lib__Work"], "props": {"lib__altTitle": ["x@fr", "y@de"]}},
                 {"uri": "a", "labels": ["lib__Copy", "Resource"], "props": {"uri": "a"}}]
        edges = [{"s": "a", "t": "lib__copyOf", "o": "b", "u": None, "props": {}},
                 {"s": "a", "t": "lib__copyOf", "o": "b", "u": "e1", "props": {"since": 2026}}]
        return nodes, edges

    def test_hash_ignores_row_order(self):
        nodes, edges = self.nodes_edges()
        self.assertEqual(lv.graph_hash(nodes, edges), lv.graph_hash(list(reversed(nodes)), list(reversed(edges))))

    def test_hash_counts_relationship_properties_and_array_order(self):
        nodes, edges = self.nodes_edges()
        base = lv.graph_hash(nodes, edges)
        edges[1]["props"] = {"since": 2025}
        self.assertNotEqual(base, lv.graph_hash(nodes, edges))
        nodes, edges = self.nodes_edges()
        nodes[0]["props"]["lib__altTitle"].reverse()
        self.assertNotEqual(base, lv.graph_hash(nodes, edges))

    def test_hash_matches_its_specification(self):
        import hashlib
        nodes, edges = self.nodes_edges()
        text = json.dumps({"nodes": [["a", ["Resource", "lib__Copy"], {"uri": "a"}],
                                     ["b", ["Resource", "lib__Work"], {"lib__altTitle": ["x@fr", "y@de"]}]],
                           "relationships": [["a", "lib__copyOf", "b", "", {}], ["a", "lib__copyOf", "b", "e1", {"since": 2026}]]},
                          sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        self.assertEqual(lv.graph_hash(nodes, edges), hashlib.sha256(text.encode("utf-8")).hexdigest())

    def test_shuffle_is_fixed_by_its_seed(self):
        text = "".join(f"<s{i}> <p> <o> .\n" for i in range(20))
        self.assertEqual(lv.shuffled(text), lv.shuffled(text))
        self.assertNotEqual(lv.shuffled(text), text)
        self.assertEqual(sorted(lv.shuffled(text).splitlines()), sorted(text.splitlines()))

    # test a2, 9: one generated fail case per kind, each with its expected components
    def test_fail_cases_cover_the_library_kinds(self):
        sub, _ = igs.subset(shapes())
        kinds = [k for k, _, _ in lv.fail_cases(sub, module(), config())]
        self.assertEqual(kinds, ["class", "datatype xsd:integer", "datatype xsd:string", "in", "inverseMaxCount",
                                 "inverseMinCount", "maxCount", "minCount", "nodeKind"])
        for kind in kinds:
            self.assertTrue(lv.expected_components(kind))

    def test_mutant_is_a_required_literal(self):
        sub, _ = igs.subset(shapes())
        self.assertEqual(lv.mutant_case(sub, module(), config()), ("lib__Authorship", "lib__position"))


def data_with_name_on_copies():
    g = module()
    g.add((COPY, lib("name"), Literal("first copy")))
    return g


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def data(self):
        return self.rows

    def single(self):
        return self.rows[0] if self.rows else None


class FakeSession:
    """Answers the load script's statements with the rows given."""

    def __init__(self, status="OK", shape_rows=3, listed=3):
        self.status, self.shape_rows, self.listed = status, shape_rows, listed

    def run(self, stmt, **_):
        if "shacl.import" in stmt:
            return FakeResult([{"target": "x"}] * self.shape_rows)
        if "rdf.import" in stmt or "onto.import" in stmt:
            return FakeResult([{"terminationStatus": self.status}])
        if "listShapes" in stmt:
            return FakeResult([{"n": self.listed}])
        return FakeResult([])


class LoadChecks(unittest.TestCase):
    """test a2, 8: the load checks each import's result."""

    def statements(self):
        return [line for line in build.cypher(config(), module(), shapes()).splitlines() if line]

    def test_good_load_returns_both_counts(self):
        self.assertEqual(lv.load(FakeSession(), self.statements()), (3, 3))

    def test_failed_import_stops(self):
        with self.assertRaises(lv.Failed):
            lv.load(FakeSession(status="KO"), self.statements())

    def test_shapes_count_mismatch_stops(self):
        with self.assertRaises(lv.Failed):
            lv.load(FakeSession(shape_rows=2, listed=3), self.statements())

    def test_no_shapes_stops(self):
        with self.assertRaises(lv.Failed):
            lv.load(FakeSession(shape_rows=0, listed=0), self.statements())


class RoundThree(unittest.TestCase):
    """test b2, 1: every kind left in the graph gets a fail case, or the report says it has none."""

    def library_subset(self, change=None):
        full = shapes()
        if change:
            change(full)
        return igs.subset(full)[0]

    def test_closed_and_disjoint_get_cases(self):
        def change(s):
            s.add((lib("PersonShape"), SH.closed, Literal(True)))
            s.add((lib("AuthorshipShape-agent"), SH.disjoint, lib("creatorRole")))
        cases = {k: c for k, _, c in lv.fail_cases(self.library_subset(change), module(), config())}
        self.assertIn("closed", cases)
        self.assertIn("lib__notInTheShape", cases["closed"])
        self.assertIn("disjoint", cases)
        self.assertIn("CREATE (n)-[:`lib__creatorRole`]->(m)", cases["disjoint"])
        self.assertEqual(lv.expected_components("closed"), {"ClosedConstraintComponent"})
        self.assertEqual(lv.expected_components("disjoint"), {"DisjointConstraintComponent"})

    def test_every_kept_kind_of_the_library_has_a_case(self):
        sub = self.library_subset()
        generated = {k for k, _, _ in lv.fail_cases(sub, module(), config())}
        self.assertEqual([k for k in lv.kept_kinds(sub, module()) if k not in generated], [])

    def test_a_kind_without_a_case_is_listed(self):
        sub = self.library_subset(lambda s: s.add((lib("PersonShape-name"), SH.nodeKind, SH.Literal)))
        generated = {k for k, _, _ in lv.fail_cases(sub, module(), config())}
        self.assertIn("nodeKind sh:Literal", [k for k in lv.kept_kinds(sub, module()) if k not in generated])

    def test_check_report_fails_on_a_kind_without_a_case(self):
        man = {"input_fingerprint": "f", "shapes_fingerprint": "s"}
        rep = Build.good_report(None, man)
        rep["kinds_without_case"] = ["nodeKind sh:Literal"]
        self.assertTrue(any("no fail case" in f for f in build.check_report(man, rep)))
        rep["manual_cases"] = [{"kind": "nodeKind sh:Literal", "passed": False}]
        self.assertTrue(build.check_report(man, rep))
        rep["manual_cases"] = [{"kind": "nodeKind sh:Literal", "passed": True, "focus": "x",
                                "cypher": "MATCH (n) ... RETURN n.uri AS focus",
                                "components": ["NodeKindConstraintComponent"]}]
        self.assertEqual(build.check_report(man, rep), [])


class RoundFour(OneBreak, unittest.TestCase):
    """One test per code finding of review round 2; each failed on ef4c4e3."""

    # 3: a stub manual case does not clear a kind
    def test_stub_manual_case_does_not_clear_a_kind(self):
        man = {"input_fingerprint": "f", "shapes_fingerprint": "s"}
        for stub in ({"kind": "closed", "passed": True},
                     {"kind": "closed", "passed": True, "cypher": "", "focus": "x", "components": ["C"]},
                     {"kind": "closed", "passed": True, "cypher": "MATCH", "focus": "", "components": ["C"]},
                     {"kind": "closed", "passed": True, "cypher": "MATCH", "focus": "x", "components": []},
                     {"kind": "closed", "passed": "yes", "cypher": "MATCH", "focus": "x", "components": ["C"]}):
            rep = Build.good_report(None, man)
            rep["kinds_without_case"] = ["closed"]
            rep["manual_cases"] = [stub]
            self.assertTrue(any("no fail case" in f for f in build.check_report(man, rep)), stub)

    # 4: a report without its mutant fails
    def test_missing_mutant_fails(self):
        man = {"input_fingerprint": "f", "shapes_fingerprint": "s"}
        for value in (None, "absent"):
            rep = Build.good_report(None, man)
            if value == "absent":
                rep.pop("mutant")
            else:
                rep["mutant"] = None
            self.assertIn("report has no mutant object (pipeline.md, rule 15)", build.check_report(man, rep))

    def test_mutant_that_caught_nothing_fails(self):
        man = {"input_fingerprint": "f", "shapes_fingerprint": "s"}
        rep = Build.good_report(None, man)
        rep["mutant"]["violations"] = 0
        self.assertIn("report mutant caught no violation", build.check_report(man, rep))

    # 8: dropping an sh:or list keeps a blank property shape another shape still uses
    def test_or_list_keeps_a_shared_blank_property_shape(self):
        g = Graph()
        ps = BNode()
        g.add((lib("S"), RDF.type, SH.NodeShape))
        g.add((lib("S"), SH.targetClass, lib("Copy")))
        g.add((lib("S"), SH.property, ps))
        g.add((ps, SH.path, lib("barcode")))
        g.add((ps, SH.minCount, Literal(1)))
        head = BNode()
        Collection(g, head, [ps])
        g.add((lib("S"), SH["or"], head))
        sub, dropped = igs.subset(g)
        self.assertNotIn((lib("S"), SH["or"], None), sub)
        self.assertIn((lib("S"), SH.property, ps), sub)
        self.assertIn((ps, SH.minCount, Literal(1)), sub)
        data = module()
        data.remove((COPY, lib("barcode"), None))
        self.assertFalse(validate(data, shacl_graph=sub)[0])

    # 9: sh:node one hop from an applied shape stays, with the reached shape; sh:targetQuery stays
    def node_hop(self):
        g = Graph()
        g.add((lib("S"), RDF.type, SH.NodeShape))
        g.add((lib("S"), SH.targetClass, lib("Copy")))
        g.add((lib("S"), SH.node, lib("Inner")))
        g.add((lib("Inner"), RDF.type, SH.NodeShape))
        g.add((lib("Inner"), SH.property, lib("Inner-p")))
        g.add((lib("Inner-p"), SH.path, lib("barcode")))
        g.add((lib("Inner-p"), SH.minCount, Literal(1)))
        return g

    def test_node_hop_from_an_applied_shape_is_kept(self):
        sub, _ = igs.subset(self.node_hop())
        self.assertIn((lib("S"), SH.node, lib("Inner")), sub)
        self.assertIn((lib("Inner-p"), SH.minCount, Literal(1)), sub)
        self.assertIn(lib("Inner-p"), [r[1] for r in igs.property_rows(sub) if r[0] == lib("S")])

    def test_second_node_hop_is_dropped(self):
        g = self.node_hop()
        g.add((lib("Inner"), SH.node, lib("Deeper")))
        g.add((lib("Deeper"), RDF.type, SH.NodeShape))
        g.add((lib("Deeper"), SH.property, lib("Deeper-p")))
        g.add((lib("Deeper-p"), SH.path, lib("copyOf")))
        g.add((lib("Deeper-p"), SH.minCount, Literal(1)))
        sub, dropped = igs.subset(g)
        self.assertNotIn((lib("Inner"), SH.node, lib("Deeper")), sub)
        self.assertNotIn((lib("Deeper-p"), None, None), sub)
        self.assertIn((lib("Inner"), SH.node), {(x, p) for x, p, _ in dropped})

    def test_node_on_a_property_shape_is_dropped(self):
        sub, dropped = igs.subset(minimal_shape(SH.node, lib("Other")))
        self.assertNotIn((lib("S-p"), SH.node, None), sub)
        self.assertIn((lib("S-p"), SH.node), {(x, p) for x, p, _ in dropped})

    def test_target_query_shape_is_kept(self):
        g = minimal_shape(SH.minCount, Literal(1))
        g.remove((lib("S"), SH.targetClass, None))
        g.add((lib("S"), igs.TARGET_QUERY, Literal("MATCH (focus:lib__Copy)")))
        sub, _ = igs.subset(g)
        self.assertIn((lib("S"), igs.TARGET_QUERY, None), sub)
        self.assertIn((lib("S-p"), SH.minCount, Literal(1)), sub)

    # 10: n10s applies rdfs:Class shapes, not owl:Class ones; the inventories see class shapes
    def class_shape(self, kind):
        g = Graph()
        g.add((lib("Copy"), RDF.type, kind))
        g.add((lib("Copy"), RDF.type, SH.NodeShape))
        g.add((lib("Copy"), SH.property, lib("C-p")))
        g.add((lib("C-p"), SH.path, lib("barcode")))
        g.add((lib("C-p"), SH.minCount, Literal(1)))
        return g

    def test_owl_class_shape_without_target_is_not_applied(self):
        sub, dropped = igs.subset(self.class_shape(OWL.Class))
        self.assertNotIn((lib("C-p"), SH.minCount, Literal(1)), sub)
        self.assertIn(lib("Copy"), {x for x, _, _ in dropped})

    def test_rdfs_class_shape_is_in_every_inventory(self):
        sub, _ = igs.subset(self.class_shape(RDFS.Class))
        self.assertIn("minCount", lv.kept_kinds(sub, module()))
        self.assertIn("minCount", [k for k, _, _ in lv.fail_cases(sub, module(), config())])
        self.assertEqual(lv.mutant_case(sub, module(), config()), ("lib__Copy", "lib__barcode"))

    def class_with_hop(self):
        g = Graph()
        g.add((lib("Copy"), RDF.type, RDFS.Class))
        g.add((lib("Copy"), RDF.type, SH.NodeShape))
        g.add((lib("Copy"), SH.node, lib("Inner")))
        g.add((lib("Inner"), RDF.type, SH.NodeShape))
        g.add((lib("Inner"), SH.property, lib("Inner-p")))
        g.add((lib("Inner-p"), SH.path, lib("barcode")))
        g.add((lib("Inner-p"), SH.minCount, Literal(1)))
        return g

    def test_node_hop_from_an_rdfs_class_shape_is_dropped(self):
        # quick check 2: n10s's implicit-class branch reads only the class's own sh:property
        # (SHACLValidator.java lines 88 and 89), so the hop never runs; the subset drops it and records why.
        sub, dropped = igs.subset(self.class_with_hop())
        self.assertNotIn((lib("Copy"), SH.node, None), sub)
        self.assertNotIn((lib("Inner-p"), SH.minCount, Literal(1)), sub)
        self.assertIn((lib("Copy"), SH.node), {(x, p) for x, p, _ in dropped})
        self.assertEqual(lv.kept_kinds(sub, module()), [])
        self.assertEqual(lv.fail_cases(sub, module(), config()), [])
        self.assertIsNone(lv.mutant_case(sub, module(), config()))

    def test_rdfs_class_keeps_its_own_property_and_drops_the_hop(self):
        g = self.class_with_hop()
        g.add((lib("Copy"), SH.property, lib("Own-p")))
        g.add((lib("Own-p"), SH.path, lib("copyOf")))
        g.add((lib("Own-p"), SH.minCount, Literal(1)))
        sub, _ = igs.subset(g)
        self.assertIn((lib("Own-p"), SH.minCount, Literal(1)), sub)
        self.assertNotIn((lib("Inner-p"), SH.minCount, Literal(1)), sub)
        self.assertEqual(sorted({r[1] for r in igs.property_rows(sub) if r[0] == lib("Copy")}), [lib("Own-p")])

    def test_inventories_do_not_follow_a_hop_from_a_class_shape(self):
        # even if a hop from an rdfs:Class reached the inventories, they would not follow it
        self.assertEqual([r for r in igs.property_rows(self.class_with_hop()) if r[0] == lib("Copy")], [])

    def test_rdfs_class_not_typed_as_a_shape_is_not_applied(self):
        # both n10s queries need ?ns typed sh:NodeShape (lines 72 to 74, 129 and 130)
        g = Graph()
        g.add((lib("Copy"), RDF.type, RDFS.Class))
        g.add((lib("Copy"), SH.property, lib("C-p")))
        g.add((lib("C-p"), SH.path, lib("barcode")))
        g.add((lib("C-p"), SH.minCount, Literal(1)))
        self.assertEqual(igs.property_rows(g), [])
        sub, dropped = igs.subset(g)
        self.assertNotIn((lib("C-p"), SH.minCount, Literal(1)), sub)
        reasons = {(x, p): r for x, p, r in dropped}
        # quick check 3, #4: the reason states what failed for this node, and nothing false about it
        self.assertIn("it is not typed sh:NodeShape or sh:Shape", reasons[(lib("Copy"), SH.property)])
        self.assertNotIn("not an rdfs:Class", reasons[(lib("Copy"), SH.property)])
        self.assertIn("no shape typed sh:NodeShape or sh:Shape reaches it", reasons[(lib("C-p"), SH.minCount)])

    # quick check 3: each graph the report names, with the engine's result on 2026-10-23
    def test_sh_shape_class_keeps_its_own_property(self):
        g = Graph()
        g.add((lib("Copy"), RDF.type, RDFS.Class))
        g.add((lib("Copy"), RDF.type, SH.Shape))
        g.add((lib("Copy"), SH.property, lib("A-p")))
        g.add((lib("A-p"), SH.path, lib("name")))
        g.add((lib("A-p"), SH.minCount, Literal(1)))
        sub, dropped = igs.subset(g)
        self.assertIn((lib("A-p"), SH.minCount, Literal(1)), sub)
        self.assertEqual(dropped, [])
        self.assertEqual(lv.mutant_case(sub, data_with_name_on_copies(), config()), ("lib__Copy", "lib__name"))

    def test_class_to_class_hop_is_kept(self):
        g = Graph()
        g.add((lib("Work"), RDF.type, RDFS.Class))
        g.add((lib("Work"), RDF.type, SH.NodeShape))
        g.add((lib("Work"), SH.node, lib("Copy")))
        g.add((lib("Copy"), RDF.type, RDFS.Class))
        g.add((lib("Copy"), SH.property, lib("B-p")))
        g.add((lib("B-p"), SH.path, lib("name")))
        g.add((lib("B-p"), SH.minCount, Literal(1)))
        sub, dropped = igs.subset(g)
        self.assertIn((lib("B-p"), SH.minCount, Literal(1)), sub)
        self.assertIn((lib("Work"), SH.node, lib("Copy")), sub)
        self.assertEqual(dropped, [])
        self.assertEqual(lv.target_pairs(sub), [(lib("Copy"), lib("B-p"))])

    def test_untyped_target_class_shape_with_a_hop_is_dropped(self):
        g = Graph()
        g.add((lib("C1"), SH.targetClass, lib("Copy")))
        g.add((lib("C1"), SH.node, lib("C2")))
        g.add((lib("C2"), RDF.type, SH.NodeShape))
        g.add((lib("C2"), SH.property, lib("C-p")))
        g.add((lib("C-p"), SH.path, lib("name")))
        g.add((lib("C-p"), SH.minCount, Literal(1)))
        sub, dropped = igs.subset(g)
        self.assertEqual(len(sub), 0)
        reasons = {(x, p): r for x, p, r in dropped}
        self.assertIn("it is not typed sh:NodeShape or sh:Shape", reasons[(lib("C1"), SH.node)])
        self.assertIn("library/C2>) have no sh:targetClass", reasons[(lib("C-p"), SH.minCount)])

    def test_closed_on_a_shape_that_is_not_a_node_shape_is_dropped(self):
        g = Graph()
        g.add((lib("E"), RDF.type, SH.Shape))
        g.add((lib("E"), SH.targetClass, lib("Person")))
        g.add((lib("E"), SH.closed, Literal(True)))
        g.add((lib("E"), SH.property, lib("E-p")))
        g.add((lib("E-p"), SH.path, lib("name")))
        g.add((lib("E-p"), SH.minCount, Literal(0)))
        sub, dropped = igs.subset(g)
        self.assertIn((lib("E-p"), SH.minCount, Literal(0)), sub)
        self.assertNotIn((lib("E"), SH.closed, None), sub)
        reasons = {(x, p): r for x, p, r in dropped}
        self.assertIn("not typed sh:NodeShape", reasons[(lib("E"), SH.closed)])

    def test_closed_on_a_targeted_node_shape_is_kept(self):
        sub, _ = igs.subset(shapes() + Graph().add((lib("PersonShape"), SH.closed, Literal(True))))
        self.assertIn((lib("PersonShape"), SH.closed, Literal(True)), sub)
        self.assertIn("closed", lv.kept_kinds(sub, module()))

    def main_output(self, kinds):
        """load_verify.main with the database part replaced by a fixed report."""
        import sys as _sys
        from unittest import mock
        report = {"shacl_violations_in_graph": 0, "in_graph_mutant_violations": 1, "mutant": {"after_restore": 0},
                  "roundtrip_lost": 0, "roundtrip_added": 0, "determinism_hash_sorted": "h",
                  "determinism_hash_shuffled": "h", "fail_cases": [], "kinds_without_case": kinds,
                  "shapes_import_rows": 1, "in_graph_shape_constraints": 1, "nodes": 1, "relationships": 0}
        fake = mock.MagicMock()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"NEO4J_PASSWORD": "x"}), \
                mock.patch.dict(_sys.modules, {"neo4j": fake}), mock.patch.object(lv, "run", return_value=report):
            args = ["--config", CONFIG, "--shapes", SHAPES, "--bolt", "bolt://127.0.0.1:1", "--import-dir", tmp,
                    "--merged", MODULE, "--loadable", MODULE, "--inferred", MODULE,
                    "--report", os.path.join(tmp, "r.json"), MODULE]
            return run_main(lv.main, args)

    def test_load_verify_says_to_keep_the_container_for_manual_cases(self):
        code, out = self.main_output(["closed"])
        self.assertEqual(code, 0, out)
        self.assertIn("still need a case: closed. Next: keep the container up", out)
        self.assertIn("build.py check-report --manifest <projection-manifest.json> --report ", out)
        self.assertNotIn("every check passed", out)

    def test_load_verify_names_the_next_step_when_nothing_is_left(self):
        code, out = self.main_output([])
        self.assertEqual(code, 0, out)
        self.assertIn("Next: run build.py check-report --manifest <projection-manifest.json> --report ", out)
        self.assertIn("then remove the container", out)
        self.assertNotIn("every check passed", out)

    def test_manual_cases_survive_a_rerun_on_the_same_inputs(self):
        case = {"kind": "closed", "cypher": "MATCH", "focus": "x", "components": ["C"], "passed": True}
        same = {"input_fingerprint": "f", "shapes_fingerprint": "s", "versions": {"n10s": "1"},
                "plugin_jars_sha256": {"n10s.jar": "a"}}
        old = dict(same, manual_cases=[case])
        self.assertEqual(lv.carried_manual_cases(old, dict(same)), [case])
        self.assertEqual(lv.carried_manual_cases(old, dict(same, input_fingerprint="g")), [])
        self.assertEqual(lv.carried_manual_cases(None, dict(same)), [])

    def test_rdfs_class_shape_that_is_only_closed_is_dropped(self):
        # quick check 3: NODE_CONSTRAINT_QUERY's class branch filters on ?ns inside its own group, so it
        # returns no row; in the engine on 2026-10-23 such a shape reported no closed violation.
        g = Graph()
        g.add((lib("Copy"), RDF.type, RDFS.Class))
        g.add((lib("Copy"), RDF.type, SH.NodeShape))
        g.add((lib("Copy"), SH.closed, Literal(True)))
        sub, dropped = igs.subset(g)
        self.assertNotIn((lib("Copy"), SH.closed, None), sub)
        self.assertNotIn("closed", lv.kept_kinds(sub, module()))
        reasons = {(x, p): r for x, p, r in dropped}
        self.assertIn("NODE_CONSTRAINT_QUERY", reasons[(lib("Copy"), SH.closed)])

    def test_load_verify_passes_with_kinds_left_for_manual_cases(self):
        # quick check 2: the gate for a listed kind is check-report with a manual case, not load_verify
        report = {"shacl_violations_in_graph": 0, "in_graph_mutant_violations": 1, "mutant": {"after_restore": 0},
                  "roundtrip_lost": 0, "roundtrip_added": 0, "determinism_hash_sorted": "h",
                  "determinism_hash_shuffled": "h", "fail_cases": [], "kinds_without_case": ["closed"]}
        self.assertTrue(lv.passed(report))

    def test_target_query_kinds_need_a_case(self):
        g = minimal_shape(SH.minCount, Literal(1))
        g.remove((lib("S"), SH.targetClass, None))
        g.add((lib("S"), igs.TARGET_QUERY, Literal("MATCH (focus:lib__Copy)")))
        sub, _ = igs.subset(g)
        self.assertIn("minCount", lv.kept_kinds(sub, module()))
        self.assertNotIn("minCount", [k for k, _, _ in lv.fail_cases(sub, module(), config())])

    # 12: every script stops under Rule 4b
    def config_4b(self, tmp):
        raw = raw_config()
        raw["rule4"] = "4b"
        path = os.path.join(tmp, "config.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(raw, f)
        return path

    def test_validate_data_stops_under_4b(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = run_main(vd.main, ["--config", self.config_4b(tmp), "--shapes", SHAPES, MODULE])
        self.assertEqual(code, 2, out)
        self.assertIn("validate_data.py reads RDF 1.1", out)

    def test_build_cypher_stops_under_4b(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = run_main(build.main, ["cypher", "--config", self.config_4b(tmp), "--shapes", SHAPES, MODULE])
        self.assertEqual(code, 2, out)
        self.assertIn("build.py cypher reads RDF 1.1", out)

    def test_load_verify_stops_under_4b(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"NEO4J_PASSWORD": "x"}):
            args = ["--config", self.config_4b(tmp), "--shapes", SHAPES, "--bolt", "bolt://127.0.0.1:1",
                    "--import-dir", tmp, "--merged", MODULE, "--loadable", MODULE, "--inferred", MODULE,
                    "--report", os.path.join(tmp, "r.json"), MODULE]
            code, out = run_main(lv.main, args)
        self.assertEqual(code, 2, out)
        self.assertIn("load_verify.py reads RDF 1.1", out)

    # 17: predicates inside property paths, and superproperties, need a prefix
    def test_sequence_path_namespace_needs_a_prefix(self):
        def change(s):
            head = BNode()
            Collection(s, head, [lib("copyOf"), URIRef("https://vocab.example.net/terms#holder")])
            s.add((lib("CopyShape-path"), SH.path, head))
            s.add((lib("CopyShape"), SH.property, lib("CopyShape-path")))
        self.assertOnly(self.broken(mutate_shapes=change), "rule-3",
                        "Rule 3: no fixed prefix for the namespace https://vocab.example.net/terms#")

    def test_alternative_path_namespace_needs_a_prefix(self):
        def change(s):
            alt, head = BNode(), BNode()
            Collection(s, head, [lib("copyOf"), URIRef("https://vocab.example.net/terms#holder")])
            s.add((alt, SH.alternativePath, head))
            s.add((lib("CopyShape-path"), SH.path, alt))
            s.add((lib("CopyShape"), SH.property, lib("CopyShape-path")))
        self.assertOnly(self.broken(mutate_shapes=change), "rule-3",
                        "Rule 3: no fixed prefix for the namespace https://vocab.example.net/terms#")

    def wrapped_path(self, wrapper):
        def change(s):
            path = BNode()
            s.add((path, wrapper, URIRef("https://vocab.example.net/terms#holder")))
            s.add((lib("CopyShape-path"), SH.path, path))
            s.add((lib("CopyShape"), SH.property, lib("CopyShape-path")))
        return self.broken(mutate_shapes=change)

    def test_inverse_path_namespace_needs_a_prefix(self):
        self.assertOnly(self.wrapped_path(SH.inversePath), "rule-3",
                        "Rule 3: no fixed prefix for the namespace https://vocab.example.net/terms#")

    def test_zero_or_more_path_namespace_needs_a_prefix(self):
        self.assertOnly(self.wrapped_path(SH.zeroOrMorePath), "rule-3",
                        "Rule 3: no fixed prefix for the namespace https://vocab.example.net/terms#")

    def test_one_or_more_path_namespace_needs_a_prefix(self):
        self.assertOnly(self.wrapped_path(SH.oneOrMorePath), "rule-3",
                        "Rule 3: no fixed prefix for the namespace https://vocab.example.net/terms#")

    def test_zero_or_one_path_namespace_needs_a_prefix(self):
        self.assertOnly(self.wrapped_path(SH.zeroOrOnePath), "rule-3",
                        "Rule 3: no fixed prefix for the namespace https://vocab.example.net/terms#")

    def test_superproperty_namespace_needs_a_prefix(self):
        self.assertOnly(self.broken(lambda g: g.add((lib("copyOf"), RDFS.subPropertyOf,
                                                     URIRef("https://vocab.example.net/terms#related")))),
                        "rule-3", "Rule 3: no fixed prefix for the namespace https://vocab.example.net/terms#")

    def broken(self, mutate_data=None, mutate_shapes=None, cfg=None):
        g, s = module(), shapes()
        if mutate_data:
            mutate_data(g)
        if mutate_shapes:
            mutate_shapes(s)
        return cpr.check(g, s, cfg or config())

    # 19: a pin must name a release, not a candidate
    def test_candidate_pin_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "lending", "1.2.0-rc.1"))
            fails = cpr.check(module(), shapes(), config(lambda r: r["packages"].update({"lending": "1.2.0-rc.1"})), tmp)
        self.assertEqual(fails, [("inputs", "Inputs: lending is pinned at 1.2.0-rc.1, which is not a release (X.Y.Z)")])


# The selection lines of n10s 2025.06.1's three shape queries, copied by hand from
# SHACLValidator.java at tag 2025.06.1 (lines 72 to 74, 84 to 94, 129 to 151, 158 to 180).
JAVA_PROP_LINES = [
    "{ ?ns a ?shapeOrNodeShape ;", "sh:node?/sh:property ?ps .",
    "filter ( ?shapeOrNodeShape = sh:Shape || ?shapeOrNodeShape = sh:NodeShape )",
    "{ ?ns sh:targetClass  ?targetClass .", "bind( false as ?targetIsQuery )}", "union",
    "{ ?targetClass sh:property ?ps;", "a rdfs:Class .", "{ ?ns sh:targetQuery ?targetClass .",
    "bind( true as ?targetIsQuery )}"]
JAVA_CLOSED_LINES = [
    "{ ?ns a sh:NodeShape ;", "sh:closed true .", "?ns sh:targetClass  ?targetClass .",
    "?targetClass a rdfs:Class . filter(?targetClass = ?ns) .", "?ns sh:targetQuery  ?targetClass ."]
JAVA_NODE_CLASS_LINES = [
    "{ ?ns a sh:NodeShape .", "?ns sh:targetClass  ?targetClass .",
    "?targetClass a rdfs:Class . filter(?targetClass = ?ns) .", "?ns sh:targetQuery  ?targetClass ."]


def squeeze(text):
    return "".join(text.split())


def triples(*items):
    return set(items)


class RoundFive(unittest.TestCase):
    """Quick check 4: one test per code finding; each failed on 83c1031."""

    # 8: the query constants carry the Java selection lines
    def test_queries_carry_the_java_selection_lines(self):
        for query, lines in ((igs.PROPERTY_ROWS, JAVA_PROP_LINES), (igs.CLOSED_ROWS, JAVA_CLOSED_LINES),
                             (igs.NODE_CLASS_ROWS, JAVA_NODE_CLASS_LINES)):
            for line in lines:
                self.assertIn(squeeze(line), squeeze(query), line)

    # 8: the kept and dropped triples of the five graphs the engine was run on, written out by hand
    def test_engine_graphs_keep_what_n10s_ran(self):
        A, B, C, D, E = (Graph() for _ in range(5))
        A.add((lib("Copy"), RDF.type, RDFS.Class)); A.add((lib("Copy"), RDF.type, SH.Shape))
        A.add((lib("Copy"), SH.property, lib("A-p"))); A.add((lib("A-p"), SH.path, lib("name")))
        A.add((lib("A-p"), SH.minCount, Literal(1)))
        self.assertEqual(set(igs.subset(A)[0]), set(A))                       # engine: 1 row, 1 violation
        B.add((lib("Work"), RDF.type, RDFS.Class)); B.add((lib("Work"), RDF.type, SH.NodeShape))
        B.add((lib("Work"), SH.node, lib("Copy"))); B.add((lib("Copy"), RDF.type, RDFS.Class))
        B.add((lib("Copy"), SH.property, lib("B-p"))); B.add((lib("B-p"), SH.path, lib("name")))
        B.add((lib("B-p"), SH.minCount, Literal(1)))
        self.assertEqual(set(igs.subset(B)[0]), set(B) - {(lib("Work"), RDF.type, RDFS.Class)})  # 1 row, 1 violation
        C.add((lib("C1"), SH.targetClass, lib("Copy"))); C.add((lib("C1"), SH.node, lib("C2")))
        C.add((lib("C2"), RDF.type, SH.NodeShape)); C.add((lib("C2"), SH.property, lib("C-p")))
        C.add((lib("C-p"), SH.path, lib("name"))); C.add((lib("C-p"), SH.minCount, Literal(1)))
        self.assertEqual(set(igs.subset(C)[0]), set())                         # 0 rows
        D.add((lib("Person"), RDF.type, RDFS.Class)); D.add((lib("Person"), RDF.type, SH.NodeShape))
        D.add((lib("Person"), SH.closed, Literal(True))); D.add((lib("Person"), SH.property, lib("D-p")))
        D.add((lib("D-p"), SH.path, lib("name"))); D.add((lib("D-p"), SH.minCount, Literal(0)))
        self.assertEqual(set(igs.subset(D)[0]), set(D) - {(lib("Person"), SH.closed, Literal(True))})  # no closed
        E.add((lib("E"), RDF.type, SH.Shape)); E.add((lib("E"), SH.targetClass, lib("Person")))
        E.add((lib("E"), SH.closed, Literal(True))); E.add((lib("E"), SH.property, lib("E-p")))
        E.add((lib("E-p"), SH.path, lib("name"))); E.add((lib("E-p"), SH.minCount, Literal(0)))
        self.assertEqual(set(igs.subset(E)[0]), set(E) - {(lib("E"), SH.closed, Literal(True))})  # no closed

    # 2: a property shape whose path n10s cannot read leaves the subset with its edges
    def bad_path_graph(self, path_value):
        g = minimal_shape(SH.minCount, Literal(1))
        g.add((lib("S"), SH.property, lib("Bad-p")))
        if path_value is not None:
            g.add((lib("Bad-p"), SH.path, path_value))
        g.add((lib("Bad-p"), SH.minCount, Literal(1)))
        return g

    def test_sequence_path_shape_leaves_with_its_edge(self):
        g = self.bad_path_graph(BNode())
        head = g.value(lib("Bad-p"), SH.path)
        Collection(g, head, [lib("copyOf"), lib("barcode")])
        sub, dropped = igs.subset(g)
        self.assertNotIn((lib("S"), SH.property, lib("Bad-p")), sub)
        self.assertNotIn((lib("Bad-p"), None, None), sub)
        self.assertEqual([r for r in igs.property_rows(sub) if r[1] == lib("Bad-p")], [])
        self.assertIn((lib("S-p"), SH.minCount, Literal(1)), sub)
        reasons = {(x, p): r for x, p, r in dropped}
        self.assertIn("skips this path (line 989)", reasons[(lib("Bad-p"), SH.minCount)])

    def test_missing_path_shape_leaves_with_its_edge(self):
        sub, dropped = igs.subset(self.bad_path_graph(None))
        self.assertNotIn((lib("S"), SH.property, lib("Bad-p")), sub)
        reasons = {(x, p): r for x, p, r in dropped}
        self.assertIn("it has no sh:path", reasons[(lib("Bad-p"), SH.minCount)])

    # 1: reasons name the condition that failed, and nothing false
    def test_closed_class_reason_names_the_filter_scope(self):
        g = Graph()
        g.add((lib("Copy"), RDF.type, RDFS.Class)); g.add((lib("Copy"), RDF.type, SH.NodeShape))
        g.add((lib("Copy"), SH.closed, Literal(True)))
        reasons = {(x, p): r for x, p, r in igs.subset(g)[1]}
        self.assertEqual(reasons[(lib("Copy"), SH.closed)],
                         "NODE_CONSTRAINT_QUERY (lines 129 to 151) returns no row: it has no sh:targetClass or "
                         "sh:targetQuery, and its class branch cannot stand in: filter(?targetClass = ?ns) sits inside "
                         "the union group (line 138), where ?ns is unbound, so that branch returns no row")

    def test_class_hop_reason_names_the_reached_node(self):
        g = Graph()
        g.add((lib("Copy"), RDF.type, RDFS.Class)); g.add((lib("Copy"), RDF.type, SH.NodeShape))
        g.add((lib("Copy"), SH.node, lib("Inner"))); g.add((lib("Inner"), RDF.type, SH.NodeShape))
        g.add((lib("Inner"), SH.property, lib("Inner-p"))); g.add((lib("Inner-p"), SH.path, lib("barcode")))
        g.add((lib("Inner-p"), SH.minCount, Literal(1)))
        reason = {(x, p): r for x, p, r in igs.subset(g)[1]}[(lib("Copy"), SH.node)]
        self.assertIn("is not an rdfs:Class with its own sh:property", reason)
        self.assertNotIn("target only for its own", reason)

    def test_property_class_reason_is_the_property_reason(self):
        g = Graph()
        g.add((lib("Loose-p"), SH.path, lib("copyOf")))
        g.add((lib("Loose-p"), SH["class"], lib("Work")))
        reason = {(x, p): r for x, p, r in igs.subset(g)[1]}[(lib("Loose-p"), SH["class"])]
        self.assertIn("PROP_CONSTRAINT_QUERY", reason)
        self.assertNotIn("NODE_ADDITIONAL", reason)

    # 3: a node-level sh:class enters the inventory and needs a manual case
    def test_node_level_class_is_a_kind(self):
        g = Graph()
        g.add((lib("PersonShape"), RDF.type, SH.NodeShape))
        g.add((lib("PersonShape"), SH.targetClass, lib("Person")))
        g.add((lib("PersonShape"), SH["class"], lib("Agent")))
        sub, _ = igs.subset(g)
        self.assertIn((lib("PersonShape"), SH["class"], lib("Agent")), sub)
        self.assertIn("nodeClass", lv.kept_kinds(sub, module()))
        self.assertNotIn("nodeClass", [k for k, _, _ in lv.fail_cases(sub, module(), config())])

    # 5, 6, 7: report handling
    def run_main_with(self, existing, run_result=None, run_error=None):
        import sys as _sys
        from unittest import mock
        fake = mock.MagicMock()
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        path = os.path.join(tmp, "r.json")
        if existing is not None:
            with open(path, "w", encoding="utf-8") as f:
                f.write(existing)
        patch = mock.patch.object(lv, "run", side_effect=run_error) if run_error else \
            mock.patch.object(lv, "run", return_value=run_result)
        with mock.patch.dict(os.environ, {"NEO4J_PASSWORD": "x"}), mock.patch.dict(_sys.modules, {"neo4j": fake}), \
                patch as run:
            args = ["--config", CONFIG, "--shapes", SHAPES, "--bolt", "bolt://127.0.0.1:1", "--import-dir", tmp,
                    "--merged", MODULE, "--loadable", MODULE, "--inferred", MODULE, "--report", path, MODULE]
            code, out = run_main(lv.main, args)
        return code, out, path, run

    def test_invalid_report_json_stops_before_the_database(self):
        for text in ('{"manual_cases": [1,],}', "[1, 2]"):
            code, out, path, run = self.run_main_with(text, run_result={})
            self.assertEqual(code, 2, out)
            self.assertFalse(run.called)
            with open(path, encoding="utf-8") as f:
                self.assertEqual(f.read(), text)

    def test_cases_do_not_carry_across_versions_or_jars(self):
        case = {"kind": "closed", "cypher": "MATCH", "focus": "x", "components": ["C"], "passed": True}
        same = {"input_fingerprint": "f", "shapes_fingerprint": "s", "versions": {"n10s": "1"},
                "plugin_jars_sha256": {"n10s.jar": "a"}}
        old = dict(same, manual_cases=[case])
        self.assertEqual(lv.carried_manual_cases(old, dict(same, versions={"n10s": "2"})), [])
        self.assertEqual(lv.carried_manual_cases(old, dict(same, plugin_jars_sha256={"n10s.jar": "b"})), [])

    def test_failed_run_sets_the_previous_report_aside(self):
        passing = json.dumps({"input_fingerprint": "f", "shacl_violations_in_graph": 0})
        code, out, path, _ = self.run_main_with(passing, run_error=lv.Failed("the shapes import returned 0 rows"))
        self.assertEqual(code, 1, out)
        self.assertFalse(os.path.exists(path))
        with open(path + ".previous", encoding="utf-8") as f:
            self.assertEqual(f.read(), passing)
        self.assertIn("do not run check-report", out)
        self.assertIn("docker rm -f -v lpg-projection", out)

    def test_driver_error_is_handled_like_a_failure(self):
        code, out, path, _ = self.run_main_with("{}", run_error=OSError("connection refused"))
        self.assertEqual(code, 1, out)
        self.assertFalse(os.path.exists(path))


class FinalRun(unittest.TestCase):
    """The final real-ontology run's code items; each failed on c82da9a."""

    # 6: the container name comes from --container or $LPG_CONTAINER and is printed
    def main_with(self, extra_args=(), env=None):
        import sys as _sys
        from unittest import mock
        report = {"shacl_violations_in_graph": 0, "in_graph_mutant_violations": 1, "mutant": {"after_restore": 0},
                  "roundtrip_lost": 0, "roundtrip_added": 0, "determinism_hash_sorted": "h",
                  "determinism_hash_shuffled": "h", "fail_cases": [], "kinds_without_case": [],
                  "shapes_import_rows": 1, "in_graph_shape_constraints": 1, "nodes": 1, "relationships": 0}
        environ = {"NEO4J_PASSWORD": "x"}
        environ.update(env or {})
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, environ, clear=False), \
                mock.patch.dict(_sys.modules, {"neo4j": mock.MagicMock()}), \
                mock.patch.object(lv, "run", return_value=report):
            if not env:
                os.environ.pop("LPG_CONTAINER", None)
            args = ["--config", CONFIG, "--shapes", SHAPES, "--bolt", "bolt://127.0.0.1:1", "--import-dir", tmp,
                    "--merged", MODULE, "--loadable", MODULE, "--inferred", MODULE,
                    "--report", os.path.join(tmp, "r.json"), *extra_args, MODULE]
            return run_main(lv.main, args)

    def test_container_option_is_printed(self):
        code, out = self.main_with(["--container", "lpg-run-7"])
        self.assertEqual(code, 0, out)
        self.assertIn("docker rm -f -v lpg-run-7", out)
        self.assertNotIn("lpg-projection", out)

    def test_container_environment_variable_is_printed(self):
        code, out = self.main_with(env={"LPG_CONTAINER": "lpg-env-run"})
        self.assertEqual(code, 0, out)
        self.assertIn("docker rm -f -v lpg-env-run", out)

    def test_default_container_name(self):
        code, out = self.main_with()
        self.assertIn("docker rm -f -v lpg-projection", out)

    # 7: build.py checks the step 4 gate items
    def test_check_serialised_passes_on_the_build_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            loadable, inferred_path = os.path.join(tmp, "loadable.nt"), os.path.join(tmp, "inferred.nt")
            self.assertEqual(run_main(build.main, ["loadable", "--output", loadable, MODULE])[0], 0)
            with open(inferred_path, "w", encoding="utf-8") as f:
                f.write(f"<{LIB}work/W-0043> <{RDF.type}> <{LIB}Work> .\n")
            code, out = run_main(build.main, ["check-serialised", "--loadable", loadable, "--inferred", inferred_path])
        self.assertEqual(code, 0, out)

    def test_check_serialised_finds_order_duplicates_and_declarations(self):
        a = f"<{LIB}a> <{RDF.type}> <{LIB}Work> .".encode()
        b = f"<{LIB}b> <{RDF.type}> <{LIB}Work> .".encode()
        self.assertTrue(any("byte order" in f for f in build.check_serialised(b + b"\n" + a + b"\n", b"")))
        self.assertTrue(any("byte order" in f for f in build.check_serialised(a + b"\n" + a + b"\n", b"")))
        declaration = f"<{LIB}a> <{RDF.type}> <{OWL.NamedIndividual}> .\n".encode()
        self.assertTrue(any("filter drops" in f for f in build.check_serialised(b"", declaration)))
        label = f'<{LIB}a> <{RDFS.label}> "x" .\n'.encode()
        self.assertTrue(any("filter drops" in f for f in build.check_serialised(b"", label)))
        self.assertEqual(build.check_serialised(a + b"\n" + b + b"\n", a + b"\n"), [])


if __name__ == "__main__":
    unittest.main()
