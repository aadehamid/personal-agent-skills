#!/usr/bin/env python3
"""Add-on F: tag every node and relationship of a loaded projection with the package it came from,
check the tags, and build the module graph.

    uv run --no-project --with rdflib --with neo4j python3 module_tags.py tag     --config <config> (--uri U | --env E) [--inferred inferred.nt] [--graph FILE=IRI]... [--separator _] <package.ttl>...
    uv run --no-project --with rdflib --with neo4j python3 module_tags.py check   --config <config> (--uri U | --env E) [--inferred inferred.nt] [--separator _] <package.ttl>...
    uv run --no-project --with rdflib --with neo4j python3 module_tags.py modules (--uri U | --env E) [--separator _] <package.ttl>...
    uv run --no-project --with rdflib python3 module_tags.py construct --output <module-map.rq>

--separator (underscores only) is what the graph puts between a prefix and a local name: n10s's two
underscores unless the load renamed the names (load_verify.py --separator); give the same value here. A
prefix that holds it is refused (exit 2), as the load refuses it.

Each package file is one released package: its owl:Ontology header names the package by its
owl:versionIRI, the same IRI the rdf-store skill names the package's named graph by. --graph FILE=IRI
(repeatable) makes a plain file a package named IRI, with no requirements, whatever header it has: the
files mode of run_projection.py names a file without an owl:versionIRI that way, as it names its graph. The tag is that
version IRI, stored on the reserved property `graph` (add-on F's name); the projection's own keys are
always prefixed (n10s joins prefix and local name with two underscores, and after the optional rename the kept
graph uses the configured separator), so a bare `graph` cannot collide with ontology data.
load_verify.graph_hash leaves `graph` out, so tagging after step 6 keeps the report's hash, and
copy_graph.py still copies the tags; `check` proves them on any target.

The tag rules, applied to the package files, never to the graph:
  a node     the packages that type its IRI (rdf:type with it as subject); if none, every package that
             mentions it. Among those, the packages whose ontology IRI followed by "/" starts the node's
             IRI, if any (the module's own namespace). Then the first in dependency order (a package's
             requirements, by dcterms:requires, come before it; ties by ontology IRI).
  an edge    the first package in dependency order whose file holds the triple; an inferred triple
             (--inferred, not in any package) takes its subject's tag.
An edge is read back from the graph as (source uri, type, target uri); its predicate is the type's
prefix expanded with the configuration's prefixes. A relationship whose type starts with n4sch and the separator is
schema that n10s.onto.import derives from the ontology (SCO, SPO, DOMAIN, RANGE, EQC and the
*_RESTRICTION types, some of which point at a restriction's filler and repeat no single triple): it is
tagged with the tag of the node it starts from, and checked against that, never matched to a triple.
The triples it repeats are in the graph as ordinary relationships too.

`tag` sets the tags and fails (exit 1) when a node or relationship of the graph has no expected tag:
the graph holds something no package states. `check` reads every :Resource node and every
relationship between two of them and fails unless each carries exactly one `graph`, a string equal
to its expected tag, the expected nodes and edges are all in the graph, and no two relationships share
their ends and type (n10s writes one per triple, so a second would hide the first); it counts what it
read.
`modules` builds the module graph beside the projection: one (:Module {uri: <version IRI>,
ontology, version}) per package and (:Module)-[:REQUIRES {pin}]->(:Module) per dcterms:requires,
pointing at the loaded release of the required module, with the pinned version IRI as `pin` (a pin
older than the loaded release shows a requirement that lags). :Module nodes carry no :Resource label,
so the projection's hash and checks never see them. `construct` prints the same graph as a SPARQL
CONSTRUCT over a store that holds one named graph per package (the rdf-store skill).

Exit 0 on a pass, 1 on a failed check, 2 on bad input or a failed query. An error prints a fixed
context and the exception's type, never its text (shell.error_line). Every printed value is quoted.
"""
import sys
from collections import namedtuple

from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF

import load_verify as lv
from shell import Refusal, error_line, q

TAG = lv.MODULE_TAG
SEP = lv.N10S_SEP   # n10s's separator; --separator names another when the graph was renamed (load_verify.py)


def schema_prefix(sep=None):
    """What n10s.onto.import's schema relationship types start with: n4sch and the graph's separator.
    They are tagged by the node they start from (module docstring)."""
    return "n4sch" + (sep or SEP)


SCHEMA_PREFIX = schema_prefix()
LPG = "https://w3id.org/ontology-to-lpg/module#"

Package = namedtuple("Package", "path ontology version requires graph")

CONSTRUCT = f"""PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX lpgm: <{LPG}>
# The module graph (module_tags.py modules) from a store with one named graph per package.
# Each requirement is its own node (?requirement), so a pin stays with the package that names it.
CONSTRUCT {{
  ?version a lpgm:Module ; lpgm:ontology ?ontology ; lpgm:graph ?g ; lpgm:requires ?loaded .
  ?requirement a lpgm:Requirement ; lpgm:from ?version ; lpgm:to ?loaded ; lpgm:pin ?pin .
}} WHERE {{
  GRAPH ?g {{ ?ontology a owl:Ontology ; owl:versionIRI ?version . }}
  OPTIONAL {{
    GRAPH ?g {{ ?ontology dcterms:requires ?pin . }}
    GRAPH ?h {{ ?required a owl:Ontology ; owl:versionIRI ?loaded . }}
    FILTER(STRSTARTS(STR(?pin), CONCAT(STR(?required), "/")) || ?pin = ?loaded)
    # The longest matching ontology IRI wins, as module_tags.required_package picks it.
    FILTER NOT EXISTS {{
      GRAPH ?h2 {{ ?longer a owl:Ontology ; owl:versionIRI ?other . }}
      FILTER(STRLEN(STR(?longer)) > STRLEN(STR(?required)) &&
             (STRSTARTS(STR(?pin), CONCAT(STR(?longer), "/")) || ?pin = ?other))
    }}
  }}
  # Outside the OPTIONAL: inside it ?version is not yet bound. With no ?pin it stays unbound.
  BIND(IRI(CONCAT(STR(?version), "#requires-", ENCODE_FOR_URI(STR(?pin)))) AS ?requirement)
}}
"""


def read_package(path, graph=None):
    g = Graph().parse(path)
    if graph is not None:   # a plain file (run_projection.py's files mode), named by its graph IRI
        return Package(path, graph, graph, (), g)
    heads = [(s, v) for s in g.subjects(RDF.type, OWL.Ontology) for v in g.objects(s, OWL.versionIRI)]
    if len({h for h in heads}) != 1:
        raise Refusal("each package file needs exactly one owl:Ontology with one owl:versionIRI")
    ontology, version = heads[0]
    requires = tuple(sorted(str(r) for r in g.objects(ontology, DCTERMS.requires)))
    return Package(path, str(ontology), str(version), requires, g)


def required_package(pin, packages):
    """The package a dcterms:requires pin names: the one whose ontology IRI followed by "/" starts it
    (the longest, if several), or None."""
    hits = [p for p in packages if pin.startswith(p.ontology + "/") or pin == p.version]
    return max(hits, key=lambda p: len(p.ontology)) if hits else None


def dependency_order(packages):
    """Packages with every requirement before its requirer; ties by ontology IRI. A cycle refuses."""
    if len({p.ontology for p in packages}) != len(packages):
        raise Refusal("two package files have the same owl:Ontology; give one release per module")
    needs = {p.ontology: {r.ontology for pin in p.requires if (r := required_package(pin, packages)) and r != p}
             for p in packages}
    order, done = [], set()
    while len(order) < len(packages):
        ready = sorted(o for o in needs if o not in done and needs[o] <= done)
        if not ready:
            raise Refusal("the packages' dcterms:requires form a cycle")
        done.add(ready[0])
        order.append(next(p for p in packages if p.ontology == ready[0]))
    return order


def read_packages(paths, graphs=None):
    graphs = graphs or {}
    return dependency_order([read_package(p, graphs.get(p)) for p in paths])


def expected_tags(packages, inferred=None):
    """({node IRI: version IRI}, {(s, p, o): version IRI}) for every IRI in the packages and every
    triple whose object is an IRI, by the rules in the module docstring."""
    rank = {p.version: i for i, p in enumerate(packages)}
    typed, mentioned, edges = {}, {}, {}
    for p in packages:
        for s, pred, o in p.graph:
            for term in (s, o):
                if isinstance(term, URIRef):
                    mentioned.setdefault(str(term), set()).add(p)
            if pred == RDF.type and isinstance(s, URIRef):
                typed.setdefault(str(s), set()).add(p)
            if isinstance(s, URIRef) and isinstance(o, URIRef):
                key = (str(s), str(pred), str(o))
                if key not in edges or rank[p.version] < rank[edges[key]]:
                    edges[key] = p.version
    nodes = {}
    for iri, where in mentioned.items():
        pool = typed.get(iri) or where
        own = [p for p in pool if iri.startswith(p.ontology + "/")]
        nodes[iri] = min(own or pool, key=lambda p: rank[p.version]).version
    if inferred is not None:
        for s, pred, o in inferred:
            key = (str(s), str(pred), str(o))
            if isinstance(s, URIRef) and isinstance(o, URIRef) and key not in edges and str(s) in nodes:
                edges[key] = nodes[str(s)]
    return nodes, edges


def predicate(rel_type, prefixes, sep=None):
    """The predicate IRI of a relationship type: the prefixed name expanded, or a schema type. The split is
    at the first separator, which is right because no prefix holds it (build.check_prefixes)."""
    if rel_type.startswith(schema_prefix(sep)):
        return None
    prefix, found, local = rel_type.partition(sep or SEP)
    if not found or prefix not in prefixes:
        return None
    return prefixes[prefix] + local


def compare(graph_nodes, graph_edges, nodes, edges, prefixes, sep=None):
    """The tag problems of a graph read back as [{uri, tag}] and [{s, t, o, tag}]: counts by kind, and
    up to five examples each, holding IRIs and types only (no property values)."""
    schema = schema_prefix(sep)
    problems = {"untagged": [], "wrong_tag": [], "not_in_packages": [], "missing_from_graph": [], "parallel": []}
    seen_nodes, seen_edges, seen_rels = set(), set(), set()
    for n in graph_nodes:
        want = nodes.get(n["uri"])
        seen_nodes.add(n["uri"])
        if want is None:
            problems["not_in_packages"].append(n["uri"])
        elif n.get("tag") is None:
            problems["untagged"].append(n["uri"])
        elif n["tag"] != want:
            problems["wrong_tag"].append(n["uri"])
    for e in graph_edges:
        is_schema = e["t"].startswith(schema)
        key = (e["s"], predicate(e["t"], prefixes, sep), e["o"])
        want = nodes.get(e["s"]) if is_schema else edges.get(key)
        if not is_schema:
            seen_edges.add(key)
        label = f"{e['s']} {e['t']} {e['o']}"
        if (e["s"], e["t"], e["o"]) in seen_rels:
            # n10s writes one relationship per triple; two with the same ends and type hide one another
            problems["parallel"].append(label)
        seen_rels.add((e["s"], e["t"], e["o"]))
        if want is None:
            problems["not_in_packages"].append(label)
        elif e.get("tag") is None:
            problems["untagged"].append(label)
        elif e["tag"] != want:
            problems["wrong_tag"].append(label)
    problems["missing_from_graph"] += sorted(set(nodes) - seen_nodes)
    problems["missing_from_graph"] += sorted(" ".join(k) for k in set(edges) - seen_edges)
    return problems


NODES = f"MATCH (n:Resource) RETURN n.uri AS uri, n.`{TAG}` AS tag"
EDGES = f"MATCH (a:Resource)-[r]->(b:Resource) RETURN a.uri AS s, type(r) AS t, b.uri AS o, r.`{TAG}` AS tag"
SET_NODES = f"UNWIND $rows AS row MATCH (n:Resource {{uri: row.uri}}) SET n.`{TAG}` = row.tag"
SET_EDGES = (f"UNWIND $rows AS row MATCH (a:Resource {{uri: row.s}})-[r]->(b:Resource {{uri: row.o}}) "
             f"WHERE type(r) = row.t SET r.`{TAG}` = row.tag")


def chunks(rows, size=2000):
    for i in range(0, len(rows), size):
        yield rows[i:i + size]


def tag(run, nodes, edges, prefixes, sep=None):
    graph_nodes, graph_edges = run(NODES), run(EDGES)
    node_rows = [{"uri": n["uri"], "tag": nodes[n["uri"]]} for n in graph_nodes if n["uri"] in nodes]
    edge_rows = []
    for e in graph_edges:
        if e["t"].startswith(schema_prefix(sep)):
            want = nodes.get(e["s"])
        else:
            want = edges.get((e["s"], predicate(e["t"], prefixes, sep), e["o"]))
        if want is not None:
            edge_rows.append({"s": e["s"], "t": e["t"], "o": e["o"], "tag": want})
    for rows in chunks(node_rows):
        run(SET_NODES, rows=rows)
    for rows in chunks(edge_rows):
        run(SET_EDGES, rows=rows)
    return len(node_rows), len(edge_rows), len(graph_nodes) - len(node_rows), len(graph_edges) - len(edge_rows)


def check(run, nodes, edges, prefixes, sep=None):
    graph_nodes, graph_edges = run(NODES), run(EDGES)
    return len(graph_nodes), len(graph_edges), compare(graph_nodes, graph_edges, nodes, edges, prefixes, sep)


def module_rows(packages):
    """[{uri, ontology, version}] and [{source, target, pin}] for the module graph."""
    mods = [{"uri": p.version, "ontology": p.ontology, "version": p.version[len(p.ontology) + 1:]} for p in packages]
    reqs = []
    for p in packages:
        for pin in p.requires:
            r = required_package(pin, packages)
            if r is not None and r != p:
                reqs.append({"source": p.version, "target": r.version, "pin": pin})
    return mods, reqs


MODULES = ("UNWIND $mods AS m MERGE (n:Module {uri: m.uri}) SET n.ontology = m.ontology, n.version = m.version")
# One REQUIRES per pin, like the CONSTRUCT's one requirement node per pin: two pins resolving to one
# loaded module stay two relationships.
REQUIRES = ("UNWIND $reqs AS r MATCH (a:Module {uri: r.source}), (b:Module {uri: r.target}) "
            "MERGE (a)-[:REQUIRES {pin: r.pin}]->(b)")
CLEAR_MODULES = "MATCH (n:Module) DETACH DELETE n"


def options(argv):
    opts, files, i = {"--graph": {}}, [], 0
    known = {"--config", "--uri", "--env", "--inferred", "--query-timeout", "--separator"}
    while i < len(argv):
        if argv[i] == "--graph" and i + 1 < len(argv):
            path, sep, iri = argv[i + 1].partition("=")
            if not sep or not path or not iri:
                raise Refusal("--graph takes FILE=IRI")
            opts["--graph"][path] = iri
            i += 2
        elif argv[i].startswith("--"):
            if argv[i] not in known or i + 1 >= len(argv):
                raise Refusal("an unknown flag, or a flag without its value")
            opts[argv[i]] = argv[i + 1]
            i += 2
        else:
            files.append(argv[i])
            i += 1
    return opts, files


def main(argv):
    if not argv or argv[0] not in ("tag", "check", "modules", "construct"):
        print("usage: module_tags.py tag|check|modules|construct [options] <package.ttl>...", file=sys.stderr)
        return 2
    command = argv[0]
    if command == "construct":
        if len(argv) != 3 or argv[1] != "--output":
            print("usage: module_tags.py construct --output <module-map.rq>", file=sys.stderr)
            return 2
        try:
            with open(argv[2], "w", encoding="utf-8") as f:
                f.write(CONSTRUCT)
        except OSError as exc:
            print(f"ERROR {q(error_line('the query file was not written', exc))}", file=sys.stderr)
            return 2
        print(f"wrote {q(argv[2])}: the module-graph CONSTRUCT")
        return 0
    try:
        opts, files = options(argv[1:])
        if not files:
            raise Refusal("give the package files")
        if ("--uri" in opts) == ("--env" in opts):
            raise Refusal("give exactly one of --uri and --env")
        if command != "modules" and "--config" not in opts:
            raise Refusal("give --config")
        timeout = lv.query_timeout(opts)
        sep = lv.separator(opts)
        packages = read_packages(files, opts["--graph"])
        inferred = Graph().parse(opts["--inferred"], format="nt") if "--inferred" in opts else None
        prefixes = {}
        if "--config" in opts:
            import build
            prefixes = dict(build.load_config(opts["--config"]).prefixes)
            build.check_prefixes(prefixes, sep)
        from model_review import connection
        uri, auth, database = connection(opts)
    except (OSError, ValueError) as exc:
        print(f"ERROR {q(error_line('the arguments, the packages or the --env file could not be read', exc))}",
              file=sys.stderr)
        return 2
    try:
        from neo4j import GraphDatabase
        with GraphDatabase.driver(uri, auth=auth) as driver, driver.session(database=database) as raw:
            session = lv.Timed(raw, timeout)
            run = lambda stmt, **params: session.run(stmt, params).data()   # noqa: E731
            if command == "modules":
                mods, reqs = module_rows(packages)
                run(CLEAR_MODULES)
                run(MODULES, mods=mods)
                run(REQUIRES, reqs=reqs)
                print(f"module graph: {q(len(mods))} module(s), {q(len(reqs))} requirement(s)")
                for r in reqs:
                    if r["pin"] == r["target"]:
                        print(f"  {q(r['source'])} requires {q(r['target'])}")
                    else:
                        print(f"  {q(r['source'])} requires {q(r['target'])} (pinned {q(r['pin'])})")
                return 0
            nodes, edges = expected_tags(packages, inferred)
            if command == "tag":
                tagged_nodes, tagged_edges, left_nodes, left_edges = tag(run, nodes, edges, prefixes, sep)
                print(f"tagged {q(tagged_nodes)} node(s) and {q(tagged_edges)} relationship(s) with {q(TAG)}")
                if left_nodes or left_edges:
                    print(f"FAIL {q(left_nodes)} node(s) and {q(left_edges)} relationship(s) match no package triple; "
                          "run check for examples")
                    return 1
                return 0
            read_nodes, read_edges, problems = check(run, nodes, edges, prefixes, sep)
    except Exception as exc:  # the driver raises several types; any of them stops the run
        print(f"ERROR {q(error_line('a graph query failed', exc))}", file=sys.stderr)
        return 2
    print(f"read {q(read_nodes)} node(s) and {q(read_edges)} relationship(s); "
          f"expected {q(len(nodes))} node(s) and {q(len(edges))} edge(s) from {q(len(packages))} package(s)")
    failed = False
    for kind, items in problems.items():
        if items:
            failed = True
            print(f"FAIL {q(kind)}: {q(len(items))}; for example {q(items[0])}")
    if not failed:
        print(f"every node and relationship carries exactly one {q(TAG)}, equal to the package it came from")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
