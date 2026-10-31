"""Tests for module_tags.py and explore.py (add-on F), with no database or store.

Run from this folder:
  uv run --no-project --with rdflib python3 -m unittest test_explore

The store side runs explore.py's real SPARQL on an rdflib Dataset holding the fixture packages, one
named graph each. The Neo4j side is a fake session that answers explore.py's and module_tags.py's
Cypher from the same packages as n10s would hold them (SHORTEN names, rdf:type as relationships), with
the `graph` tags module_tags.py would set. So a walk that agrees here agrees because the two query
paths read the same graph the same way; the live comparison is references/add-ons.md, add-on F.
"""
import os
import sys
import tempfile
import unittest

from rdflib import Dataset, Graph, URIRef

import explore
import load_verify as lv
import module_tags as mt

PREFIXES = {"base": "https://example.org/base/", "app": "https://example.org/app/",
            "owl": "http://www.w3.org/2002/07/owl#", "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
            "dcterms": "http://purl.org/dc/terms/", "skos": "http://www.w3.org/2004/02/skos/core#"}

BASE = """@prefix base: <https://example.org/base/> . @prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
<https://example.org/base> a owl:Ontology ; owl:versionIRI <https://example.org/base/1.1.0> .
base:p1 a skos:Concept ; skos:broader base:p0 .
base:p0 a skos:Concept .
base:shared a skos:Concept .
"""
APP = """@prefix base: <https://example.org/base/> . @prefix app: <https://example.org/app/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> . @prefix dcterms: <http://purl.org/dc/terms/> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
<https://example.org/app> a owl:Ontology ; owl:versionIRI <https://example.org/app/2.0.0> ;
    dcterms:requires <https://example.org/base/1.0.0> .
app:sys a skos:Concept ; app:supports base:p1 .
base:shared a skos:Concept .
base:p1 skos:broader base:p0 .
"""


def write(folder, name, text):
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def shorten(iri, sep=mt.SEP):
    for prefix, ns in PREFIXES.items():
        if iri.startswith(ns):
            return f"{prefix}{sep}{iri[len(ns):]}"
    raise ValueError(iri)


SCHEMA_EDGES = 2   # the n4sch__ relationships FakeNeo4j adds, beyond the package triples


class FakeNeo4j:
    """Answers the Cypher statements explore.py and module_tags.py send, from an edge list. sep is the
    separator the graph was loaded with: n10s's, or the one load_verify.py renamed the names to."""

    def __init__(self, packages, wrong=None, sep=mt.SEP):
        nodes, edges = mt.expected_tags(packages)
        self.sep = sep
        self.nodes = dict(nodes)
        self.edges = [(s, shorten(p, sep), o, t) for (s, p, o), t in edges.items()]
        if wrong:
            self.nodes[wrong] = "https://example.org/wrong/0.0.0"
        # Schema relationships n10s.onto.import writes, tagged by the node they start from; one points at a
        # node standing for a restriction filler, repeating no single triple.
        for s, t, o in (("https://example.org/base/p1", "n4sch" + sep + "EQC", "https://example.org/base/p0"),
                        ("https://example.org/base/p1", "n4sch" + sep + "SCO_RESTRICTION", "https://example.org/base/shared")):
            self.edges.append((s, t, o, self.nodes.get(s)))
        self.mods, self.reqs = mt.module_rows(packages)
        self.set_calls = 0

    def __call__(self, stmt, **params):
        if stmt in (explore.CY_EDGES, explore.cy_edges(self.sep)):   # it leaves out n10s's schema relationships
            schema = mt.schema_prefix(self.sep if stmt == explore.cy_edges(self.sep) else None)
            f = set(params["frontier"])
            return [{"s": s, "t": t, "o": o, "g": g} for s, t, o, g in self.edges
                    if (s in f or o in f) and not t.startswith(schema)]
        if stmt == explore.CY_NODES:
            return [{"uri": u, "g": self.nodes[u]} for u in params["uris"] if u in self.nodes]
        if stmt == explore.CY_MODULES:
            return [{"source": r["source"], "target": r["target"], "pin": r["pin"]} for r in self.reqs]
        if stmt == mt.NODES:
            return [{"uri": u, "tag": t} for u, t in self.nodes.items()]
        if stmt == mt.EDGES:
            return [{"s": s, "t": t, "o": o, "tag": g} for s, t, o, g in self.edges]
        if stmt in (mt.SET_NODES, mt.SET_EDGES):
            self.set_calls += 1
            return []
        raise AssertionError(f"unexpected statement: {stmt}")


def store(packages):
    ds = Dataset(default_union=False)
    for p in packages:
        g = ds.graph(URIRef(p.version))
        for t in p.graph:
            g.add(t)

    def select(query):
        return [{str(k): str(v) for k, v in row.asdict().items()} for row in ds.query(query)]
    return explore.StoreSide(select)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        app = write(self.tmp, "app.ttl", APP)
        base = write(self.tmp, "base.ttl", BASE)
        self.packages = mt.read_packages([app, base])   # given out of order on purpose


class ModuleTags(Fixture):
    def test_requirements_come_first(self):
        self.assertEqual([p.version for p in self.packages],
                         ["https://example.org/base/1.1.0", "https://example.org/app/2.0.0"])

    def test_a_node_takes_its_typing_package_then_its_own_namespace_then_the_earliest(self):
        nodes, _ = mt.expected_tags(self.packages)
        self.assertEqual(nodes["https://example.org/app/sys"], "https://example.org/app/2.0.0")
        # typed in both packages; base's namespace starts it, so base wins
        self.assertEqual(nodes["https://example.org/base/shared"], "https://example.org/base/1.1.0")
        # only mentioned (never typed) in app: its pin target is tagged by app, the one package naming it
        self.assertEqual(nodes["https://example.org/base/1.0.0"], "https://example.org/app/2.0.0")

    def test_an_edge_takes_the_earliest_package_holding_it(self):
        _, edges = mt.expected_tags(self.packages)
        broader = ("https://example.org/base/p1", PREFIXES["skos"] + "broader", "https://example.org/base/p0")
        self.assertEqual(edges[broader], "https://example.org/base/1.1.0")

    def test_an_inferred_triple_takes_its_subjects_tag(self):
        inferred = Graph()
        inferred.add((URIRef("https://example.org/app/sys"), URIRef(PREFIXES["rdf"] + "type"),
                      URIRef("https://example.org/base/Thing")))
        _, edges = mt.expected_tags(self.packages, inferred)
        self.assertEqual(edges[("https://example.org/app/sys", PREFIXES["rdf"] + "type", "https://example.org/base/Thing")],
                         "https://example.org/app/2.0.0")

    def test_a_cycle_refuses(self):
        a = write(self.tmp, "a.ttl", BASE.replace("versionIRI <https://example.org/base/1.1.0> .",
                                                  "versionIRI <https://example.org/base/1.1.0> ; "
                                                  "<http://purl.org/dc/terms/requires> <https://example.org/app/2.0.0> ."))
        with self.assertRaisesRegex(ValueError, "cycle"):
            mt.read_packages([a, os.path.join(self.tmp, "app.ttl")])

    def test_schema_types_and_prefixes_map_to_predicates(self):
        for schema in ("n4sch__DOMAIN", "n4sch__SPO", "n4sch__EQC", "n4sch__SCO_RESTRICTION"):
            self.assertIsNone(mt.predicate(schema, PREFIXES))   # schema: tagged by its start node instead
        self.assertEqual(mt.predicate("skos__broader", PREFIXES), PREFIXES["skos"] + "broader")
        self.assertIsNone(mt.predicate("nope__x", PREFIXES))

    def test_a_renamed_graphs_types_map_only_under_its_separator(self):
        self.assertEqual(mt.predicate("skos_broader", PREFIXES, "_"), PREFIXES["skos"] + "broader")
        self.assertEqual(mt.predicate("skos_SCO_RESTRICTION", PREFIXES, "_"), PREFIXES["skos"] + "SCO_RESTRICTION")
        self.assertIsNone(mt.predicate("n4sch_SCO_RESTRICTION", PREFIXES, "_"))
        self.assertIsNone(mt.predicate("skos_broader", PREFIXES))               # read with n10s's separator
        self.assertEqual(mt.schema_prefix("_"), "n4sch_")
        self.assertEqual(mt.schema_prefix(), mt.SCHEMA_PREFIX)
        self.assertIn("STARTS WITH 'n4sch_' ", explore.cy_edges("_"))
        self.assertEqual(explore.cy_edges(), explore.CY_EDGES)

    def test_tag_and_check_read_a_renamed_graph_under_its_separator(self):
        nodes, edges = mt.expected_tags(self.packages)
        fake = FakeNeo4j(self.packages, sep="_")
        self.assertEqual(mt.tag(fake, nodes, edges, PREFIXES, sep="_"), (len(nodes), len(edges) + SCHEMA_EDGES, 0, 0))
        read_nodes, read_edges, problems = mt.check(fake, nodes, edges, PREFIXES, sep="_")
        self.assertEqual((read_nodes, read_edges), (len(nodes), len(edges) + SCHEMA_EDGES))
        self.assertEqual({k: v for k, v in problems.items() if v}, {})
        # read with n10s's separator, no type expands and every edge is unstated
        _, _, problems = mt.check(fake, nodes, edges, PREFIXES)
        self.assertEqual(len(problems["not_in_packages"]), len(edges) + SCHEMA_EDGES)
        self.assertEqual(mt.tag(FakeNeo4j(self.packages, sep="_"), nodes, edges, PREFIXES)[3], len(edges) + SCHEMA_EDGES)

    def test_a_prefix_holding_the_separator_stops_the_tag_check_and_walk_commands_before_any_query(self):
        import json
        import build
        config = write(self.tmp, "config.json", json.dumps({
            "rule4": "4a", "rule4_reason": "test", "own_namespaces": ["https://example.org/base/"],
            "prefixes": {**PREFIXES, "my_ns": "https://example.org/my-ns/"}}))
        with self.assertRaises(build.Refusal):
            build.check_prefixes(build.load_config(config).prefixes, "_")
        from unittest import mock
        import contextlib
        import io
        for main, argv in ((mt.main, ["check", "--config", config, "--uri", "bolt://h", "--separator", "_",
                                      os.path.join(self.tmp, "base.ttl")]),
                           (explore.main, ["walk", "--config", config, "--uri", "bolt://h", "--sparql", "http://h/q",
                                           "--iri", "https://example.org/base/p1", "--separator", "_"])):
            with self.subTest(main=main.__module__), mock.patch.dict(os.environ, {"NEO4J_PASSWORD": "pw"}), \
                    mock.patch.dict(sys.modules, {"neo4j": mock.MagicMock()}) as modules, \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(main(argv), 2)
                modules["neo4j"].GraphDatabase.driver.assert_not_called()
            self.assertIn("inside 1 of the configured prefixes", err.getvalue())
            self.assertNotIn("my_ns", err.getvalue())

    def test_check_passes_on_a_correctly_tagged_graph(self):
        nodes, edges = mt.expected_tags(self.packages)
        read_nodes, read_edges, problems = mt.check(FakeNeo4j(self.packages), nodes, edges, PREFIXES)
        self.assertEqual((read_nodes, read_edges), (len(nodes), len(edges) + SCHEMA_EDGES))
        self.assertEqual({k: v for k, v in problems.items() if v}, {})

    def test_a_schema_relationship_takes_its_start_nodes_tag(self):
        nodes, edges = mt.expected_tags(self.packages)
        fake = FakeNeo4j(self.packages)
        _, _, problems = mt.check(fake, nodes, edges, PREFIXES)
        self.assertEqual({k: v for k, v in problems.items() if v}, {})
        fake.edges = [(s, t, o, "https://example.org/app/2.0.0" if t == "n4sch__EQC" else g) for s, t, o, g in fake.edges]
        _, _, problems = mt.check(fake, nodes, edges, PREFIXES)
        self.assertEqual(problems["wrong_tag"],
                         ["https://example.org/base/p1 n4sch__EQC https://example.org/base/p0"])

    def test_check_finds_a_wrong_tag(self):
        nodes, edges = mt.expected_tags(self.packages)
        _, _, problems = mt.check(FakeNeo4j(self.packages, wrong="https://example.org/base/p0"), nodes, edges, PREFIXES)
        self.assertEqual(problems["wrong_tag"], ["https://example.org/base/p0"])

    def test_check_finds_an_untagged_node_and_a_missing_edge(self):
        nodes, edges = mt.expected_tags(self.packages)
        fake = FakeNeo4j(self.packages)
        fake.nodes["https://example.org/base/p0"] = None
        fake.edges = [e for e in fake.edges if e[1] != "app__supports"]
        _, _, problems = mt.check(fake, nodes, edges, PREFIXES)
        self.assertEqual(problems["untagged"], ["https://example.org/base/p0"])
        self.assertEqual(problems["missing_from_graph"],
                         ["https://example.org/app/sys https://example.org/app/supports https://example.org/base/p1"])

    def test_check_finds_two_relationships_with_the_same_ends_and_type(self):
        nodes, edges = mt.expected_tags(self.packages)
        fake = FakeNeo4j(self.packages)
        fake.edges.append(next(e for e in fake.edges if e[1] == "app__supports")[:3] + (None,))
        _, _, problems = mt.check(fake, nodes, edges, PREFIXES)
        self.assertEqual(problems["parallel"],
                         ["https://example.org/app/sys app__supports https://example.org/base/p1"])

    def test_check_finds_a_relationship_no_package_states(self):
        nodes, edges = mt.expected_tags(self.packages)
        fake = FakeNeo4j(self.packages)
        fake.edges.append(("https://example.org/base/p0", "skos__broader", "https://example.org/base/p1",
                           "https://example.org/base/1.1.0"))
        _, _, problems = mt.check(fake, nodes, edges, PREFIXES)
        self.assertEqual(len(problems["not_in_packages"]), 1)

    def test_tag_writes_both_kinds(self):
        nodes, edges = mt.expected_tags(self.packages)
        fake = FakeNeo4j(self.packages)
        self.assertEqual(mt.tag(fake, nodes, edges, PREFIXES), (len(nodes), len(edges) + SCHEMA_EDGES, 0, 0))
        self.assertEqual(fake.set_calls, 2)

    def test_the_module_graph_points_at_the_loaded_release_and_keeps_the_pin(self):
        mods, reqs = mt.module_rows(self.packages)
        self.assertEqual(len(mods), 2)
        self.assertEqual(reqs, [{"source": "https://example.org/app/2.0.0", "target": "https://example.org/base/1.1.0",
                                 "pin": "https://example.org/base/1.0.0"}])

    def test_two_pins_to_one_module_stay_two_requirements(self):
        two = write(self.tmp, "two.ttl", APP.replace("dcterms:requires <https://example.org/base/1.0.0> .",
                                                     "dcterms:requires <https://example.org/base/1.0.0>, "
                                                     "<https://example.org/base/1.1.0> ."))
        packages = mt.read_packages([two, os.path.join(self.tmp, "base.ttl")])
        fake = FakeNeo4j(packages)
        rows = explore.Neo4jSide(fake, PREFIXES).modules()
        self.assertEqual([r[2] for r in rows], ["https://example.org/base/1.0.0", "https://example.org/base/1.1.0"])
        self.assertEqual(rows, store(packages).modules())
        self.assertIn("MERGE (a)-[:REQUIRES {pin: r.pin}]->(b)", mt.REQUIRES)

    def test_an_exact_version_pin_is_a_requirement_in_both_forms(self):
        exact = write(self.tmp, "exact.ttl", APP.replace("<https://example.org/base/1.0.0>", "<https://example.org/base/1.1.0>"))
        packages = mt.read_packages([exact, os.path.join(self.tmp, "base.ttl")])
        ds = Dataset(default_union=False)
        for p in packages:
            g = ds.graph(URIRef(p.version))
            for t in p.graph:
                g.add(t)
        out = ds.query(mt.CONSTRUCT).graph
        self.assertEqual(len(list(out.subject_objects(URIRef(mt.LPG + "requires")))), len(mt.module_rows(packages)[1]))

    def test_the_construct_takes_the_longest_matching_ontology_as_modules_does(self):
        nested = write(self.tmp, "nested.ttl", BASE.replace("<https://example.org/base>", "<https://example.org/base/ext>")
                       .replace("<https://example.org/base/1.1.0>", "<https://example.org/base/ext/1.0.0>"))
        pin = APP.replace("<https://example.org/base/1.0.0>", "<https://example.org/base/ext/0.9.0>")
        app = write(self.tmp, "app2.ttl", pin)
        packages = mt.read_packages([app, os.path.join(self.tmp, "base.ttl"), nested])
        ds = Dataset(default_union=False)
        for p in packages:
            g = ds.graph(URIRef(p.version))
            for t in p.graph:
                g.add(t)
        out = ds.query(mt.CONSTRUCT).graph
        self.assertEqual({str(o) for o in out.objects(URIRef("https://example.org/app/2.0.0"), URIRef(mt.LPG + "requires"))},
                         {r["target"] for r in mt.module_rows(packages)[1]})
        self.assertEqual({r["target"] for r in mt.module_rows(packages)[1]}, {"https://example.org/base/ext/1.0.0"})

    def test_the_construct_gives_the_same_module_graph(self):
        ds = Dataset(default_union=False)
        for p in self.packages:
            g = ds.graph(URIRef(p.version))
            for t in p.graph:
                g.add(t)
        out = ds.query(mt.CONSTRUCT).graph
        lpgm = mt.LPG
        self.assertEqual(set(out.subject_objects(URIRef(lpgm + "requires"))),
                         {(URIRef("https://example.org/app/2.0.0"), URIRef("https://example.org/base/1.1.0"))})
        self.assertEqual(set(out.objects(None, URIRef(lpgm + "pin"))), {URIRef("https://example.org/base/1.0.0")})


class Walk(Fixture):
    def test_neo4j_and_the_store_give_the_same_walk(self):
        result = explore.compare_walk(explore.Neo4jSide(FakeNeo4j(self.packages), PREFIXES), store(self.packages),
                                      "https://example.org/app/sys", 2)
        self.assertTrue(result["equal"], result)

    def test_the_walk_rows_are_the_expected_ones(self):
        edges, nodes = explore.walk(store(self.packages), "https://example.org/app/sys", 1)
        sk, app, base = PREFIXES["skos"], "https://example.org/app/", "https://example.org/base/"
        # sorted as text: "http://" comes before "https://"
        self.assertEqual(edges, [[app + "sys", PREFIXES["rdf"] + "type", sk + "Concept", app + "2.0.0"],
                                 [app + "sys", app + "supports", base + "p1", app + "2.0.0"]])
        self.assertEqual([n[0] for n in nodes], [sk + "Concept", app + "sys", base + "p1"])

    def test_two_hops_reach_both_modules(self):
        edges, nodes = explore.walk(store(self.packages), "https://example.org/app/sys", 2)
        self.assertEqual(explore.modules_reached(edges, nodes),
                         ["https://example.org/app/2.0.0", "https://example.org/base/1.1.0"])

    def test_a_renamed_graph_walks_equal_only_under_its_separator(self):
        fake = FakeNeo4j(self.packages, sep="_")
        told = explore.compare_walk(explore.Neo4jSide(fake, PREFIXES, "_"), store(self.packages), "https://example.org/app/sys", 2)
        self.assertTrue(told["equal"], told)
        self.assertEqual(told["modules"], ["https://example.org/app/2.0.0", "https://example.org/base/1.1.0"])
        # read with n10s's separator: no type expands and the schema relationships are walked
        untold = explore.compare_walk(explore.Neo4jSide(fake, PREFIXES), store(self.packages), "https://example.org/app/sys", 2)
        self.assertFalse(untold["equal"])
        self.assertTrue(any(e[1] is None for e in untold["only_in_neo4j"]), untold)

    def test_a_wrong_tag_in_neo4j_makes_the_walks_differ(self):
        result = explore.compare_walk(
            explore.Neo4jSide(FakeNeo4j(self.packages, wrong="https://example.org/base/p1"), PREFIXES),
            store(self.packages), "https://example.org/app/sys", 1)
        self.assertFalse(result["equal"])

    def test_the_inferred_graph_takes_its_name_from_the_option_and_any_other_graph_shows(self):
        rdf_type = URIRef(PREFIXES["rdf"] + "type")
        extra = (URIRef("https://example.org/app/sys"), rdf_type, URIRef("https://example.org/base/Thing"))
        for name, tag in (("urn:x:inferred", "https://example.org/app/2.0.0"), ("urn:x:stray", None)):
            ds = Dataset(default_union=False)
            for p in self.packages:
                g = ds.graph(URIRef(p.version))
                for t in p.graph:
                    g.add(t)
            ds.graph(URIRef(name)).add(extra)
            side = explore.StoreSide(lambda q, ds=ds: [{str(k): str(v) for k, v in r.asdict().items()} for r in ds.query(q)],
                                     "urn:x:inferred")
            edges, _ = explore.walk(side, "https://example.org/app/sys", 1)
            self.assertIn([str(extra[0]), str(extra[1]), str(extra[2]), tag], edges, name)

    def test_an_inferred_triple_whose_subject_no_package_mentions_shows_with_no_tag(self):
        # The triple above is in no package (an inferred-only triple) and takes its subject's tag. A subject
        # only the inferred graph mentions has no package tag, so its triple is kept with none and shows.
        rdf_type = URIRef(PREFIXES["rdf"] + "type")
        orphan = (URIRef("https://example.org/base/p0"), rdf_type, URIRef("https://example.org/base/Thing"))
        lone = (URIRef("https://example.org/nowhere/x"), rdf_type, URIRef("https://example.org/base/p0"))
        ds = Dataset(default_union=False)
        for p in self.packages:
            g = ds.graph(URIRef(p.version))
            for t in p.graph:
                g.add(t)
        for t in (orphan, lone):
            ds.graph(URIRef(explore.INFERRED)).add(t)
        side = explore.StoreSide(lambda q: [{str(k): str(v) for k, v in r.asdict().items()} for r in ds.query(q)])
        edges, _ = explore.walk(side, "https://example.org/base/p0", 1)
        self.assertIn([str(t) for t in orphan] + ["https://example.org/base/1.1.0"], edges)
        self.assertIn([str(t) for t in lone] + [None], edges)

    def test_a_plain_file_is_a_package_named_by_its_graph_on_both_sides(self):
        # run_projection.py's files mode: a file with no owl:versionIRI, named by module_tags --graph and,
        # in the store, by the graph it was loaded into (explore.py --files).
        plain = write(self.tmp, "plain.ttl", "<https://example.org/plain/n1> <http://www.w3.org/2004/02/skos/core#related> "
                                             "<https://example.org/base/p0> .\n")
        packages = mt.read_packages([plain] + [p.path for p in self.packages], {plain: "urn:x:plain"})
        self.assertIn("urn:x:plain", [p.version for p in packages])
        ds = Dataset(default_union=False)
        for p in packages:
            g = ds.graph(URIRef(p.version))
            for t in p.graph:
                g.add(t)
        select = lambda q: [{str(k): str(v) for k, v in r.asdict().items()} for r in ds.query(q)]   # noqa: E731
        neo = explore.Neo4jSide(FakeNeo4j(packages), PREFIXES)
        self.assertTrue(explore.compare_walk(neo, explore.StoreSide(select, None, True), "https://example.org/plain/n1", 2)["equal"])
        self.assertFalse(explore.compare_walk(neo, explore.StoreSide(select), "https://example.org/plain/n1", 2)["equal"])

    def test_the_module_maps_agree(self):
        self.assertEqual(explore.Neo4jSide(FakeNeo4j(self.packages), PREFIXES).modules(), store(self.packages).modules())

    def test_the_paste_able_walk_matches_with_a_self_loop_and_a_cycle(self):
        # An edge touching the start is a first-hop edge, so selecting the start again as the middle
        # node (through a self-loop or a cycle back) adds nothing the stepwise walk lacks.
        loop = write(self.tmp, "loop.ttl", APP + "app:sys skos:related app:sys . base:p0 skos:related app:sys .\n")
        packages = mt.read_packages([loop, os.path.join(self.tmp, "base.ttl")])
        ds = Dataset(default_union=False)
        for p in packages:
            g = ds.graph(URIRef(p.version))
            for t in p.graph:
                g.add(t)
        for hops in (1, 2, 3):
            query = explore.sparql_walk(hops).replace("<https://example.org/your-node>", "<https://example.org/app/sys>")
            single = {(str(r.s), str(r.p), str(r.o)) for r in ds.query(query)}
            stepwise, _ = explore.walk(store(packages), "https://example.org/app/sys", hops)
            self.assertEqual(single, {tuple(e[:3]) for e in stepwise}, hops)

    def test_the_paste_able_sparql_walk_matches_the_hop_by_hop_walk(self):
        ds = Dataset(default_union=False)
        for p in self.packages:
            g = ds.graph(URIRef(p.version))
            for t in p.graph:
                g.add(t)
        query = explore.sparql_walk(2).replace("<https://example.org/your-node>", "<https://example.org/app/sys>")
        single = {(str(r.s), str(r.p), str(r.o)) for r in ds.query(query)}
        stepwise, _ = explore.walk(store(self.packages), "https://example.org/app/sys", 2)
        self.assertEqual(single, {tuple(e[:3]) for e in stepwise})


class QueryFiles(unittest.TestCase):
    """The paste-able files in ../queries are what the generators write, so they cannot drift."""

    def read(self, name):
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "queries", name), encoding="utf-8") as f:
            return f.read()

    def test_the_sparql_walk_file_is_generated(self):
        self.assertEqual(self.read("walk-2-hops.rq"), explore.sparql_walk(2))

    def test_the_module_map_file_is_generated(self):
        self.assertEqual(self.read("module-map.rq"), mt.CONSTRUCT)

    def test_no_cypher_walk_crosses_a_schema_relationship_and_the_rows_carry_the_tags(self):
        # The path filter, not a filter on the rows: a schema relationship (a class to a restriction's
        # filler) must not count as a hop, or the far side's edges come back.
        for name in ("walk.cypher", "walk-visual.cypher"):
            text = self.read(name)
            match, rest = text.split("MATCH p = ", 1)[1].split("\n", 1)
            self.assertTrue(rest.startswith("WHERE none(") and "STARTS WITH 'n4sch__'" in rest.split("\n", 1)[0], name)
            # a graph renamed with another separator needs that edit, which the file's comment says
            self.assertIn("separator", text.split("MATCH p = ", 1)[0], name)
        self.assertIn("r.graph AS module", self.read("walk.cypher"))


class HashLeavesTheTagOut(unittest.TestCase):
    def test_the_tag_does_not_change_the_hash_and_another_property_does(self):
        def nodes(props):
            return [{"uri": "u", "labels": ["Resource"], "props": {"uri": "u", **props}}]
        self.assertEqual(lv.graph_hash(nodes({}), []), lv.graph_hash(nodes({lv.MODULE_TAG: "v"}), []))
        self.assertNotEqual(lv.graph_hash(nodes({}), []), lv.graph_hash(nodes({"ns__x": "v"}), []))
        edge = {"s": "u", "t": "t", "o": "u", "u": None, "props": {}}
        tagged = dict(edge, props={lv.MODULE_TAG: "v"})
        self.assertEqual(lv.graph_hash(nodes({}), [edge]), lv.graph_hash(nodes({}), [tagged]))


if __name__ == "__main__":
    unittest.main()
