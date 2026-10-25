"""Tests for check_docs.py and build_docs.py.

Run from this folder:
  uv run --no-project python3 -m unittest test_docs
The build test runs Widoco and needs Java; it runs only when WIDOCO_JAR names a Widoco jar, for example
  WIDOCO_JAR=/path/to/widoco-1.4.25-jar-with-dependencies_JDK-17.jar python3 -m unittest test_docs

Each check gets a clean case and one planted error per failure it claims.
"""
import contextlib
import hashlib
import io
import json
import os
import shutil
import tempfile
import unittest

import build_docs
import check_docs

LENDING_TTL = """@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
<https://id.example.org/library/lending> a owl:Ontology ; rdfs:label "Library lending"@en .
<https://id.example.org/library/Loan> a owl:Class ; rdfs:label "Loan"@en .
"""


class Docs(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.releases = os.path.join(self.root, "releases")
        self.docs = os.path.join(self.root, "docs")
        for version in ("1.0.0", "1.1.0"):
            package = os.path.join(self.releases, "lending", version)
            os.makedirs(package)
            with open(os.path.join(package, "manifest.json"), "w") as f:
                json.dump({"module": "lending", "version": version}, f)
            with open(os.path.join(package, "lending.ttl"), "w") as f:
                f.write(LENDING_TTL)
            self.write_source("lending", version)

    def tearDown(self):
        shutil.rmtree(self.root)

    def manifest_hash(self, module, version):
        with open(os.path.join(self.releases, module, version, "manifest.json"), "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    def write_source(self, mod, ver, **override):
        folder = os.path.join(self.docs, mod, ver)
        os.makedirs(folder, exist_ok=True)
        record = {"module": mod, "version": ver, "manifest_sha256": self.manifest_hash(mod, ver)}
        record.update(override)
        with open(os.path.join(folder, "docs-source.json"), "w") as f:
            json.dump(record, f)

    def assertOnly(self, name, fragment):
        fails = check_docs.check(self.releases, self.docs)
        self.assertTrue(fails, f"expected {name!r}, got no failure")
        self.assertEqual({n for n, _ in fails}, {name}, fails)
        self.assertTrue(any(fragment in m for _, m in fails), fails)

    def test_current_docs_pass(self):
        self.assertEqual(check_docs.check(self.releases, self.docs), [])

    def test_a_package_without_docs(self):
        shutil.rmtree(os.path.join(self.docs, "lending", "1.1.0"))
        self.assertOnly("missing", "lending 1.1.0")

    def test_docs_without_a_package(self):
        os.makedirs(os.path.join(self.docs, "lending", "2.0.0"))
        self.assertOnly("orphan", "lending 2.0.0")

    def test_a_folder_without_its_source_record(self):
        os.remove(os.path.join(self.docs, "lending", "1.0.0", "docs-source.json"))
        self.assertOnly("source", "lending 1.0.0 has no readable docs-source.json")

    def test_a_source_record_for_another_version(self):
        self.write_source("lending", "1.0.0", version="1.1.0")
        self.assertOnly("source", "does not name module, version and manifest_sha256")

    def test_docs_built_from_another_manifest(self):
        with open(os.path.join(self.releases, "lending", "1.0.0", "manifest.json"), "a") as f:
            f.write(" ")
        self.assertOnly("stale", "lending 1.0.0: built from manifest")

    def test_main_exit_codes(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            self.assertEqual(check_docs.main(["--releases", self.releases, "--docs", self.docs]), 0)
            shutil.rmtree(os.path.join(self.docs, "lending", "1.0.0"))
            self.assertEqual(check_docs.main(["--releases", self.releases, "--docs", self.docs]), 1)
            self.assertEqual(check_docs.main(["--releases", self.releases, "--docs", os.path.join(self.root, "no")]), 2)

    @unittest.skipUnless(os.environ.get("WIDOCO_JAR"), "set WIDOCO_JAR to a Widoco jar to run Widoco")
    def test_build_writes_pages_and_a_source_record_the_check_accepts(self):
        shutil.rmtree(self.docs)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = build_docs.main(["--jar", os.environ["WIDOCO_JAR"], "--releases", self.releases, "--docs", self.docs])
        self.assertEqual(code, 0, out.getvalue())
        self.assertTrue(os.path.isfile(os.path.join(self.docs, "lending", "1.1.0", "index-en.html")))
        self.assertEqual(check_docs.check(self.releases, self.docs), [])


if __name__ == "__main__":
    unittest.main()
