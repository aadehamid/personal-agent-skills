#!/usr/bin/env python3
"""Walk any node end to end across modules, in Neo4j and in a SPARQL store, and compare the answers.

    uv run --no-project --with rdflib --with neo4j python3 explore.py walk    --config <config> (--uri U | --env E) --sparql <query URL> --iri <IRI> [--hops N] [--separator _]
    uv run --no-project --with rdflib --with neo4j python3 explore.py compare --config <config> (--uri U | --env E) --sparql <query URL> --queries <queries.json> [--report out.json] [--separator _]
    uv run --no-project --with rdflib python3 explore.py sparql-walk --output <walk.rq> [--hops N]   (the paste-able SPARQL walk)

The walk (default 2 hops, --hops to change): every relationship within N hops of the start node, in
both directions, with its predicate and its module tag, and the module tag of every node it reaches.
It runs hop by hop: hop k reads every relationship that touches a node reached at hop k-1. In Neo4j a
relationship is (source uri, type, target uri) between two :Resource nodes, its type expanded to the
predicate IRI by the configuration's prefixes (module_tags.predicate), leaving out n10s's schema
relationships (n4sch plus the separator, which n10s derives from the ontology; the triples they repeat are ordinary
relationships too), its tag the `graph` property. --separator (underscores only) is what the graph puts
between a prefix and a local name: n10s's two underscores unless the load renamed the names
(load_verify.py --separator); give the same value here, or no type expands and the schema relationships
are walked. A prefix that holds it is refused (exit 2), as the load refuses it. The paste-able Cypher walks
in ../queries/ name n10s's schema prefix; edit it for a renamed graph, as their comments say. A
relationship's tag is the `graph` property module_tags.py set, and a node's tag its own `graph`. In the store a relationship is a triple with an
IRI subject and object in a named graph; its tag is derived from the store by module_tags's rules (the
first graph in dependency order that holds it, the subject's tag for a triple only in the inferred
graph) and a node's tag likewise, so agreement also proves the tags. The inferred graph is the named
graph the projection's inferred.nt was loaded into: --inferred-graph, by default
urn:ontology-to-lpg:inferred (load it with rdfstore.py --graph inferred.nt=<that IRI>). A triple in any
other graph that is not a package is kept with no tag, so it shows as a difference; with --files
(run_projection.py's files mode) every other graph is a package named by its graph, as module_tags.py
--graph names a plain file. Both answers become one sorted
list of [subject, predicate, object, tag] and one of [node, tag]; `walk` prints both stores' counts
and whether they are equal, and the modules reached.

`compare` runs each entry of a queries file ({"queries": [{"name", "iri", "hops"}...]}) as a walk and
also compares the module map (module_tags.py modules in Neo4j against the CONSTRUCT's pattern in the
store); it exits 1 when any answer differs. The paste-able forms are in ../queries/.

Exit 0 when every answer agrees, 1 when one differs, 2 on bad input or a failed query. An error prints a
fixed context and the exception's type, never its text. Every printed value is quoted.
"""
import json
import sys
import urllib.parse
import urllib.request

import load_verify as lv
import module_tags as mt
from shell import Refusal, error_line, q

DEFAULT_HOPS = 2
INFERRED = "urn:ontology-to-lpg:inferred"
BATCH = 400


def cy_edges(sep=None):
    """The edges of one hop, leaving out n10s's schema relationships under the graph's separator."""
    return (f"MATCH (a:Resource)-[r]-(b:Resource) WHERE a.uri IN $frontier AND NOT type(r) STARTS WITH '{mt.schema_prefix(sep)}' "
            f"RETURN DISTINCT startNode(r).uri AS s, type(r) AS t, endNode(r).uri AS o, r.`{mt.TAG}` AS g")


CY_EDGES = cy_edges()
CY_NODES = f"MATCH (n:Resource) WHERE n.uri IN $uris RETURN n.uri AS uri, n.`{mt.TAG}` AS g"
CY_MODULES = "MATCH (a:Module)-[r:REQUIRES]->(b:Module) RETURN a.uri AS source, b.uri AS target, r.pin AS pin"

SP_HEADERS = """PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX dcterms: <http://purl.org/dc/terms/>
SELECT ?g ?ontology ?version ?pin WHERE {
  GRAPH ?g { ?ontology a owl:Ontology ; owl:versionIRI ?version . OPTIONAL { ?ontology dcterms:requires ?pin } }
}"""

SP_GRAPHS = "SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o } }"


def iri_values(iris):
    return " ".join(f"<{i}>" for i in iris)


def sp_edges(frontier):
    return f"""SELECT DISTINCT ?s ?p ?o ?g WHERE {{
  VALUES ?x {{ {iri_values(frontier)} }}
  GRAPH ?g {{ {{ ?x ?p ?o . BIND(?x AS ?s) }} UNION {{ ?s ?p ?x . BIND(?x AS ?o) }} }}
  FILTER(isIRI(?s) && isIRI(?o))
}}"""


def sp_nodes(uris):
    return f"""PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
SELECT DISTINCT ?n ?g ?typed WHERE {{
  VALUES ?n {{ {iri_values(uris)} }}
  GRAPH ?g {{ {{ ?n ?p ?o }} UNION {{ ?s ?p ?n }} }}
  BIND(EXISTS {{ GRAPH ?g {{ ?n rdf:type ?t }} }} AS ?typed)
}}"""


def sparql_walk(hops):
    """One paste-able SPARQL query for the walk from ?start (bind it in VALUES): every triple within
    `hops` hops, both directions, with its named graph. A triple the inferred graph alone holds is shown
    with that graph; explore.py walk maps it to its subject's tag."""
    lines = ["# The walk: every triple within %d hop(s) of ?start, both directions, with its named graph." % hops,
             "SELECT DISTINCT ?s ?p ?o ?g WHERE {", "  VALUES ?start { <https://example.org/your-node> }"]
    branches = []
    for h in range(1, hops + 1):
        steps, prev = [], "?start"
        for k in range(1, h):
            steps.append(f"GRAPH ?g{k} {{ {{ {prev} ?q{k} ?n{k} }} UNION {{ ?n{k} ?q{k} {prev} }} }} FILTER(isIRI(?n{k}))")
            prev = f"?n{k}"
        steps.append(f"GRAPH ?g {{ {{ {prev} ?p ?o . BIND({prev} AS ?s) }} UNION {{ ?s ?p {prev} . BIND({prev} AS ?o) }} }}")
        branches.append("  { " + " ".join(steps) + " }")
    lines.append("\n  UNION\n".join(branches))
    lines += ["  FILTER(isIRI(?s) && isIRI(?o))", "}"]
    return "\n".join(lines) + "\n"


class Neo4jSide:
    def __init__(self, run, prefixes, sep=None):
        self.run, self.prefixes, self.sep = run, prefixes, sep
        self.cy_edges = cy_edges(sep)

    def edges(self, frontier):
        out = set()
        for i in range(0, len(frontier), BATCH):
            for r in self.run(self.cy_edges, frontier=frontier[i:i + BATCH]):
                out.add((r["s"], mt.predicate(r["t"], self.prefixes, self.sep), r["o"], r["g"]))
        return out

    def node_tags(self, uris):
        tags = {}
        for i in range(0, len(uris), BATCH):
            for r in self.run(CY_NODES, uris=uris[i:i + BATCH]):
                tags[r["uri"]] = r["g"]
        return tags

    def modules(self):
        return sorted([r["source"], r["target"], r["pin"]] for r in self.run(CY_MODULES))


class StoreSide:
    """A SPARQL store holding one named graph per package (and INFERRED). select(query) returns rows of
    {variable: value} with every value a string (an IRI's text, a literal's lexical form, true/false)."""

    def __init__(self, select, inferred_graph=None, files=False):
        self.select = select
        self.inferred = inferred_graph or INFERRED
        heads = self.select(SP_HEADERS)
        by_graph = {}
        for r in heads:
            by_graph.setdefault(r["g"], (r["ontology"], r["version"], set()))[2].update([r["pin"]] if r.get("pin") else [])
        if files:   # every other graph is a plain file, a package named by its graph (module_tags --graph)
            for r in self.select(SP_GRAPHS):
                if r["g"] not in by_graph and r["g"] != self.inferred:
                    by_graph[r["g"]] = (r["g"], r["g"], set())
        self.packages = mt.dependency_order([mt.Package(g, o, v, tuple(sorted(p)), None)
                                             for g, (o, v, p) in by_graph.items()])
        self.rank = {p.path: i for i, p in enumerate(self.packages)}
        self.version = {p.path: p.version for p in self.packages}
        self.ontology = {p.path: p.ontology for p in self.packages}
        self._tags = {}

    def node_tags(self, uris):
        todo = [u for u in uris if u not in self._tags]
        found = {}
        for i in range(0, len(todo), BATCH):
            for r in self.select(sp_nodes(todo[i:i + BATCH])):
                if r["g"] in self.rank:
                    found.setdefault(r["n"], []).append((r["g"], r["typed"] == "true"))
        for n, where in found.items():
            pool = [g for g, typed in where if typed] or [g for g, _ in where]
            own = [g for g in pool if n.startswith(self.ontology[g] + "/")]
            self._tags[n] = self.version[min(own or pool, key=self.rank.get)]
        return {u: self._tags.get(u) for u in uris}

    def edges(self, frontier):
        raw = {}
        for i in range(0, len(frontier), BATCH):
            for r in self.select(sp_edges(frontier[i:i + BATCH])):
                raw.setdefault((r["s"], r["p"], r["o"]), set()).add(r["g"])
        out, inferred_only = set(), []
        for key, graphs in raw.items():
            known = [g for g in graphs if g in self.rank]
            if known:
                out.add((*key, self.version[min(known, key=self.rank.get)]))
            elif self.inferred in graphs:
                inferred_only.append(key)
            else:
                # a graph that is neither a package nor the inferred graph: kept, with no tag, so the
                # comparison shows it instead of losing it
                out.add((*key, None))
        subjects = self.node_tags(sorted({k[0] for k in inferred_only}))
        out.update((*k, subjects[k[0]]) for k in inferred_only)
        return out

    def modules(self):
        rows = []
        for p in self.packages:
            for pin in p.requires:
                r = mt.required_package(pin, self.packages)
                if r is not None and r != p:
                    rows.append([p.version, r.version, pin])
        return sorted(rows)


def walk(side, iri, hops):
    """(sorted [[s, p, o, tag]], sorted [[node, tag]]) within `hops` hops of iri."""
    seen, frontier, edges = {iri}, [iri], set()
    for _ in range(hops):
        if not frontier:
            break
        found = side.edges(sorted(frontier))
        edges |= found
        nxt = {t for e in found for t in (e[0], e[2])} - seen
        seen |= nxt
        frontier = sorted(nxt)
    tags = side.node_tags(sorted(seen))
    return sorted(list(e) for e in edges), sorted([n, tags.get(n)] for n in seen)


def modules_reached(edges, nodes):
    return sorted({e[3] for e in edges if e[3]} | {n[1] for n in nodes if n[1]})


def compare_walk(neo, store, iri, hops):
    a_edges, a_nodes = walk(neo, iri, hops)
    b_edges, b_nodes = walk(store, iri, hops)
    only_neo = [e for e in a_edges if e not in b_edges][:3]
    only_store = [e for e in b_edges if e not in a_edges][:3]
    return {"iri": iri, "hops": hops, "edges": [len(a_edges), len(b_edges)], "nodes": [len(a_nodes), len(b_nodes)],
            "equal": a_edges == b_edges and a_nodes == b_nodes, "modules": modules_reached(a_edges, a_nodes),
            "only_in_neo4j": only_neo, "only_in_store": only_store}


def http_select(endpoint):
    def select(query):
        data = urllib.parse.urlencode({"query": query}).encode()
        req = urllib.request.Request(endpoint, data=data, headers={"Accept": "application/sparql-results+json"})
        with urllib.request.urlopen(req, timeout=300) as resp:
            body = json.load(resp)
        return [{k: v["value"] for k, v in b.items()} for b in body["results"]["bindings"]]
    return select


def options(argv):
    opts, i = {}, 0
    known = {"--config", "--uri", "--env", "--sparql", "--iri", "--hops", "--queries", "--report", "--query-timeout",
             "--output", "--inferred-graph", "--separator"}
    while i < len(argv):
        if argv[i] == "--files":
            opts["--files"], i = True, i + 1
            continue
        if argv[i] not in known or i + 1 >= len(argv):
            raise Refusal("an unknown flag, or a flag without its value")
        opts[argv[i]] = argv[i + 1]
        i += 2
    try:
        hops = int(opts.get("--hops", DEFAULT_HOPS))
    except ValueError:
        raise Refusal("--hops needs a whole number") from None
    if hops < 1:
        raise Refusal("--hops needs a number of at least 1")
    return opts, hops


def main(argv):
    if not argv or argv[0] not in ("walk", "compare", "sparql-walk"):
        print("usage: explore.py walk|compare|sparql-walk [options]", file=sys.stderr)
        return 2
    command = argv[0]
    try:
        opts, hops = options(argv[1:])
        if command == "sparql-walk":
            if "--output" not in opts:
                raise Refusal("give --output for the query file")
            with open(opts["--output"], "w", encoding="utf-8") as f:
                f.write(sparql_walk(hops))
            print(f"wrote {q(opts['--output'])}: the walk, {q(hops)} hop(s)")
            return 0
        for flag in ("--config", "--sparql") + (("--iri",) if command == "walk" else ("--queries",)):
            if flag not in opts:
                raise Refusal(f"give {flag}")
        if ("--uri" in opts) == ("--env" in opts):
            raise Refusal("give exactly one of --uri and --env")
        import build
        prefixes = dict(build.load_config(opts["--config"]).prefixes)
        sep = lv.separator(opts)
        build.check_prefixes(prefixes, sep)
        queries = []
        if command == "compare":
            with open(opts["--queries"], encoding="utf-8") as f:
                queries = json.load(f)["queries"]
        timeout = lv.query_timeout(opts)
        from model_review import connection
        uri, auth, database = connection(opts)
    except (OSError, ValueError) as exc:
        print(f"ERROR {q(error_line('the arguments, the queries or the --env file could not be read', exc))}",
              file=sys.stderr)
        return 2
    try:
        from neo4j import GraphDatabase
        with GraphDatabase.driver(uri, auth=auth) as driver, driver.session(database=database) as raw:
            session = lv.Timed(raw, timeout)
            neo = Neo4jSide(lambda stmt, **params: session.run(stmt, params).data(), prefixes, sep)
            store = StoreSide(http_select(opts["--sparql"]), opts.get("--inferred-graph"), opts.get("--files", False))
            if command == "walk":
                results = [compare_walk(neo, store, opts["--iri"], hops)]
                module_map = None
            else:
                results = [dict(compare_walk(neo, store, e["iri"], int(e.get("hops", DEFAULT_HOPS))), name=e["name"])
                           for e in queries]
                a, b = neo.modules(), store.modules()
                module_map = {"rows": [len(a), len(b)], "equal": a == b,
                              "only_in_neo4j": [r for r in a if r not in b][:3],
                              "only_in_store": [r for r in b if r not in a][:3]}
    except Exception as exc:  # the driver and urllib raise several types; any of them stops the run
        print(f"ERROR {q(error_line('a store query failed', exc))}", file=sys.stderr)
        return 2
    ok = all(r["equal"] for r in results) and (module_map is None or module_map["equal"])
    for r in results:
        print(f"{q(r.get('name', 'walk'))} from {q(r['iri'])}, {q(r['hops'])} hop(s): edges neo4j {q(r['edges'][0])} "
              f"store {q(r['edges'][1])}, nodes neo4j {q(r['nodes'][0])} store {q(r['nodes'][1])}, "
              f"{q('equal' if r['equal'] else 'DIFFERENT')}; modules reached {q(len(r['modules']))}")
    if module_map is not None:
        print(f"module map: neo4j {q(module_map['rows'][0])} row(s), store {q(module_map['rows'][1])}, "
              f"{q('equal' if module_map['equal'] else 'DIFFERENT')}")
    if "--report" in opts:
        try:
            from model_review import write_report
            write_report(opts["--report"], {"walks": results, "module_map": module_map, "agree": ok})
        except OSError as exc:
            print(f"ERROR {q(error_line('the report was not written', exc))}", file=sys.stderr)
            return 2
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
