"""Tests for check_sssom.py.

Run from this folder:
  uv run --no-project --with pyyaml python3 -m unittest test_sssom

The template mapping set passes; each one-break test changes it in one way and asserts that exactly the named
check fires, so a check that passes vacuously, or fires for the wrong reason, fails here.
"""
import contextlib
import io
import os
import tempfile
import unittest

import check_sssom

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "templates", "mappings.sssom.tsv")


def template():
    with open(TEMPLATE, encoding="utf-8") as f:
        return f.read()


def replace(text, old, new):
    assert old in text, old
    return text.replace(old, new, 1)


class CheckSssom(unittest.TestCase):
    def assertOnly(self, text, name, fragment):
        fails = check_sssom.check_text(text)
        self.assertTrue(fails, f"expected {name!r} containing {fragment!r}, got no failure")
        self.assertEqual({n for n, _ in fails}, {name}, fails)
        self.assertTrue(any(fragment in m for _, m in fails), fails)

    def test_template_passes(self):
        self.assertEqual(check_sssom.check_text(template()), [])

    def test_missing_license(self):
        self.assertOnly(replace(template(), "#license: https://id.example.org/library/licence\n", ""),
                        "metadata", "no license")

    def test_missing_mapping_set_id(self):
        text = "".join(l for l in template().splitlines(keepends=True) if not l.startswith("#mapping_set_id"))
        self.assertOnly(text, "metadata", "no mapping_set_id")

    def test_metadata_not_yaml(self):
        self.assertOnly(replace(template(), "#mapping_date: 2026-10-24", "#mapping_date: [2026"),
                        "metadata", "not valid YAML")

    def test_stated_version_other_than_1_1(self):
        self.assertOnly(replace(template(), "#mapping_date:", "#sssom_version: 1.0\n#mapping_date:"),
                        "version", "must say 1.1")

    def test_missing_required_column(self):
        text = template().replace("\tmapping_justification", "\tjustification", 1)
        self.assertOnly(text, "columns", "no mapping_justification")

    def test_repeated_column(self):
        self.assertOnly(replace(template(), "\tcomment\n", "\tauthor_id\n"), "columns", "author_id more than once")

    def test_empty_required_cell(self):
        self.assertOnly(replace(template(), "\tsemapv:ManualMappingCuration\trole:modeller\t0.95",
                                "\t\trole:modeller\t0.95"), "required", "no mapping_justification")

    def test_literal_mapping_may_leave_its_object_empty(self):
        text = replace(template(), "\tcomment\n", "\tcomment\tobject_type\n")
        text = "".join(line.rstrip("\n") + ("\t\n" if not line.startswith("#") and "subject_id" not in line else "\n")
                       for line in text.splitlines(keepends=True))
        text = replace(text, "\tskos:exactMatch\text:Lending\t", "\tskos:exactMatch\t\t")
        text = replace(text, "both name one agreement".capitalize() + " for one copy until a due date.\t",
                       "Both name one agreement for one copy until a due date.\trdfs literal")
        self.assertEqual(check_sssom.check_text(text), [])

    def test_undeclared_prefix(self):
        self.assertOnly(replace(template(), "\text:Lending\t", "\tother:Lending\t"), "curie", "prefix other")

    def test_iri_instead_of_curie(self):
        self.assertOnly(replace(template(), "\text:Lending\t", "\thttps://id.example.org/other-vocabulary/Lending\t"),
                        "curie", "is an IRI")

    def test_built_in_prefix_redefined(self):
        self.assertOnly(replace(template(), "#curie_map:\n", "#curie_map:\n#  skos: http://example.org/skos#\n"),
                        "curie", "built-in prefix skos")

    def test_predicate_outside_the_allowed_set(self):
        self.assertOnly(replace(template(), "\tskos:exactMatch\t", "\towl:equivalentClass\t"),
                        "predicate", "owl:equivalentClass")

    def test_allowed_predicate_can_be_widened(self):
        text = replace(template(), "\tskos:exactMatch\t", "\towl:equivalentClass\t")
        self.assertEqual(check_sssom.check_text(text, {"owl:equivalentClass"}), [])

    def test_predicate_modifier_other_than_not(self):
        text = replace(template(), "\tcomment\n", "\tcomment\tpredicate_modifier\n")
        text = text.replace("until a due date.\n", "until a due date.\tNo\n", 1)
        lines = text.splitlines(keepends=True)
        text = "".join(l if l.startswith("#") or "subject_id" in l or "\tNo\n" in l else l.rstrip("\n") + "\t\n"
                       for l in lines)
        self.assertOnly(text, "modifier", "is No")

    def test_confidence_above_one(self):
        self.assertOnly(replace(template(), "\trole:modeller\t0.95\t", "\trole:modeller\t1.5\t"),
                        "confidence", "1.5")

    def test_confidence_not_a_number(self):
        self.assertOnly(replace(template(), "\trole:modeller\t0.95\t", "\trole:modeller\thigh\t"),
                        "confidence", "high")

    def test_justification_outside_semapv(self):
        self.assertOnly(replace(template(), "\tsemapv:ManualMappingCuration\trole:modeller\t0.95",
                                "\tsemapv:Guesswork\trole:modeller\t0.95"), "justification", "semapv:Guesswork")

    def test_a_1_1_justification_needs_a_1_1_set(self):
        text = replace(template(), "\tsemapv:ManualMappingCuration\trole:modeller\t0.95",
                       "\tsemapv:MappingInversion\trole:modeller\t0.95")
        self.assertOnly(text, "justification", "SSSOM 1.0")
        self.assertEqual(check_sssom.check_text(replace(text, "#mapping_date:", "#sssom_version: 1.1\n#mapping_date:")),
                         [])

    def test_an_unreleased_justification_fails_even_in_a_1_1_set(self):
        text = replace(template(), "\tsemapv:ManualMappingCuration\trole:modeller\t0.95",
                       "\tsemapv:LLMBasedMatching\trole:modeller\t0.95")
        self.assertOnly(replace(text, "#mapping_date:", "#sssom_version: 1.1\n#mapping_date:"), "justification",
                        "semapv:LLMBasedMatching")

    def test_row_width_differs_from_header(self):
        self.assertOnly(replace(template(), "\tLibrary services\tsemapv:ManualMappingCuration\trole:modeller\t0.9\t",
                                "\tLibrary services\tsemapv:ManualMappingCuration\trole:modeller\t0.9"),
                        "width", "8 cells")

    def test_a_non_exact_match_without_a_comment(self):
        self.assertOnly(replace(template(), "\t0.9\tLibrary services also covers reference and events; circulation is the "
                                            "lending part of it.\n", "\t0.9\t\n"), "comment", "skos:broadMatch")

    def test_an_exact_match_needs_no_comment(self):
        text = replace(template(), "\t0.95\tBoth name one agreement for one copy until a due date.\n", "\t0.95\t\n")
        self.assertEqual(check_sssom.check_text(text), [])

    def test_no_version_of_the_other_vocabulary(self):
        self.assertOnly(replace(template(), '#object_source_version: "2026-01"\n', ""), "source-version",
                        "object_source_version")

    def test_the_version_may_sit_on_every_row(self):
        text = replace(template(), '#object_source_version: "2026-01"\n', "")
        lines = text.splitlines(keepends=True)
        text = "".join(l if l.startswith("#") else
                       l.rstrip("\n") + ("\tobject_source_version\n" if l.startswith("subject_id") else "\t2026-01\n")
                       for l in lines)
        self.assertEqual(check_sssom.check_text(text), [])

    def test_main_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            bad = os.path.join(d, "bad.sssom.tsv")
            with open(bad, "w", encoding="utf-8") as f:
                f.write(replace(template(), "\tskos:exactMatch\t", "\towl:sameAs\t"))
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                self.assertEqual(check_sssom.main([TEMPLATE]), 0)
                self.assertEqual(check_sssom.main([bad]), 1)
                self.assertEqual(check_sssom.main([os.path.join(d, "missing.tsv")]), 2)


if __name__ == "__main__":
    unittest.main()
