"""The guide (references/playbook.md) stays neutral: it names no build, company, repository path or
industry of the project that proved the method. Moved here from that project's own check when the
guide moved into this skill (2026-10-25). The method's evidence lives in each project's worklog.

Run: python3 -m unittest test_playbook_guide
"""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
GUIDE = os.path.join(HERE, "..", "references", "playbook.md")
# The guide's HTML page, built from playbook.md (scripts/build_playbook_html.py at the repository root).
GUIDE_HTML = os.path.join(HERE, "..", "references", "ontology-build-playbook.html")

# Each pattern names one kind of build-specific text. \s+ inside a pattern also matches a line break,
# so a term wrapped across two lines is still found.
TERMS = [
    ("a project decision record", r"EPM-DEC|\bEPM\b"),
    ("a company or its filer names", r"\bMPC\b|Marathon|\bMPLX\b|Valero|Phillips\s+66|\bPBF\b|HF\s+Sinclair"
                                     r"|\bDelek\b|\bCVR\b|Par\s+Pacific"),
    ("a project's framework or namespace", r"\bAPQC\b|w3id\.org/lsc|\bLSC\b"),
    ("a path into a project repository", r"business_architecture|\bstep4/|\.\./domain|lpg-projection/|ontology-worklog"
                                         r"|competency-questions\.md|downstream_process_map|enterprise-performance-model"),
    ("a row, process or proposal ID of a project", r"\bREL-\d{5}\b|\bCM[ -]\d|\bMPC-P\d"),
    ("a refining or oil and gas term", r"refin(?:ery|eries|ing|er)|petroleum|crack\s+spread|\bbarrels?\b"
                                       r"|\bdownstream\b|oil\s+and\s+gas|\bcrude\b"),
    ("a reference to one project's build", r"this\s+repository|worked\s+example's"),
]


def problems(text):
    """(line, kind, matched text) for each build-specific term in text."""
    starts = [0] + [m.end() for m in re.finditer("\n", text)]
    found = []
    for kind, pattern in TERMS:
        for m in re.finditer(pattern, text, re.I):
            line = max(i for i, s in enumerate(starts) if s <= m.start()) + 1
            found.append((line, kind, m.group(0)))
    return sorted(found)


class Guide(unittest.TestCase):
    def test_the_guide_is_neutral(self):
        with open(GUIDE, encoding="utf-8") as f:
            self.assertEqual(problems(f.read()), [])

    def test_the_html_page_is_neutral_too(self):
        with open(GUIDE_HTML, encoding="utf-8") as f:
            self.assertEqual(problems(f.read()), [])

    def test_each_kind_of_term_is_caught(self):
        for text, kind in (("see EPM-DEC-001-0001", "a project decision record"),
                           ("as Marathon\nPetroleum files", "a company or its filer names"),
                           ("the APQC frame", "a project's framework or namespace"),
                           ("in business_architecture/x", "a path into a project repository"),
                           ("row REL-00012", "a row, process or proposal ID of a project"),
                           ("a crack\nspread", "a refining or oil and gas term"),
                           ("in this repository", "a reference to one project's build")):
            with self.subTest(kind=kind):
                self.assertIn(kind, {k for _, k, _ in problems(text)})

    def test_a_term_wrapped_across_lines_is_reported_on_its_first_line(self):
        # A term whose pattern allows a line break inside it; a refining term, so the test reads the same wherever
        # the company list differs.
        self.assertEqual(problems("one\ntwo crack\nspread three"), [(2, "a refining or oil and gas term", "crack\nspread")])


if __name__ == "__main__":
    unittest.main()
