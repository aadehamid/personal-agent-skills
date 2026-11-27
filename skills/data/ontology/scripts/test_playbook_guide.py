"""The guide (references/playbook.md) stays neutral: it names no build, company, repository path or
industry of the project that proved the method. Every file of the data skills also stays free of one
industry's terms and one company's names, so the skills work for an ontology in any industry. Moved here from that project's own check when the
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


# The data skills: the ontology skill and the skills beside it that project or draw its output. In this
# repository they sit together under skills/data. Where the ontology skill is shipped on its own (copied
# into an ontology release, or installed under another folder), only its own folder is scanned.
SKILL_ROOT = os.path.normpath(os.path.join(HERE, ".."))
_PARENT = os.path.dirname(SKILL_ROOT)
DATA_SKILLS = (_PARENT if os.path.basename(_PARENT) == "data"
               and os.path.basename(os.path.dirname(_PARENT)) == "skills" else SKILL_ROOT)
# The kinds that name one company, industry or project. The framework kind is left out, since a neutral
# skill may still cite a cross-industry framework such as APQC's; so is "this repository", which in a
# skill means the skills repository, and the generic file names its templates share with projects.
SCANNED_KINDS = ("a company or its filer names", "a refining or oil and gas term", "a project decision record",
                 "a row, process or proposal ID of a project")
INDUSTRY_TERMS = [
    ("a company or its filer names", r"\bPearland\b|\b0001510295\b"),
    ("a refining or oil and gas term", r"crack[\s-]+spread|oil[\s-]*(?:and|&)[\s-]*gas|\bmidstream\b"
                                       r"|renewable\s+diesel|renewable\s+fuel\s+standard|\bRINs\b"),
    ("a project's repository or namespace", r"w3id\.org/lsc|business_architecture|downstream_process_map"
                                            r"|enterprise-performance-model|downstream_oil_and_gas"),
]
BINARY_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip"}


def industry_problems(text):
    """(line, kind, matched text) for each industry, company or project term in text."""
    starts = [0] + [m.end() for m in re.finditer("\n", text)]
    found = [p for p in problems(text) if p[1] in SCANNED_KINDS]
    for kind, pattern in INDUSTRY_TERMS:
        for m in re.finditer(pattern, text, re.I):
            line = max(i for i, s in enumerate(starts) if s <= m.start()) + 1
            found.append((line, kind, m.group(0)))
    return sorted(set(found))


def data_skill_files():
    """Every file of the data skills, except this test, caches and the vendored upstream copies."""
    this_file = os.path.abspath(__file__)
    for root, dirs, files in os.walk(DATA_SKILLS):
        # Vendored copies sit at skills/<area>/<skill>/upstream/, as .gitignore says.
        if DATA_SKILLS == SKILL_ROOT:
            at_skill_root = os.path.abspath(root) == os.path.abspath(SKILL_ROOT)
        else:
            at_skill_root = os.path.dirname(os.path.abspath(root)) == os.path.abspath(DATA_SKILLS)
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")
                   and not (d == "upstream" and at_skill_root)]
        for name in files:
            path = os.path.join(root, name)
            if os.path.abspath(path) != this_file and not name.endswith(".pyc") and name != ".DS_Store":
                yield path


class DataSkillsAreIndustryNeutral(unittest.TestCase):
    def test_no_data_skill_file_names_one_industry_company_or_project(self):
        found = []
        for path in data_skill_files():
            if os.path.splitext(path)[1].lower() in BINARY_EXTENSIONS:
                continue
            # A file that cannot be read as UTF-8 fails the test rather than being skipped.
            with open(path, encoding="utf-8") as f:
                text = f.read()
            for line, kind, match in industry_problems(text):
                found.append((os.path.relpath(path, DATA_SKILLS), line, kind, match))
        self.assertEqual(found, [])

    def test_the_check_catches_industry_terms_companies_and_project_ids(self):
        kinds = {p[1] for p in industry_problems(
            "a crude unit\nas Valero files\na crack-spread series\noil & gas\nEPM-DEC-001-0001"
            "\nin enterprise-performance-model")}
        self.assertEqual(kinds, {"a refining or oil and gas term", "a company or its filer names",
                                 "a project decision record", "a project's repository or namespace"})
        self.assertEqual(industry_problems("a public library lends a book; APQC is a crosswalk"), [])

    def test_each_added_pattern_catches_its_term(self):
        for text in ("a crack-spread series", "oil & gas", "oil-and-gas", "a midstream unit", "renewable diesel",
                     "the Renewable Fuel Standard", "RINs", "Pearland", "CIK 0001510295", "CM 1.1.4",
                     "w3id.org/lsc", "enterprise-performance-model"):
            self.assertNotEqual(industry_problems(text), [], text)


if __name__ == "__main__":
    unittest.main()
