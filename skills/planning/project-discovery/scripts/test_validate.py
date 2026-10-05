"""Regression tests for the skill package checker."""

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from validate import ROOT, validate


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "skill"
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns("__pycache__"))

    def test_package(self):
        self.assertEqual(validate(self.root), [])

    def test_missing_reference(self):
        (self.root / "references/discovery.md").unlink()
        self.assertTrue(any("discovery.md" in error for error in validate(self.root)))

    def test_frontmatter(self):
        p = self.root / "SKILL.md"
        p.write_text(p.read_text().replace("name: project-discovery", "name: wrong"))
        self.assertIn("Incorrect skill name", validate(self.root))

    def test_specific_runtime_path(self):
        p = self.root / "SKILL.md"
        p.write_text(p.read_text() + "\nUse /Users/example/project.\n")
        self.assertTrue(any("machine-specific" in error for error in validate(self.root)))

    def test_duplicate_cases(self):
        p = self.root / "evals/cases.json"
        data = json.loads(p.read_text())
        data["cases"].append(data["cases"][0])
        p.write_text(json.dumps(data))
        self.assertIn("Duplicate evaluation case IDs", validate(self.root))

    def test_missing_restraint_case(self):
        p = self.root / "evals/cases.json"
        data = json.loads(p.read_text())
        data["cases"] = [case for case in data["cases"] if case["id"] != "publishing-restraint"]
        p.write_text(json.dumps(data))
        self.assertTrue(any("publishing-restraint" in error for error in validate(self.root)))

    def test_invalid_json(self):
        (self.root / "evals/cases.json").write_text("{")
        self.assertTrue(any("Invalid evaluation" in error for error in validate(self.root)))

    def test_invalid_case_fields(self):
        path = self.root / "evals/cases.json"
        original = json.loads(path.read_text())
        for field, value, expected_error in [
            ("kind", "unknown", "invalid kind"),
            ("kind", "behavior", "execution contract"),
            ("prompt", 42, "prompt must"),
            ("id", [], "id must"),
            ("expected", "a string is not a list", "expected must"),
            ("expected", ["", 42], "expected must"),
        ]:
            with self.subTest(field=field, value=value):
                data = json.loads(json.dumps(original))
                data["cases"][0][field] = value
                path.write_text(json.dumps(data))
                self.assertTrue(any(expected_error in error for error in validate(self.root)))

    def test_case_list_contains_nonobject(self):
        path = self.root / "evals/cases.json"
        data = json.loads(path.read_text())
        data["cases"].append(None)
        path.write_text(json.dumps(data))
        self.assertTrue(any("expected an object" in error for error in validate(self.root)))

    def test_cases_must_be_list(self):
        path = self.root / "evals/cases.json"
        path.write_text(json.dumps({"version": 1, "cases": {}}))
        self.assertTrue(any("cases must be a list" in error for error in validate(self.root)))

    def test_unknown_fields(self):
        path = self.root / "evals/cases.json"
        original = json.loads(path.read_text())
        for level in ("root", "case"):
            with self.subTest(level=level):
                data = json.loads(json.dumps(original))
                if level == "root":
                    data["unexpected"] = True
                else:
                    data["cases"][0]["unexpected"] = True
                path.write_text(json.dumps(data))
                self.assertTrue(any("unknown fields" in error for error in validate(self.root)))


if __name__ == "__main__":
    unittest.main()
