"""Tests for build_catalog.py.

Run from this folder:
  uv run --no-project --with rdflib --with pyyaml --with pyshacl python3 -m unittest test_build_catalog

Two packages are built with build_package.py from the library skeleton; the catalog is built from them, and
each one-break test changes one thing (a package added, a hand edit, a second catalog IRI, a distribution
naming no file, two datasets) and expects the named failure.
"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml

import build_catalog
import build_package

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = os.path.join(HERE, "..", "templates")
TITLE, DESCRIPTION = "Library ontology", "Every released module of the library ontology."
MODULE_TTL = """@prefix owl: <http://www.w3.org/2002/07/owl#> .
<{iri}> a owl:Ontology .
<{iri}/Thing> a owl:Class .
"""


def run(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = build_catalog.main(argv)
    return code, out.getvalue()


class Catalog(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        self.releases = os.path.join(self.root, "releases")
        for name in ("ontology-skeleton.ttl", "shapes-skeleton.ttl"):
            shutil.copy(os.path.join(TEMPLATES, name), self.root)
        with open(os.path.join(TEMPLATES, "package-answers.yaml"), encoding="utf-8") as f:
            self.answers = yaml.safe_load(f)
        self.package()
        self.package(module="core", ontology_iri="https://id.example.org/library/core", title="Library core")
        self.catalog = os.path.join(self.releases, "catalog.ttl")

    def package(self, **changes):
        """Build one package: the library skeleton, or, for another module, a one-class module of that IRI."""
        answers = dict(self.answers, **changes)
        if answers["module"] != "lending":
            with open(os.path.join(self.root, f"{answers['module']}.ttl"), "w", encoding="utf-8") as f:
                f.write(MODULE_TTL.format(iri=answers["ontology_iri"]))
            answers.update(sources=[f"{answers['module']}.ttl"], shapes=[])
        path = os.path.join(self.root, f"{answers['module']}-{answers['version']}.yaml")
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(answers, f, sort_keys=False)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = build_package.main(["build", path, "--releases", self.releases])
        self.assertEqual(code, 0, out.getvalue())
        return os.path.join(self.releases, answers["module"], answers["version"])

    def build(self, *extra):
        return run(["build", "--releases", self.releases, "--title", TITLE, "--description", DESCRIPTION, *extra])

    def verify(self, *extra):
        return run(["verify", "--releases", self.releases, "--title", TITLE, "--description", DESCRIPTION, *extra])

    def test_build_lists_every_package_and_verify_passes(self):
        code, out = self.build()
        self.assertEqual(code, 0, out)
        self.assertIn("2 releases from 2 packages", out)
        with open(self.catalog, encoding="utf-8") as f:
            text = f.read()
        self.assertIn('dcterms:title "Library ontology"@en', text)
        self.assertIn('dcterms:description "Every released module of the library ontology."@en', text)
        for dataset in ("<https://id.example.org/library/lending/1.0.0> a dcat:Dataset",
                        "<https://id.example.org/library/core/1.0.0> a dcat:Dataset"):
            self.assertIn(dataset, text)
        code, out = self.verify()
        self.assertEqual(code, 0, out)
        self.assertIn("equals a fresh build: 2 releases from 2 packages", out)

    def test_the_catalog_adds_only_its_title_and_description(self):
        self.build()
        from rdflib import Graph
        union = Graph()
        for module in ("lending", "core"):
            union.parse(os.path.join(self.releases, module, "1.0.0", "catalog.ttl"), format="turtle")
        written = Graph().parse(self.catalog, format="turtle")
        extra = set(written) - set(union)
        self.assertEqual({str(p).rsplit("/", 1)[-1] for _, p, _ in extra}, {"title", "description"})
        self.assertEqual(set(union) - set(written), set())

    def test_a_rebuild_in_another_process_is_byte_identical(self):
        self.build()
        env = dict(os.environ, PYTHONHASHSEED="12345", PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run([sys.executable, os.path.join(HERE, "build_catalog.py"), "verify", "--releases", self.releases,
                                 "--title", TITLE, "--description", DESCRIPTION], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_package_added_later_fails_verify(self):
        self.build()
        self.package(version="1.1.0", changes=["Clearer wording, a patch."])
        code, out = self.verify()
        self.assertEqual(code, 1)
        self.assertIn("catalog.ttl differs from a fresh build of the 3 packages", out)

    def test_a_hand_edit_fails_verify(self):
        self.build()
        with open(self.catalog, "a", encoding="utf-8") as f:
            f.write("\n<https://id.example.org/library/catalog> <http://purl.org/dc/terms/creator> \"someone\" .\n")
        code, out = self.verify()
        self.assertEqual(code, 1)
        self.assertIn("differs from a fresh build", out)

    def test_a_crlf_edit_fails_verify(self):
        self.build()
        with open(self.catalog, "rb") as f:
            text = f.read()
        with open(self.catalog, "wb") as f:
            f.write(text.replace(b"\n", b"\r\n"))
        code, out = self.verify()
        self.assertEqual(code, 1)
        self.assertIn("differs from a fresh build", out)

    def test_a_record_of_another_release_fails(self):
        # core's record copied from lending: one dataset, listed by the catalog, but not core's own release.
        shutil.copy(os.path.join(self.releases, "lending", "1.0.0", "catalog.ttl"),
                    os.path.join(self.releases, "core", "1.0.0", "catalog.ttl"))
        code, out = self.build()
        self.assertEqual(code, 1)
        self.assertIn("FAIL core 1.0.0: catalog.ttl describes https://id.example.org/library/lending/1.0.0, not this package's "
                      "release https://id.example.org/library/core/1.0.0", out)

    def test_a_manifest_without_a_version_iri_fails(self):
        path = os.path.join(self.releases, "core", "1.0.0", "manifest.json")
        with open(path, encoding="utf-8") as f:
            m = json.load(f)
        del m["version_iri"]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(m, f)
        code, out = self.build()
        self.assertEqual(code, 1)
        self.assertIn("FAIL core 1.0.0: the manifest names no version_iri", out)

    def test_a_changed_title_fails_verify(self):
        self.build()
        code, out = run(["verify", "--releases", self.releases, "--title", "Other", "--description", DESCRIPTION])
        self.assertEqual(code, 1)
        self.assertIn("differs from a fresh build", out)

    def test_no_written_catalog_fails_verify(self):
        code, out = self.verify()
        self.assertEqual(code, 1)
        self.assertIn("FAIL no written catalog at", out)

    def test_two_catalog_iris_fail(self):
        self.package(module="party", ontology_iri="https://id.example.org/party/people", title="People",
                     catalog_iri="https://id.example.org/party/catalog")
        code, out = self.build()
        self.assertEqual(code, 1)
        self.assertIn("FAIL the packages name different catalog IRIs: https://id.example.org/library/catalog (core 1.0.0, "
                      "lending 1.0.0); https://id.example.org/party/catalog (party 1.0.0)", out)
        self.assertFalse(os.path.exists(self.catalog))

    def edit_record(self, module, transform):
        path = os.path.join(self.releases, module, "1.0.0", "catalog.ttl")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        with open(path, "w", encoding="utf-8") as f:
            f.write(transform(text))

    def test_a_distribution_naming_no_file_fails(self):
        self.edit_record("core", lambda t: t.replace("releases/1.0.0/shapes.ttl", "releases/1.0.0/extra.ttl"))
        code, out = self.build()
        self.assertEqual(code, 1)
        self.assertIn("FAIL core 1.0.0: distribution https://id.example.org/library/core/releases/1.0.0/extra.ttl downloads extra.ttl, "
                      "which the manifest does not list", out)

    def test_a_download_url_naming_no_file_fails(self):
        # The distribution IRI still ends in shapes.ttl; only the URL a consumer follows points at a missing file.
        self.edit_record("core", lambda t: t.replace(
            "dcat:downloadURL <https://id.example.org/library/core/releases/1.0.0/shapes.ttl>",
            "dcat:downloadURL <https://id.example.org/library/core/releases/1.0.0/missing.ttl>"))
        code, out = self.build()
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL core 1.0.0: distribution https://id.example.org/library/core/releases/1.0.0/shapes.ttl downloads missing.ttl, "
                      "which the manifest does not list", out)

    def test_every_download_url_of_a_distribution_is_checked(self):
        # A second URL beside the good one, so the result cannot depend on which one the graph hands back.
        good = "dcat:downloadURL <https://id.example.org/library/core/releases/1.0.0/shapes.ttl>"
        record = os.path.join(self.releases, "core", "1.0.0", "catalog.ttl")
        with open(record, encoding="utf-8") as f:
            original = f.read()
        for extra, message in ((", <https://id.example.org/library/core/releases/1.0.0/missing.ttl>", "downloads missing.ttl"),
                               (', "https://id.example.org/library/core/releases/1.0.0/core.ttl"', "is not described")):
            with self.subTest(extra=extra):
                self.edit_record("core", lambda _: original.replace(good, good + extra))
                code, out = self.build()
                self.assertEqual(code, 1, out)
                self.assertIn(message, out)

    def test_a_distribution_not_described_fails(self):
        self.edit_record("core", lambda t: t.replace(
            "<https://id.example.org/library/core/releases/1.0.0/shapes.ttl> a dcat:Distribution ;\n"
            "    dcat:downloadURL <https://id.example.org/library/core/releases/1.0.0/shapes.ttl> ;",
            "<https://id.example.org/library/core/releases/1.0.0/shapes.ttl> a dcat:Distribution ;"))
        code, out = self.build()
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL core 1.0.0: distribution https://id.example.org/library/core/releases/1.0.0/shapes.ttl is not described", out)

    def test_a_download_url_that_is_a_literal_fails(self):
        self.edit_record("core", lambda t: t.replace(
            "dcat:downloadURL <https://id.example.org/library/core/releases/1.0.0/shapes.ttl>",
            'dcat:downloadURL "https://id.example.org/library/core/releases/1.0.0/shapes.ttl"'))
        code, out = self.build()
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL core 1.0.0: distribution https://id.example.org/library/core/releases/1.0.0/shapes.ttl is not described", out)

    def test_two_datasets_in_one_record_fail(self):
        self.edit_record("core", lambda t: t + "\n<https://id.example.org/library/core/2.0.0> a dcat:Dataset .\n")
        code, out = self.build()
        self.assertEqual(code, 1)
        self.assertIn("FAIL core 1.0.0: catalog.ttl holds 2 dcat:Dataset, not one", out)

    def test_a_dataset_the_catalog_does_not_list_fails(self):
        self.edit_record("core", lambda t: t.replace("    dcat:dataset <https://id.example.org/library/core/1.0.0> .",
                                                     "    dcterms:title \"x\"@en ."))
        code, out = self.build()
        self.assertEqual(code, 1)
        self.assertIn("FAIL core 1.0.0: https://id.example.org/library/catalog does not list https://id.example.org/library/core/1.0.0", out)

    def test_a_package_without_a_record_fails(self):
        os.remove(os.path.join(self.releases, "core", "1.0.0", "catalog.ttl"))
        code, out = self.build()
        self.assertEqual(code, 1)
        self.assertIn("FAIL core 1.0.0: cannot read catalog.ttl", out)

    def test_an_empty_releases_folder_fails(self):
        empty = os.path.join(self.root, "empty")
        os.makedirs(empty)
        code, out = run(["build", "--releases", empty, "--title", TITLE, "--description", DESCRIPTION])
        self.assertEqual(code, 1)
        self.assertIn("FAIL no release package under", out)

    def test_out_names_the_file(self):
        out_path = os.path.join(self.root, "combined.ttl")
        self.assertEqual(self.build("--out", out_path)[0], 0)
        self.assertTrue(os.path.isfile(out_path))
        self.assertFalse(os.path.exists(self.catalog))
        self.assertEqual(self.verify("--out", out_path)[0], 0)

    def test_bad_arguments_are_usage_errors(self):
        self.assertEqual(run(["build", "--releases", os.path.join(self.root, "nope"), "--title", TITLE, "--description", DESCRIPTION])[0], 2)
        self.assertEqual(run(["build", "--releases", self.releases, "--title", " ", "--description", DESCRIPTION])[0], 2)
        self.assertEqual(run(["build", "--releases", self.releases])[0], 2)
        self.assertEqual(run(["rebuild", "--releases", self.releases, "--title", TITLE, "--description", DESCRIPTION])[0], 2)

    def test_the_manifest_is_read_as_check_packages_reads_it(self):
        path = os.path.join(self.releases, "core", "1.0.0", "manifest.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"files": ["core.ttl"]}, f)
        code, out = self.build()
        self.assertEqual(code, 1)
        self.assertIn('FAIL core 1.0.0: manifest "files" is not an object', out)


if __name__ == "__main__":
    unittest.main()
