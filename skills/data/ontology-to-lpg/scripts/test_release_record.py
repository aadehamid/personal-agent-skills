"""Tests of release_record.py with a stand-in session: no database.

Run: uv run --no-project --with rdflib python3 -m unittest test_release_record
"""
import contextlib
import hashlib
import io
import json
import os
import pathlib
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build  # noqa: E402
import load_verify as lv  # noqa: E402
import release_record as rr  # noqa: E402

BASE = "https://x.org/modules/m"
MODULE = f"""@prefix owl: <http://www.w3.org/2002/07/owl#> .
<{BASE}> a owl:Ontology ; owl:versionIRI <{BASE}/1.2.0> .
"""
CATALOG = f"""@prefix dcat: <http://www.w3.org/ns/dcat#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
<{BASE}/1.2.0> a dcat:Dataset ; dcterms:isVersionOf <{BASE}> ; owl:versionInfo "1.2.0" ;
    dcat:distribution <{BASE}/releases/1.2.0/m.ttl>, <{BASE}/releases/1.2.0/shapes.ttl> .
<{BASE}/releases/1.2.0/m.ttl> a dcat:Distribution ; dcat:downloadURL <{BASE}/releases/1.2.0/m.ttl> .
<{BASE}/releases/1.2.0/shapes.ttl> a dcat:Distribution ; dcat:downloadURL <{BASE}/releases/1.2.0/shapes.ttl> .
"""
SHAPES = "# shapes\n"


def sha_of(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def manifest(folder, **change):
    """What a run that read this test's three files in folder records."""
    entry = lambda name, text: [{"path": os.path.join(folder, name), "sha256": sha_of(text)}]   # noqa: E731
    return {"data": entry("m.ttl", MODULE), "shapes": entry("shapes.ttl", SHAPES), "catalogs": entry("catalog.ttl", CATALOG), **change}


def earned_report(**change):
    """A report that earns its pass; test_engine_gate holds the shape build.report_earned reads."""
    from test_engine_gate import earned_report as base
    return {**base(in_graph_shape_constraints=7, shapes_import_rows=7, versions={"method": "ontology-to-lpg 2.3"}), **change}


class Result:
    def __init__(self, rows):
        self.rows = rows

    def data(self):
        return self.rows

    def single(self):
        return self.rows[0]

    def consume(self):
        return None


class FakeSession:
    """Plays the statements release_record.py and load_verify.hash_graph send, over the :Resource nodes it holds. As a
    transaction it keeps a copy of the records, and a rollback restores them. move_on_write changes the graph during
    WRITE, and fail_on names a statement that raises."""

    def __init__(self, uris=(BASE,), move_on_write=False, fail_on=None):
        self.resources = [{"uri": u, "labels": ["Resource"], "props": {"uri": u}} for u in uris]
        self.records, self.links = [], {}
        self.statements = []
        self.move_on_write, self.fail_on = move_on_write, fail_on
        self.begun = self.committed = self.rolled_back = 0

    def begin_transaction(self):
        self.begun += 1
        self.saved = ([dict(r) for r in self.records], dict(self.links), [dict(n, props=dict(n["props"])) for n in self.resources])
        return self

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1
        self.records, self.links, self.resources = self.saved

    def run(self, query, parameters=None, **kwargs):
        self.statements.append(query)
        params = {**(parameters or {}), **kwargs}
        if query == self.fail_on:
            raise RuntimeError("the statement failed")
        if query == rr.CLEAR:
            self.records, self.links = [], {}
            return Result([])
        if query == rr.WRITE:
            if self.move_on_write:
                self.resources[0]["props"]["moved"] = "yes"
            linked = 0
            for row in params["rows"]:
                self.records.append(dict(row))
                if any(n["uri"] == row["ontology"] for n in self.resources):
                    self.links[row["version_iri"]] = [row["ontology"]]
                    linked += 1
            return Result([{"linked": linked}])
        if query == rr.READ:
            return Result([{"fields": dict(r), "links": self.links.get(r["version_iri"], [])} for r in self.records])
        if "RETURN n.uri AS uri, labels(n)" in query:
            return Result(self.resources)
        if "RETURN a.uri AS s" in query:
            return Result([])
        raise AssertionError(query)


class Records(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.path = self.write("m.ttl", MODULE)
        self.write("catalog.ttl", CATALOG)
        self.write("shapes.ttl", SHAPES)

    def write(self, name, text):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def test_every_field_comes_from_the_release_files_and_the_report(self):
        content = rr.build_records([self.path], earned_report(), "2026-11-01T00:00:00Z", manifest(self.tmp))
        self.assertEqual(content["graph_hash"], earned_report()["determinism_hash_sorted"])
        self.assertEqual(content["records"], [{
            "module": "m", "version": "1.2.0", "version_iri": f"{BASE}/1.2.0", "ontology": BASE,
            "download_url": f"{BASE}/releases/1.2.0/m.ttl", "conforms": True, "in_graph_constraints": 7, "violations": 0,
            "shapes_sha256": sha_of(SHAPES), "projection_version": "ontology-to-lpg 2.3",
            "loaded_at": "2026-11-01T00:00:00Z"}])

    def test_a_report_that_did_not_earn_its_pass_makes_no_record(self):
        rep = earned_report(roundtrip_lost=1)
        self.assertTrue(build.report_earned(rep))
        with self.assertRaises(rr.Refusal):
            rr.build_records([self.path], rep, "t", manifest(self.tmp))

    def test_a_catalog_of_another_release_is_refused(self):
        text = CATALOG.replace("1.2.0", "1.1.0")
        self.write("catalog.ttl", text)
        with self.assertRaisesRegex(rr.Refusal, "no dcat:Dataset"):
            rr.build_records([self.path], earned_report(), "t", manifest(self.tmp, catalogs=[{"path": os.path.join(self.tmp, "catalog.ttl"), "sha256": sha_of(text)}]))

    def test_a_file_edited_after_the_load_makes_no_record(self):
        for name, text in (("shapes.ttl", SHAPES + "# edited\n"), ("catalog.ttl", CATALOG + "# edited\n"), ("m.ttl", MODULE + "# edited\n")):
            with self.subTest(name=name):
                before = open(os.path.join(self.tmp, name)).read()
                self.write(name, text)
                with self.assertRaisesRegex(rr.Refusal, "not the file the run read"):
                    rr.build_records([self.path], earned_report(), "t", manifest(self.tmp))
                self.write(name, before)

    def test_a_known_digest_at_another_path_is_refused(self):
        """Two releases' shapes swapped: each digest is in the run manifest, but not at that path."""
        other = os.path.join(self.tmp, "other-shapes.ttl")
        ran = manifest(self.tmp, shapes=[{"path": os.path.join(self.tmp, "shapes.ttl"), "sha256": sha_of("# the other module's\n")},
                                         {"path": other, "sha256": sha_of(SHAPES)}])
        with self.assertRaisesRegex(rr.Refusal, "shapes.ttl is not the file the run read"):
            rr.build_records([self.path], earned_report(), "t", ran)

    def test_a_file_replaced_during_the_read_cannot_enter_the_record(self):
        """Each file is opened once: what is hashed is what is parsed. A swap after that read changes nothing."""
        opened, real = [], open

        def counting(path, *a, **k):
            opened.append(os.path.basename(str(path)))
            return real(path, *a, **k)
        with mock.patch("builtins.open", counting):
            rr.build_records([self.path], earned_report(), "t", manifest(self.tmp))
        for name in ("m.ttl", "shapes.ttl", "catalog.ttl"):
            self.assertEqual(opened.count(name), 1, name)

    def test_a_relative_iri_resolves_against_its_own_file(self):
        body = b"<> <https://x.org/p> <1.2.0> ."
        g = rr.parsed(os.path.join(self.tmp, "m.ttl"), body)
        s, _, o = next(iter(g))
        self.assertEqual(str(s), pathlib.Path(os.path.abspath(os.path.join(self.tmp, "m.ttl"))).as_uri())
        self.assertTrue(str(o).endswith("/1.2.0"))
        self.assertIn(os.path.basename(self.tmp), str(o))

    def test_a_manifest_without_catalogs_is_refused(self):
        with self.assertRaisesRegex(rr.Refusal, "lists no catalogs"):
            rr.build_records([self.path], earned_report(), "t", {"data": [], "shapes": []})

    def test_a_catalog_that_names_another_module_is_refused(self):
        text = CATALOG.replace(f"dcterms:isVersionOf <{BASE}>", "dcterms:isVersionOf <https://x.org/modules/other>")
        self.write("catalog.ttl", text)
        with self.assertRaisesRegex(rr.Refusal, "another module"):
            rr.build_records([self.path], earned_report(), "t", manifest(self.tmp, catalogs=[{"path": os.path.join(self.tmp, "catalog.ttl"), "sha256": sha_of(text)}]))

    def test_two_modules_with_one_version_iri_are_refused(self):
        other = os.path.join(self.tmp, "two")
        os.makedirs(other)
        second_module = MODULE.replace(f"<{BASE}> a", "<https://x.org/modules/n> a")
        second_catalog = CATALOG.replace(f"dcterms:isVersionOf <{BASE}>", "dcterms:isVersionOf <https://x.org/modules/n>").replace("m.ttl", "n.ttl")
        for name, text in (("n.ttl", second_module), ("catalog.ttl", second_catalog), ("shapes.ttl", SHAPES)):
            with open(os.path.join(other, name), "w", encoding="utf-8") as f:
                f.write(text)
        row = lambda name, text: {"path": os.path.join(other, name), "sha256": sha_of(text)}   # noqa: E731
        first = manifest(self.tmp)
        both = {"data": first["data"] + [row("n.ttl", second_module)], "shapes": first["shapes"] + [row("shapes.ttl", SHAPES)],
                "catalogs": first["catalogs"] + [row("catalog.ttl", second_catalog)]}
        with self.assertRaisesRegex(rr.Refusal, "one release"):
            rr.build_records([self.path, os.path.join(other, "n.ttl")], earned_report(), "t", both)

    def test_a_catalog_without_the_files_download_url_is_refused(self):
        text = CATALOG.replace("m.ttl", "other.ttl")
        self.write("catalog.ttl", text)
        with self.assertRaisesRegex(rr.Refusal, "downloadURL"):
            rr.build_records([self.path], earned_report(), "t", manifest(self.tmp, catalogs=[{"path": os.path.join(self.tmp, "catalog.ttl"), "sha256": sha_of(text)}]))

    def test_the_cli_writes_the_file_and_a_missing_catalog_exits_2(self):
        report = self.write("report.json", json.dumps(earned_report()))
        ran = self.write("run-manifest.json", json.dumps(manifest(self.tmp)))
        out = os.path.join(self.tmp, "records.json")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(rr.main(["records", "--report", report, "--manifest", ran, "--output", out, "--loaded-at", "t", self.path]), 0)
        with open(out, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["records"][0]["loaded_at"], "t")
        os.remove(os.path.join(self.tmp, "catalog.ttl"))
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(rr.main(["records", "--report", report, "--manifest", ran, "--output", out, self.path]), 2)


class WriteAndCheck(unittest.TestCase):
    def content(self, session, **fields):
        record = {"module": "m", "version": "1.2.0", "version_iri": f"{BASE}/1.2.0", "ontology": BASE,
                  "download_url": "u", "conforms": True, "in_graph_constraints": 7, "violations": 0,
                  "shapes_sha256": "s", "projection_version": "v", "loaded_at": "t", **fields}
        return {"graph_hash": lv.hash_graph(session)[0], "records": [record]}

    def test_the_records_leave_the_graph_hash_where_it_was(self):
        s = FakeSession()
        content = self.content(s)
        before = lv.hash_graph(s)
        self.assertEqual(rr.write(s, content), ([], 1))
        self.assertEqual((s.committed, s.rolled_back), (1, 0))
        self.assertEqual(lv.hash_graph(s), before)
        self.assertEqual(rr.check(s, content), [])

    def test_the_hash_statements_read_only_resource_nodes(self):
        s = FakeSession()
        lv.hash_graph(s)
        self.assertEqual(s.statements, [
            "MATCH (n:Resource) RETURN n.uri AS uri, labels(n) AS labels, properties(n) AS props",
            "MATCH (a:Resource)-[r]->(b:Resource) RETURN a.uri AS s, type(r) AS t, b.uri AS o, r.uri AS u, properties(r) AS props"])
        self.assertEqual(rr.CLEAR, "MATCH (r:ModuleRelease) DETACH DELETE r")
        self.assertEqual(rr.WRITE, "UNWIND $rows AS row CREATE (r:ModuleRelease) SET r = row WITH r "
                                   "MATCH (o:Resource {uri: r.ontology}) CREATE (r)-[:DESCRIBES]->(o) RETURN count(*) AS linked")

    def test_the_tags_read_resource_nodes_and_the_edges_between_them(self):
        import module_tags as mt
        self.assertEqual(mt.NODES, "MATCH (n:Resource) RETURN n.uri AS uri, n.`graph` AS tag")
        self.assertEqual(mt.EDGES, "MATCH (a:Resource)-[r]->(b:Resource) RETURN a.uri AS s, type(r) AS t, b.uri AS o, r.`graph` AS tag")

    def test_the_round_trip_starts_only_at_resource_nodes_so_the_link_is_not_read(self):
        self.assertIn("MATCH (n:Resource) OPTIONAL MATCH (n)-[r]->(m)", lv.EXPORT)

    def test_a_graph_that_is_not_the_verified_one_gets_no_record(self):
        s = FakeSession()
        content = {**self.content(s), "graph_hash": "other"}
        problems, _ = rr.write(s, content)
        self.assertIn("nothing was written", problems[0])
        self.assertEqual(s.records, [])

    def test_a_second_write_replaces_the_records(self):
        s = FakeSession()
        rr.write(s, self.content(s, loaded_at="first"))
        content = self.content(s, loaded_at="second")
        rr.write(s, content)
        self.assertEqual([r["loaded_at"] for r in s.records], ["second"])
        self.assertEqual(rr.check(s, content), [])

    def test_a_module_with_no_ontology_node_fails_and_leaves_the_earlier_records(self):
        s = FakeSession()
        rr.write(s, self.content(s, loaded_at="earlier"))
        problems, linked = rr.write(s, self.content(s, ontology="https://x.org/other", loaded_at="later"))
        self.assertEqual(linked, 0)
        self.assertIn("0 of 1 records", problems[0])
        self.assertEqual([r["loaded_at"] for r in s.records], ["earlier"])
        self.assertEqual(s.rolled_back, 1)

    def test_a_write_that_moves_the_graph_is_rolled_back(self):
        s = FakeSession(move_on_write=True)
        problems, _ = rr.write(s, self.content(s))
        self.assertEqual(problems, ["the graph hash moved when the records were written; nothing was written"])
        self.assertEqual((s.committed, s.rolled_back, s.records), (0, 1, []))
        self.assertNotIn("moved", s.resources[0]["props"])

    def test_an_error_after_the_clear_keeps_the_earlier_records(self):
        s = FakeSession()
        rr.write(s, self.content(s, loaded_at="earlier"))
        s.fail_on = rr.WRITE
        with self.assertRaises(RuntimeError):
            rr.write(s, self.content(s, loaded_at="later"))
        self.assertEqual([r["loaded_at"] for r in s.records], ["earlier"])

    def test_check_finds_each_kind_of_difference(self):
        s = FakeSession()
        content = self.content(s)
        rr.write(s, content)
        s.records[0]["violations"] = 3
        self.assertEqual(rr.check(s, content), ["m: violations differ"])
        s.records[0]["violations"] = 0
        s.links = {}
        self.assertEqual(rr.check(s, content), ["m: not linked to its owl:Ontology node alone"])
        s.records = []
        self.assertEqual(rr.check(s, content), ["no record of m"])
        s.records = [{"version_iri": "https://x.org/stray"}]
        self.assertTrue(any("does not list" in p for p in rr.check(s, content)))

    def test_check_fails_when_the_graph_moved(self):
        s = FakeSession()
        content = self.content(s)
        rr.write(s, content)
        s.resources[0]["props"]["uri2"] = "x"
        self.assertEqual(rr.check(s, content), ["the graph hash is not the verified graph's"])


if __name__ == "__main__":
    unittest.main()
