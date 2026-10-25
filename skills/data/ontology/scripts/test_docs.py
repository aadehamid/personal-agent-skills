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
from unittest import mock

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
            with open(os.path.join(package, "lending.ttl"), "w") as f:
                f.write(LENDING_TTL)
            with open(os.path.join(package, "manifest.json"), "w") as f:
                json.dump({"module": "lending", "version": version,
                           "files": {"lending.ttl": hashlib.sha256(LENDING_TTL.encode()).hexdigest()}}, f)
            self.write_source("lending", version)
        # A stand-in for java on PATH: FAKE_JAVA=ok writes an index page into -outFolder, fail exits 1.
        self.bin = os.path.join(self.root, "bin")
        os.makedirs(self.bin)
        fake = os.path.join(self.bin, "java")
        with open(fake, "w") as f:
            f.write('#!/bin/sh\necho called >> "$FAKE_JAVA_LOG"\n[ "$FAKE_JAVA" = ok ] || exit 1\n'
                    'while [ $# -gt 0 ]; do [ "$1" = -outFolder ] && out=$2; shift; done\n'
                    'echo NEW > "$out/index-en.html"\n')
        os.chmod(fake, 0o755)
        self.java_log = os.path.join(self.root, "java.log")
        self.jar = os.path.join(self.root, "widoco.jar")
        open(self.jar, "w").close()

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

    def test_a_folder_that_is_not_a_version_is_not_a_package(self):
        notes = os.path.join(self.releases, "lending", "notes")
        os.makedirs(notes)
        with open(os.path.join(notes, "manifest.json"), "w") as f:
            f.write("{}")
        self.assertEqual(check_docs.check(self.releases, self.docs), [])

    def test_main_exit_codes(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            self.assertEqual(check_docs.main(["--releases", self.releases, "--docs", self.docs]), 0)
            shutil.rmtree(os.path.join(self.docs, "lending", "1.0.0"))
            self.assertEqual(check_docs.main(["--releases", self.releases, "--docs", self.docs]), 1)
            self.assertEqual(check_docs.main(["--releases", self.releases, "--docs", os.path.join(self.root, "no")]), 2)

    def build_with_fake_java(self, mode, *packages):
        env = {"PATH": self.bin + os.pathsep + os.environ["PATH"], "FAKE_JAVA": mode, "FAKE_JAVA_LOG": self.java_log}
        saved = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                code = build_docs.main(["--jar", self.jar, "--releases", self.releases, "--docs", self.docs,
                                        *[a for p in packages for a in ("--package", p)]])
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        return code, out.getvalue()

    def write_old_pages(self):
        with open(os.path.join(self.docs, "lending", "1.1.0", "index-en.html"), "w") as f:
            f.write("OLD")

    def leftovers(self):
        return [n for n in os.listdir(os.path.join(self.docs, "lending")) if n.startswith(".")]

    def test_a_turtle_changed_after_release_stops_the_build_before_widoco(self):
        with open(os.path.join(self.releases, "lending", "1.1.0", "lending.ttl"), "a") as f:
            f.write("<https://id.example.org/library/Extra> a <http://www.w3.org/2002/07/owl#Class> .\n")
        code, out = self.build_with_fake_java("ok", "lending/1.1.0")
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL package: lending 1.1.0: lending.ttl does not match the SHA-256 in its manifest", out)
        self.assertFalse(os.path.exists(self.java_log), "Widoco ran on a package that does not match its manifest")

    def test_a_manifest_that_lists_no_turtle_stops_the_build(self):
        with open(os.path.join(self.releases, "lending", "1.1.0", "manifest.json"), "w") as f:
            json.dump({"module": "lending", "version": "1.1.0", "files": {}}, f)
        code, out = self.build_with_fake_java("ok", "lending/1.1.0")
        self.assertEqual(code, 1, out)
        self.assertIn("its manifest lists no lending.ttl", out)

    def test_a_failed_widoco_run_keeps_the_previous_pages(self):
        self.write_old_pages()
        code, out = self.build_with_fake_java("fail", "lending/1.1.0")
        self.assertEqual(code, 1, out)
        with open(os.path.join(self.docs, "lending", "1.1.0", "index-en.html")) as f:
            self.assertEqual(f.read(), "OLD")
        self.assertEqual(check_docs.check(self.releases, self.docs), [])
        self.assertEqual(self.leftovers(), [])

    def test_a_successful_run_replaces_the_previous_pages(self):
        self.write_old_pages()
        code, out = self.build_with_fake_java("ok", "lending/1.1.0")
        self.assertEqual(code, 0, out)
        with open(os.path.join(self.docs, "lending", "1.1.0", "index-en.html")) as f:
            self.assertEqual(f.read(), "NEW\n")
        self.assertEqual(check_docs.check(self.releases, self.docs), [])
        self.assertEqual(self.leftovers(), [])

    def test_a_failed_promotion_puts_the_previous_pages_back(self):
        self.write_old_pages()
        real_rename = os.rename

        def rename(src, dst):
            if os.path.basename(src).startswith(".1.1.0.building-") and not src.endswith(".old"):
                raise OSError("injected failure promoting the new pages")
            return real_rename(src, dst)

        with mock.patch("build_docs.os.rename", side_effect=rename):
            code, out = self.build_with_fake_java("ok", "lending/1.1.0")
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL promote: lending 1.1.0: injected failure", out)
        with open(os.path.join(self.docs, "lending", "1.1.0", "index-en.html")) as f:
            self.assertEqual(f.read(), "OLD")
        self.assertEqual(check_docs.check(self.releases, self.docs), [])
        self.assertEqual(self.leftovers(), [])

    def test_a_failed_restore_keeps_the_previous_pages_and_names_where_they_are(self):
        self.write_old_pages()
        real_rename = os.rename

        def rename(src, dst):
            name = os.path.basename(src)
            if name.startswith(".1.1.0.building-"):
                if name.endswith(".old"):
                    raise OSError("injected failure restoring the previous pages")
                raise OSError("injected failure promoting the new pages")
            return real_rename(src, dst)

        with mock.patch("build_docs.os.rename", side_effect=rename):
            code, out = self.build_with_fake_java("ok", "lending/1.1.0")
        self.assertEqual(code, 1, out)
        old = [n for n in self.leftovers() if n.endswith(".old")]
        self.assertEqual(len(old), 1, self.leftovers())
        old_path = os.path.join(self.docs, "lending", old[0])
        self.assertIn(f"they are at {old_path}: move that folder back to", out)
        with open(os.path.join(old_path, "index-en.html")) as f:
            self.assertEqual(f.read(), "OLD")

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
