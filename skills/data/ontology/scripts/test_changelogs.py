"""Tests for check_changelogs.py.

Run from this folder:
  uv run --no-project python3 -m unittest test_changelogs

A changelog with a Known gaps section passes; each one-break test plants one failure.
"""
import contextlib
import io
import os
import shutil
import tempfile
import unittest

import check_changelogs

GOOD = """# lending 1.1.0

## Changes
- Added the renewal limit. Approved by the module owner, decision 0012. Minor.

## Known gaps
- Holds are not modelled. Reason: no holds export exists yet. Record: parked list, trigger "a holds export".
- The overdue fee has no source. Reason: the policy names no amount. Record: open question Q7 to the ontology owner.

## Approval
The module owner, 2026-10-24.
"""


class CheckChangelogs(unittest.TestCase):
    def assertOnly(self, text, name, fragment):
        fails = check_changelogs.check_text(text, "lending 1.1.0")
        self.assertTrue(fails, f"expected {name!r}, got no failure")
        self.assertEqual({n for n, _ in fails}, {name}, fails)
        self.assertTrue(any(fragment in m for _, m in fails), fails)

    def test_listed_gaps_pass(self):
        self.assertEqual(check_changelogs.check_text(GOOD, "lending 1.1.0"), [])

    def test_none_passes(self):
        text = GOOD.split("## Known gaps")[0] + "## Known gaps\nNone.\n"
        self.assertEqual(check_changelogs.check_text(text, "lending 1.1.0"), [])

    def test_a_lower_level_heading_counts(self):
        self.assertEqual(check_changelogs.check_text(GOOD.replace("## Known gaps", "### Known gaps"), "x"), [])

    def test_no_section(self):
        self.assertOnly(GOOD.replace("## Known gaps", "## Open items"), "section", "no Known gaps section")

    def test_an_empty_section(self):
        text = GOOD.split("## Known gaps")[0] + "## Known gaps\n\n## Approval\nThe module owner.\n"
        self.assertOnly(text, "content", "neither")

    def test_a_gap_without_its_reason(self):
        self.assertOnly(GOOD.replace("Reason: no holds export exists yet. ", ""), "gap", "has no Reason: value")

    def test_a_gap_without_its_record(self):
        self.assertOnly(GOOD.replace(" Record: open question Q7 to the ontology owner.", ""), "gap", "has no Record: value")

    def test_a_reason_label_with_no_value(self):
        self.assertOnly(GOOD.replace("Reason: no holds export exists yet.", "Reason: ."), "gap", "has no Reason: value")

    def test_a_record_label_with_no_value(self):
        self.assertOnly(GOOD.replace("Record: open question Q7 to the ontology owner.", "Record:"), "gap",
                        "has no Record: value")

    def test_a_reason_of_punctuation_only(self):
        self.assertOnly(GOOD.replace("Reason: no holds export exists yet.", "Reason: —"), "gap", "has no Reason: value")

    def test_a_record_of_punctuation_only(self):
        self.assertOnly(GOOD.replace("Record: open question Q7 to the ontology owner.", "Record: ?"), "gap",
                        "has no Record: value")

    def test_the_next_section_is_not_read_as_gaps(self):
        text = GOOD.replace("## Approval\nThe module owner, 2026-10-24.", "## Approval\n- The module owner, 2026-10-24.")
        self.assertEqual(check_changelogs.check_text(text, "lending 1.1.0"), [])

    def run_main(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = check_changelogs.main(argv)
        return code, out.getvalue()

    def test_a_releases_folder_with_no_package_fails(self):
        root = tempfile.mkdtemp()
        try:
            code, out = self.run_main(["--releases", root])
            self.assertEqual(code, 1, out)
            self.assertIn("FAIL packages:", out)
        finally:
            shutil.rmtree(root)

    def test_a_folder_that_is_not_a_version_is_not_a_package(self):
        root = tempfile.mkdtemp()
        try:
            for version, text in (("1.0.0", GOOD), ("notes", "no section here")):
                package = os.path.join(root, "lending", version)
                os.makedirs(package)
                with open(os.path.join(package, "manifest.json"), "w") as f:
                    f.write("{}")
                with open(os.path.join(package, "CHANGELOG.md"), "w") as f:
                    f.write(text)
            code, out = self.run_main(["--releases", root])
            self.assertEqual(code, 0, out)
        finally:
            shutil.rmtree(root)

    def test_all_packages_exempt_passes(self):
        root = tempfile.mkdtemp()
        try:
            package = os.path.join(root, "lending", "1.0.0")
            os.makedirs(package)
            with open(os.path.join(package, "manifest.json"), "w") as f:
                f.write("{}")
            with open(os.path.join(package, "CHANGELOG.md"), "w") as f:
                f.write("# lending 1.0.0\n")
            code, out = self.run_main(["--releases", root, "--exempt", "lending/1.0.0"])
            self.assertEqual(code, 0, out)
        finally:
            shutil.rmtree(root)

    def test_releases_mode_and_exemptions(self):
        root = tempfile.mkdtemp()
        try:
            for version, changelog in (("1.0.0", "# lending 1.0.0\n\n## Changes\n- First release.\n"), ("1.1.0", GOOD)):
                package = os.path.join(root, "lending", version)
                os.makedirs(package)
                open(os.path.join(package, "manifest.json"), "w").write("{}")
                open(os.path.join(package, "CHANGELOG.md"), "w").write(changelog)
            os.makedirs(os.path.join(root, "lending", "1.2.0"))
            open(os.path.join(root, "lending", "1.2.0", "manifest.json"), "w").write("{}")
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                self.assertEqual(check_changelogs.main(["--releases", root]), 1)
            self.assertIn("FAIL section: lending 1.0.0 has no Known gaps section", out.getvalue())
            self.assertIn("FAIL changelog: lending 1.2.0 has no CHANGELOG.md", out.getvalue())
            shutil.rmtree(os.path.join(root, "lending", "1.2.0"))
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                self.assertEqual(check_changelogs.main(["--releases", root, "--exempt", "lending/1.0.0"]), 0)
                self.assertEqual(check_changelogs.main([]), 2)
        finally:
            shutil.rmtree(root)


if __name__ == "__main__":
    unittest.main()
