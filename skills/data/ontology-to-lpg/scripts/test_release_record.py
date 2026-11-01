"""Tests of release_record.py with a stand-in session: no database.

Run: uv run --no-project --with rdflib python3 -m unittest test_release_record
"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

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
    """Plays the statements release_record.py and load_verify.hash_graph send, over the :Resource nodes it holds."""

    def __init__(self, uris=(BASE,)):
        self.resources = [{"uri": u, "labels": ["Resource"], "props": {"uri": u}} for u in uris]
        self.records, self.links = [], {}
        self.statements = []

    def run(self, query, parameters=None, **kwargs):
        self.statements.append(query)
        params = {**(parameters or {}), **kwargs}
        if query == rr.CLEAR:
            self.records, self.links = [], {}
            return Result([])
        if query == rr.WRITE:
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
        content = rr.build_records([self.path], earned_report(), "2026-11-01T00:00:00Z")
        self.assertEqual(content["graph_hash"], earned_report()["determinism_hash_sorted"])
        self.assertEqual(content["records"], [{
            "module": "m", "version": "1.2.0", "version_iri": f"{BASE}/1.2.0", "ontology": BASE,
            "download_url": f"{BASE}/releases/1.2.0/m.ttl", "conforms": True, "in_graph_constraints": 7, "violations": 0,
            "shapes_sha256": rr.sha256(os.path.join(self.tmp, "shapes.ttl")), "projection_version": "ontology-to-lpg 2.3",
            "loaded_at": "2026-11-01T00:00:00Z"}])

    def test_a_report_that_did_not_earn_its_pass_makes_no_record(self):
        rep = earned_report(roundtrip_lost=1)
        self.assertTrue(build.report_earned(rep))
        with self.assertRaises(rr.Refusal):
            rr.build_records([self.path], rep, "t")

    def test_a_catalog_of_another_release_is_refused(self):
        self.write("catalog.ttl", CATALOG.replace("1.2.0", "1.1.0"))
        with self.assertRaisesRegex(rr.Refusal, "no dcat:Dataset"):
            rr.build_records([self.path], earned_report(), "t")

    def test_a_catalog_without_the_files_download_url_is_refused(self):
        self.write("catalog.ttl", CATALOG.replace("m.ttl", "other.ttl"))
        with self.assertRaisesRegex(rr.Refusal, "downloadURL"):
            rr.build_records([self.path], earned_report(), "t")

    def test_the_cli_writes_the_file_and_a_missing_catalog_exits_2(self):
        report = self.write("report.json", json.dumps(earned_report()))
        out = os.path.join(self.tmp, "records.json")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(rr.main(["records", "--report", report, "--output", out, "--loaded-at", "t", self.path]), 0)
        with open(out, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["records"][0]["loaded_at"], "t")
        os.remove(os.path.join(self.tmp, "catalog.ttl"))
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(rr.main(["records", "--report", report, "--output", out, self.path]), 2)


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
        self.assertEqual(lv.hash_graph(s), before)
        self.assertEqual(rr.check(s, content), [])

    def test_the_hash_statements_read_only_resource_nodes(self):
        s = FakeSession()
        lv.hash_graph(s)
        self.assertEqual(s.statements, [
            "MATCH (n:Resource) RETURN n.uri AS uri, labels(n) AS labels, properties(n) AS props",
            "MATCH (a:Resource)-[r]->(b:Resource) RETURN a.uri AS s, type(r) AS t, b.uri AS o, r.uri AS u, properties(r) AS props"])
        self.assertNotIn("Resource", rr.LABEL)
        self.assertRegex(rr.WRITE, r"CREATE \(r:ModuleRelease\)")
        self.assertRegex(rr.WRITE, r"CREATE \(r\)-\[:DESCRIBES\]->\(o\)")

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

    def test_a_module_with_no_ontology_node_fails(self):
        s = FakeSession(uris=("https://x.org/other",))
        problems, linked = rr.write(s, self.content(s))
        self.assertEqual(linked, 0)
        self.assertIn("0 of 1 records", problems[0])

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
