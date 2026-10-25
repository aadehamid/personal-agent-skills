#!/usr/bin/env python3
"""Tests for rdfstore.py. None needs Docker or Databricks: the Graph Store Protocol runs against a
small HTTP server in this process backed by pyoxigraph, and the Delta table against a fake connection
that decodes the SQL rdfstore.py sends. Each planted fault (a lost triple, a changed literal, datatype
or language tag, a triple in the wrong graph) must fail the round trip.

Live tests run only when asked: RDF_STORE_LIVE_FUSEKI=<base URL of a Fuseki dataset, such as
http://127.0.0.1:13030/ds> and RDF_STORE_LIVE_DATABRICKS=<env file>.

Run: uv run --no-project --with pyoxigraph python3 -m unittest test_rdf_store
"""
import base64
import http.server
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.parse

import pyoxigraph as ox

import rdfstore as rs

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)

LIBRARY = """@prefix lib: <https://example.org/library/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
<https://example.org/library> a owl:Ontology ; owl:versionIRI <https://example.org/library/1.0.0> .
lib:Loan a owl:Class ; skos:prefLabel "Loan"@en, "Prêt"@fr ; skos:definition "A book lent to a member, with \\"quotes\\" and a back\\\\slash."@en .
lib:loanDays a owl:DatatypeProperty ; lib:defaultValue "21"^^xsd:integer ; lib:note "plain" .
lib:Loan lib:hasPart [ a lib:Clause ; skos:prefLabel "Return clause"@en ] .
"""
CATALOG = """@prefix owl: <http://www.w3.org/2002/07/owl#> .
<https://example.org/catalog> a owl:Ontology ; owl:versionIRI <https://example.org/catalog/2.1.0> .
<https://example.org/catalog/item> <https://example.org/library/title> "Catalog" .
"""
G_LIB = ox.NamedNode("https://example.org/library/1.0.0")
G_CAT = ox.NamedNode("https://example.org/catalog/2.1.0")


def write(folder, name, text):
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def release_dataset():
    folder = tempfile.mkdtemp()
    return rs.pack([write(folder, "library.ttl", LIBRARY), write(folder, "catalog.ttl", CATALOG)])


# ---- faults a store could make -----------------------------------------------------------

def find(dataset, predicate_suffix, graph=G_LIB):
    return next(q for q in dataset if q.predicate.value.endswith(predicate_suffix) and q.graph_name == graph)


def lose_a_triple(ds):
    ds.remove(find(ds, "defaultValue"))


def change_a_literal(ds):
    q = find(ds, "note")
    ds.remove(q)
    ds.add(ox.Quad(q.subject, q.predicate, ox.Literal("plain "), q.graph_name))


def change_a_datatype(ds):
    q = find(ds, "defaultValue")
    ds.remove(q)
    ds.add(ox.Quad(q.subject, q.predicate, ox.Literal("21", datatype=ox.NamedNode("http://www.w3.org/2001/XMLSchema#string")), q.graph_name))


def change_a_language_tag(ds):
    q = next(q for q in ds if isinstance(q.object, ox.Literal) and q.object.language == "fr")
    ds.remove(q)
    ds.add(ox.Quad(q.subject, q.predicate, ox.Literal(q.object.value, language="en"), q.graph_name))


def move_to_the_wrong_graph(ds):
    q = find(ds, "title", G_CAT)
    ds.remove(q)
    ds.add(ox.Quad(q.subject, q.predicate, q.object, G_LIB))


FAULTS = [lose_a_triple, change_a_literal, change_a_datatype, change_a_language_tag, move_to_the_wrong_graph]


# ---- a Graph Store Protocol server in this process ---------------------------------------

class GspHandler(http.server.BaseHTTPRequestHandler):
    store = None      # pyoxigraph.Store, set per server
    fault = None      # applied to every GET of a graph, to plant a store's mistake

    def log_message(self, *args):
        pass

    def _graph(self):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query, keep_blank_values=True)
        if "default" in query:
            return ox.DefaultGraph()
        return ox.NamedNode(query["graph"][0])

    def _send(self, code, body=b"", ctype="text/plain"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_PUT(self):
        g = self._graph()
        data = self.rfile.read(int(self.headers["Content-Length"]))
        self.store.remove_graph(g) if isinstance(g, ox.NamedNode) and g in self.store.named_graphs() else None
        for t in ox.parse(data, format=ox.RdfFormat.N_TRIPLES):
            self.store.add(ox.Quad(t.subject, t.predicate, t.object, g))
        self._send(201)

    def do_DELETE(self):
        g = self._graph()
        if g not in list(self.store.named_graphs()):
            return self._send(404)
        self.store.remove_graph(g)
        self._send(204)

    def do_GET(self):
        g = self._graph()
        ds = ox.Dataset(self.store.quads_for_pattern(None, None, None, g))
        if self.fault:
            # The fault works on the whole dataset; this graph's part of the result is sent.
            whole = ox.Dataset(self.store)
            self.fault(whole)
            ds = ox.Dataset(q for q in whole if q.graph_name == g)
        body = rs.nt_bytes(ds, g)
        self._send(200, body, "application/n-triples")

    def do_POST(self):
        form = urllib.parse.parse_qs(self.rfile.read(int(self.headers["Content-Length"])).decode())
        names = sorted({q.graph_name.value for q in self.store if isinstance(q.graph_name, ox.NamedNode)})
        if self.fault:
            whole = ox.Dataset(self.store)
            self.fault(whole)
            names = sorted({q.graph_name.value for q in whole if isinstance(q.graph_name, ox.NamedNode)})
        assert "GRAPH ?g" in form["query"][0]
        body = json.dumps({"results": {"bindings": [{"g": {"type": "uri", "value": n}} for n in names]}}).encode()
        self._send(200, body, "application/sparql-results+json")


def gsp_server(fault=None):
    handler = type("H", (GspHandler,), {"store": ox.Store(), "fault": staticmethod(fault) if fault else None})
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    return server, rs.FusekiStore(base + "/ds/data", base + "/ds/query")


# ---- a fake Databricks connection that runs the SQL rdfstore.py sends ---------------------

class FakeCursor:
    def __init__(self, db):
        self.db, self.result = db, []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql):
        self.db.statements.append(sql)
        if sql.startswith("CREATE OR REPLACE TABLE"):
            self.db.rows = []
        elif sql.startswith("INSERT INTO"):
            body = sql.split("FROM VALUES\n", 1)[1].rsplit("\nAS v(", 1)[0]
            for line in body.split(",\n"):
                values = re.findall(r"NULL|'([A-Za-z0-9+/=]*)'", line.strip()[1:-1])
                cells = re.findall(r"NULL|'[A-Za-z0-9+/=]*'", line)
                row = tuple(None if c == "NULL" else base64.b64decode(c[1:-1]).decode("utf-8") for c in cells)
                assert len(row) == len(rs.COLUMNS), (line, values)
                self.db.rows.append(row)
        elif sql.startswith("SELECT"):
            rows = list(self.db.rows)
            if self.db.fault:
                ds = rs.from_rows(rows)
                self.db.fault(ds)
                rows = rs.to_rows(ds)
            self.result = rows
        else:
            raise AssertionError(sql)

    def fetchall(self):
        return self.result


class FakeConnection:
    def __init__(self, fault=None):
        self.rows, self.statements, self.fault = [], [], fault

    def cursor(self):
        return FakeCursor(self)


# ---- the tests ---------------------------------------------------------------------------

class CanonicalHash(unittest.TestCase):
    def test_the_hash_ignores_blank_node_labels_and_order(self):
        a = ox.Dataset(ox.parse(b'_:x <http://p> "v" <http://g> .\n_:x <http://q> _:y <http://g> .\n', format=ox.RdfFormat.N_QUADS))
        b = ox.Dataset(ox.parse(b'_:k <http://q> _:m <http://g> .\n_:k <http://p> "v" <http://g> .\n', format=ox.RdfFormat.N_QUADS))
        self.assertEqual(rs.dataset_hash(a), rs.dataset_hash(b))

    def test_the_hash_matches_a_w3c_rdfc_test_case(self):
        # rdf-canon test001 (w3c.github.io/rdf-canon/tests/rdfc10/test001-in.nq and -rdfc10.nq).
        source = b'<http://example.com/#p> <http://example.com/#q> <http://example.com/#Foo> .\n<http://example.com/#p> <http://example.com/#r> <http://example.com/#Bar> .\n'
        lines = rs.canonical_lines(ox.Dataset(ox.parse(source, format=ox.RdfFormat.N_QUADS)))
        self.assertEqual("".join(lines), source.decode())

    def test_every_fault_changes_the_hash(self):
        clean = release_dataset()
        for fault in FAULTS:
            with self.subTest(fault.__name__):
                ds = release_dataset()
                fault(ds)
                passed, report = rs.compare(clean, ds)
                self.assertFalse(passed)
                self.assertTrue(report["diff"][0].endswith("extra") or "missing" in report["diff"][0])

    def test_counts_can_match_while_the_hash_does_not(self):
        clean, changed = release_dataset(), release_dataset()
        change_a_literal(changed)
        passed, report = rs.compare(clean, changed)
        self.assertFalse(passed)
        self.assertEqual(report["predicate_counts_differ"], {})


class Packing(unittest.TestCase):
    def test_each_file_is_its_own_graph_named_by_its_version_iri(self):
        ds = release_dataset()
        graphs, _ = rs.counts(ds)
        self.assertEqual(sorted(graphs), [G_CAT.value, G_LIB.value])

    def test_a_file_without_an_ontology_header_needs_a_graph_name(self):
        folder = tempfile.mkdtemp()
        path = write(folder, "shapes.ttl", "<https://example.org/s> <https://example.org/p> 1 .\n")
        with self.assertRaises(rs.BadInput):
            rs.pack([path])
        ds = rs.pack([path], rs.parse_graph_options([f"{path}=https://example.org/shapes/1.0.0"]))
        self.assertEqual(list(rs.counts(ds)[0]), ["https://example.org/shapes/1.0.0"])

    def test_two_files_cannot_share_a_graph(self):
        folder = tempfile.mkdtemp()
        a, b = write(folder, "a.ttl", LIBRARY), write(folder, "b.ttl", LIBRARY)
        with self.assertRaises(rs.BadInput):
            rs.pack([a, b])


class Skolemize(unittest.TestCase):
    def test_blank_nodes_become_stable_genid_iris(self):
        folder = tempfile.mkdtemp()
        path = write(folder, "library.ttl", LIBRARY)
        first = rs.skolemize(rs.read_triples(path), G_LIB.value, "https://example.org")
        again = rs.skolemize(list(reversed(rs.read_triples(path))), G_LIB.value, "https://example.org/")
        self.assertEqual(sorted(map(str, first)), sorted(map(str, again)))
        self.assertFalse(any(isinstance(t.subject, ox.BlankNode) or isinstance(t.object, ox.BlankNode) for t in first))
        self.assertTrue(any("/.well-known/genid/" in t.subject.value for t in first))

    def test_the_same_blank_node_shape_in_another_graph_gets_another_iri(self):
        folder = tempfile.mkdtemp()
        triples = rs.read_triples(write(folder, "library.ttl", LIBRARY))
        a = {t.subject.value for t in rs.skolemize(triples, "https://example.org/a", "https://example.org")}
        b = {t.subject.value for t in rs.skolemize(triples, "https://example.org/b", "https://example.org")}
        self.assertNotEqual({x for x in a if "genid" in x}, {x for x in b if "genid" in x})


class DeltaTable(unittest.TestCase):
    def test_rows_round_trip_every_kind_of_term(self):
        ds = release_dataset()
        self.assertEqual(rs.dataset_hash(rs.from_rows(rs.to_rows(ds))), rs.dataset_hash(ds))

    def test_text_that_looks_like_sql_or_a_term_stays_a_literal(self):
        ds = ox.Dataset([ox.Quad(ox.NamedNode("http://s"), ox.NamedNode("http://p"), ox.Literal(text), ox.NamedNode("http://g"))
                         for text in ("_:b0", "http://looks.like/an/iri", "it's'); DROP TABLE x; --", "back\\slash")])
        conn = FakeConnection()
        passed, _ = rs.roundtrip(rs.DatabricksStore(conn, "c.s.t"), ds)
        self.assertTrue(passed)
        self.assertFalse(any("DROP TABLE" in s for s in conn.statements))

    def test_the_default_graph_is_a_null_graph(self):
        ds = ox.Dataset([ox.Quad(ox.NamedNode("http://s"), ox.NamedNode("http://p"), ox.NamedNode("http://o"), ox.DefaultGraph())])
        self.assertIsNone(rs.to_rows(ds)[0][-1])
        self.assertEqual(rs.dataset_hash(rs.from_rows(rs.to_rows(ds))), rs.dataset_hash(ds))

    def test_a_clean_round_trip_passes_in_batches(self):
        conn = FakeConnection()
        store = rs.DatabricksStore(conn, "c.s.t")
        store.BATCH = 3
        passed, report = rs.roundtrip(store, release_dataset())
        self.assertTrue(passed, report)
        self.assertGreater(sum(s.startswith("INSERT") for s in conn.statements), 1)

    def test_each_fault_fails_the_round_trip(self):
        for fault in FAULTS:
            with self.subTest(fault.__name__):
                passed, _ = rs.roundtrip(rs.DatabricksStore(FakeConnection(fault), "c.s.t"), release_dataset())
                self.assertFalse(passed)


class GraphStoreProtocol(unittest.TestCase):
    def test_a_clean_round_trip_passes(self):
        server, store = gsp_server()
        try:
            passed, report = rs.roundtrip(store, release_dataset())
        finally:
            server.shutdown(); server.server_close()
        self.assertTrue(passed, report)
        self.assertEqual(report["graph_counts"][G_CAT.value], [1 + 2, 1 + 2])

    def test_each_fault_fails_the_round_trip(self):
        for fault in FAULTS:
            with self.subTest(fault.__name__):
                server, store = gsp_server(fault)
                try:
                    passed, report = rs.roundtrip(store, release_dataset())
                finally:
                    server.shutdown(); server.server_close()
                self.assertFalse(passed)
                self.assertIn("diff", report)

    def test_a_graph_left_from_an_earlier_load_shows_as_extra(self):
        server, store = gsp_server()
        try:
            store.load(ox.Dataset([ox.Quad(ox.NamedNode("http://s"), ox.NamedNode("http://p"), ox.Literal("old"), ox.NamedNode("http://stale"))]))
            passed, report = rs.roundtrip(store, release_dataset())
        finally:
            server.shutdown(); server.server_close()
        self.assertFalse(passed)
        self.assertEqual(report["graph_counts"]["http://stale"], [0, 1])


class CommandLine(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, os.path.join(HERE, "rdfstore.py"), *args], capture_output=True, text=True)

    def test_compare_exits_1_with_a_diff(self):
        folder = tempfile.mkdtemp()
        lib = write(folder, "library.ttl", LIBRARY)
        out = os.path.join(folder, "a.nq")
        self.assertEqual(self.run_cli("pack", "--out", out, lib).returncode, 0)
        changed = os.path.join(folder, "b.nq")
        with open(out) as f, open(changed, "w") as g:
            g.write(f.read().replace('"plain"', '"plain "'))
        r = self.run_cli("compare", out, changed)
        self.assertEqual(r.returncode, 1)
        self.assertIn('\\"plain \\"', r.stdout)
        self.assertEqual(self.run_cli("compare", out, out).returncode, 0)

    def test_bad_input_exits_2(self):
        self.assertEqual(self.run_cli("roundtrip", "--store", "nowhere", "x.ttl").returncode, 2)
        self.assertEqual(self.run_cli("pack").returncode, 2)

    def test_the_token_is_never_printed(self):
        folder = tempfile.mkdtemp()
        env = write(folder, "db.env", "DATABRICKS_HOST=https://h\nDATABRICKS_TOKEN=dapiSECRET123\n")
        r = self.run_cli("roundtrip", "--store", "databricks", "--env", env, write(folder, "l.ttl", LIBRARY))
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("dapiSECRET123", r.stdout + r.stderr)


class FusekiImage(unittest.TestCase):
    def test_the_fuseki_dockerfile_matches_ontology_to_lpg(self):
        # Each skill installs on its own, so each keeps a copy; the two must not drift.
        other = os.path.join(SKILL, "..", "ontology-to-lpg", "docker", "fuseki", "Dockerfile")
        if not os.path.exists(other):
            self.skipTest("ontology-to-lpg is not beside this skill")
        with open(os.path.join(SKILL, "docker", "fuseki", "Dockerfile")) as a, open(other) as b:
            self.assertEqual(a.read(), b.read())


@unittest.skipUnless(os.environ.get("RDF_STORE_LIVE_FUSEKI"), "set RDF_STORE_LIVE_FUSEKI to a Fuseki dataset URL")
class LiveFuseki(unittest.TestCase):
    def test_round_trip(self):
        base = os.environ["RDF_STORE_LIVE_FUSEKI"].rstrip("/")
        passed, report = rs.roundtrip(rs.FusekiStore(base + "/data", base + "/query"), release_dataset())
        self.assertTrue(passed, report)


@unittest.skipUnless(os.environ.get("RDF_STORE_LIVE_DATABRICKS"), "set RDF_STORE_LIVE_DATABRICKS to an env file")
class LiveDatabricks(unittest.TestCase):
    def test_round_trip(self):
        store = rs.DatabricksStore.from_env(os.environ["RDF_STORE_LIVE_DATABRICKS"], "rdf_store_test")
        passed, report = rs.roundtrip(store, release_dataset())
        self.assertTrue(passed, report)


if __name__ == "__main__":
    unittest.main()
