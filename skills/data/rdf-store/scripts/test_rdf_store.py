#!/usr/bin/env python3
"""Tests for rdfstore.py. None needs Docker or Databricks: the Graph Store Protocol runs against a
small HTTP server in this process backed by a pyoxigraph Store that executes the SPARQL it receives,
and the Delta table against a fake connection that decodes the SQL rdfstore.py sends and keeps one
row list per table. Each planted fault must fail the round trip, with the diff in the right direction.

Live tests run only when asked: RDF_STORE_LIVE_FUSEKI=<base URL of a Fuseki dataset, such as
http://127.0.0.1:13031/ds> and RDF_STORE_LIVE_DATABRICKS=<env file>.

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
lib:loanDays a owl:DatatypeProperty ; lib:defaultValue "21"^^xsd:integer ; lib:note "plain" ; lib:seeAlso lib:Loan .
lib:Loan lib:hasPart _:b0, _:b1 .
_:b0 a lib:Clause ; skos:prefLabel "Return clause"@en .
_:b1 a lib:Clause ; skos:prefLabel "Renewal clause"@en .
"""
CATALOG = """@prefix owl: <http://www.w3.org/2002/07/owl#> .
<https://example.org/catalog> a owl:Ontology ; owl:versionIRI <https://example.org/catalog/2.1.0> .
<https://example.org/catalog/item> <https://example.org/library/title> "Catalog" .
<https://example.org/catalog/item> <https://example.org/library/part> _:b0 .
_:b0 <https://example.org/library/title> "Index" .
"""
G_LIB = ox.NamedNode("https://example.org/library/1.0.0")
G_CAT = ox.NamedNode("https://example.org/catalog/2.1.0")


def write(folder, name, text):
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def release_files():
    folder = tempfile.mkdtemp()
    return folder, [write(folder, "library.ttl", LIBRARY), write(folder, "catalog.ttl", CATALOG)]


def release_dataset():
    return rs.pack(release_files()[1])


# ---- faults a store could make -----------------------------------------------------------

def find(dataset, predicate_suffix, graph=G_LIB):
    return next(q for q in dataset if q.predicate.value.endswith(predicate_suffix) and q.graph_name == graph)


def replace(ds, q, obj=None, graph=None):
    ds.remove(q)
    ds.add(ox.Quad(q.subject, q.predicate, obj if obj is not None else q.object, graph or q.graph_name))


def lose_a_triple(ds):
    ds.remove(find(ds, "defaultValue"))


def add_a_triple(ds):
    ds.add(ox.Quad(ox.NamedNode("https://example.org/x"), ox.NamedNode("https://example.org/p"), ox.Literal("new"), G_LIB))


def change_a_literal(ds):
    replace(ds, find(ds, "note"), ox.Literal("plain "))


def change_a_datatype(ds):
    replace(ds, find(ds, "defaultValue"), ox.Literal("21", datatype=ox.NamedNode("http://www.w3.org/2001/XMLSchema#string")))


def change_a_language_tag(ds):
    q = next(q for q in ds if isinstance(q.object, ox.Literal) and q.object.language == "fr")
    replace(ds, q, ox.Literal(q.object.value, language="en"))


def change_an_object_kind(ds):
    q = find(ds, "seeAlso")
    replace(ds, q, ox.Literal(q.object.value))


def merge_two_blank_nodes(ds):
    """The two clauses in the library graph become one node."""
    keep, gone = sorted({q.object for q in ds if q.predicate.value.endswith("hasPart")}, key=str)
    for q in [q for q in ds if gone in (q.subject, q.object)]:
        ds.remove(q)
        ds.add(ox.Quad(keep if q.subject == gone else q.subject, q.predicate, keep if q.object == gone else q.object, q.graph_name))


def move_to_the_wrong_graph(ds):
    replace(ds, find(ds, "title", G_CAT), graph=G_LIB)


# (fault, quads missing, quads extra) as the diff must report them.
FAULTS = [(lose_a_triple, 1, 0), (add_a_triple, 0, 1), (change_a_literal, 1, 1), (change_a_datatype, 1, 1),
          (change_a_language_tag, 1, 1), (change_an_object_kind, 1, 1), (move_to_the_wrong_graph, 1, 1)]


# ---- a Graph Store Protocol server in this process ---------------------------------------

class GspHandler(http.server.BaseHTTPRequestHandler):
    store = None       # pyoxigraph.Store, set per server
    fault = None       # applied to what GET and the graph query see, to plant a store's mistake
    fail_put = None    # the PUT number (1-based) that answers 500
    fail_update = False
    fail_update_after_first = False   # applies the first operation, then answers 500
    requests = None    # list of (method, query string)

    def log_message(self, *args):
        pass

    def _graph(self):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query, keep_blank_values=True)
        return ox.DefaultGraph() if "default" in query else ox.NamedNode(query["graph"][0])

    def _send(self, code, body=b"", ctype="text/plain"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _view(self):
        whole = ox.Dataset(self.store)
        if self.fault:
            self.fault(whole)
        return whole

    def do_PUT(self):
        self.requests.append(("PUT", self.path))
        data = self.rfile.read(int(self.headers["Content-Length"]))
        if self.fail_put and sum(m == "PUT" for m, _ in self.requests) == self.fail_put:
            return self._send(500, b"store failed")
        g = self._graph()
        self.store.remove_graph(g) if isinstance(g, ox.NamedNode) and g in list(self.store.named_graphs()) else None
        for t in ox.parse(data, format=ox.RdfFormat.N_TRIPLES):
            self.store.add(ox.Quad(t.subject, t.predicate, t.object, g))
        self._send(201)

    def do_DELETE(self):
        self.requests.append(("DELETE", self.path))
        g = self._graph()
        if g not in list(self.store.named_graphs()):
            return self._send(404)
        self.store.remove_graph(g)
        self._send(204)

    def do_GET(self):
        self.requests.append(("GET", self.path))
        g = self._graph()
        ds = ox.Dataset(q for q in self._view() if q.graph_name == g)
        self._send(200, rs.nt_bytes(ds, g), "application/n-triples")

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"])).decode()
        if self.headers["Content-Type"] == "application/sparql-update":
            self.requests.append(("UPDATE", ""))
            if self.fail_update:
                return self._send(500, b"update failed")
            if self.fail_update_after_first:
                self.store.update(body.split(" ;\n")[0])
                return self._send(500, b"update failed part way")
            self.store.update(body)   # pyoxigraph applies one update request as one transaction
            return self._send(204)
        self.requests.append(("QUERY", ""))
        view = ox.Store()
        for q in self._view():
            view.add(q)
        rows = view.query(urllib.parse.parse_qs(body)["query"][0])
        out = {"results": {"bindings": [{"g": {"type": "uri", "value": r["g"].value}} for r in rows]}}
        self._send(200, json.dumps(out).encode(), "application/sparql-results+json")


def gsp_server(fault=None, update=False, **flags):
    attrs = {"store": ox.Store(), "fault": staticmethod(fault) if fault else None, "requests": [], **flags}
    handler = type("H", (GspHandler,), attrs)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    server.handler = handler
    return server, rs.FusekiStore(base + "/ds/data", base + "/ds/query", base + "/ds/update" if update else None)


def close(server):
    server.shutdown()
    server.server_close()


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
        if self.db.fail_on and self.db.fail_on(sql, len(self.db.statements)):
            raise RuntimeError(f"warehouse error while running statement {len(self.db.statements)}")
        m = re.match(r"CREATE OR REPLACE TABLE (\S+) AS SELECT \* FROM (\S+)$", sql)
        if m:
            self.db.tables[m.group(1)] = list(self.db.tables[m.group(2)])
            return
        m = re.match(r"CREATE OR REPLACE TABLE (\S+) \((.*?)\) USING DELTA", sql)
        if m:
            assert [c.split()[0] for c in m.group(2).split(", ")] == list(rs.COLUMNS), m.group(2)
            self.db.tables[m.group(1)] = []
            return
        m = re.match(r"DROP TABLE IF EXISTS (\S+)$", sql)
        if m:
            self.db.tables.pop(m.group(1), None)
            return
        m = re.match(r"INSERT INTO (\S+) \((.*?)\)\n", sql)
        if m:
            assert m.group(2).split(", ") == list(rs.COLUMNS), m.group(2)
            body = sql.split("FROM VALUES\n", 1)[1].rsplit("\nAS v(", 1)[0]
            for line in body.split(",\n"):
                cells = re.findall(r"NULL|'[A-Za-z0-9+/=]*'", line)
                assert len(cells) == len(rs.COLUMNS), line
                self.db.tables[m.group(1)].append(tuple(None if c == "NULL" else base64.b64decode(c[1:-1]).decode("utf-8") for c in cells))
            return
        m = re.match(r"SELECT (.*?) FROM (\S+)$", sql)
        if m:
            assert m.group(1).split(", ") == list(rs.COLUMNS), m.group(1)
            rows = list(self.db.tables[m.group(2)])
            if self.db.fault and (self.db.fault_table is None or self.db.fault_table == m.group(2)):
                ds = rs.from_rows(rows)
                self.db.fault(ds)
                rows = rs.to_rows(ds)
            self.result = rows
            return
        raise AssertionError(sql)

    def fetchall(self):
        return self.result


class FakeConnection:
    def __init__(self, fault=None, fault_table=None, fail_on=None, tables=None):
        self.tables, self.statements = dict(tables or {}), []
        self.fault, self.fault_table, self.fail_on = fault, fault_table, fail_on

    def cursor(self):
        return FakeCursor(self)


OLD_ROWS = [("https://example.org/old", "https://example.org/p", "old", "literal", rs.XSD_STRING, None, "https://example.org/g")]


# ---- the tests ---------------------------------------------------------------------------

class CanonicalHash(unittest.TestCase):
    def test_the_hash_ignores_blank_node_labels_and_order(self):
        a = ox.Dataset(ox.parse(b'_:x <http://p> "v" <http://g> .\n_:x <http://q> _:y <http://g> .\n', format=ox.RdfFormat.N_QUADS))
        b = ox.Dataset(ox.parse(b'_:k <http://q> _:m <http://g> .\n_:k <http://p> "v" <http://g> .\n', format=ox.RdfFormat.N_QUADS))
        self.assertEqual(rs.dataset_hash(a), rs.dataset_hash(b))

    def test_the_canonical_form_matches_w3c_blank_node_cases(self):
        with open(os.path.join(HERE, "testdata", "rdfc10-cases.json"), encoding="utf-8") as f:
            cases = json.load(f)["cases"]
        self.assertEqual(sorted(cases), ["016", "017", "044"])
        for name, case in cases.items():
            with self.subTest(name):
                ds = ox.Dataset(ox.parse(case["input"].encode(), format=ox.RdfFormat.N_QUADS))
                self.assertIn("_:", case["input"])
                self.assertEqual("".join(rs.canonical_lines(ds)), case["expected"])

    def test_every_fault_fails_with_the_diff_in_the_right_direction(self):
        clean = release_dataset()
        for fault, missing, extra in FAULTS + [(merge_two_blank_nodes, None, None)]:
            with self.subTest(fault.__name__):
                ds = release_dataset()
                fault(ds)
                passed, report = rs.compare(clean, ds)
                self.assertFalse(passed)
                if missing is not None:
                    self.assertEqual((report["missing"], report["extra"]), (missing, extra))

    def test_counts_can_match_while_the_hash_does_not(self):
        clean, changed = release_dataset(), release_dataset()
        change_a_literal(changed)
        passed, report = rs.compare(clean, changed)
        self.assertFalse(passed)
        self.assertEqual(report["predicate_counts_differ"], {})

    def test_a_failed_compare_canonicalizes_each_side_once(self):
        calls = []
        real = rs.canonical_lines
        rs.canonical_lines = lambda d: calls.append(1) or real(d)
        try:
            changed = release_dataset()
            change_a_literal(changed)
            rs.compare(release_dataset(), changed)
        finally:
            rs.canonical_lines = real
        self.assertEqual(len(calls), 2)


class Packing(unittest.TestCase):
    def test_each_file_is_its_own_graph_named_by_its_version_iri(self):
        self.assertEqual(sorted(rs.counts(release_dataset())[0]), [G_CAT.value, G_LIB.value])

    def test_blank_nodes_from_two_files_stay_apart(self):
        ds = release_dataset()
        blanks = {n for q in ds for n in (q.subject, q.object) if isinstance(n, ox.BlankNode)}
        self.assertEqual(len(blanks), 3)

    def test_a_file_without_an_ontology_header_needs_a_graph_name(self):
        folder = tempfile.mkdtemp()
        path = write(folder, "shapes.ttl", "<https://example.org/s> <https://example.org/p> 1 .\n")
        with self.assertRaises(rs.BadInput):
            rs.pack([path])
        ds = rs.pack([path], rs.parse_graph_options([f"{path}=https://example.org/shapes/1.0.0"], [path]))
        self.assertEqual(list(rs.counts(ds)[0]), ["https://example.org/shapes/1.0.0"])

    def test_a_repeated_version_iri_still_names_the_graph(self):
        folder = tempfile.mkdtemp()
        path = write(folder, "lib.ttl", LIBRARY + "<https://example.org/library> <http://www.w3.org/2002/07/owl#versionIRI> <https://example.org/library/1.0.0> .\n")
        self.assertEqual(list(rs.counts(rs.pack([path]))[0]), [G_LIB.value])

    def test_two_different_version_iris_are_refused(self):
        folder = tempfile.mkdtemp()
        path = write(folder, "lib.ttl", LIBRARY + "<https://example.org/library> <http://www.w3.org/2002/07/owl#versionIRI> <https://example.org/library/2.0.0> .\n")
        with self.assertRaises(rs.BadInput):
            rs.pack([path])

    def test_two_files_cannot_share_a_graph(self):
        folder = tempfile.mkdtemp()
        with self.assertRaises(rs.BadInput):
            rs.pack([write(folder, "a.ttl", LIBRARY), write(folder, "b.ttl", LIBRARY)])

    def test_n_quads_input_keeps_its_graphs(self):
        folder = tempfile.mkdtemp()
        path = write(folder, "d.nq", '<http://s> <http://p> "v" <http://g1> .\n_:b <http://p> "w" <http://g2> .\n')
        self.assertEqual(sorted(rs.counts(rs.pack([path]))[0]), ["http://g1", "http://g2"])

    def test_n_quads_with_a_default_graph_quad_is_refused(self):
        folder = tempfile.mkdtemp()
        path = write(folder, "d.nq", '<http://s> <http://p> "v" .\n')
        with self.assertRaises(rs.BadInput):
            rs.pack([path])

    def test_a_graph_option_must_name_an_input(self):
        folder, files = release_files()
        with self.assertRaises(rs.BadInput):
            rs.parse_graph_options([os.path.join(folder, "other.ttl") + "=https://example.org/x"], files)


class Skolemize(unittest.TestCase):
    def test_blank_nodes_become_stable_genid_iris(self):
        folder = tempfile.mkdtemp()
        path = write(folder, "library.ttl", LIBRARY)
        first = rs.skolemize(rs.read_quads(path), G_LIB.value, "https://example.org")
        again = rs.skolemize(list(reversed(rs.read_quads(path))), G_LIB.value, "https://example.org/")
        self.assertEqual(sorted(map(str, first)), sorted(map(str, again)))
        self.assertFalse(any(isinstance(t.subject, ox.BlankNode) or isinstance(t.object, ox.BlankNode) for t in first))
        self.assertTrue(any("/.well-known/genid/" in t.subject.value for t in first))

    def test_the_same_blank_node_shape_in_another_graph_gets_another_iri(self):
        folder = tempfile.mkdtemp()
        quads = rs.read_quads(write(folder, "library.ttl", LIBRARY))
        a = {t.subject.value for t in rs.skolemize(quads, "https://example.org/a", "https://example.org") if "genid" in t.subject.value}
        b = {t.subject.value for t in rs.skolemize(quads, "https://example.org/b", "https://example.org") if "genid" in t.subject.value}
        self.assertNotEqual(a, b)

    def test_a_skolem_iri_already_in_the_input_is_refused(self):
        folder = tempfile.mkdtemp()
        quads = rs.read_quads(write(folder, "library.ttl", LIBRARY))
        minted = next(t.subject.value for t in rs.skolemize(quads, G_LIB.value, "https://example.org") if "genid" in t.subject.value)
        clash = write(folder, "clash.ttl", LIBRARY + f"<{minted}> <https://example.org/p> \"named\" .\n")
        with self.assertRaises(rs.BadInput):
            rs.skolemize(rs.read_quads(clash), G_LIB.value, "https://example.org")


    def test_a_skolem_iri_already_used_as_a_datatype_is_refused(self):
        folder = tempfile.mkdtemp()
        quads = rs.read_quads(write(folder, "library.ttl", LIBRARY))
        minted = next(t.subject.value for t in rs.skolemize(quads, G_LIB.value, "https://example.org") if "genid" in t.subject.value)
        clash = write(folder, "clash.ttl", LIBRARY + f'<https://example.org/x> <https://example.org/p> "x"^^<{minted}> .\n')
        with self.assertRaises(rs.BadInput):
            rs.skolemize(rs.read_quads(clash), G_LIB.value, "https://example.org")

    def test_triple_terms_and_directional_literals_are_refused(self):
        folder = tempfile.mkdtemp()
        head = "<https://example.org/o> a <http://www.w3.org/2002/07/owl#Ontology> .\n"
        for name, body in (("triple term", "<http://s> <http://p> <<( <http://a> <http://b> _:b0 )>> .\n"),
                           ("direction", '<http://s> <http://p> "hi"@en--ltr .\n')):
            with self.subTest(name):
                path = write(folder, "t.ttl", head + body)
                with self.assertRaises(rs.BadInput):
                    rs.skolemize(rs.read_quads(path), "https://example.org/o", "https://example.org")


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
        self.assertFalse(any("DROP TABLE x" in s for s in conn.statements))

    def test_a_clean_round_trip_stages_then_replaces_the_table(self):
        conn = FakeConnection(tables={"c.s.t": OLD_ROWS})
        store = rs.DatabricksStore(conn, "c.s.t")
        store.BATCH = 3
        passed, report = rs.roundtrip(store, release_dataset())
        self.assertTrue(passed, report)
        self.assertGreater(sum(s.startswith(f"INSERT INTO {store.staging}") for s in conn.statements), 1)
        self.assertEqual(sorted(conn.tables), ["c.s.t"])
        self.assertEqual(rs.dataset_hash(rs.from_rows(conn.tables["c.s.t"])), rs.dataset_hash(release_dataset()))

    def test_a_failure_on_any_batch_leaves_the_previous_table(self):
        batches = -(-len(rs.to_rows(release_dataset())) // 4)
        self.assertGreater(batches, 3)
        for which, number in (("first", 1), ("middle", batches // 2), ("last", batches)):
            with self.subTest(which):
                count = {"n": 0}

                def fail(sql, _n, number=number):
                    if not sql.startswith("INSERT"):
                        return False
                    count["n"] += 1
                    return count["n"] == number
                conn = FakeConnection(fail_on=fail, tables={"c.s.t": OLD_ROWS})
                store = rs.DatabricksStore(conn, "c.s.t")
                store.BATCH = 4
                with self.assertRaises(RuntimeError):
                    rs.roundtrip(store, release_dataset())
                self.assertEqual(count["n"], number)
                self.assertEqual(conn.tables, {"c.s.t": OLD_ROWS})

    def test_a_failed_promotion_leaves_the_previous_table_and_drops_staging(self):
        conn = FakeConnection(fail_on=lambda sql, _n: " AS SELECT * FROM " in sql, tables={"c.s.t": OLD_ROWS})
        with self.assertRaises(RuntimeError):
            rs.roundtrip(rs.DatabricksStore(conn, "c.s.t"), release_dataset())
        self.assertEqual(conn.tables, {"c.s.t": OLD_ROWS})

    def test_a_failed_staging_drop_or_live_read_fails_the_run(self):
        for name, fail in (("drop", lambda sql, _n: sql.startswith("DROP TABLE")),
                           ("live read", lambda sql, _n: sql.startswith("SELECT") and "__staging_" not in sql)):
            with self.subTest(name):
                conn = FakeConnection(fail_on=fail, tables={"c.s.t": OLD_ROWS})
                with self.assertRaises(RuntimeError):
                    rs.roundtrip(rs.DatabricksStore(conn, "c.s.t"), release_dataset())

    def test_two_runs_on_one_table_never_promote_each_others_rows(self):
        conn = FakeConnection(tables={"c.s.t": OLD_ROWS})
        a, b = rs.DatabricksStore(conn, "c.s.t"), rs.DatabricksStore(conn, "c.s.t")
        self.assertNotEqual(a.staging, b.staging)
        mine, theirs = release_dataset(), release_dataset()
        add_a_triple(theirs)
        a.stage(rs.to_rows(mine))
        b.stage(rs.to_rows(theirs))      # B writes between A's check and A's promotion
        a.promote()
        self.assertEqual(rs.dataset_hash(rs.from_rows(conn.tables["c.s.t"])), rs.dataset_hash(mine))

    def test_a_successful_run_canonicalizes_three_times(self):
        calls = []
        real = rs.canonical_lines
        rs.canonical_lines = lambda d: calls.append(1) or real(d)
        try:
            passed, _ = rs.roundtrip(rs.DatabricksStore(FakeConnection(), "c.s.t"), release_dataset())
        finally:
            rs.canonical_lines = real
        self.assertTrue(passed)
        self.assertEqual(len(calls), 3)

    def test_a_staging_copy_that_differs_is_never_published(self):
        conn = FakeConnection(fault=change_a_literal, tables={"c.s.t": OLD_ROWS})
        store = rs.DatabricksStore(conn, "c.s.t")
        conn.fault_table = store.staging
        passed, report = rs.roundtrip(store, release_dataset())
        self.assertFalse(passed)
        self.assertFalse(report["published"])
        self.assertEqual(conn.tables, {"c.s.t": OLD_ROWS})

    def test_unsupported_terms_are_refused_before_any_statement(self):
        ds = ox.Dataset([ox.Quad(ox.NamedNode("http://s"), ox.NamedNode("http://p"),
                                 ox.Triple(ox.NamedNode("http://a"), ox.NamedNode("http://b"), ox.NamedNode("http://c")), ox.NamedNode("http://g"))])
        conn = FakeConnection(tables={"c.s.t": OLD_ROWS})
        with self.assertRaises(rs.BadInput):
            rs.roundtrip(rs.DatabricksStore(conn, "c.s.t"), ds)
        self.assertEqual(conn.statements, [])

    def test_each_fault_in_the_published_table_fails(self):
        for fault, _, _ in FAULTS:
            with self.subTest(fault.__name__):
                passed, _ = rs.roundtrip(rs.DatabricksStore(FakeConnection(fault, fault_table="c.s.t"), "c.s.t"), release_dataset())
                self.assertFalse(passed)


class GraphStoreProtocol(unittest.TestCase):
    def roundtrip(self, **kw):
        server, store = gsp_server(**kw)
        try:
            return (*rs.roundtrip(store, release_dataset()), server.handler)
        finally:
            close(server)

    def test_a_clean_round_trip_replaces_each_graph_with_one_put(self):
        server, store = gsp_server()
        try:
            server.handler.store.add(ox.Quad(ox.NamedNode("http://old"), ox.NamedNode("http://p"), ox.Literal("old"), G_LIB))
            passed, report = rs.roundtrip(store, release_dataset())
            handler = server.handler
        finally:
            close(server)
        self.assertTrue(passed, report)
        methods = [m for m, _ in handler.requests]
        self.assertEqual(methods.count("PUT"), 2)
        self.assertEqual(methods.count("DELETE"), 0)

    def test_the_update_endpoint_publishes_in_one_request(self):
        passed, report, handler = self.roundtrip(update=True)
        self.assertTrue(passed, report)
        self.assertEqual([m for m, _ in handler.requests].count("UPDATE"), 1)

    def test_a_failed_update_leaves_the_store_unchanged(self):
        server, store = gsp_server(update=True, fail_update=True)
        try:
            server.handler.store.add(ox.Quad(ox.NamedNode("http://s"), ox.NamedNode("http://p"), ox.Literal("old"), G_LIB))
            with self.assertRaises(Exception):
                rs.roundtrip(store, release_dataset())
            self.assertEqual([q.object.value for q in server.handler.store], ["old"])
        finally:
            close(server)

    def test_an_update_that_fails_part_way_fails_the_run(self):
        # SPARQL 1.1 Update only says a request SHOULD be atomic; a store that applies part of it and
        # then fails must end the run with an error, never a pass.
        server, store = gsp_server(update=True, fail_update_after_first=True)
        try:
            with self.assertRaises(Exception):
                rs.roundtrip(store, release_dataset())
        finally:
            close(server)

    def test_a_blank_node_in_two_graphs_is_refused_before_any_request(self):
        for update in (False, True):
            with self.subTest(update=update):
                server, store = gsp_server(update=update)
                ds = ox.Dataset([ox.Quad(ox.BlankNode("b"), ox.NamedNode("http://p"), ox.Literal(g), ox.NamedNode(g)) for g in ("http://g1", "http://g2")])
                try:
                    with self.assertRaises(rs.BadInput):
                        rs.roundtrip(store, ds)
                    self.assertEqual(server.handler.requests, [])
                finally:
                    close(server)

    def test_a_failed_put_stops_the_round_trip(self):
        server, store = gsp_server(fail_put=2)
        try:
            with self.assertRaises(Exception):
                rs.roundtrip(store, release_dataset())
        finally:
            close(server)

    def test_each_fault_fails_the_round_trip(self):
        for fault, missing, extra in FAULTS:
            with self.subTest(fault.__name__):
                passed, report, _ = self.roundtrip(fault=fault)
                self.assertFalse(passed)
                self.assertEqual((report["missing"], report["extra"]), (missing, extra))

    def test_a_store_that_merges_two_blank_nodes_in_a_graph_fails(self):
        passed, _, _ = self.roundtrip(fault=merge_two_blank_nodes)
        self.assertFalse(passed)

    def test_blank_nodes_with_one_label_in_two_graphs_export_as_two(self):
        server, store = gsp_server()
        try:
            for g in ("http://g1", "http://g2"):
                server.handler.store.add(ox.Quad(ox.BlankNode("b0"), ox.NamedNode("http://p"), ox.Literal(g), ox.NamedNode(g)))
            out = store.export()
        finally:
            close(server)
        self.assertEqual(len({q.subject for q in out}), 2)

    def test_a_graph_left_from_an_earlier_load_shows_as_extra(self):
        server, store = gsp_server()
        try:
            server.handler.store.add(ox.Quad(ox.NamedNode("http://s"), ox.NamedNode("http://p"), ox.Literal("old"), ox.NamedNode("http://stale")))
            passed, report = rs.roundtrip(store, release_dataset())
        finally:
            close(server)
        self.assertFalse(passed)
        self.assertEqual(report["graph_counts"]["http://stale"], [0, 1])

    def test_stale_default_graph_content_fails(self):
        server, store = gsp_server()
        try:
            server.handler.store.add(ox.Quad(ox.NamedNode("http://s"), ox.NamedNode("http://p"), ox.Literal("old"), ox.DefaultGraph()))
            passed, report = rs.roundtrip(store, release_dataset())
        finally:
            close(server)
        self.assertFalse(passed)
        self.assertEqual(report["graph_counts"]["(default graph)"], [0, 1])


class FakeDatabricks:
    """A fake databricks.sql package on PYTHONPATH, for the command-line tests."""

    @staticmethod
    def install(mode):
        folder = tempfile.mkdtemp()
        os.makedirs(os.path.join(folder, "databricks"))
        write(folder, os.path.join("databricks", "__init__.py"), "")
        write(folder, os.path.join("databricks", "sql.py"), textwrap_sql(mode))
        return folder


def textwrap_sql(mode):
    return f"""
MODE = {mode!r}
class Cursor:
    def __init__(self, token): self.token = token
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def execute(self, sql):
        if MODE == "fail-load" and sql.startswith("INSERT"):
            raise RuntimeError("warehouse said: bad token " + self.token)
    def fetchall(self): return []
class Connection:
    def __init__(self, token): self.token = token
    def cursor(self): return Cursor(self.token)
def connect(server_hostname, http_path, access_token):
    if MODE == "fail-connect":
        raise RuntimeError("could not connect with token " + access_token + " to " + server_hostname)
    return Connection(access_token)
"""


class CommandLine(unittest.TestCase):
    def run_cli(self, *args, env=None):
        return subprocess.run([sys.executable, os.path.join(HERE, "rdfstore.py"), *args], capture_output=True, text=True,
                              env={**os.environ, **(env or {})})

    def test_compare_exits_1_with_a_diff(self):
        folder, files = release_files()
        out = os.path.join(folder, "a.nq")
        self.assertEqual(self.run_cli("pack", "--out", out, files[0]).returncode, 0)
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

    def test_an_unknown_option_exits_2(self):
        folder, files = release_files()
        r = self.run_cli("pack", "--out", os.path.join(folder, "a.nq"), "--tabel", "x", *files)
        self.assertEqual(r.returncode, 2)
        self.assertFalse(os.path.exists(os.path.join(folder, "a.nq")))

    def test_a_graph_option_for_a_file_not_given_exits_2(self):
        folder, files = release_files()
        r = self.run_cli("pack", "--out", os.path.join(folder, "a.nq"), "--graph", "missing.ttl=https://example.org/x", *files)
        self.assertEqual(r.returncode, 2)

    def test_pack_reads_n_quads(self):
        folder, files = release_files()
        nq = os.path.join(folder, "a.nq")
        self.assertEqual(self.run_cli("pack", "--out", nq, *files).returncode, 0)
        again = os.path.join(folder, "b.nq")
        r = self.run_cli("pack", "--out", again, nq)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.run_cli("compare", nq, again).returncode, 0)

    def test_skolemize_refuses_a_directional_literal_and_writes_nothing(self):
        folder = tempfile.mkdtemp()
        path = write(folder, "t.ttl", '<https://example.org/o> a <http://www.w3.org/2002/07/owl#Ontology> .\n<http://s> <http://p> "hi"@en--ltr .\n')
        out = os.path.join(folder, "out")
        r = self.run_cli("skolemize", "--authority", "https://example.org", "--out", out, path)
        self.assertEqual(r.returncode, 2)
        self.assertFalse(os.path.exists(out))

    def test_skolemize_refuses_two_inputs_with_one_file_name(self):
        a, b = tempfile.mkdtemp(), tempfile.mkdtemp()
        one, two = write(a, "lib.ttl", LIBRARY), write(b, "lib.ttl", CATALOG)
        out = tempfile.mkdtemp()
        r = self.run_cli("skolemize", "--authority", "https://example.org", "--out", out, one, two)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(os.listdir(out), [])

    def test_skolemize_refuses_to_overwrite_its_input(self):
        folder, files = release_files()
        r = self.run_cli("skolemize", "--authority", "https://example.org", "--out", folder, files[0])
        self.assertEqual(r.returncode, 2)
        with open(files[0], encoding="utf-8") as f:
            self.assertEqual(f.read(), LIBRARY)

    def test_pack_refuses_to_overwrite_an_input(self):
        folder, files = release_files()
        self.assertEqual(self.run_cli("pack", "--out", files[0], *files).returncode, 2)

    def test_a_failed_rerun_removes_the_earlier_report(self):
        folder, files = release_files()
        report = os.path.join(folder, "report.json")
        write(folder, "report.json", '{"hashes_equal": true}')
        server, store = gsp_server(update=True, fail_update=True)
        try:
            r = self.run_cli("roundtrip", "--store", "fuseki", "--gsp", store.gsp, "--query", store.query_url,
                             "--update", store.update_url, "--report", report, *files)
        finally:
            close(server)
        self.assertEqual(r.returncode, 1)
        self.assertFalse(os.path.exists(report))
        self.assertEqual([f for f in os.listdir(folder) if f.startswith(".rdfstore.")], [])

    def test_an_option_error_also_removes_the_earlier_report(self):
        folder, files = release_files()
        report = os.path.join(folder, "report.json")
        for bad in (["--tabel", "x"], ["--store", "fuseki", "--store", "fuseki"], ["--gsp"]):
            with self.subTest(bad):
                write(folder, "report.json", '{"hashes_equal": true}')
                r = self.run_cli("roundtrip", "--report", report, *files, *bad)
                self.assertEqual(r.returncode, 2)
                self.assertFalse(os.path.exists(report))

    def test_a_report_folder_that_cannot_take_a_file_stops_before_the_store(self):
        folder, files = release_files()
        server, store = gsp_server(update=True)
        try:
            r = self.run_cli("roundtrip", "--store", "fuseki", "--gsp", store.gsp, "--query", store.query_url,
                             "--update", store.update_url, "--report", os.path.join(folder, "missing", "r.json"), *files)
            self.assertEqual(r.returncode, 2)
            self.assertEqual(server.handler.requests, [])
        finally:
            close(server)

    def test_n_quads_with_a_blank_graph_name_is_refused(self):
        folder = tempfile.mkdtemp()
        path = write(folder, "d.nq", '<http://s> <http://p> "v" _:g .\n')
        self.assertEqual(self.run_cli("pack", "--out", os.path.join(folder, "o.nq"), path).returncode, 2)

    def test_a_graph_option_through_a_link_to_n_quads_is_refused(self):
        folder = tempfile.mkdtemp()
        path = write(folder, "d.nq", '<http://s> <http://p> "v" <http://g> .\n')
        link = os.path.join(folder, "alias")
        os.symlink(path, link)
        out = os.path.join(folder, "o.nq")
        r = self.run_cli("pack", "--out", out, "--graph", f"{link}=https://example.org/x", path)
        self.assertEqual(r.returncode, 2)
        self.assertFalse(os.path.exists(out))

    def test_a_repeated_option_exits_2(self):
        folder, files = release_files()
        self.assertEqual(self.run_cli("pack", "--out", os.path.join(folder, "a.nq"), "--out", os.path.join(folder, "b.nq"), *files).returncode, 2)

    def test_pack_reads_n_triples(self):
        folder = tempfile.mkdtemp()
        path = write(folder, "g.nt", '<http://s> <http://p> "v" .\n')
        out = os.path.join(folder, "o.nq")
        self.assertEqual(self.run_cli("pack", "--out", out, "--graph", f"{path}=http://g", path).returncode, 0)
        with open(out) as f:
            self.assertEqual(f.read(), '<http://s> <http://p> "v" <http://g> .\n')

    def test_a_failed_write_leaves_no_temporary_file(self):
        folder = tempfile.mkdtemp()
        real = os.replace
        os.replace = lambda *a: (_ for _ in ()).throw(OSError("disk full"))
        try:
            with self.assertRaises(OSError):
                rs.write_atomically(os.path.join(folder, "out.nq"), b"x")
        finally:
            os.replace = real
        self.assertEqual(os.listdir(folder), [])

    def test_the_token_is_never_printed_when_the_env_file_is_incomplete(self):
        folder, files = release_files()
        env = write(folder, "db.env", "DATABRICKS_HOST=https://h\nDATABRICKS_TOKEN=dapiSECRET123\n")
        r = self.run_cli("roundtrip", "--store", "databricks", "--env", env, *files)
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("dapiSECRET123", r.stdout + r.stderr)

    def test_the_token_is_redacted_from_connector_errors(self):
        folder, files = release_files()
        env = write(folder, "db.env", "DATABRICKS_HOST=https://h\nDATABRICKS_TOKEN=dapiSECRET123\nDATABRICKS_HTTP_PATH=/sql/1.0/warehouses/x\n"
                                      "DATABRICKS_CATALOG=c\nDATABRICKS_SCHEMA=s\n")
        report = os.path.join(folder, "r.json")
        for mode in ("fail-connect", "fail-load"):
            with self.subTest(mode):
                fake = FakeDatabricks.install(mode)
                r = self.run_cli("roundtrip", "--store", "databricks", "--env", env, "--report", report, *files,
                                 env={"PYTHONPATH": fake})
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertNotIn("dapiSECRET123", r.stdout + r.stderr)
                self.assertIn("[redacted]", r.stdout)
                self.assertFalse(os.path.exists(report))

    def test_a_token_in_an_identifier_is_never_printed(self):
        folder, files = release_files()
        base = "DATABRICKS_HOST=https://h\nDATABRICKS_TOKEN=dapiSECRET123\nDATABRICKS_HTTP_PATH=/p\n"
        for name, env_text, extra in (
                ("catalog", base + "DATABRICKS_CATALOG=x-dapiSECRET123\nDATABRICKS_SCHEMA=s\n", []),
                ("schema", base + "DATABRICKS_CATALOG=c\nDATABRICKS_SCHEMA=x-dapiSECRET123\n", []),
                ("table", base + "DATABRICKS_CATALOG=c\nDATABRICKS_SCHEMA=s\n", ["--table", "x-dapiSECRET123"])):
            with self.subTest(name):
                env = write(folder, "db.env", env_text)
                r = self.run_cli("roundtrip", "--store", "databricks", "--env", env, *extra, *files)
                self.assertEqual(r.returncode, 2)
                self.assertNotIn("dapiSECRET123", r.stdout + r.stderr)

    def test_a_token_inside_the_data_is_redacted_from_a_mismatch(self):
        folder = tempfile.mkdtemp()
        data = write(folder, "lib.ttl", LIBRARY + '<https://example.org/x> <https://example.org/p> "dapiSECRET123" .\n')
        env = write(folder, "db.env", "DATABRICKS_HOST=https://h\nDATABRICKS_TOKEN=dapiSECRET123\nDATABRICKS_HTTP_PATH=/p\n"
                                      "DATABRICKS_CATALOG=c\nDATABRICKS_SCHEMA=s\n")
        report = os.path.join(folder, "r.json")
        r = self.run_cli("roundtrip", "--store", "databricks", "--env", env, "--report", report, data,
                         env={"PYTHONPATH": FakeDatabricks.install("empty")})
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        with open(report) as f:
            saved = f.read()
        self.assertIn("missing from the store", saved)
        self.assertNotIn("dapiSECRET123", r.stdout + r.stderr + saved)

    def test_export_refuses_an_output_that_a_side_file_would_overwrite(self):
        folder, files = release_files()
        server, store = gsp_server()
        try:
            store.publish(rs.pack(files))
            ttl = os.path.join(folder, "ttl")
            for out in (os.path.join(ttl, "graph-1.ttl"), os.path.join(ttl, "graphs.tsv")):
                with self.subTest(out=os.path.basename(out)):
                    r = self.run_cli("export", "--store", "fuseki", "--gsp", store.gsp, "--query", store.query_url,
                                     "--out", out, "--ttl-dir", ttl)
                    self.assertEqual(r.returncode, 2)
                    self.assertFalse(os.path.exists(ttl))
            os.makedirs(ttl)
            write(ttl, "graph-9.ttl", "old")
            r = self.run_cli("export", "--store", "fuseki", "--gsp", store.gsp, "--query", store.query_url,
                             "--out", os.path.join(folder, "x.nq"), "--ttl-dir", ttl)
            self.assertEqual(r.returncode, 2)
        finally:
            close(server)

    def test_a_failed_side_file_leaves_no_export_output(self):
        folder, files = release_files()
        server, store = gsp_server()
        real = rs.ox.serialize
        calls = {"turtle": 0}

        def serialize(data, *a, **kw):
            if kw.get("format") == rs.ox.RdfFormat.TURTLE:
                calls["turtle"] += 1
                if calls["turtle"] == 2:
                    raise OSError("disk full on the second Turtle file")
            return real(data, *a, **kw)
        try:
            store.publish(rs.pack(files))
            out, ttl = os.path.join(folder, "export.nq"), os.path.join(folder, "ttl")
            rs.ox.serialize = serialize
            code = rs.main(["export", "--store", "fuseki", "--gsp", store.gsp, "--query", store.query_url,
                            "--out", out, "--ttl-dir", ttl])
        finally:
            rs.ox.serialize = real
            close(server)
        self.assertEqual(code, 1)
        self.assertEqual(calls["turtle"], 2)
        self.assertFalse(os.path.exists(out))
        self.assertFalse(os.path.exists(ttl))
        self.assertEqual([f for f in os.listdir(folder) if f.startswith(".rdfstore.")], [])

    def test_a_failed_rename_removes_what_was_already_published(self):
        folder = tempfile.mkdtemp()
        real, count = os.replace, {"n": 0}

        def replace(src, dst):
            count["n"] += 1
            if count["n"] == 2:
                raise OSError("rename failed")
            real(src, dst)
        os.replace = replace
        try:
            with self.assertRaises(OSError):
                rs.publish_all([(os.path.join(folder, "a.nq"), lambda: b"a"), (os.path.join(folder, "b.ttl"), lambda: b"b")])
        finally:
            os.replace = real
        self.assertEqual(os.listdir(folder), [])

    def test_export_refuses_an_existing_output_file(self):
        folder = tempfile.mkdtemp()
        out = write(folder, "old.nq", "keep me\n")
        server, store = gsp_server()
        try:
            r = self.run_cli("export", "--store", "fuseki", "--gsp", store.gsp, "--query", store.query_url, "--out", out)
            requests = list(server.handler.requests)
        finally:
            close(server)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(requests, [])
        with open(out) as f:
            self.assertEqual(f.read(), "keep me\n")

    def test_export_takes_no_update_endpoint(self):
        folder = tempfile.mkdtemp()
        r = self.run_cli("export", "--store", "fuseki", "--gsp", "http://h/d", "--query", "http://h/q",
                         "--update", "http://h/u", "--out", os.path.join(folder, "x.nq"))
        self.assertEqual(r.returncode, 2)

    def test_export_writes_the_store_and_one_turtle_file_per_graph(self):
        folder, files = release_files()
        server, store = gsp_server()
        try:
            store.publish(rs.pack(files))
            out, ttl = os.path.join(folder, "export.nq"), os.path.join(folder, "ttl")
            r = self.run_cli("export", "--store", "fuseki", "--gsp", store.gsp, "--query", store.query_url,
                             "--out", out, "--ttl-dir", ttl)
        finally:
            close(server)
        self.assertEqual(r.returncode, 0, r.stderr)
        packed = os.path.join(folder, "packed.nq")
        self.run_cli("pack", "--out", packed, *files)
        self.assertEqual(self.run_cli("compare", packed, out).returncode, 0)
        with open(os.path.join(ttl, "graphs.tsv")) as f:
            index = [line.rstrip("\n").split("\t") for line in f]
        self.assertEqual(sorted(g for _, g in index), [G_CAT.value, G_LIB.value])
        rebuilt = rs.pack([os.path.join(ttl, n) for n, _ in index],
                          rs.parse_graph_options([f"{os.path.join(ttl, n)}={g}" for n, g in index], [os.path.join(ttl, n) for n, _ in index]))
        self.assertEqual(rs.dataset_hash(rebuilt), rs.dataset_hash(rs.pack(files)))


class FusekiImage(unittest.TestCase):
    def test_the_fuseki_build_steps_match_ontology_to_lpg(self):
        # Each skill installs on its own, so each keeps a copy; the build steps must not drift. The
        # leading comment block differs, since each names its own skill and compose file.
        other = os.path.join(SKILL, "..", "ontology-to-lpg", "docker", "fuseki", "Dockerfile")
        if not os.path.exists(other):
            self.skipTest("ontology-to-lpg is not beside this skill")

        def steps(path):
            with open(path) as f:
                lines = f.read().splitlines()
            return lines[next(i for i, line in enumerate(lines) if not line.startswith("#")):]
        self.assertEqual(steps(os.path.join(SKILL, "docker", "fuseki", "Dockerfile")), steps(other))


@unittest.skipUnless(os.environ.get("RDF_STORE_LIVE_FUSEKI"), "set RDF_STORE_LIVE_FUSEKI to a Fuseki dataset URL")
class LiveFuseki(unittest.TestCase):
    def test_round_trip(self):
        base = os.environ["RDF_STORE_LIVE_FUSEKI"].rstrip("/")
        passed, report = rs.roundtrip(rs.FusekiStore(base + "/data", base + "/query", base + "/update"), release_dataset())
        self.assertTrue(passed, report)


@unittest.skipUnless(os.environ.get("RDF_STORE_LIVE_DATABRICKS"), "set RDF_STORE_LIVE_DATABRICKS to an env file")
class LiveDatabricks(unittest.TestCase):
    def test_round_trip(self):
        env = rs.DatabricksStore.check_env(os.environ["RDF_STORE_LIVE_DATABRICKS"], "rdf_store_test")
        passed, report = rs.roundtrip(rs.DatabricksStore.from_env(env, "rdf_store_test"), release_dataset())
        self.assertTrue(passed, report)


if __name__ == "__main__":
    unittest.main()
