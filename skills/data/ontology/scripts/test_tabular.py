"""Tests for build_tabular.py on the worked example in templates/tabular/.

Morph-KGC 2.10.0 needs rdflib below 7.3 and maplib 0.20.26 needs rdflib 7.6 or later, so the two engines cannot
share an environment. Each runs in its own, and both must reproduce the same committed output,
templates/tabular/loan-states.nt, which proves they agree:
  TABULAR_ENGINE=morph-kgc uv run --no-project --with morph-kgc==2.10.0 --with rdflib python3 -m unittest test_tabular
  TABULAR_ENGINE=maplib uv run --no-project --with maplib==0.20.26 --with polars --with rdflib python3 -m unittest test_tabular

Without TABULAR_ENGINE the tests skip, so the skill's plain test run needs neither engine. With it, a missing
engine fails instead of skipping.
"""
import contextlib
import io
import os
import shutil
import tempfile
import unittest

import build_tabular

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLE = os.path.join(HERE, "..", "templates", "tabular")
EXPECTED = os.path.join(EXAMPLE, "loan-states.nt")
MAPPINGS = {"morph-kgc": "loan-states.rml.ttl", "maplib": "loan-states.maplib.py"}
ENGINE = os.environ.get("TABULAR_ENGINE")
if ENGINE:
    __import__({"morph-kgc": "morph_kgc", "maplib": "maplib"}[ENGINE])


def run(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = build_tabular.main(argv)
    return code, out.getvalue()


@unittest.skipUnless(ENGINE, "set TABULAR_ENGINE to morph-kgc or maplib, with that engine installed")
class BuildTabular(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        for name in os.listdir(EXAMPLE):
            if os.path.isfile(os.path.join(EXAMPLE, name)):
                shutil.copy(os.path.join(EXAMPLE, name), self.dir)
        self.out = os.path.join(self.dir, "loan-states.nt")

    def tearDown(self):
        shutil.rmtree(self.dir)

    def args(self, *extra):
        return ["--engine", ENGINE, "--mapping", os.path.join(self.dir, MAPPINGS[ENGINE]), "--out", self.out, *extra]

    def edit(self, name, old, new):
        path = os.path.join(self.dir, name)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        self.assertIn(old, text)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text.replace(old, new, 1))

    def test_the_committed_output_equals_a_fresh_build(self):
        code, out = run(["--engine", ENGINE, "--mapping", os.path.join(EXAMPLE, MAPPINGS[ENGINE]), "--out", EXPECTED,
                         "--verify"])
        self.assertEqual(code, 0, out)

    def test_only_the_governed_triples_are_written(self):
        # maplib maps rows into a named staging graph and writes the default graph; no staging
        # (raw:) triple may reach the output; the subjects are the scheme and the concepts named by the slug column.
        self.assertEqual(run(self.args())[0], 0)
        with open(self.out, encoding="utf-8") as f:
            lines = f.read().splitlines()
        self.assertFalse([l for l in lines if "library/raw#" in l], "a staging triple reached the output")
        subjects = sorted({l.split(" ", 1)[0] for l in lines})
        self.assertEqual(subjects, ["<https://id.example.org/library/loan-state>", "<https://id.example.org/library/on-loan>",
                                    "<https://id.example.org/library/overdue>", "<https://id.example.org/library/returned>"])

    def test_the_example_gives_its_rows_and_the_scheme(self):
        self.assertEqual(run(self.args())[0], 0)
        with open(self.out, encoding="utf-8") as f:
            lines = f.read().splitlines()
        self.assertEqual(len(lines), 27)   # 3 rows x 7 triples, plus the scheme's type, label, definition and 3 top concepts
        self.assertIn('<https://id.example.org/library/overdue> <http://www.w3.org/2004/02/skos/core#prefLabel> '
                      '"Overdue"@en .', lines)

    def test_the_output_passes_check_taxonomy(self):
        import subprocess
        import sys
        self.assertEqual(run(self.args())[0], 0)
        result = subprocess.run([sys.executable, os.path.join(HERE, "check_taxonomy.py"), self.out],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_rebuild_writes_the_same_bytes(self):
        run(self.args())
        with open(self.out, "rb") as f:
            first = f.read()
        run(self.args())
        with open(self.out, "rb") as f:
            self.assertEqual(f.read(), first)

    def test_a_changed_cell_fails_verify(self):
        self.edit("loan-states.csv", "LS-2,overdue,Overdue,", "LS-2,overdue,Late,")
        code, out = run(self.args("--verify"))   # self.out is the copied committed output
        self.assertEqual(code, 1, out)
        self.assertIn('only in a fresh build: <https://id.example.org/library/overdue> '
                      '<http://www.w3.org/2004/02/skos/core#prefLabel> "Late"@en .', out)
        self.assertIn('only in ' + self.out + ': <https://id.example.org/library/overdue> '
                      '<http://www.w3.org/2004/02/skos/core#prefLabel> "Overdue"@en .', out)

    def test_a_hand_edit_to_the_output_fails_verify(self):
        self.edit("loan-states.nt", '"LS-1"', '"LS-9"')
        self.assertEqual(run(self.args("--verify"))[0], 1)

    def test_a_line_ending_edit_to_the_output_fails_verify(self):
        with open(self.out, "rb") as f:
            text = f.read()
        with open(self.out, "wb") as f:
            f.write(text.replace(b"\n", b"\r\n"))
        code, out = run(self.args("--verify"))
        self.assertEqual(code, 1, out)
        self.assertIn("holds the same triples in another order or layout", out)

    def test_a_missing_mapping_is_an_input_error(self):
        code, _ = run(["--engine", ENGINE, "--mapping", os.path.join(self.dir, "missing"), "--out", self.out])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
