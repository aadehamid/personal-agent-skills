#!/usr/bin/env python3
"""Load RDF releases into a store and prove, by a round trip, that nothing was lost.

Run: uv run --no-project --with pyoxigraph python3 rdfstore.py <command> ...
     (add --with databricks-sql-connector for --store databricks)

Commands:
  skolemize --authority <https://host> --out <dir> <file.ttl>...
      Replace every blank node with an IRI <authority>/.well-known/genid/<id> (RDF 1.1 Concepts, 3.5).
      The id is a hash of the file's graph IRI and the node's RDFC-1.0 canonical label, so the same
      release always gives the same IRIs. Writes <dir>/<file name> as N-Triples-in-Turtle.
  pack [--graph FILE=IRI]... --out <dataset.nq> <file.ttl>...
      One named graph per file, written as N-Quads. A file's graph is the owl:versionIRI of its one
      owl:Ontology, else that ontology's IRI; --graph names it when the file has neither, or to override.
  roundtrip --store fuseki|databricks [store options] [--graph FILE=IRI]... [--report <json>] <file>...
      pack, clear the store's copy, load, export everything back, and compare (below).
  compare <expected.nq> <actual.nq>
      Exit 0 when the two datasets have the same RDFC-1.0 hash, 1 with a readable diff otherwise.

Store options:
  fuseki      --gsp <Graph Store URL> --query <SPARQL query URL> [--update <SPARQL update URL>]
  databricks  --env <file> [--table <name>]   the file holds DATABRICKS_HOST, DATABRICKS_TOKEN,
              DATABRICKS_HTTP_PATH, DATABRICKS_CATALOG, DATABRICKS_SCHEMA (the token is never printed);
              --table defaults to rdf_quads.

The proof is the hash (references/no-loss.md): each dataset is canonicalized with RDFC-1.0
(pyoxigraph's implementation), its quads are written in canonical N-Quads form and sorted, and the
SHA-256 of that text is the dataset's hash. Equal hashes mean isomorphic datasets, blank nodes
included. Counts per graph and per predicate are reported as a quick check only: they can match
while a value differs.

Exit 0 on a pass, 1 when the round trip or a store request failed, 2 on bad input.
"""
import base64
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import pyoxigraph as ox

OWL = "http://www.w3.org/2002/07/owl#"
RDF_TYPE = ox.NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
XSD_STRING = "http://www.w3.org/2001/XMLSchema#string"
RDF_LANGSTRING = "http://www.w3.org/1999/02/22-rdf-syntax-ns#langString"
GENID = "/.well-known/genid/"


class BadInput(Exception):
    pass


# ---- reading and naming ------------------------------------------------------------------

def read_triples(path):
    fmt = ox.RdfFormat.N_TRIPLES if path.endswith(".nt") else ox.RdfFormat.TURTLE
    with open(path, "rb") as f:
        return list(ox.parse(f, format=fmt))


def graph_iri(triples, path):
    """The owl:versionIRI of the file's one owl:Ontology, else that ontology's IRI."""
    ontologies = sorted({t.subject.value for t in triples
                         if t.predicate == RDF_TYPE and t.object == ox.NamedNode(OWL + "Ontology")
                         and isinstance(t.subject, ox.NamedNode)})
    if len(ontologies) != 1:
        raise BadInput(f"{path} has {len(ontologies)} owl:Ontology headers; name its graph with --graph FILE=IRI")
    versions = [t.object.value for t in triples if t.subject.value == ontologies[0]
                and t.predicate == ox.NamedNode(OWL + "versionIRI") and isinstance(t.object, ox.NamedNode)]
    return versions[0] if len(versions) == 1 else ontologies[0]


def parse_graph_options(values):
    named = {}
    for value in values:
        path, sep, iri = value.partition("=")
        if not sep or not iri:
            raise BadInput(f"--graph takes FILE=IRI, got {value}")
        named[os.path.abspath(path)] = iri
    return named


def pack(paths, named=None):
    """A dataset with one named graph per file."""
    named = named or {}
    dataset, seen = ox.Dataset(), {}
    for path in paths:
        triples = read_triples(path)
        iri = named.get(os.path.abspath(path)) or graph_iri(triples, path)
        if iri in seen:
            raise BadInput(f"{path} and {seen[iri]} both map to graph {iri}; name one with --graph")
        seen[iri] = path
        g = ox.NamedNode(iri)
        for t in triples:
            dataset.add(ox.Quad(t.subject, t.predicate, t.object, g))
    return dataset


# ---- skolemization -----------------------------------------------------------------------

def skolemize(triples, graph, authority):
    """Blank nodes to <authority>/.well-known/genid/<id>, with ids that depend only on the graph."""
    ds = ox.Dataset(ox.Quad(t.subject, t.predicate, t.object, ox.DefaultGraph()) for t in triples)
    ds.canonicalize(ox.CanonicalizationAlgorithm.RDFC_1_0)

    def term(node):
        if isinstance(node, ox.BlankNode):
            digest = hashlib.sha256(f"{graph}\n{node.value}".encode()).hexdigest()[:32]
            return ox.NamedNode(authority.rstrip("/") + GENID + digest)
        return node
    return [ox.Triple(term(q.subject), q.predicate, term(q.object)) for q in ds]


# ---- the hash and the diff ---------------------------------------------------------------

def canonical_lines(dataset):
    """The dataset's quads in canonical N-Quads form, RDFC-1.0 labels, sorted (RDFC-1.0, 4.4.3)."""
    ds = ox.Dataset(dataset)
    ds.canonicalize(ox.CanonicalizationAlgorithm.RDFC_1_0)
    return sorted(f"{q} .\n" for q in ds)


def dataset_hash(dataset):
    return hashlib.sha256("".join(canonical_lines(dataset)).encode("utf-8")).hexdigest()


def counts(dataset):
    graphs, predicates = {}, {}
    for q in dataset:
        g = q.graph_name.value if isinstance(q.graph_name, ox.NamedNode) else "(default graph)"
        graphs[g] = graphs.get(g, 0) + 1
        predicates[q.predicate.value] = predicates.get(q.predicate.value, 0) + 1
    return dict(sorted(graphs.items())), dict(sorted(predicates.items()))


def diff(expected, actual, limit=20):
    """Lines missing from and extra in the store's copy. Exact when neither side has blank nodes;
    with blank nodes the labels come from each side's own canonicalization, so a changed blank-node
    neighbourhood can show as one line missing and one extra."""
    exp, act = set(canonical_lines(expected)), set(canonical_lines(actual))
    missing, extra = sorted(exp - act), sorted(act - exp)
    out = [f"{len(missing)} quads missing from the store's copy, {len(extra)} extra"]
    out += ["- " + line.rstrip("\n") for line in missing[:limit]]
    out += ["+ " + line.rstrip("\n") for line in extra[:limit]]
    if len(missing) > limit or len(extra) > limit:
        out.append(f"(first {limit} of each shown)")
    return out


def compare(expected, actual):
    """(passed, report) for two datasets."""
    he, ha = dataset_hash(expected), dataset_hash(actual)
    ge, pe = counts(expected)
    ga, pa = counts(actual)
    report = {"expected_hash": he, "actual_hash": ha, "hashes_equal": he == ha,
              "expected_quads": len(expected), "actual_quads": len(actual),
              "graph_counts": {g: [ge.get(g, 0), ga.get(g, 0)] for g in sorted(set(ge) | set(ga))},
              "predicate_counts_differ": {p: [pe.get(p, 0), pa.get(p, 0)]
                                          for p in sorted(set(pe) | set(pa)) if pe.get(p, 0) != pa.get(p, 0)}}
    if he != ha:
        report["diff"] = diff(expected, actual)
    return he == ha, report


# ---- stores ------------------------------------------------------------------------------

def nt_bytes(dataset, graph):
    return ox.serialize((ox.Triple(q.subject, q.predicate, q.object) for q in dataset.quads_for_graph_name(graph)),
                        format=ox.RdfFormat.N_TRIPLES)


class FusekiStore:
    """Any store that speaks the SPARQL 1.1 Graph Store HTTP Protocol and the SPARQL 1.1 Protocol;
    Jena Fuseki is the default."""

    def __init__(self, gsp, query, update=None, timeout=300):
        self.gsp, self.query_url, self.update_url, self.timeout = gsp, query, update, timeout

    def _request(self, url, method="GET", data=None, headers=None):
        req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return resp.status, resp.read()

    def _graph_url(self, iri):
        return self.gsp + ("&" if "?" in self.gsp else "?") + urllib.parse.urlencode({"graph": iri})

    def graphs(self):
        body = urllib.parse.urlencode({"query": "SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o } }"}).encode()
        _, data = self._request(self.query_url, "POST", body, {"Content-Type": "application/x-www-form-urlencoded",
                                                               "Accept": "application/sparql-results+json"})
        return sorted(b["g"]["value"] for b in json.loads(data)["results"]["bindings"])

    def clear(self, iris):
        for iri in iris:
            try:
                self._request(self._graph_url(iri), "DELETE")
            except urllib.error.HTTPError as exc:
                if exc.code != 404:   # a graph that is not there is already clear
                    raise

    def load(self, dataset):
        for g in sorted({q.graph_name.value for q in dataset if isinstance(q.graph_name, ox.NamedNode)}):
            self._request(self._graph_url(g), "PUT", nt_bytes(dataset, ox.NamedNode(g)),
                          {"Content-Type": "application/n-triples"})

    def export(self):
        """Every named graph the store holds, and its default graph, as one dataset."""
        out = ox.Dataset()
        for iri in self.graphs():
            _, data = self._request(self._graph_url(iri), "GET", headers={"Accept": "application/n-triples"})
            for t in ox.parse(data, format=ox.RdfFormat.N_TRIPLES):
                out.add(ox.Quad(t.subject, t.predicate, t.object, ox.NamedNode(iri)))
        default = self.gsp + ("&" if "?" in self.gsp else "?") + "default"
        _, data = self._request(default, "GET", headers={"Accept": "application/n-triples"})
        for t in ox.parse(data, format=ox.RdfFormat.N_TRIPLES):
            out.add(ox.Quad(t.subject, t.predicate, t.object, ox.DefaultGraph()))
        return out


# The Delta table: N-Quads as columns. object_kind says whether object is an IRI, a blank node or a
# literal, since the same text can be any of the three; a literal's datatype and language tag have
# their own columns; graph is NULL for the default graph. A subject is an IRI or "_:label": an IRI
# always has a scheme, and "_" cannot start one (RFC 3987), so the two cannot be confused.
COLUMNS = ("subject", "predicate", "object", "object_kind", "datatype", "lang", "graph")


def term_text(node):
    return "_:" + node.value if isinstance(node, ox.BlankNode) else node.value


def to_rows(dataset):
    rows = []
    for q in dataset:
        o = q.object
        if isinstance(o, ox.Literal):
            if getattr(o, "direction", None):
                raise BadInput(f"a literal with a base direction cannot be stored in the table: {q}")
            kind, lang = "literal", o.language
            datatype = None if lang else o.datatype.value
        elif isinstance(o, ox.BlankNode):
            kind, datatype, lang = "bnode", None, None
        elif isinstance(o, ox.NamedNode):
            kind, datatype, lang = "iri", None, None
        else:
            raise BadInput(f"a quoted triple cannot be stored in the table: {q}")
        graph = q.graph_name.value if isinstance(q.graph_name, ox.NamedNode) else None
        rows.append((term_text(q.subject), q.predicate.value, o.value, kind, datatype, lang, graph))
    return sorted(rows, key=lambda r: tuple("" if v is None else v for v in r))


def from_rows(rows):
    def node(text):
        return ox.BlankNode(text[2:]) if text.startswith("_:") else ox.NamedNode(text)
    out = ox.Dataset()
    for s, p, o, kind, datatype, lang, graph in rows:
        if kind == "literal":
            obj = ox.Literal(o, language=lang) if lang else ox.Literal(o, datatype=ox.NamedNode(datatype or XSD_STRING))
        elif kind == "bnode":
            obj = ox.BlankNode(o[2:] if o.startswith("_:") else o)
        elif kind == "iri":
            obj = ox.NamedNode(o)
        else:
            raise ValueError(f"unknown object_kind {kind!r}")
        out.add(ox.Quad(node(s), ox.NamedNode(p), obj, ox.NamedNode(graph) if graph else ox.DefaultGraph()))
    return out


def b64(value):
    return "NULL" if value is None else "'" + base64.b64encode(value.encode("utf-8")).decode("ascii") + "'"


def insert_sql(table, rows):
    """One INSERT for a batch of rows. Every value travels base64-encoded and is decoded in SQL, so no
    text from the data is ever parsed as SQL, whatever quotes or backslashes it holds."""
    values = ",\n".join("(" + ", ".join(b64(v) for v in row) + ")" for row in rows)
    decoded = ", ".join(f"decode(unbase64(c{i}), 'UTF-8')" for i in range(len(COLUMNS)))
    names = ", ".join(f"c{i}" for i in range(len(COLUMNS)))
    return f"INSERT INTO {table} ({', '.join(COLUMNS)})\nSELECT {decoded}\nFROM VALUES\n{values}\nAS v({names})"


def create_sql(table):
    return (f"CREATE OR REPLACE TABLE {table} (subject STRING NOT NULL, predicate STRING NOT NULL, "
            "object STRING NOT NULL, object_kind STRING NOT NULL, datatype STRING, lang STRING, graph STRING) "
            "USING DELTA COMMENT 'RDF quads, one row per quad (rdf-store skill)'")


def read_env_file(path):
    values = {}
    with open(path, encoding="utf-8") as f:
        for number, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, sep, value = line.partition("=")
            if not sep:
                raise BadInput(f"{path} line {number} is not KEY=VALUE")
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


class DatabricksStore:
    """A Delta table in Unity Catalog, written and read from this machine over the Databricks SQL
    connector, so it works on Free Edition's serverless warehouse with its outbound limits."""

    BATCH = 2000

    def __init__(self, connection, table):
        self.connection, self.table = connection, table

    @classmethod
    def from_env(cls, env_path, table):
        env = read_env_file(env_path)
        missing = [k for k in ("DATABRICKS_HOST", "DATABRICKS_TOKEN", "DATABRICKS_HTTP_PATH",
                               "DATABRICKS_CATALOG", "DATABRICKS_SCHEMA") if not env.get(k)]
        if missing:
            raise BadInput(f"{env_path} lacks {', '.join(missing)}")
        from databricks import sql
        connection = sql.connect(server_hostname=env["DATABRICKS_HOST"].removeprefix("https://").rstrip("/"),
                                 http_path=env["DATABRICKS_HTTP_PATH"], access_token=env["DATABRICKS_TOKEN"])
        for part in (env["DATABRICKS_CATALOG"], env["DATABRICKS_SCHEMA"], table):
            if not part.replace("_", "").isalnum():
                raise BadInput(f"catalog, schema and table names must be letters, digits and _: {part}")
        return cls(connection, f"{env['DATABRICKS_CATALOG']}.{env['DATABRICKS_SCHEMA']}.{table}")

    def clear(self, iris=None):
        with self.connection.cursor() as cur:
            cur.execute(create_sql(self.table))

    def load(self, dataset):
        rows = to_rows(dataset)
        with self.connection.cursor() as cur:
            for start in range(0, len(rows), self.BATCH):
                cur.execute(insert_sql(self.table, rows[start:start + self.BATCH]))

    def export(self):
        with self.connection.cursor() as cur:
            cur.execute(f"SELECT {', '.join(COLUMNS)} FROM {self.table}")
            return from_rows(tuple(r) for r in cur.fetchall())


# ---- the round trip ----------------------------------------------------------------------

def roundtrip(store, dataset):
    """(passed, report): clear the graphs, load, export everything, compare."""
    started = time.time()
    store.clear(sorted({q.graph_name.value for q in dataset if isinstance(q.graph_name, ox.NamedNode)}))
    store.load(dataset)
    loaded = time.time()
    exported = store.export()
    passed, report = compare(dataset, exported)
    report["seconds"] = {"load": round(loaded - started, 1), "export_and_compare": round(time.time() - loaded, 1)}
    return passed, report


def options(argv, multi=("--graph",)):
    opts, files, i = {k: [] for k in multi}, [], 0
    while i < len(argv):
        arg = argv[i]
        if arg.startswith("--"):
            if i + 1 >= len(argv):
                raise BadInput(f"{arg} needs a value")
            if arg in multi:
                opts[arg].append(argv[i + 1])
            else:
                opts[arg] = argv[i + 1]
            i += 2
        else:
            files.append(arg)
            i += 1
    return opts, files


def main(argv):
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    command, rest = argv[0], argv[1:]
    try:
        opts, files = options(rest)
        if command == "compare":
            if len(files) != 2:
                raise BadInput("compare takes two N-Quads files")
            sides = [ox.Dataset(ox.parse(path=p, format=ox.RdfFormat.N_QUADS)) for p in files]
            passed, report = compare(*sides)
            print(json.dumps(report, indent=2))
            return 0 if passed else 1
        if not files:
            raise BadInput(f"{command} needs input files")
        if command == "skolemize":
            if "--authority" not in opts or "--out" not in opts:
                raise BadInput("skolemize needs --authority and --out")
            named = parse_graph_options(opts["--graph"])
            os.makedirs(opts["--out"], exist_ok=True)
            for path in files:
                triples = read_triples(path)
                g = named.get(os.path.abspath(path)) or graph_iri(triples, path)
                out = os.path.join(opts["--out"], os.path.basename(path))
                with open(out, "wb") as f:
                    f.write(ox.serialize(sorted(skolemize(triples, g, opts["--authority"]), key=str),
                                         format=ox.RdfFormat.N_TRIPLES))
                print(f"wrote {out}")
            return 0
        dataset = pack(files, parse_graph_options(opts["--graph"]))
        if command == "pack":
            if "--out" not in opts:
                raise BadInput("pack needs --out")
            with open(opts["--out"], "wb") as f:
                f.write("".join(sorted(f"{q} .\n" for q in dataset)).encode("utf-8"))
            print(f"wrote {opts['--out']}: {len(dataset)} quads in {len(counts(dataset)[0])} graphs")
            return 0
        if command != "roundtrip":
            raise BadInput(f"unknown command {command}")
        kind = opts.get("--store")
        if kind == "fuseki":
            if "--gsp" not in opts or "--query" not in opts:
                raise BadInput("--store fuseki needs --gsp and --query")
            store = FusekiStore(opts["--gsp"], opts["--query"], opts.get("--update"))
        elif kind == "databricks":
            if "--env" not in opts:
                raise BadInput("--store databricks needs --env")
            store = DatabricksStore.from_env(opts["--env"], opts.get("--table", "rdf_quads"))
        else:
            raise BadInput("--store must be fuseki or databricks")
    except (BadInput, OSError, SyntaxError, ValueError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    try:
        passed, report = roundtrip(store, dataset)
    except Exception as exc:  # a failed request: the store, the network or the warehouse
        print(f"FAIL a store request failed: {type(exc).__name__}: {exc}")
        return 1
    report["store"] = kind
    if opts.get("--report"):
        with open(opts["--report"], "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    print(json.dumps({k: v for k, v in report.items() if k not in ("graph_counts",)}, indent=2))
    print("PASS the store's copy has the same RDFC-1.0 hash" if passed else "FAIL the store's copy differs")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
