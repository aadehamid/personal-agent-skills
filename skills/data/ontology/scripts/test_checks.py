"""Tests for check_taxonomy.py and check_requirements.py.

Run: uv run --no-project --with rdflib --with pyyaml python3 -m unittest test_checks
(from this folder). Each test breaks the shipped template in one way and asserts the
exact check that fires, so a check that passes vacuously fails here.
"""
import contextlib
import copy
import io
import os
import unittest

import yaml
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS

import check_requirements
import check_taxonomy

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = os.path.join(HERE, "..", "templates")
LIB = "https://id.example.org/library/"


def lib(name):
    return URIRef(LIB + name)


def skeleton():
    return Graph().parse(os.path.join(TEMPLATES, "ontology-skeleton.ttl"), format="turtle")


def requirements():
    with open(os.path.join(TEMPLATES, "requirements.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


class TaxonomyChecks(unittest.TestCase):
    def assertFails(self, g, name, fragment):
        fails = check_taxonomy.check(g)
        self.assertTrue(any(n == name and fragment in m for n, m in fails),
                        f"expected {name!r} containing {fragment!r}, got {fails}")

    def test_skeleton_passes(self):
        self.assertEqual(check_taxonomy.check(skeleton()), [])

    def test_missing_definition(self):
        g = skeleton()
        g.remove((lib("renewal"), SKOS.definition, None))
        self.assertFails(g, "definition", "lib:renewal has no skos:definition")

    def test_two_parents(self):
        g = skeleton()
        g.add((lib("renewal"), SKOS.broader, lib("lending-activity")))
        self.assertFails(g, "parent", "lib:renewal has 2 skos:broader parents")

    def test_floating_concept(self):
        g = skeleton()
        g.remove((lib("renewal"), SKOS.broader, None))
        self.assertFails(g, "parent", "lib:renewal has 0 skos:broader parents")

    def test_top_concept_with_parent(self):
        g = skeleton()
        g.add((lib("overdue"), SKOS.broader, lib("on-loan")))
        self.assertFails(g, "parent", "lib:overdue is a top concept and also has skos:broader")

    def test_cycle(self):
        g = skeleton()
        g.remove((lib("circulation"), SKOS.topConceptOf, None))
        g.add((lib("circulation"), SKOS.broader, lib("renewal")))
        self.assertFails(g, "parent", "skos:broader cycle")

    def test_duplicate_notation_in_scheme(self):
        g = skeleton()
        g.set((lib("overdue"), SKOS.notation, Literal("LS-1")))
        self.assertFails(g, "notation", 'share the notation "LS-1"')

    def test_label_collision_ignores_case(self):
        g = skeleton()
        g.set((lib("overdue"), SKOS.prefLabel, Literal("on LOAN", lang="en")))
        self.assertFails(g, "collision", 'share the label "on loan"')

    def test_two_preferred_labels_in_one_language(self):
        g = skeleton()
        g.add((lib("overdue"), SKOS.prefLabel, Literal("Late", lang="en")))
        self.assertFails(g, "label", "lib:overdue has 2 skos:prefLabel values in language en")

    def test_untagged_literal(self):
        g = skeleton()
        g.set((lib("Copy"), RDFS.label, Literal("Copy")))
        self.assertFails(g, "untagged", 'lib:Copy rdfs:label "Copy" has no language tag')

    def test_notation_and_version_need_no_tag(self):
        fails = check_taxonomy.check(skeleton())
        self.assertFalse([f for f in fails if f[0] == "untagged"])

    def test_blank_node(self):
        g = skeleton()
        g.add((lib("Loan"), RDFS.comment, BNode()))
        self.assertFails(g, "blank-node", "lib:Loan rdfs:comment")

    def test_property_with_two_domains(self):
        g = skeleton()
        g.add((lib("dueDate"), RDFS.domain, lib("Copy")))
        self.assertFails(g, "domain-range", "lib:dueDate has 2 rdfs:domain values")

    def test_property_of_two_kinds(self):
        g = skeleton()
        g.add((lib("dueDate"), RDF.type, OWL.ObjectProperty))
        self.assertFails(g, "property-kind", "lib:dueDate is typed 2")

    def test_literal_range(self):
        g = skeleton()
        g.set((lib("dueDate"), RDFS.range, RDFS.Literal))
        self.assertFails(g, "domain-range", "lib:dueDate has range rdfs:Literal")

    def test_class_without_label(self):
        g = skeleton()
        g.remove((lib("Member"), RDFS.label, None))
        self.assertFails(g, "label", "lib:Member has no rdfs:label")

    def test_cli_exit_codes(self):
        path = os.path.join(TEMPLATES, "ontology-skeleton.ttl")
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            self.assertEqual(check_taxonomy.main([path]), 0)
            self.assertEqual(check_taxonomy.main([os.path.join(TEMPLATES, "requirements.yaml")]), 2)
        self.assertIn("all checks pass", out.getvalue())
        self.assertIn("ERROR cannot read", out.getvalue())


class RequirementsChecks(unittest.TestCase):
    def assertFails(self, req, name, fragment):
        fails = check_requirements.check(req)
        self.assertTrue(any(n == name and fragment in m for n, m in fails),
                        f"expected {name!r} containing {fragment!r}, got {fails}")

    def test_template_passes(self):
        self.assertEqual(check_requirements.check(requirements()), [])

    def test_need_out_of_scope(self):
        req = requirements()
        req["competency_questions"][0]["needs"].append("fines")
        self.assertFails(req, "conflict", "CQ1 needs 'fines', which scope.out excludes")

    def test_rationale_names_out_of_scope_area(self):
        req = requirements()
        req["competency_questions"][1]["rationale"] = "Requires the fines history."
        self.assertFails(req, "conflict", "CQ2 rationale names 'fines'")

    def test_need_not_in_scope(self):
        req = requirements()
        req["competency_questions"][0]["needs"] = ["membership"]
        self.assertFails(req, "conflict", "CQ1 needs 'membership', which scope.in does not list")

    def test_area_in_and_out(self):
        req = requirements()
        req["scope"]["out"].append("Lending")
        self.assertFails(req, "conflict", "area 'lending' is both in and out of scope")

    def test_thin_input_needs_note(self):
        req = requirements()
        req["inputs"]["representative_data"]["note"] = ""
        self.assertFails(req, "inputs", "input 'representative_data' is thin and needs a note")

    def test_confirmed_assumption_needs_record(self):
        req = requirements()
        req["assumptions"][0]["status"] = "confirmed"
        self.assertFails(req, "assumptions", "A1 is confirmed but names no decision record")

    def test_missing_field(self):
        req = copy.deepcopy(requirements())
        del req["constraints"]
        self.assertFails(req, "schema", "missing field 'constraints'")


if __name__ == "__main__":
    unittest.main()
