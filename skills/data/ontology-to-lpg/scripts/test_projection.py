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

import build
import check_projection_rules as cpr
import in_graph_shapes as igs
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
        self.assertEqual(self.broken(change), [
            ("rule-1", "Rule 1: lib:secretLink has 0 kinds; it needs exactly one of owl:ObjectProperty, "
                       "owl:DatatypeProperty and owl:AnnotationProperty"),
            ("rule-2", "Rule 2: no cardinality stated for lib:secretLink")])

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
        g = Graph()
        g.add((lib("Copy"), RDF.type, OWL.Class))
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
                "in_graph_shape_constraints": 9, "shapes_import_rows": 9}

    def test_check_report(self):
        man = {"input_fingerprint": "f", "shapes_fingerprint": "s"}
        self.assertEqual(build.check_report(man, self.good_report(man)), [])
        for key, value in (("shapes_fingerprint", "old"), ("in_graph_mutant_violations", 0), ("roundtrip_added", 3),
                           ("determinism_hash_shuffled", "other"), ("shapes_import_rows", 8)):
            rep = self.good_report(man)
            rep[key] = value
            self.assertTrue(build.check_report(man, rep), key)

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


if __name__ == "__main__":
    unittest.main()
