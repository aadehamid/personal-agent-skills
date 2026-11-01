"""Tests for check_taxonomy.py, check_requirements.py, templates/check.sh and the shapes skeleton.

Run from this folder:
  uv run --no-project --with rdflib --with pyyaml --with pyshacl python3 -m unittest test_checks

Each one-break test breaks a shipped template in one way and asserts that exactly the
named check fires with its message, so a check that passes vacuously, or fires for the
wrong reason, fails here.
"""
import contextlib
import copy
import io
import os
import shutil
import subprocess
import tempfile
import unittest

import yaml
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SH, SKOS, XSD

import check_requirements
import check_taxonomy

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = os.path.join(HERE, "..", "templates")
SKELETON = os.path.join(TEMPLATES, "ontology-skeleton.ttl")
SHAPES = os.path.join(TEMPLATES, "shapes-skeleton.ttl")
REQUIREMENTS = os.path.join(TEMPLATES, "requirements.yaml")
LIB = "https://id.example.org/library/"


def lib(name):
    return URIRef(LIB + name)


def skeleton():
    return Graph().parse(SKELETON, format="turtle")


def requirements():
    with open(REQUIREMENTS, encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_main(main, argv):
    """Call a checker's main() and return (exit code, everything it printed)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = main(argv)
    return code, out.getvalue()


class OneBreak:
    """assertOnly: every failure has the expected check name, and one has the fragment."""

    def assertOnly(self, fails, name, fragment):
        self.assertTrue(fails, f"expected {name!r} containing {fragment!r}, got no failure")
        self.assertEqual({n for n, _ in fails}, {name}, f"unexpected checks fired: {fails}")
        self.assertTrue(any(fragment in m for _, m in fails), f"no {fragment!r} in {fails}")


class TaxonomyChecks(OneBreak, unittest.TestCase):
    def broken(self, mutate, name, fragment):
        g = skeleton()
        mutate(g)
        self.assertOnly(check_taxonomy.check(g), name, fragment)

    def test_skeleton_passes(self):
        self.assertEqual(check_taxonomy.check(skeleton()), [])

    # blank-node and untagged
    def test_blank_node(self):
        self.broken(lambda g: g.add((lib("Loan"), RDFS.seeAlso, BNode())), "blank-node", "lib:Loan rdfs:seeAlso")

    def test_untagged_literal(self):
        self.broken(lambda g: g.set((lib("Copy"), RDFS.label, Literal("Copy"))),
                    "untagged", 'lib:Copy rdfs:label "Copy" has no language tag')

    def test_xsd_string_counts_as_untagged(self):
        self.broken(lambda g: g.set((lib("Copy"), SKOS.definition, Literal("A copy.", datatype=XSD.string))),
                    "untagged", "lib:Copy skos:definition")

    # label
    def test_concept_without_preferred_label(self):
        self.broken(lambda g: g.remove((lib("overdue"), SKOS.prefLabel, None)), "label", "lib:overdue has no skos:prefLabel")

    def test_two_preferred_labels_in_one_language(self):
        self.broken(lambda g: g.add((lib("overdue"), SKOS.prefLabel, Literal("Late", lang="en"))),
                    "label", "lib:overdue has 2 skos:prefLabel values in language en")

    def test_class_without_label(self):
        self.broken(lambda g: g.remove((lib("Member"), RDFS.label, None)), "label", "lib:Member has no rdfs:label")

    def test_property_without_label(self):
        self.broken(lambda g: g.remove((lib("borrower"), RDFS.label, None)), "label", "lib:borrower has no rdfs:label")

    # definition
    def test_concept_without_definition(self):
        self.broken(lambda g: g.remove((lib("renewal"), SKOS.definition, None)), "definition", "lib:renewal has no skos:definition")

    def test_class_without_definition(self):
        self.broken(lambda g: g.remove((lib("Copy"), SKOS.definition, None)), "definition", "lib:Copy has no skos:definition")

    def test_property_without_definition(self):
        self.broken(lambda g: g.remove((lib("dueDate"), SKOS.definition, None)), "definition", "lib:dueDate has no skos:definition")

    # notation
    def test_concept_without_notation(self):
        self.broken(lambda g: g.remove((lib("returned"), SKOS.notation, None)), "notation", "lib:returned has no skos:notation")

    def test_duplicate_notation_in_scheme(self):
        self.broken(lambda g: g.set((lib("overdue"), SKOS.notation, Literal("LS-1"))), "notation", 'share the notation "LS-1"')

    # scheme
    def test_concept_in_no_scheme(self):
        self.broken(lambda g: g.remove((lib("renewal"), SKOS.inScheme, None)), "scheme", "lib:renewal is in no skos:ConceptScheme")

    def test_misspelled_scheme(self):
        self.broken(lambda g: g.set((lib("renewal"), SKOS.inScheme, lib("lendng"))), "scheme",
                    "lib:renewal is in lib:lendng, which is not a declared skos:ConceptScheme")

    def test_misspelled_top_concept_of(self):
        def mutate(g):
            g.remove((lib("renewal"), SKOS.broader, None))
            g.add((lib("renewal"), SKOS.topConceptOf, lib("lendng")))
        self.broken(mutate, "scheme", "lib:renewal is a top concept of lib:lendng, which is not a declared skos:ConceptScheme")

    def test_class_listed_as_top_concept(self):
        self.broken(lambda g: g.add((lib("loan-state"), SKOS.hasTopConcept, lib("Loan"))), "scheme",
                    "lists lib:Loan as a top concept, but lib:Loan is not a declared skos:Concept")

    def test_listed_top_concept_without_top_concept_of(self):
        def mutate(g):
            g.remove((lib("returned"), SKOS.topConceptOf, None))
            g.add((lib("returned"), SKOS.broader, lib("on-loan")))
        self.broken(mutate, "scheme", "lib:loan-state lists lib:returned as a top concept, but lib:returned has no skos:topConceptOf it")

    # parent
    def test_two_parents(self):
        self.broken(lambda g: g.add((lib("renewal"), SKOS.broader, lib("lending-activity"))), "parent", "lib:renewal has 2 skos:broader parents")

    def test_floating_concept(self):
        self.broken(lambda g: g.remove((lib("renewal"), SKOS.broader, None)), "parent", "lib:renewal has 0 skos:broader parents")

    def test_top_concept_with_parent(self):
        self.broken(lambda g: g.add((lib("overdue"), SKOS.broader, lib("on-loan"))), "parent", "lib:overdue is a top concept and also has skos:broader")

    def test_undeclared_parent(self):
        def mutate(g):
            g.set((lib("renewal"), SKOS.broader, lib("circulatoin")))
        g = skeleton()
        mutate(g)
        fails = check_taxonomy.check(g)
        self.assertIn(("parent", "lib:renewal has parent lib:circulatoin, which is not a declared skos:Concept"), fails)

    def test_cycle(self):
        # Two concepts under one another; circulation stays the scheme's top concept.
        def mutate(g):
            g.set((lib("renewal"), SKOS.broader, lib("lending-activity")))
            g.set((lib("lending-activity"), SKOS.broader, lib("renewal")))
        self.broken(mutate, "parent", "skos:broader cycle")

    # collision
    def test_label_collision_ignores_case(self):
        self.broken(lambda g: g.set((lib("overdue"), SKOS.prefLabel, Literal("on LOAN", lang="en"))), "collision", 'share the label "on loan"')

    # property-kind
    def test_property_of_two_kinds(self):
        g = skeleton()
        g.add((lib("dueDate"), RDF.type, OWL.ObjectProperty))
        fails = check_taxonomy.check(g)
        # Two kinds also makes the range wrong for one of them, so both checks fire.
        self.assertEqual({n for n, _ in fails}, {"property-kind", "kind-range"}, fails)
        self.assertIn(("property-kind", "lib:dueDate is typed 2 of owl:ObjectProperty, "
                                        "owl:DatatypeProperty and owl:AnnotationProperty; it needs exactly one"), fails)

    def test_bare_rdf_property(self):
        def mutate(g):
            g.remove((lib("loanOf"), RDF.type, OWL.ObjectProperty))
            g.add((lib("loanOf"), RDF.type, RDF.Property))
        self.broken(mutate, "property-kind", "lib:loanOf is typed 0")

    def test_characteristic_only_property(self):
        # Declared only as owl:TransitiveProperty: still a property, so it needs a kind, a label and a definition.
        g = skeleton()
        g.add((lib("partOf"), RDF.type, OWL.TransitiveProperty))
        fails = check_taxonomy.check(g)
        self.assertEqual({n for n, _ in fails}, {"property-kind", "label", "definition"}, fails)
        self.assertIn(("property-kind", "lib:partOf is typed 0 of owl:ObjectProperty, "
                                        "owl:DatatypeProperty and owl:AnnotationProperty; it needs exactly one"), fails)

    def test_undeclared_local_predicate(self):
        self.broken(lambda g: g.add((lib("Copy"), lib("lpgNme"), Literal("Item", lang="en"))), "property-kind",
                    "lib:lpgNme is used as a predicate but is not declared as a property")

    # domain-range
    def test_property_with_two_domains(self):
        self.broken(lambda g: g.add((lib("dueDate"), RDFS.domain, lib("Copy"))), "domain-range", "lib:dueDate has 2 rdfs:domain values")

    def test_property_without_range(self):
        self.broken(lambda g: g.remove((lib("borrower"), RDFS.range, None)), "domain-range", "lib:borrower has 0 rdfs:range values")

    def test_literal_range(self):
        self.broken(lambda g: g.set((lib("dueDate"), RDFS.range, RDFS.Literal)), "domain-range", "lib:dueDate has range rdfs:Literal")

    def test_misspelled_range(self):
        self.broken(lambda g: g.set((lib("borrower"), RDFS.range, lib("Membr"))),
                    "domain-range", "lib:borrower has rdfs:range lib:Membr, which is neither declared")

    def test_allowed_namespace_resolves(self):
        g = skeleton()
        g.set((lib("borrower"), RDFS.range, URIRef("https://example.org/people#Person")))
        self.assertTrue(check_taxonomy.check(g))
        self.assertEqual(check_taxonomy.check(g, ["https://example.org/people#"]), [])

    # kind-range
    def test_object_property_with_datatype_range(self):
        self.broken(lambda g: g.set((lib("borrower"), RDFS.range, XSD.string)),
                    "kind-range", "lib:borrower is an owl:ObjectProperty but its range xsd:string is a datatype")

    def test_datatype_property_with_class_range(self):
        self.broken(lambda g: g.set((lib("dueDate"), RDFS.range, lib("Copy"))),
                    "kind-range", "lib:dueDate is an owl:DatatypeProperty but its range lib:Copy is not a datatype")

    def test_dir_lang_string_is_a_datatype(self):
        # RDF 1.2's directional language string, as the ontology-to-lpg checker also accepts.
        g = skeleton()
        g.set((lib("dueDate"), RDFS.range, URIRef(str(RDF) + "dirLangString")))
        self.assertEqual(check_taxonomy.check(g), [])

    # untyped
    def test_untyped_concept(self):
        def mutate(g):
            g.add((lib("hold"), SKOS.inScheme, lib("lending")))
            g.add((lib("hold"), SKOS.broader, lib("circulation")))
            g.add((lib("hold"), SKOS.prefLabel, Literal("Hold", lang="en")))
        self.broken(mutate, "untyped", "lib:hold is the subject of triples but has no rdf:type")

    def test_notation_and_version_need_no_tag(self):
        self.assertFalse([f for f in check_taxonomy.check(skeleton()) if f[0] == "untagged"])

    # untyped: any IRI used as a subject (finding #1 of the db5ae6d review)
    def test_untyped_subject_with_any_predicate(self):
        for pred, obj in ((SKOS.altLabel, Literal("Reservation", lang="en")),
                          (SKOS.note, Literal("A note.", lang="en")),
                          (SKOS.narrower, lib("renewal")),
                          (RDFS.comment, Literal("A comment.", lang="en"))):
            with self.subTest(pred=pred):
                self.broken(lambda g: g.add((lib("hold"), pred, obj)),
                            "untyped", "lib:hold is the subject of triples but has no rdf:type")

    # annotation properties (finding #3)
    def test_incomplete_annotation_property(self):
        g = skeleton()
        g.add((lib("lpgName"), RDF.type, OWL.AnnotationProperty))
        fails = check_taxonomy.check(g)
        self.assertEqual(sorted(fails), [("definition", "lib:lpgName has no skos:definition"),
                                         ("label", "lib:lpgName has no rdfs:label")])

    def test_annotation_property_with_a_domain(self):
        self.broken(lambda g: g.add((lib("maintenanceNote"), RDFS.domain, lib("Loan"))),
                    "domain-range", "lib:maintenanceNote is an annotation property and has an rdfs:domain")

    def test_annotation_property_with_a_range(self):
        self.broken(lambda g: g.add((lib("maintenanceNote"), RDFS.range, RDF.langString)),
                    "domain-range", "lib:maintenanceNote is an annotation property and has an rdfs:range")

    def test_code_property_values_need_no_tag(self):
        # A property defined here, not in the skeleton: a copy's shelf mark is a code, not language text.
        g = skeleton()
        g.add((lib("shelfMark"), RDF.type, OWL.DatatypeProperty))
        g.add((lib("shelfMark"), RDFS.label, Literal("shelf mark", lang="en")))
        g.add((lib("shelfMark"), SKOS.definition, Literal("Relates a copy to the code that places it on the shelves.", lang="en")))
        g.add((lib("shelfMark"), RDFS.domain, lib("Copy")))
        g.add((lib("shelfMark"), RDFS.range, XSD.string))
        g.add((lib("copy1"), RDF.type, lib("Copy")))
        g.add((lib("copy1"), lib("shelfMark"), Literal("QA76.9 .D3")))
        self.assertOnly(check_taxonomy.check(g), "untagged", 'lib:copy1 lib:shelfMark "QA76.9 .D3" has no language tag')
        self.assertEqual(check_taxonomy.check(g, code_properties=[LIB + "shelfMark"]), [])

    def test_complete_annotation_property_needs_no_domain_or_range(self):
        g = skeleton()
        g.add((lib("lpgName"), RDF.type, OWL.AnnotationProperty))
        g.add((lib("lpgName"), RDFS.label, Literal("property-graph name", lang="en")))
        g.add((lib("lpgName"), SKOS.definition, Literal("Relates a term to the name it takes in the property graph.", lang="en")))
        self.assertEqual(check_taxonomy.check(g), [])

    # literal targets (finding #4)
    def test_literal_domain_range_and_superclass(self):
        target = Literal(LIB + "Member", datatype=XSD.anyURI)
        for pred, subject, axis in ((RDFS.domain, "borrower", "rdfs:domain"),
                                    (RDFS.range, "borrower", "rdfs:range"),
                                    (RDFS.subClassOf, "Member", "rdfs:subClassOf")):
            with self.subTest(axis=axis):
                self.broken(lambda g: g.set((lib(subject), pred, target)),
                            "domain-range", f"lib:{subject} has {axis}")
                g = skeleton()
                g.set((lib(subject), pred, target))
                self.assertTrue(any("a literal; it must be an IRI" in m for _, m in check_taxonomy.check(g)))

    # rdfs:Class (finding #8)
    def test_bare_rdfs_class_is_checked(self):
        g = skeleton()
        g.add((lib("Fine"), RDF.type, RDFS.Class))
        g.set((lib("borrower"), RDFS.range, lib("Fine")))
        fails = check_taxonomy.check(g)
        self.assertEqual(sorted(fails), [("class-kind", "lib:Fine is an rdfs:Class; write classes as owl:Class"),
                                         ("definition", "lib:Fine has no skos:definition"),
                                         ("label", "lib:Fine has no rdfs:label")])

    def test_documented_rdfs_class_still_fails_class_kind(self):
        def mutate(g):
            g.add((lib("Fine"), RDF.type, RDFS.Class))
            g.add((lib("Fine"), RDFS.label, Literal("Fine", lang="en")))
            g.add((lib("Fine"), SKOS.definition, Literal("A charge a member owes.", lang="en")))
        self.broken(mutate, "class-kind", "lib:Fine is an rdfs:Class")

    # the command line
    def test_cli_pass_is_0(self):
        code, out = run_main(check_taxonomy.main, [SKELETON])
        self.assertEqual(code, 0)
        self.assertIn("all checks pass", out)

    def test_cli_failure_is_1(self):
        g = skeleton()
        g.remove((lib("renewal"), SKOS.definition, None))
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "broken.ttl")
            g.serialize(path, format="turtle")
            code, out = run_main(check_taxonomy.main, [path])
        self.assertEqual(code, 1)
        self.assertIn("FAIL definition: lib:renewal has no skos:definition", out)

    def test_cli_bad_input_is_2(self):
        self.assertEqual(run_main(check_taxonomy.main, [])[0], 2)
        self.assertEqual(run_main(check_taxonomy.main, [REQUIREMENTS])[0], 2)
        self.assertEqual(run_main(check_taxonomy.main, ["--allow-namespace=", SKELETON])[0], 2)
        self.assertEqual(run_main(check_taxonomy.main, ["--code-property=", SKELETON])[0], 2)


class QskosChecks(OneBreak, unittest.TestCase):
    """One break per qSKOS issue that check_taxonomy.py adds (references/quality.md, "The qSKOS issues")."""

    def broken(self, mutate, name, fragment):
        g = skeleton()
        mutate(g)
        self.assertOnly(check_taxonomy.check(g), name, fragment)

    def test_invalid_language_tag(self):
        # On a class, so the odd language does not also break concept language coverage.
        self.broken(lambda g: g.add((lib("Copy"), SKOS.editorialNote, Literal("Check.", lang="e"))),
                    "lang-tag", "has the language tag 'e'")

    def test_valid_language_tags_pass(self):
        # Well-formed under RFC 5646, section 2.1: a 4-letter language, grandfathered tags, private use.
        for tag in ("en", "en-GB", "zh-Hant-TW", "sr-Latn-RS", "de-CH-1996", "x-local", "abcd", "i-klingon"):
            self.assertTrue(check_taxonomy.well_formed_tag(tag), tag)

    def test_incomplete_language_coverage(self):
        self.broken(lambda g: g.add((lib("overdue"), SKOS.prefLabel, Literal("En retard", lang="fr"))),
                    "language", "lib:renewal has no language-tagged literal in fr")

    def test_language_used_only_in_an_alternative_label_counts(self):
        self.broken(lambda g: g.add((lib("renewal"), SKOS.altLabel, Literal("Renouvellement", lang="fr"))),
                    "language", "lib:overdue has no language-tagged literal in fr")

    def test_empty_label(self):
        self.broken(lambda g: g.add((lib("renewal"), SKOS.altLabel, Literal("  ", lang="en"))),
                    "label", "lib:renewal has an empty skos:altLabel")

    def test_scheme_without_label(self):
        self.broken(lambda g: g.remove((lib("loan-state"), SKOS.prefLabel, None)),
                    "label", "lib:loan-state is a skos:ConceptScheme with no skos:prefLabel")

    def test_unprintable_character_in_label(self):
        self.broken(lambda g: g.add((lib("renewal"), SKOS.altLabel, Literal("Re\nnewal", lang="en"))),
                    "label-chars", "holds unprintable characters (Cc)")

    def test_alternative_label_overlaps_another_concept(self):
        self.broken(lambda g: g.add((lib("returned"), SKOS.altLabel, Literal("overdue", lang="en"))),
                    "collision", 'lib:overdue, lib:returned share the label "overdue" (en)')

    def test_two_concepts_share_a_hidden_label(self):
        def mutate(g):
            g.add((lib("on-loan"), SKOS.hiddenLabel, Literal("Shared", lang="en")))
            g.add((lib("returned"), SKOS.hiddenLabel, Literal("Shared", lang="en")))
        self.broken(mutate, "collision", 'lib:on-loan, lib:returned share the label "shared" (en)')

    def test_label_shared_across_schemes(self):
        self.broken(lambda g: g.add((lib("renewal"), SKOS.altLabel, Literal("Returned", lang="en"))),
                    "collision", 'lib:renewal, lib:returned share the label "returned" (en)')

    def test_same_literal_as_preferred_and_alternative_label(self):
        self.broken(lambda g: g.add((lib("renewal"), SKOS.altLabel, Literal("Renewal", lang="en"))),
                    "disjoint-labels", 'lib:renewal has "Renewal" as both skos:prefLabel and skos:altLabel')

    def test_concept_related_to_itself(self):
        self.broken(lambda g: g.add((lib("renewal"), SKOS.related, lib("renewal"))),
                    "related", "lib:renewal is linked to itself by skos:related")

    def test_concept_linked_to_itself_by_any_semantic_relation(self):
        self.broken(lambda g: g.add((lib("renewal"), SKOS.semanticRelation, lib("renewal"))),
                    "related", "lib:renewal is linked to itself by skos:semanticRelation")

    def test_narrower_to_itself_is_a_reflexive_relation(self):
        self.broken(lambda g: g.add((lib("renewal"), SKOS.narrower, lib("renewal"))),
                    "related", "lib:renewal is linked to itself by skos:narrower")

    def test_siblings_also_related(self):
        def mutate(g):
            g.add((lib("renewal"), SKOS.related, lib("lending-activity")))
            g.add((lib("lending-activity"), SKOS.related, lib("renewal")))
        self.broken(mutate, "related", "are siblings and also skos:related")

    def test_siblings_also_related_by_a_mapping(self):
        # In one scheme, so mapping misuse fires too; the sibling clash must be among the failures.
        g = skeleton()
        g.add((lib("renewal"), SKOS.relatedMatch, lib("lending-activity")))
        g.add((lib("lending-activity"), SKOS.relatedMatch, lib("renewal")))
        self.assertIn(("related", "lib:lending-activity and lib:renewal are siblings and also skos:relatedMatch"),
                      check_taxonomy.check(g))

    def test_related_to_an_ancestor(self):
        def mutate(g):
            g.add((lib("renewal"), SKOS.related, lib("circulation")))
            g.add((lib("circulation"), SKOS.related, lib("renewal")))
        self.broken(mutate, "related", "are hierarchically related and also skos:related")

    def test_related_stated_one_way(self):
        self.broken(lambda g: g.add((lib("on-loan"), SKOS.related, lib("overdue"))),
                    "reciprocal", "lib:on-loan skos:related lib:overdue has no skos:related the other way")

    def test_exact_match_stated_one_way(self):
        self.broken(lambda g: g.add((lib("circulation"), SKOS.exactMatch, lib("overdue"))),
                    "reciprocal", "lib:circulation skos:exactMatch lib:overdue has no skos:exactMatch the other way")

    def test_one_way_mapping_to_an_outside_concept_passes(self):
        g = skeleton()
        g.add((lib("circulation"), SKOS.closeMatch, URIRef("https://ext.example.org/circulation")))
        self.assertEqual(check_taxonomy.check(g), [])

    def test_top_concept_not_listed_by_its_scheme(self):
        self.broken(lambda g: g.remove((lib("loan-state"), SKOS.hasTopConcept, lib("returned"))),
                    "reciprocal", "but lib:loan-state has no skos:hasTopConcept lib:returned")

    def test_narrower_without_broader(self):
        self.broken(lambda g: g.add((lib("lending-activity"), SKOS.narrower, lib("renewal"))),
                    "reciprocal", "lib:lending-activity skos:narrower lib:renewal has no skos:broader the other way")

    def test_solely_transitive_relation(self):
        def mutate(g):
            g.add((lib("on-loan"), SKOS.broaderTransitive, lib("circulation")))
            g.add((lib("circulation"), SKOS.narrowerTransitive, lib("on-loan")))
        self.broken(mutate, "transitive", "lib:on-loan skos:broaderTransitive lib:circulation has no skos:broader path")

    def test_transitive_relation_stated_one_way(self):
        self.broken(lambda g: g.add((lib("renewal"), SKOS.broaderTransitive, lib("circulation"))),
                    "reciprocal", "lib:renewal skos:broaderTransitive lib:circulation has no skos:narrowerTransitive")

    def test_transitive_relation_backed_by_a_two_step_path_passes(self):
        g = skeleton()
        g.set((lib("renewal"), SKOS.broader, lib("lending-activity")))
        g.add((lib("renewal"), SKOS.broaderTransitive, lib("circulation")))
        g.add((lib("circulation"), SKOS.narrowerTransitive, lib("renewal")))
        self.assertEqual(check_taxonomy.check(g), [])

    def test_transitive_relation_backed_by_broader_passes(self):
        g = skeleton()
        g.add((lib("renewal"), SKOS.broaderTransitive, lib("circulation")))
        g.add((lib("circulation"), SKOS.narrowerTransitive, lib("renewal")))
        self.assertEqual(check_taxonomy.check(g), [])

    def test_scheme_without_top_concept(self):
        def mutate(g):
            g.add((lib("hold-state"), RDF.type, SKOS.ConceptScheme))
            g.add((lib("hold-state"), SKOS.prefLabel, Literal("Hold state", lang="en")))
        self.broken(mutate, "scheme", "lib:hold-state has no top concept")

    def test_mapping_to_itself(self):
        self.broken(lambda g: g.add((lib("overdue"), SKOS.closeMatch, lib("overdue"))),
                    "related", "lib:overdue is linked to itself by skos:closeMatch")

    def test_mapping_inside_one_scheme(self):
        def mutate(g):
            g.add((lib("overdue"), SKOS.closeMatch, lib("returned")))
            g.add((lib("returned"), SKOS.closeMatch, lib("overdue")))
        self.broken(mutate, "mapping", "but both are in lib:loan-state")

    def test_mapping_between_concepts_in_no_scheme(self):
        # Removing the schemes also fails "scheme"; the mapping misuse must be among the failures.
        g = skeleton()
        for c in ("overdue", "returned"):
            g.remove((lib(c), SKOS.inScheme, None))
        g.add((lib("overdue"), SKOS.closeMatch, lib("returned")))
        g.add((lib("returned"), SKOS.closeMatch, lib("overdue")))
        self.assertIn(("mapping", "lib:overdue skos:closeMatch lib:returned, but both are in no scheme; "
                                  "a mapping joins different schemes"), check_taxonomy.check(g))

    def test_exact_match_clashes_with_broad_match(self):
        ext = URIRef("https://ext.example.org/circulation")
        def mutate(g):
            g.add((lib("circulation"), SKOS.exactMatch, ext))
            g.add((lib("circulation"), SKOS.broadMatch, ext))
        self.broken(mutate, "mapping", "lib:circulation skos:broadMatch <https://ext.example.org/circulation>, and a skos:exactMatch chain")

    def test_exact_match_clashes_with_narrow_match(self):
        ext = URIRef("https://ext.example.org/circulation")
        def mutate(g):
            g.add((lib("circulation"), SKOS.exactMatch, ext))
            g.add((lib("circulation"), SKOS.narrowMatch, ext))
        self.broken(mutate, "mapping", "skos:narrowMatch <https://ext.example.org/circulation>, and a skos:exactMatch chain")

    def test_clash_through_a_chain_of_exact_matches(self):
        # circulation and overdue (different schemes) both exactMatch one outside concept, so a chain joins them.
        ext = URIRef("https://ext.example.org/one")
        def mutate(g):
            g.add((lib("circulation"), SKOS.exactMatch, ext))
            g.add((lib("overdue"), SKOS.exactMatch, ext))
            g.add((lib("circulation"), SKOS.relatedMatch, lib("overdue")))
            g.add((lib("overdue"), SKOS.relatedMatch, lib("circulation")))
        self.broken(mutate, "mapping", "lib:circulation skos:relatedMatch lib:overdue, and a skos:exactMatch chain")

    def test_undefined_skos_term(self):
        self.broken(lambda g: g.add((lib("renewal"), URIRef(str(SKOS) + "subjectIndicator"), lib("Loan"))),
                    "skos-term", "skos:subjectIndicator is in the SKOS namespace but is not a SKOS term")

    def test_concept_outside_http(self):
        def mutate(g):
            for p, o in list(g.predicate_objects(lib("renewal"))):
                g.add((URIRef("urn:example:renewal"), p, o))
            g.remove((lib("renewal"), None, None))
        self.broken(mutate, "uri-scheme", "<urn:example:renewal> is not an http or https IRI")

    def test_upper_case_http_scheme_passes(self):
        def mutate(g):
            for p, o in list(g.predicate_objects(lib("renewal"))):
                g.add((URIRef("HTTPS://id.example.org/library/renewal"), p, o))
            g.remove((lib("renewal"), None, None))
        g = skeleton()
        mutate(g)
        self.assertFalse([f for f in check_taxonomy.check(g) if f[0] == "uri-scheme"])

    def test_non_skos_subject_outside_http_passes(self):
        g = skeleton()
        g.add((URIRef("urn:example:note"), RDF.type, OWL.NamedIndividual))
        self.assertEqual(check_taxonomy.check(g), [])


class QskosRoundTwo(OneBreak, unittest.TestCase):
    """Branches the round-2 review found untested; each test breaks one of them alone, or, where that
    is impossible, asserts the exact failure is present."""

    def broken(self, mutate, name, fragment):
        g = skeleton()
        mutate(g)
        self.assertOnly(check_taxonomy.check(g), name, fragment)

    @staticmethod
    def concept(g, name, parent, notation, label):
        c = lib(name)
        for p, o in ((RDF.type, SKOS.Concept), (SKOS.inScheme, lib("lending")), (SKOS.broader, lib(parent)),
                     (SKOS.notation, Literal(notation)), (SKOS.prefLabel, Literal(label, lang="en")),
                     (SKOS.definition, Literal("A test concept.", lang="en"))):
            g.add((c, p, o))

    def transitive_siblings(self, state):
        """renewal sits under lending-activity, hold-request under hold-activity, and they are related; state(g, c)
        says that each reaches circulation transitively. Neither is the other's ancestor."""
        g = skeleton()
        self.concept(g, "hold-activity", "circulation", "C-3", "Holds")
        self.concept(g, "hold-request", "hold-activity", "C-3-1", "Hold request")
        g.set((lib("renewal"), SKOS.broader, lib("lending-activity")))
        for c in ("renewal", "hold-request"):
            state(g, lib(c))
        g.add((lib("renewal"), SKOS.related, lib("hold-request")))
        g.add((lib("hold-request"), SKOS.related, lib("renewal")))
        return check_taxonomy.check(g)

    # Each direction alone also fails "reciprocal" (its inverse is missing), so the sibling failure is asserted present.
    def test_siblings_under_a_parent_stated_by_broader_transitive(self):
        fails = self.transitive_siblings(lambda g, c: g.add((c, SKOS.broaderTransitive, lib("circulation"))))
        self.assertIn(("related", "lib:hold-request and lib:renewal are siblings and also skos:related"), fails)

    def test_siblings_under_a_parent_stated_by_narrower_transitive(self):
        fails = self.transitive_siblings(lambda g, c: g.add((lib("circulation"), SKOS.narrowerTransitive, c)))
        self.assertIn(("related", "lib:hold-request and lib:renewal are siblings and also skos:related"), fails)

    def test_scheme_with_an_empty_rdfs_label(self):
        self.broken(lambda g: g.add((lib("loan-state"), RDFS.label, Literal("  ", lang="en"))),
                    "label", "lib:loan-state has an empty rdfs:label")

    def test_scheme_with_an_empty_dcterms_title(self):
        self.broken(lambda g: g.add((lib("loan-state"), DCTERMS.title, Literal(" ", lang="en"))),
                    "label", "lib:loan-state has an empty dcterms:title")

    def test_two_preferred_labels_whose_tags_differ_only_in_case(self):
        g = skeleton()
        g.add((lib("overdue"), SKOS.prefLabel, Literal("Late", lang="EN")))
        self.assertIn(("label", "lib:overdue has 2 skos:prefLabel values in language en"), check_taxonomy.check(g))

    def test_self_link_through_a_declared_subproperty(self):
        p = lib("localRelated")
        def mutate(g):
            for pred, obj in ((RDF.type, OWL.ObjectProperty), (RDFS.label, Literal("local related", lang="en")),
                              (SKOS.definition, Literal("A local kind of related.", lang="en")),
                              (RDFS.domain, SKOS.Concept), (RDFS.range, SKOS.Concept), (RDFS.subPropertyOf, SKOS.related)):
                g.add((p, pred, obj))
            g.add((lib("renewal"), p, lib("renewal")))
        self.broken(mutate, "related", "lib:renewal is linked to itself by lib:localRelated")

    def test_every_semantic_self_link(self):
        for pred in sorted(check_taxonomy.SEMANTIC_RELATIONS - {SKOS.broader}):
            with self.subTest(pred=pred):
                self.broken(lambda g: g.add((lib("renewal"), pred, lib("renewal"))), "related", "is linked to itself by")

    def test_broader_to_itself_is_a_parent_failure_only(self):
        g = skeleton()
        g.add((lib("renewal"), SKOS.broader, lib("renewal")))
        self.assertEqual({n for n, _ in check_taxonomy.check(g)}, {"parent"})

    def test_overlap_ignores_language_tag_case_across_schemes(self):
        self.broken(lambda g: g.add((lib("renewal"), SKOS.altLabel, Literal("Returned", lang="EN"))),
                    "collision", 'lib:renewal, lib:returned share the label "returned" (en)')

    def test_preferred_collision_ignores_language_tag_case_in_one_scheme(self):
        self.broken(lambda g: g.set((lib("overdue"), SKOS.prefLabel, Literal("On loan", lang="EN"))),
                    "collision", 'share the label "on loan" (en) in lib:loan-state')

    def test_reciprocal_branches(self):
        # Declared concepts in different schemes, each stated one way.
        for pred, back in ((SKOS.narrowMatch, "skos:broadMatch"), (SKOS.broadMatch, "skos:narrowMatch"),
                           (SKOS.relatedMatch, "skos:relatedMatch"), (SKOS.closeMatch, "skos:closeMatch")):
            with self.subTest(pred=pred):
                self.broken(lambda g: g.add((lib("circulation"), pred, lib("overdue"))),
                            "reciprocal", f"lib:overdue has no {back} the other way")
        self.broken(lambda g: g.add((lib("circulation"), SKOS.narrowerTransitive, lib("renewal"))),
                    "reciprocal", "lib:circulation skos:narrowerTransitive lib:renewal has no skos:broaderTransitive")

    def test_language_used_only_in_a_definition_counts(self):
        self.broken(lambda g: g.add((lib("renewal"), SKOS.definition, Literal("Prolonger un pr\u00eat.", lang="fr"))),
                    "language", "lib:overdue has no language-tagged literal in fr")

    def test_preferred_labels_shared_across_schemes_pass(self):
        # Each scheme names its own concept; identity is the IRI (references/quality.md, Overlapping Labels).
        g = skeleton()
        g.set((lib("renewal"), SKOS.prefLabel, Literal("Returned", lang="en")))
        self.assertEqual(check_taxonomy.check(g), [])

    def test_preferred_labels_shared_in_one_scheme_fail_beside_another_scheme(self):
        # overdue and returned share loan-state; renewal, in another scheme, is not reported.
        def mutate(g):
            g.set((lib("overdue"), SKOS.prefLabel, Literal("Returned", lang="en")))
            g.set((lib("renewal"), SKOS.prefLabel, Literal("Returned", lang="en")))
        g = skeleton()
        mutate(g)
        fails = check_taxonomy.check(g)
        self.assertEqual(fails, [("collision", 'lib:overdue, lib:returned share the label "returned" (en) in lib:loan-state')])

    def test_preferred_label_shared_with_a_concept_in_no_scheme_fails(self):
        g = skeleton()
        g.set((lib("renewal"), SKOS.prefLabel, Literal("Returned", lang="en")))
        g.remove((lib("renewal"), SKOS.inScheme, None))
        g.remove((lib("renewal"), SKOS.topConceptOf, None))
        fails = check_taxonomy.check(g)
        self.assertIn(("collision", 'lib:renewal, lib:returned share the label "returned" (en) '
                                    "as a preferred, alternative or hidden label"), fails)

    def test_parent_known_only_through_narrower(self):
        # renewal's parent is stated only as circulation skos:narrower renewal, which also fails "parent";
        # the sibling clash must still be found.
        g = skeleton()
        g.remove((lib("renewal"), SKOS.broader, None))
        g.add((lib("circulation"), SKOS.narrower, lib("renewal")))
        g.add((lib("renewal"), SKOS.related, lib("lending-activity")))
        g.add((lib("lending-activity"), SKOS.related, lib("renewal")))
        self.assertIn(("related", "lib:lending-activity and lib:renewal are siblings and also skos:related"),
                      check_taxonomy.check(g))

    def test_narrower_transitive_without_a_path(self):
        g = skeleton()
        g.add((lib("on-loan"), SKOS.broaderTransitive, lib("circulation")))
        g.add((lib("circulation"), SKOS.narrowerTransitive, lib("on-loan")))
        self.assertIn(("transitive", "lib:circulation skos:narrowerTransitive lib:on-loan has no skos:narrower path "
                                     "behind it; the transitive properties are not for assertions"),
                      check_taxonomy.check(g))


class RequirementsChecks(OneBreak, unittest.TestCase):
    def broken(self, mutate, name, fragment):
        req = requirements()
        mutate(req)
        self.assertOnly(check_requirements.check(req), name, fragment)

    def test_template_passes(self):
        self.assertEqual(check_requirements.check(requirements()), [])

    # top-level schema
    def test_missing_field(self):
        self.broken(lambda r: r.pop("constraints"), "schema", "missing field 'constraints'")

    def test_empty_purpose(self):
        self.broken(lambda r: r.update(purpose=None), "schema", "'purpose' must be one non-empty sentence")

    def test_users_not_a_list(self):
        self.broken(lambda r: r.update(users="staff"), "schema", "'users' must be a non-empty list")

    def test_constraints_not_a_list(self):
        self.broken(lambda r: r.update(constraints=None), "schema", "'constraints' must be a list of strings")

    def test_empty_use_cases(self):
        self.broken(lambda r: r.update(use_cases=[]), "schema", "'use_cases' must be a non-empty list")

    def test_use_case_without_text(self):
        self.broken(lambda r: r["use_cases"][0].pop("text"), "schema", "use case 1 needs an 'id' and a 'text'")

    def test_duplicate_use_case(self):
        self.broken(lambda r: r["use_cases"][1].update(id="UC1"), "schema", "use case UC1 is used twice")

    def test_malformed_scope(self):
        req = requirements()
        req["scope"] = ["lending"]
        self.assertOnly(check_requirements.check(req), "schema", "'scope' needs 'in'")

    def test_empty_question_list(self):
        self.broken(lambda r: r.update(competency_questions=[]), "schema", "'competency_questions' must be a non-empty list")

    # competency questions
    def test_question_without_rationale(self):
        self.broken(lambda r: r["competency_questions"][0].pop("rationale"), "schema", "CQ1 has no 'rationale'")

    def test_bad_priority(self):
        self.broken(lambda r: r["competency_questions"][0].update(priority="high"), "schema", "CQ1 priority 'high' is not must, should or could")

    def test_bad_lock_status(self):
        self.broken(lambda r: r["competency_questions"][0].update(status="answerable"), "schema", "CQ1 status 'answerable' is not drafted or locked")

    def test_duplicate_question_id(self):
        self.broken(lambda r: r["competency_questions"][1].update(id="CQ1"), "schema", "CQ1 is used twice")

    def test_needs_not_a_list(self):
        self.broken(lambda r: r["competency_questions"][0].update(needs="lending"), "schema", "CQ1 'needs' must be a list")

    # conflicts
    def test_need_out_of_scope(self):
        self.broken(lambda r: r["competency_questions"][0]["needs"].append("fines"), "conflict", "CQ1 needs 'fines', which scope.out excludes")

    def test_rationale_names_out_of_scope_area(self):
        self.broken(lambda r: r["competency_questions"][1].update(rationale="Requires the fines history."),
                    "conflict", "CQ2 rationale names 'fines'")

    def test_need_not_in_scope(self):
        self.broken(lambda r: r["competency_questions"][0].update(needs=["membership"]),
                    "conflict", "CQ1 needs 'membership', which scope.in does not list")

    def test_area_in_and_out(self):
        self.broken(lambda r: r["scope"]["out"].append("Lending"), "conflict", "area 'lending' is both in and out of scope")

    # inputs
    def test_missing_input_kind(self):
        self.broken(lambda r: r["inputs"].pop("semantic_evidence"), "inputs", "input 'semantic_evidence' needs a status")

    def test_bad_input_status(self):
        self.broken(lambda r: r["inputs"]["purpose"].update(status="partial"), "inputs", "input 'purpose' needs a status")

    def test_thin_input_needs_note(self):
        self.broken(lambda r: r["inputs"]["representative_data"].update(note=""), "inputs", "input 'representative_data' is thin and needs a note")

    def test_inputs_not_a_mapping(self):
        def mutate(r):
            r["inputs"] = []
        req = requirements()
        mutate(req)
        fails = check_requirements.check(req)
        self.assertIn(("inputs", "'inputs' must map each of the six kinds to {status, note}"), fails)

    # assumptions
    def test_bad_assumption_status(self):
        self.broken(lambda r: r["assumptions"][0].update(status="maybe"), "assumptions", "A1 needs a status of ASSUMED or confirmed")

    def test_assumption_without_text(self):
        self.broken(lambda r: r["assumptions"][0].pop("text"), "assumptions", "A1 needs an 'id', a 'text' and a 'record' string")

    def test_confirmed_assumption_needs_record(self):
        self.broken(lambda r: r["assumptions"][0].update(status="confirmed"), "assumptions", "A1 is confirmed but names no decision record")

    # structural schema (finding #2 of the db5ae6d review)
    def test_missing_scope_out(self):
        self.broken(lambda r: r["scope"].pop("out"), "schema", "'scope' needs 'in'")

    def test_duplicate_assumption_id(self):
        def mutate(req):
            twin = dict(req["assumptions"][0])
            twin["text"] = "A different assumption with the same id."
            req["assumptions"].append(twin)
        self.broken(mutate, "assumptions", "is used twice")

    def test_assumed_item_with_a_record(self):
        self.broken(lambda r: r["assumptions"][0].update(record="DEC-001"),
                    "assumptions", "A1 is ASSUMED but names record 'DEC-001'")

    def test_input_without_note_key(self):
        self.broken(lambda r: r["inputs"]["purpose"].pop("note"), "inputs", "input 'purpose' needs a 'note' string")

    def test_question_text_not_a_string(self):
        for value in (["What is a loan?"], 42):
            with self.subTest(value=value):
                self.broken(lambda r: r["competency_questions"][0].update(question=value),
                            "schema", "CQ1 'question' must be a string")

    def test_rationale_not_a_string(self):
        self.broken(lambda r: r["competency_questions"][1].update(rationale=7), "schema", "CQ2 'rationale' must be a string")

    # the command line
    def test_cli_exit_codes(self):
        self.assertEqual(run_main(check_requirements.main, [REQUIREMENTS])[0], 0)
        self.assertEqual(run_main(check_requirements.main, [])[0], 2)
        self.assertEqual(run_main(check_requirements.main, [os.path.join(HERE, "missing.yaml")])[0], 2)
        req = requirements()
        req["competency_questions"][0]["needs"].append("fines")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "requirements.yaml")
            with open(path, "w", encoding="utf-8") as f:
                yaml.safe_dump(req, f)
            code, out = run_main(check_requirements.main, [path])
        self.assertEqual(code, 1)
        self.assertIn("FAIL conflict: CQ1 needs 'fines'", out)


class ShapesSkeleton(unittest.TestCase):
    """The shapes skeleton meets shacl.md rules 5 and 8 under pySHACL; check_taxonomy is not meant for it."""

    PREFIXES = ("@prefix lib: <%s> . @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
                "lib:m1 a lib:Member . lib:m2 a lib:Member . lib:c1 a lib:Copy . lib:c2 a lib:Copy .\n") % LIB
    VALID_LOAN = ('lib:loan1 a lib:Loan ; lib:borrower lib:m1 ; lib:loanOf lib:c1 ;'
                  ' lib:dueDate "2026-11-01"^^xsd:date ; lib:loanState lib:on-loan .')

    def results(self, data_ttl, shapes=None):
        """Validate the skeleton plus data_ttl.

        Return (conforms, {(focus, source shape, severity, constraint component)}) read from the
        validation report graph.
        """
        from pyshacl import validate
        data = Graph().parse(SKELETON, format="turtle")
        data.parse(data=self.PREFIXES + data_ttl, format="turtle")
        shapes = shapes if shapes is not None else Graph().parse(SHAPES, format="turtle")
        conforms, report, _ = validate(data, shacl_graph=shapes)
        found = {(report.value(r, SH.focusNode), report.value(r, SH.sourceShape),
                  report.value(r, SH.resultSeverity), report.value(r, SH.sourceConstraintComponent))
                 for r in report.subjects(RDF.type, SH.ValidationResult)}
        return conforms, found

    def assertViolations(self, data_ttl, focus, shape, components, shapes=None):
        """Exactly one sh:Violation per named constraint component, all on focus from shape."""
        conforms, found = self.results(data_ttl, shapes)
        self.assertFalse(conforms)
        self.assertEqual(found, {(lib(focus), lib(shape), SH.Violation, getattr(SH, c)) for c in components})

    TWO_DATES = '"2026-11-01"^^xsd:date, "2026-11-15"^^xsd:date'

    def test_valid_loan_conforms(self):
        conforms, found = self.results(self.VALID_LOAN + ' lib:renewal lib:maintenanceNote "Recheck at the 2027 policy edition."@en .')
        self.assertTrue(conforms, found)

    def test_every_declared_property_has_a_type_and_cardinality_shape(self):
        shapes = Graph().parse(SHAPES, format="turtle")
        declared = {p for kind in (OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty)
                    for p in skeleton().subjects(RDF.type, kind)}
        self.assertTrue(declared)
        for prop in sorted(declared):
            with self.subTest(prop=prop):
                stated = [s for s in shapes.subjects(SH.path, prop)
                          if ((s, SH.minCount, None) in shapes or (s, SH.maxCount, None) in shapes)
                          and ((s, SH["class"], None) in shapes or (s, SH.datatype, None) in shapes)]
                self.assertTrue(stated, f"{prop} has no property shape stating its type and cardinality")

    def test_loan_without_borrower(self):
        self.assertViolations(self.VALID_LOAN.replace(" lib:borrower lib:m1 ;", ""),
                              "loan1", "LoanShape-borrower", ["MinCountConstraintComponent"])

    def test_loan_of_two_copies(self):
        self.assertViolations(self.VALID_LOAN.replace("lib:loanOf lib:c1", "lib:loanOf lib:c1, lib:c2"),
                              "loan1", "LoanShape-loanOf", ["MaxCountConstraintComponent"])

    def test_loan_with_two_due_dates(self):
        self.assertViolations(self.VALID_LOAN.replace('"2026-11-01"^^xsd:date', self.TWO_DATES),
                              "loan1", "LoanShape-dueDate", ["MaxCountConstraintComponent"])

    def test_value_from_wrong_list_fails(self):
        self.assertViolations(self.VALID_LOAN.replace("lib:on-loan", "lib:circulation"),
                              "loan1", "LoanShape-loanState", ["InConstraintComponent"])

    def test_loan_state_that_is_not_a_concept(self):
        self.assertViolations(self.VALID_LOAN.replace("lib:on-loan", "lib:m1"),
                              "loan1", "LoanShape-loanState", ["ClassConstraintComponent", "InConstraintComponent"])

    def test_loan_with_two_borrowers(self):
        self.assertViolations(self.VALID_LOAN.replace("lib:borrower lib:m1", "lib:borrower lib:m1, lib:m2"),
                              "loan1", "LoanShape-borrower", ["MaxCountConstraintComponent"])

    def test_loan_with_two_states(self):
        self.assertViolations(self.VALID_LOAN.replace("lib:loanState lib:on-loan", "lib:loanState lib:on-loan, lib:overdue"),
                              "loan1", "LoanShape-loanState", ["MaxCountConstraintComponent"])

    def test_concept_with_two_maintenance_notes(self):
        self.assertViolations('lib:renewal lib:maintenanceNote "Recheck clause 3.3."@en, "Ask about express items."@en .',
                              "renewal", "ConceptShape-maintenanceNote", ["MaxCountConstraintComponent"])

    def test_maintenance_note_that_is_not_language_text(self):
        for value in ("42", '"Recheck clause 3.3."'):
            with self.subTest(value=value):
                self.assertViolations(f"lib:renewal lib:maintenanceNote {value} .",
                                      "renewal", "ConceptShape-maintenanceNote", ["DatatypeConstraintComponent"])

    # Mutations named by earlier reviews: each must turn a test red.
    def test_dropping_due_date_max_count_is_caught(self):
        shapes = Graph().parse(SHAPES, format="turtle")
        shapes.remove((lib("LoanShape-dueDate"), SH.maxCount, None))
        with self.assertRaises(AssertionError):
            self.assertViolations(self.VALID_LOAN.replace('"2026-11-01"^^xsd:date', self.TWO_DATES),
                                  "loan1", "LoanShape-dueDate", ["MaxCountConstraintComponent"], shapes)

    def test_lowering_loan_state_severity_is_caught(self):
        shapes = Graph().parse(SHAPES, format="turtle")
        shapes.add((lib("LoanShape-loanState"), SH.severity, SH.Warning))
        with self.assertRaises(AssertionError):
            self.assertViolations(self.VALID_LOAN.replace("lib:on-loan", "lib:circulation"),
                                  "loan1", "LoanShape-loanState", ["InConstraintComponent"], shapes)

    def test_dropping_maintenance_note_datatype_is_caught(self):
        shapes = Graph().parse(SHAPES, format="turtle")
        shapes.remove((lib("ConceptShape-maintenanceNote"), SH.datatype, None))
        with self.assertRaises(AssertionError):
            self.assertViolations("lib:renewal lib:maintenanceNote 42 .",
                                  "renewal", "ConceptShape-maintenanceNote", ["DatatypeConstraintComponent"], shapes)

    def test_dropping_borrower_or_loan_state_max_count_is_caught(self):
        cases = (("LoanShape-borrower", ("lib:borrower lib:m1", "lib:borrower lib:m1, lib:m2")),
                 ("LoanShape-loanState", ("lib:loanState lib:on-loan", "lib:loanState lib:on-loan, lib:overdue")))
        for shape, (old, new) in cases:
            with self.subTest(shape=shape):
                shapes = Graph().parse(SHAPES, format="turtle")
                shapes.remove((lib(shape), SH.maxCount, None))
                with self.assertRaises(AssertionError):
                    self.assertViolations(self.VALID_LOAN.replace(old, new), "loan1", shape,
                                          ["MaxCountConstraintComponent"], shapes)

    def test_shapes_hold_blank_nodes_so_check_taxonomy_skips_them(self):
        fails = check_taxonomy.check(Graph().parse(SHAPES, format="turtle"))
        self.assertIn("blank-node", {n for n, _ in fails})


class CheckScriptSkeleton(unittest.TestCase):
    """templates/check.sh, copied into a fresh repository, behaves as its comments say."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self.env.update(GIT_PAGER="cat", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        os.makedirs(os.path.join(self.tmp, "scripts"))
        shutil.copy(os.path.join(TEMPLATES, "check.sh"), os.path.join(self.tmp, "scripts", "check.sh"))
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.org")
        self.git("config", "user.name", "test")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.tmp, env=self.env, check=True,
                       stdin=subprocess.DEVNULL, capture_output=True)

    def commit(self):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "state")

    def edit_script(self, transform):
        path = os.path.join(self.tmp, "scripts", "check.sh")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        with open(path, "w", encoding="utf-8") as f:
            f.write(transform(text))

    def run_script(self):
        return subprocess.run(["bash", "scripts/check.sh"], cwd=self.tmp, env=self.env,
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=300)

    @staticmethod
    def drop_todos(text):
        return "\n".join(l for l in text.split("\n") if not l.startswith("# TODO:"))

    def test_unfilled_skeleton_fails(self):
        self.commit()
        result = self.run_script()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("still the skeleton", result.stderr)

    def test_filled_skeleton_passes(self):
        self.edit_script(self.drop_todos)
        self.commit()
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("all checks passed", result.stdout)

    def test_write_guard_catches_a_dropped_execute_bit(self):
        tool = os.path.join(self.tmp, "tool.sh")
        with open(tool, "w") as f:
            f.write("echo hi\n")
        os.chmod(tool, 0o755)
        self.edit_script(lambda t: self.drop_todos(t).replace(
            'after="$(snapshot)"', 'chmod -x tool.sh\nafter="$(snapshot)"', 1))
        self.commit()
        os.chmod(tool, 0o755)
        result = self.run_script()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("the checks changed the working tree", result.stderr)

    TAXONOMY_LINES = ("# TODO: data=()", "# TODO: [ \"${#data[@]}\"", "# TODO: uv run --no-project --with rdflib python3 scripts/ontology/check_taxonomy.py")

    def fill_taxonomy(self, text):
        lines = []
        for line in text.split("\n"):
            if line.startswith(self.TAXONOMY_LINES):
                lines.append(line[len("# TODO: "):])
            elif not line.startswith("# TODO:"):
                lines.append(line)
        return "\n".join(lines)

    def set_up_taxonomy(self, files):
        modules = os.path.join(self.tmp, "modules", "lending")
        os.makedirs(modules)
        for src, name in files:
            shutil.copy(src, os.path.join(modules, name))
        os.makedirs(os.path.join(self.tmp, "scripts", "ontology"))
        shutil.copy(os.path.join(HERE, "check_taxonomy.py"), os.path.join(self.tmp, "scripts", "ontology"))
        self.edit_script(self.fill_taxonomy)
        self.commit()
        return modules

    def test_taxonomy_lines_are_three(self):
        with open(os.path.join(TEMPLATES, "check.sh"), encoding="utf-8") as f:
            text = f.read()
        for prefix in self.TAXONOMY_LINES:
            self.assertEqual(sum(l.startswith(prefix) for l in text.split("\n")), 1, prefix)

    def test_taxonomy_line_checks_data_and_skips_shapes(self):
        modules = self.set_up_taxonomy([(SKELETON, "lending.ttl"), (SHAPES, "lending-shapes.ttl")])
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("all checks pass", result.stdout)

        with open(os.path.join(modules, "lending.ttl"), "a", encoding="utf-8") as f:
            f.write('\nlib:Copy rdfs:comment "untagged" .\n')
        self.commit()
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAIL untagged", result.stdout)

    def test_taxonomy_line_fails_with_no_data_file(self):
        # Only a shapes file: an empty set of data files must fail, never pass silently.
        self.set_up_taxonomy([(SHAPES, "lending-shapes.ttl")])
        result = self.run_script()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("no data Turtle under modules/", result.stderr)

    def inject(self, command):
        """Run `command` between the two snapshots, with every TODO dropped."""
        self.edit_script(lambda t: self.drop_todos(t).replace('after="$(snapshot)"', command + '\nafter="$(snapshot)"', 1))
        self.commit()

    def test_write_guard_catches_a_new_file(self):
        self.inject("echo made > made.txt")
        result = self.run_script()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("the checks changed the working tree", result.stderr)

    def test_write_guard_catches_a_changed_file(self):
        with open(os.path.join(self.tmp, "note.txt"), "w") as f:
            f.write("before\n")
        self.inject("echo after > note.txt")
        result = self.run_script()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("the checks changed the working tree", result.stderr)

    def test_write_guard_ignores_build_output(self):
        # In a checkout the repository's own ignore file keeps build output out of git's listing; in a plain
        # folder the guard's own list does.
        with open(os.path.join(self.tmp, ".gitignore"), "w") as f:
            f.write("__pycache__/\n.pytest_cache/\n")
        self.inject("mkdir -p __pycache__ .pytest_cache && echo x > __pycache__/a.pyc && echo y > .pytest_cache/b")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)


class CheckScriptWithoutGit(CheckScriptSkeleton):
    """The same script in a plain folder: releases need no git (release.md, "Without a remote"), so the guard
    snapshots every file under the folder instead of git's listing. Every test above runs again here."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        os.makedirs(os.path.join(self.tmp, "scripts"))
        shutil.copy(os.path.join(TEMPLATES, "check.sh"), os.path.join(self.tmp, "scripts", "check.sh"))

    def git(self, *args):
        raise AssertionError("no git in this folder")

    def commit(self):
        pass

    def test_the_folder_is_not_a_repository(self):
        self.assertFalse(os.path.exists(os.path.join(self.tmp, ".git")))
        probe = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=self.tmp, env=self.env,
                               stdin=subprocess.DEVNULL, capture_output=True)
        self.assertNotEqual(probe.returncode, 0, "the temporary folder sits inside a repository")

    def without_git(self):
        """An environment whose PATH holds only what the filled script runs, so `git` is not found."""
        bin_dir = os.path.join(os.path.dirname(self.tmp), f"bin-{os.path.basename(self.tmp)}")
        os.makedirs(bin_dir, exist_ok=True)
        self.addCleanup(shutil.rmtree, bin_dir)
        for tool in ("bash", "dirname", "grep", "python3", "uv", "find", "mkdir", "chmod"):
            found = shutil.which(tool)
            if found:
                os.symlink(found, os.path.join(bin_dir, tool))
        return dict(self.env, PATH=bin_dir)

    def test_the_guard_runs_with_no_git_installed(self):
        self.edit_script(self.drop_todos)
        env = self.without_git()
        self.assertIsNone(shutil.which("git", path=env["PATH"]))
        result = subprocess.run(["bash", "scripts/check.sh"], cwd=self.tmp, env=env,
                                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=300)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("all checks passed", result.stdout)
        self.inject("echo made > made.txt")
        result = subprocess.run(["bash", "scripts/check.sh"], cwd=self.tmp, env=env,
                                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=300)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("the checks changed the working tree", result.stderr)

    def test_a_git_that_fails_stops_the_guard(self):
        # git is present but cannot answer (a dubious owner, a broken repository): the guard must not fall
        # back to the plain-folder snapshots, which would leave out the index and status it was asked for.
        self.edit_script(self.drop_todos)
        env = self.without_git()
        fake = os.path.join(env["PATH"], "git")
        with open(fake, "w") as f:
            f.write("#!/bin/sh\necho 'fatal: detected dubious ownership in repository' >&2\nexit 128\n")
        os.chmod(fake, 0o755)
        result = subprocess.run(["bash", "scripts/check.sh"], cwd=self.tmp, env=env,
                                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=300)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("git rev-parse failed, so the guard cannot tell whether this is a checkout: fatal: detected dubious ownership",
                      result.stderr)
        self.assertNotIn("all checks passed", result.stdout)

    def test_a_broken_git_directory_stops_the_guard(self):
        # git says "not a git repository" here too, but names the path: this is a broken checkout, not a plain folder.
        self.edit_script(self.drop_todos)
        with open(os.path.join(self.tmp, ".git"), "w") as f:
            f.write("gitdir: /no/such/folder\n")
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("git rev-parse failed, so the guard cannot tell whether this is a checkout", result.stderr)
        self.assertNotIn("all checks passed", result.stdout)

    def test_a_folder_that_cannot_be_listed_stops_the_guard(self):
        if os.geteuid() == 0:
            self.skipTest("root can list any folder")
        self.edit_script(self.drop_todos)
        locked = os.path.join(self.tmp, "locked")
        os.makedirs(locked)
        with open(os.path.join(locked, "inside.txt"), "w") as f:
            f.write("x\n")
        os.chmod(locked, 0o100)
        try:
            result = self.run_script()
        finally:
            os.chmod(locked, 0o755)  # before tearDown removes the folder
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PermissionError", result.stderr)
        self.assertNotIn("all checks passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
