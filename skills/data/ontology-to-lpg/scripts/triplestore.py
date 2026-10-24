#!/usr/bin/env python3
"""Load the validated inputs into any SPARQL 1.1 store, one named graph per input file, and check
that nothing was lost: the store's counts against the files, and against the n10s export.

Run: uv run --no-project --with rdflib python3 triplestore.py --gsp <graph store URL> --query <SPARQL URL>
         [--env <file>] [--graph-base <IRI>] --inferred inferred.nt [--projection-report <report.json>]
         [--cq <question.rq>]... --report <triplestore-report.json> <data.ttl>...

It speaks only W3C protocols, so it works with any store that implements them: the SPARQL 1.1 Graph
Store HTTP Protocol (https://www.w3.org/TR/sparql11-http-rdf-update/) to replace each named graph
with HTTP PUT (indirect graph identification, ?graph=<IRI>), and the SPARQL 1.1 Protocol to count.
--env names a file of KEY=VALUE lines that may set SPARQL_GSP, SPARQL_QUERY, SPARQL_USER and
SPARQL_PASSWORD (HTTP Basic credentials); flags win over the file. The password is never printed.

Graph names (graph_iri): a data file's graph is the owl:versionIRI of its one owl:Ontology, else
that ontology's IRI, else <graph-base><file name without extension>; inferred.nt goes to
<graph-base>inferred. --graph-base defaults to urn:lpg-projection:graph:. Pick one under your own
domain for anything shared. (Jena Fuseki 6.2.0 refused urn:x-lpg-projection:graph:inferred as a
relative IRI, so the default has no x- namespace.)

Counting rule: a count is the number of distinct triples, blank nodes counted as triples without
matching their labels. The checks:
  per graph      COUNT(*) in each named graph equals the triples in its file
  per predicate  the distinct triples per predicate over all the graphs equal those of the files
                 together (the union loadable.nt plus inferred.nt holds)
  three-way      with --projection-report, they also equal the report's export_predicate_counts:
                 the n10s export with schema rows (neo4j://graph.schema#) left out, n10s's own
                 configuration nodes never being exported
With --cq, each SPARQL SELECT runs over the merge of the loaded graphs (passed as default-graph-uri
parameters) and its row count is recorded.

The report is fail-closed, as load_verify.py's is: the report named by --report (and its .failed
file) is deleted before anything else, even before the flags are checked; it is written, by a
rename, only when every check passed. A count mismatch writes the details to <report>.failed; a
request that fails writes nothing. --projection-report must say passed: true.

Exit 0 when every check passed, 1 when a check or a request failed, 2 on bad input.
"""
import base64
import http.client
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF

import build
import load_verify as lv

DEFAULT_BASE = "urn:lpg-projection:graph:"


def read_env_file(path):
    values = {}
    if not path:
        return values
    with open(path, encoding="utf-8") as f:
        for number, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, sep, value = line.partition("=")
            if not sep:
                raise ValueError(f"{path} line {number} is not KEY=VALUE")
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def graph_iri(g, file_path, base):
    """The named graph for one input file (see the module docstring)."""
    ontologies = sorted(set(g.subjects(RDF.type, OWL.Ontology)), key=str)
    if len(ontologies) == 1 and isinstance(ontologies[0], URIRef):
        version = g.value(ontologies[0], OWL.versionIRI)
        return str(version) if isinstance(version, URIRef) else str(ontologies[0])
    stem = os.path.splitext(os.path.basename(file_path))[0]
    return base + stem


def predicate_counts(graphs):
    """Distinct triples per predicate IRI over the union of the graphs."""
    union = Graph()
    for g in graphs:
        union += g
    counts = {}
    for _, p, _ in union:
        counts[str(p)] = counts.get(str(p), 0) + 1
    return dict(sorted(counts.items()))


def compare(name, expected, actual):
    """A list of failure lines for two {key: count} maps."""
    fails = []
    for key in sorted(set(expected) | set(actual)):
        if expected.get(key, 0) != actual.get(key, 0):
            fails.append(f"{name}: {key} has {actual.get(key, 0)} in the store's side, {expected.get(key, 0)} expected")
    return fails


class Store:
    def __init__(self, gsp, query, user=None, password=None):
        self.gsp, self.query_url = gsp, query
        self.auth = None
        if user:
            self.auth = "Basic " + base64.b64encode(f"{user}:{password or ''}".encode()).decode()

    def _request(self, url, method="GET", data=None, headers=None):
        req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
        if self.auth:
            req.add_header("Authorization", self.auth)
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, resp.read()

    def put_graph(self, iri, ntriples_bytes):
        url = self.gsp + ("&" if "?" in self.gsp else "?") + urllib.parse.urlencode({"graph": iri})
        status, _ = self._request(url, "PUT", ntriples_bytes, {"Content-Type": "application/n-triples"})
        return status

    def select(self, sparql, default_graphs=()):
        """SPARQL 1.1 Protocol query by POST; default_graphs become default-graph-uri parameters, so
        the query runs over their merge (SPARQL 1.1 Protocol, section 2.1.4)."""
        params = [("query", sparql)] + [("default-graph-uri", g) for g in default_graphs]
        body = urllib.parse.urlencode(params).encode()
        _, data = self._request(self.query_url, "POST", body, {"Content-Type": "application/x-www-form-urlencoded",
                                                               "Accept": "application/sparql-results+json"})
        return json.loads(data)["results"]["bindings"]


def graph_count_query(iri):
    return f"SELECT (COUNT(*) AS ?n) WHERE {{ GRAPH <{iri}> {{ ?s ?p ?o }} }}"


def predicate_count_query(iris):
    graphs = ", ".join(f"<{i}>" for i in iris)
    return ("SELECT ?p (COUNT(*) AS ?n) WHERE { SELECT DISTINCT ?s ?p ?o WHERE { GRAPH ?g { ?s ?p ?o } "
            f"FILTER(?g IN ({graphs})) }} }} GROUP BY ?p")


def main(argv):
    for path in build.named_paths(argv, "--report"):
        lv.remove_report(path)
    try:
        opts, data = build.options(argv, multi=("--cq",))
        env = read_env_file(opts.get("--env"))
        gsp = opts.get("--gsp") or env.get("SPARQL_GSP")
        query = opts.get("--query") or env.get("SPARQL_QUERY")
        build.need(opts, "--inferred", "--report")
        if not gsp or not query or not data:
            raise ValueError("give --gsp, --query (or SPARQL_GSP and SPARQL_QUERY in --env) and the data files")
        base = opts.get("--graph-base", DEFAULT_BASE)
        files = []
        for path in data + [opts["--inferred"]]:
            g = Graph().parse(path, format="nt" if path.endswith(".nt") else "turtle")
            iri = base + "inferred" if path == opts["--inferred"] else graph_iri(g, path, base)
            files.append((path, iri, g))
        if len({iri for _, iri, _ in files}) != len(files):
            raise ValueError("two files map to one graph IRI; pass --graph-base and check the ontology headers")
        export = None
        if opts.get("--projection-report"):
            with open(opts["--projection-report"], encoding="utf-8") as f:
                projection = json.load(f)
            if projection.get("passed") is not True:
                raise ValueError(f"{opts['--projection-report']} does not say passed: true")
            export = projection.get("export_predicate_counts")
            if not isinstance(export, dict):
                raise ValueError(f"{opts['--projection-report']} has no export_predicate_counts")
        questions = [(p, open(p, encoding="utf-8").read()) for p in opts.get("--cq", [])]
    except Exception as exc:  # bad flags, unreadable or unparsable files
        print(f"ERROR {lv.q(exc)}", file=sys.stderr)
        return 2
    store = Store(gsp, query, env.get("SPARQL_USER"), env.get("SPARQL_PASSWORD"))
    report = {"graphs": {}, "store": {"gsp": gsp, "query": query}}
    fails = []
    try:
        for path, iri, g in files:
            status = store.put_graph(iri, build.sorted_nt(g).encode("utf-8"))
            stored = int(store.select(graph_count_query(iri))[0]["n"]["value"])
            report["graphs"][iri] = {"file": path, "put_status": status, "file_triples": len(g), "store_triples": stored}
            if stored != len(g):
                fails.append(f"graph {iri} holds {stored} triples, its file {len(g)}")
        iris = [iri for _, iri, _ in files]
        store_counts = {b["p"]["value"]: int(b["n"]["value"]) for b in store.select(predicate_count_query(iris))}
        file_counts = predicate_counts([g for _, _, g in files])
        report.update({"file_predicate_counts": file_counts, "store_predicate_counts": store_counts})
        fails += compare("store against files", file_counts, store_counts)
        if export is not None:
            report["export_predicate_counts"] = export
            fails += compare("store against the n10s export", export, store_counts)
        report["competency_questions"] = {p: len(store.select(text, iris)) for p, text in questions}
    except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError, KeyError) as exc:
        print(f"FAIL a store request failed: {lv.q(exc)}. No report was written.")
        return 1
    report["failures"] = fails
    report["passed"] = not fails
    for line in fails:
        print(f"FAIL {lv.q(line)}")
    if fails:
        lv.write_atomically(opts["--report"] + ".failed", report)
        print(f"No report was written at {lv.q(opts['--report'])}; the details are in {lv.q(opts['--report'] + '.failed')}.")
        return 1
    lv.write_atomically(opts["--report"], report)
    print(f"loaded {len(files)} named graphs; per-graph, per-predicate"
          + (" and three-way" if export is not None else "") + " counts match")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
