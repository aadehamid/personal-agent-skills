"""Tests for check_candidates.py.

Run from this folder:
  uv run --no-project --with pyyaml python3 -m unittest test_candidates

The worked example in templates/intake/ passes; each one-break test changes it in one way and asserts that exactly
the named check fires.
"""
import contextlib
import copy
import io
import os
import tempfile
import unittest

import yaml

import check_candidates

HERE = os.path.dirname(os.path.abspath(__file__))
INTAKE = os.path.join(HERE, "..", "templates", "intake")
SOURCE = os.path.join(INTAKE, "lending-policy-excerpt.txt")
RESULT = os.path.join(INTAKE, "ontogpt-result.yaml")
REGISTER = os.path.join(INTAKE, "candidates.yaml")


def load(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def document():
    with open(SOURCE, encoding="utf-8") as f:
        return f.read()


class CheckCandidates(unittest.TestCase):
    def assertOnly(self, fails, name, fragment):
        self.assertTrue(fails, f"expected {name!r} containing {fragment!r}, got no failure")
        self.assertEqual({n for n, _ in fails}, {name}, fails)
        self.assertTrue(any(fragment in m for _, m in fails), fails)

    def test_the_worked_example_passes(self):
        self.assertEqual(check_candidates.check_result(load(RESULT), document()), [])
        self.assertEqual(check_candidates.check_register(load(REGISTER), document(), "lending-policy-excerpt.txt"), [])

    def test_a_result_for_another_text(self):
        result = load(RESULT)
        result["input_text"] = result["input_text"].replace("21 days", "28 days")
        self.assertOnly(check_candidates.check_result(result, document()), "input-text", "not the supplied document")

    def test_an_entity_without_a_span(self):
        result = load(RESULT)
        result["named_entities"][0]["original_spans"] = []
        self.assertOnly(check_candidates.check_result(result, document()), "span", "'loan period' has no original_spans")

    def test_a_span_past_the_end(self):
        result = load(RESULT)
        result["named_entities"][0]["original_spans"] = ["10:99999"]
        self.assertOnly(check_candidates.check_result(result, document()), "span", "10:99999")

    def test_a_span_that_reads_another_word(self):
        result = load(RESULT)
        start = int(result["named_entities"][1]["original_spans"][0].split(":")[0])
        result["named_entities"][1]["original_spans"] = [f"{start + 1}:{start + 8}"]
        self.assertOnly(check_candidates.check_result(result, document()), "grounded", "'due date'")

    def test_a_label_the_model_made_up(self):
        result = load(RESULT)
        result["named_entities"][2]["label"] = "reservation"
        self.assertOnly(check_candidates.check_result(result, document()), "grounded", "'reservation'")

    def test_a_register_for_another_document(self):
        register = load(REGISTER)
        register["source_document"] = "other.txt"
        self.assertOnly(check_candidates.check_register(register, document(), "lending-policy-excerpt.txt"),
                        "register", "'other.txt'")

    def test_a_candidate_missing_a_field(self):
        register = load(REGISTER)
        del register["candidates"][0]["found_by"]
        self.assertOnly(check_candidates.check_register(register, document(), "lending-policy-excerpt.txt"),
                        "register", "has no found_by")

    def test_a_passage_not_in_the_document(self):
        register = load(REGISTER)
        register["candidates"][1]["source_passage"] = "unless the title is reserved"
        self.assertOnly(check_candidates.check_register(register, document(), "lending-policy-excerpt.txt"),
                        "passage", "'hold'")

    def test_a_passage_split_across_lines_still_counts(self):
        register = load(REGISTER)
        register["candidates"][2]["source_passage"] = "Renewal moves the due date\n  later; it does not start a new loan."
        self.assertEqual(check_candidates.check_register(register, document(), "lending-policy-excerpt.txt"), [])

    def test_an_approved_candidate(self):
        register = load(REGISTER)
        register["candidates"][0]["status"] = "approved"
        self.assertOnly(check_candidates.check_register(register, document(), "lending-policy-excerpt.txt"),
                        "candidate", "only the human gate approves")

    def test_an_unsupported_definition_beside_a_valid_passage_still_passes(self):
        # The limit of the script: meaning is checked by a person at the human gate, not here.
        register = load(REGISTER)
        register["candidates"][0]["proposed_definition"] = "A fine charged for every day a copy is late."
        self.assertEqual(check_candidates.check_register(register, document(), "lending-policy-excerpt.txt"), [])

    def test_a_term_its_passage_never_names_is_a_warning_not_a_failure(self):
        register = load(REGISTER)
        register["candidates"][1]["term"] = "reservation"
        self.assertEqual(check_candidates.check_register(register, document(), "lending-policy-excerpt.txt"), [])
        self.assertEqual(check_candidates.term_warnings(register),
                         [("term", "'reservation': its passage never uses reservation")])
        self.assertEqual(check_candidates.term_warnings(load(REGISTER)), [])

    def test_a_term_found_only_inside_a_longer_word_is_a_warning(self):
        register = load(REGISTER)
        register["candidates"][2]["term"] = "Renew"   # the passage has "Renewal", not "renew"
        self.assertEqual(check_candidates.term_warnings(register),
                         [("term", "'Renew': its passage never uses Renew")])

    def test_an_early_unquoted_span_is_read_as_text(self):
        with tempfile.TemporaryDirectory() as d:
            doc, res = os.path.join(d, "doc.txt"), os.path.join(d, "result.yaml")
            with open(doc, "w", encoding="utf-8") as f:
                f.write("Members renew loans.")
            with open(res, "w", encoding="utf-8") as f:
                f.write("input_text: Members renew loans.\nnamed_entities:\n- label: renew\n  original_spans:\n  - 8:12\n")
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                self.assertEqual(check_candidates.main(["--source", doc, "--ontogpt", res]), 0, out.getvalue())

    def test_crlf_document_spans_count_line_breaks_once(self):
        result = {"input_text": "Hi.\nHold the book.\n", "named_entities": [{"label": "Hold", "original_spans": ["4:7"]}]}
        self.assertEqual(check_candidates.check_result(result, "Hi.\r\nHold the book.\r\n"), [])

    def test_a_span_past_the_end_of_input_text_fails_even_with_crlf(self):
        result = {"input_text": "AB\nCD", "named_entities": [{"label": "CD", "original_spans": ["4:5"]}]}
        fails = check_candidates.check_result(result, "AB\r\nCD")
        self.assertEqual({n for n, _ in fails}, {"span"}, fails)

    def test_main_exit_codes(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            self.assertEqual(check_candidates.main(["--source", SOURCE, "--ontogpt", RESULT, "--candidates", REGISTER]), 0)
            self.assertEqual(check_candidates.main(["--source", SOURCE]), 2)
            self.assertEqual(check_candidates.main(["--source", os.path.join(INTAKE, "missing.txt"),
                                                    "--candidates", REGISTER]), 2)


if __name__ == "__main__":
    unittest.main()
