#!/usr/bin/env python3
"""Load RDF releases into a store and prove, by a round trip, that nothing was lost.

Run: uv run --no-project --with pyoxigraph python3 rdfstore.py <command> ...
     (add --with databricks-sql-connector for --store databricks)

Inputs: Turtle (.ttl), N-Triples (.nt) or N-Quads (.nq). A Turtle or N-Triples file is one named
graph: the owl:versionIRI of its one owl:Ontology (exactly one distinct value), else that ontology's
IRI; --graph FILE=IRI names it when the file has neither, or overrides it. An N-Quads file keeps its
own graph names and takes no --graph. A default-graph quad is refused: every quad has a named graph.
Blank nodes are standardized apart per input file, so two files that both say _:b0 mean two nodes.

Commands:
  skolemize --authority <https://host> --out <dir> [--graph FILE=IRI]... <file.ttl|.nt>...
      Replace every blank node with <authority>/.well-known/genid/<id> (RDF 1.1 Concepts, 3.5). The id
      hashes the file's graph IRI and the node's RDFC-1.0 label, so the same release always gives the
      same IRIs. Refuses an id that the file already uses as an IRI, and an output path that is an
      input or that two inputs share. Writes <dir>/<file name> as sorted N-Triples.
  pack --out <dataset.nq> [--graph FILE=IRI]... <file>...
      The dataset as sorted N-Quads.
  roundtrip --store fuseki|databricks <store options> [--report <json>] [--graph FILE=IRI]... <file>...
      Publish the dataset to the store, export everything the store holds, and compare (below).
  export --store fuseki|databricks <store options> --out <dataset.nq> [--ttl-dir <dir>]
      Write everything the store holds as sorted N-Quads, and with --ttl-dir one Turtle file per
      named graph (graph-<n>.ttl, listed in <dir>/graphs.tsv with its graph IRI). --out must not
      exist and --ttl-dir must be empty or absent; the outputs are written all together or not at all.
  compare <expected.nq> <actual.nq>
      Exit 0 when the two datasets have the same RDFC-1.0 hash, 1 with a readable diff otherwise.

Store options:
  fuseki      --gsp <Graph Store URL> --query <SPARQL query URL> [--update <SPARQL update URL>]
              With --update the whole dataset is published in one SPARQL Update request, which
              SPARQL 1.1 Update says "SHOULD be treated atomically" (not a guarantee); without it
              each graph is replaced by its own HTTP PUT. Either failure ends the run with exit 1;
              reload the store then. A blank node in two graphs is refused before any request.
  databricks  --env <file> [--table <name>]   the file holds DATABRICKS_HOST, DATABRICKS_TOKEN,
              DATABRICKS_HTTP_PATH, DATABRICKS_CATALOG, DATABRICKS_SCHEMA. --table defaults to
              rdf_quads. The rows go to a staging table of this run's own (<table>__staging_<random>),
              which is exported and compared first; only a staging copy with the same hash replaces
              <table>, in one CREATE OR REPLACE ... AS SELECT, so a failure before that leaves the
              previous table as it was; the staging table is always dropped. The token is never
              printed: it is removed from every message and from the report.

The proof is the hash (references/no-loss.md): each dataset is canonicalized with RDFC-1.0
(pyoxigraph's implementation), its quads are written in canonical N-Quads form and sorted, and the
SHA-256 of that text is the dataset's hash. Equal hashes mean isomorphic datasets, blank nodes
included. Counts per graph and per predicate are reported as a quick check only.

Reports are fail-closed: --report is deleted before anything else, even before the options are
checked; its folder must take a file before any store is touched; it is written, by a rename, when
the comparison ran (passed true or false, with the diff); a failed request leaves none.

Exit 0 on a pass, 1 when the round trip or a store request failed, 2 on bad input. Bad input is
found before any store is touched.
"""
import base64
import hashlib
import json
import os
import sys
import tempfile
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request

import pyoxigraph as ox

OWL = "http://www.w3.org/2002/07/owl#"
RDF_TYPE = ox.NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
XSD_STRING = "http://www.w3.org/2001/XMLSchema#string"
GENID = "/.well-known/genid/"


class BadInput(Exception):
    pass


# ---- reading and naming ------------------------------------------------------------------

def read_quads(path):
    """The file's statements. Triples come back with the default graph; N-Quads keep theirs."""
    if path.endswith(".nq"):
        fmt = ox.RdfFormat.N_QUADS
    elif path.endswith(".nt"):
        fmt = ox.RdfFormat.N_TRIPLES
    else:
        fmt = ox.RdfFormat.TURTLE
    with open(path, "rb") as f:
        out = []
        for s in ox.parse(f, format=fmt):
            g = s.graph_name if isinstance(s, ox.Quad) else ox.DefaultGraph()
            out.append(ox.Quad(s.subject, s.predicate, s.object, g))
        return out


def graph_iri(quads, path):
    """The one distinct owl:versionIRI of the file's one owl:Ontology, else that ontology's IRI."""
    ontologies = sorted({q.subject.value for q in quads
                         if q.predicate == RDF_TYPE and q.object == ox.NamedNode(OWL + "Ontology")
                         and isinstance(q.subject, ox.NamedNode)})
    if len(ontologies) != 1:
        raise BadInput(f"{path} has {len(ontologies)} owl:Ontology headers; name its graph with --graph FILE=IRI")
    versions = sorted({q.object.value for q in quads if q.subject.value == ontologies[0]
                       and q.predicate == ox.NamedNode(OWL + "versionIRI") and isinstance(q.object, ox.NamedNode)})
    if len(versions) > 1:
        raise BadInput(f"{path} gives {len(versions)} owl:versionIRI values; name its graph with --graph FILE=IRI")
    return versions[0] if versions else ontologies[0]


def parse_graph_options(values, files):
    """--graph FILE=IRI, each FILE one of the inputs (same real path), at most once, not N-Quads."""
    inputs = {os.path.realpath(f): f for f in files}
    named = {}
    for value in values:
        path, sep, iri = value.partition("=")
        if not sep or not iri:
            raise BadInput(f"--graph takes FILE=IRI, got {value}")
        real = os.path.realpath(path)
        if real not in inputs:
            raise BadInput(f"--graph names {path}, which is not one of the input files")
        if real in named:
            raise BadInput(f"--graph names {path} twice")
        if path.endswith(".nq") or inputs[real].endswith(".nq"):
            raise BadInput(f"{path} is N-Quads and keeps its own graph names; --graph does not apply")
        named[real] = iri
    return named


def apart(node, scope):
    """A blank node renamed into its input's own scope, so labels from two inputs never meet."""
    return ox.BlankNode(f"f{scope}x{node.value}") if isinstance(node, ox.BlankNode) else node


def check_term(q):
    """Refuse what the stores here cannot hold: RDF 1.2 triple terms and directional literals."""
    for node in (q.subject, q.object):
        if isinstance(node, ox.Triple):
            raise BadInput(f"a triple term cannot be stored: {q}")
        if isinstance(node, ox.Literal) and getattr(node, "direction", None):
            raise BadInput(f"a literal with a base direction cannot be stored: {q}")


def pack(paths, named=None):
    """A dataset with one named graph per Turtle or N-Triples file; N-Quads files keep their graphs."""
    named = named or {}
    dataset, seen = ox.Dataset(), {}
    for scope, path in enumerate(paths):
        quads = read_quads(path)
        if path.endswith(".nq"):
            if any(isinstance(q.graph_name, ox.DefaultGraph) for q in quads):
                raise BadInput(f"{path} has default-graph quads; give every quad a named graph")
            if any(not isinstance(q.graph_name, ox.NamedNode) for q in quads):
                raise BadInput(f"{path} names a graph with a blank node; give every graph an IRI")
            graphs = {q.graph_name.value for q in quads}
        else:
            graphs = {named.get(os.path.realpath(path)) or graph_iri(quads, path)}
        for g in sorted(graphs):
            if g in seen:
                raise BadInput(f"{path} and {seen[g]} both write graph {g}; name one with --graph")
            seen[g] = path
        target = None if path.endswith(".nq") else ox.NamedNode(next(iter(graphs)))
        for q in quads:
            check_term(q)
            dataset.add(ox.Quad(apart(q.subject, scope), q.predicate, apart(q.object, scope), target or q.graph_name))
    return dataset


def shared_blank_nodes(dataset):
    """Blank nodes that occur in more than one graph. A Graph Store Protocol store keeps each graph
    as its own document, so it cannot hold one blank node in two graphs."""
    where = {}
    for q in dataset:
        for n in (q.subject, q.object):
            if isinstance(n, ox.BlankNode):
                where.setdefault(n, set()).add(q.graph_name.value)
    return sorted(n.value for n, gs in where.items() if len(gs) > 1)


# ---- skolemization -----------------------------------------------------------------------

def skolemize(quads, graph, authority):
    """Blank nodes to <authority>/.well-known/genid/<id>, with ids that depend only on the graph.
    Refuses an id the input already uses as an IRI in any position, a literal's datatype included,
    and two blank nodes that would share one; refuses what the stores cannot hold (check_term), so a
    file this step accepts is one the store step accepts too."""
    for q in quads:
        check_term(q)
    ds = ox.Dataset(ox.Quad(q.subject, q.predicate, q.object, ox.DefaultGraph()) for q in quads)
    ds.canonicalize(ox.CanonicalizationAlgorithm.RDFC_1_0)
    taken = set()
    for q in quads:
        for n in (q.subject, q.predicate, q.object, q.graph_name):
            if isinstance(n, ox.NamedNode):
                taken.add(n.value)
            elif isinstance(n, ox.Literal):
                taken.add(n.datatype.value)
    minted = {}

    def term(node):
        if not isinstance(node, ox.BlankNode):
            return node
        iri = authority.rstrip("/") + GENID + hashlib.sha256(f"{graph}\n{node.value}".encode()).hexdigest()[:32]
        if iri in taken:
            raise BadInput(f"the skolem IRI {iri} is already used in the input; pick another --authority")
        if minted.setdefault(iri, node.value) != node.value:
            raise BadInput(f"two blank nodes map to {iri}")
        return ox.NamedNode(iri)
    return [ox.Triple(term(q.subject), q.predicate, term(q.object)) for q in ds]


# ---- the hash and the diff ---------------------------------------------------------------

def canonical_lines(dataset):
    """The dataset's quads in canonical N-Quads form, RDFC-1.0 labels, sorted (RDFC-1.0, 4.4.3)."""
    ds = ox.Dataset(dataset)
    ds.canonicalize(ox.CanonicalizationAlgorithm.RDFC_1_0)
    return sorted(f"{q} .\n" for q in ds)


def lines_hash(lines):
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def dataset_hash(dataset):
    return lines_hash(canonical_lines(dataset))


def counts(dataset):
    graphs, predicates = {}, {}
    for q in dataset:
        g = q.graph_name.value if isinstance(q.graph_name, ox.NamedNode) else "(default graph)"
        graphs[g] = graphs.get(g, 0) + 1
        predicates[q.predicate.value] = predicates.get(q.predicate.value, 0) + 1
    return dict(sorted(graphs.items())), dict(sorted(predicates.items()))


def diff(exp_lines, act_lines, limit=20):
    """Lines missing from and extra in the store's copy. Exact when neither side has blank nodes;
    with blank nodes the labels come from each side's own canonicalization, so a changed blank-node
    neighbourhood can show as one line missing and one extra."""
    exp, act = set(exp_lines), set(act_lines)
    missing, extra = sorted(exp - act), sorted(act - exp)
    out = [f"{len(missing)} quads missing from the store's copy, {len(extra)} extra"]
    out += ["- " + line.rstrip("\n") for line in missing[:limit]]
    out += ["+ " + line.rstrip("\n") for line in extra[:limit]]
    if len(missing) > limit or len(extra) > limit:
        out.append(f"(first {limit} of each shown)")
    return out, len(missing), len(extra)


def compare(expected, actual, expected_lines=None):
    """(passed, report) for two datasets; each side is canonicalized once, and the expected side's
    lines can be passed in when one dataset is compared twice."""
    el = expected_lines if expected_lines is not None else canonical_lines(expected)
    al = canonical_lines(actual)
    he, ha = lines_hash(el), lines_hash(al)
    ge, pe = counts(expected)
    ga, pa = counts(actual)
    report = {"expected_hash": he, "actual_hash": ha, "hashes_equal": he == ha,
              "expected_quads": len(expected), "actual_quads": len(actual),
              "graph_counts": {g: [ge.get(g, 0), ga.get(g, 0)] for g in sorted(set(ge) | set(ga))},
              "predicate_counts_differ": {p: [pe.get(p, 0), pa.get(p, 0)]
                                          for p in sorted(set(pe) | set(pa)) if pe.get(p, 0) != pa.get(p, 0)}}
    if he != ha:
        report["diff"], report["missing"], report["extra"] = diff(el, al)
    return he == ha, report


# ---- stores ------------------------------------------------------------------------------

def nt_bytes(dataset, graph):
    return ox.serialize((ox.Triple(q.subject, q.predicate, q.object) for q in dataset.quads_for_graph_name(graph)),
                        format=ox.RdfFormat.N_TRIPLES)


def named_graphs(dataset):
    return sorted({q.graph_name.value for q in dataset if isinstance(q.graph_name, ox.NamedNode)})


class FusekiStore:
    """Any store that speaks the SPARQL 1.1 Graph Store HTTP Protocol and the SPARQL 1.1 Protocol;
    Jena Fuseki is the default."""

    def __init__(self, gsp, query, update=None, timeout=300):
        self.gsp, self.query_url, self.update_url, self.timeout = gsp, query, update, timeout

    def _request(self, url, method="GET", data=None, headers=None):
        req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return resp.status, resp.read()

    def _graph_url(self, iri=None):
        sep = "&" if "?" in self.gsp else "?"
        return self.gsp + sep + ("default" if iri is None else urllib.parse.urlencode({"graph": iri}))

    def graphs(self):
        body = urllib.parse.urlencode({"query": "SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o } }"}).encode()
        _, data = self._request(self.query_url, "POST", body, {"Content-Type": "application/x-www-form-urlencoded",
                                                               "Accept": "application/sparql-results+json"})
        return sorted(b["g"]["value"] for b in json.loads(data)["results"]["bindings"])

    def publish(self, dataset):
        """Replace each of the dataset's graphs. With an update endpoint, one request does all of them."""
        if self.update_url:
            ops = []
            for g in named_graphs(dataset):
                body = "".join(f"{q.subject} {q.predicate} {q.object} .\n" for q in dataset.quads_for_graph_name(ox.NamedNode(g)))
                ops.append(f"DROP SILENT GRAPH <{g}> ;\nINSERT DATA {{ GRAPH <{g}> {{\n{body}}} }}")
            self._request(self.update_url, "POST", " ;\n".join(ops).encode("utf-8"),
                          {"Content-Type": "application/sparql-update"})
            return
        for g in named_graphs(dataset):
            self._request(self._graph_url(g), "PUT", nt_bytes(dataset, ox.NamedNode(g)),
                          {"Content-Type": "application/n-triples"})

    def export(self):
        """Every named graph the store holds, and its default graph, as one dataset. Each graph is
        its own document, so its blank nodes are standardized apart from every other graph's."""
        out = ox.Dataset()
        sources = [(iri, ox.NamedNode(iri)) for iri in self.graphs()] + [(None, ox.DefaultGraph())]
        for scope, (iri, g) in enumerate(sources):
            _, data = self._request(self._graph_url(iri), "GET", headers={"Accept": "application/n-triples"})
            for t in ox.parse(data, format=ox.RdfFormat.N_TRIPLES):
                out.add(ox.Quad(apart(t.subject, scope), t.predicate, apart(t.object, scope), g))
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
        check_term(q)
        o = q.object
        if isinstance(o, ox.Literal):
            kind, lang = "literal", o.language
            datatype = None if lang else o.datatype.value
        elif isinstance(o, ox.BlankNode):
            kind, datatype, lang = "bnode", None, None
        else:
            kind, datatype, lang = "iri", None, None
        graph = q.graph_name.value if isinstance(q.graph_name, ox.NamedNode) else None
        rows.append((term_text(q.subject), q.predicate.value, term_text(o) if kind == "bnode" else o.value,
                     kind, datatype, lang, graph))
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
        # One staging table per run, so two runs on one live table never verify or promote each
        # other's rows.
        self.staging = f"{table}__staging_{uuid.uuid4().hex[:12]}"

    @staticmethod
    def check_env(env_path, table):
        env = read_env_file(env_path)
        missing = [k for k in ("DATABRICKS_HOST", "DATABRICKS_TOKEN", "DATABRICKS_HTTP_PATH",
                               "DATABRICKS_CATALOG", "DATABRICKS_SCHEMA") if not env.get(k)]
        if missing:
            raise BadInput(f"{env_path} lacks {', '.join(missing)}")
        # The messages name the setting, never its value, which could hold anything, the token included.
        for name, part in (("DATABRICKS_CATALOG", env["DATABRICKS_CATALOG"]), ("DATABRICKS_SCHEMA", env["DATABRICKS_SCHEMA"]), ("--table", table)):
            if not part.replace("_", "").isalnum():
                raise BadInput(f"{name} must be letters, digits and _ only")
        return env

    @classmethod
    def from_env(cls, env, table):
        from databricks import sql
        connection = sql.connect(server_hostname=env["DATABRICKS_HOST"].removeprefix("https://").rstrip("/"),
                                 http_path=env["DATABRICKS_HTTP_PATH"], access_token=env["DATABRICKS_TOKEN"])
        return cls(connection, f"{env['DATABRICKS_CATALOG']}.{env['DATABRICKS_SCHEMA']}.{table}")

    def _export(self, table):
        with self.connection.cursor() as cur:
            cur.execute(f"SELECT {', '.join(COLUMNS)} FROM {table}")
            return from_rows(tuple(r) for r in cur.fetchall())

    def stage(self, rows):
        with self.connection.cursor() as cur:
            cur.execute(create_sql(self.staging))
            for start in range(0, len(rows), self.BATCH):
                cur.execute(insert_sql(self.staging, rows[start:start + self.BATCH]))

    def promote(self):
        with self.connection.cursor() as cur:
            cur.execute(f"CREATE OR REPLACE TABLE {self.table} AS SELECT * FROM {self.staging}")

    def drop_staging(self):
        with self.connection.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {self.staging}")

    def export(self):
        return self._export(self.table)


# ---- the round trip ----------------------------------------------------------------------

def roundtrip(store, dataset):
    """(passed, report). Validates the whole dataset before the store is touched."""
    started = time.time()
    report = {}
    if isinstance(store, DatabricksStore):
        rows = to_rows(dataset)   # BadInput here leaves the store untouched
        expected = canonical_lines(dataset)
        try:
            store.stage(rows)
            passed, staged = compare(dataset, store._export(store.staging), expected)
            report["staging"] = {"hashes_equal": passed}
            if not passed:
                report.update(staged)
                report["published"] = False
                return False, report
            store.promote()
        finally:
            store.drop_staging()
    else:
        for q in dataset:
            check_term(q)
        shared = shared_blank_nodes(dataset)
        if shared:
            raise BadInput(f"{len(shared)} blank nodes occur in more than one graph, which a Graph Store "
                           "Protocol store cannot hold; skolemize them or keep each in one graph")
        expected = None
        store.publish(dataset)
    loaded = time.time()
    passed, result = compare(dataset, store.export(), expected)
    report.update(result)
    report["published"] = True
    report["seconds"] = {"load": round(loaded - started, 1), "export_and_compare": round(time.time() - loaded, 1)}
    return passed, report


# ---- the command line --------------------------------------------------------------------

ALLOWED = {
    "skolemize": {"--authority", "--out", "--graph"},
    "pack": {"--out", "--graph"},
    "roundtrip": {"--store", "--gsp", "--query", "--update", "--env", "--table", "--report", "--graph"},
    "export": {"--store", "--gsp", "--query", "--env", "--table", "--out", "--ttl-dir"},
    "compare": set(),
}


def options(command, argv):
    if command not in ALLOWED:
        raise BadInput(f"unknown command {command}")
    opts, files, i = {"--graph": []}, [], 0
    while i < len(argv):
        arg = argv[i]
        if arg.startswith("--"):
            if arg not in ALLOWED[command]:
                raise BadInput(f"{command} does not take {arg}")
            if i + 1 >= len(argv):
                raise BadInput(f"{arg} needs a value")
            if arg == "--graph":
                opts[arg].append(argv[i + 1])
            elif arg in opts:
                raise BadInput(f"{arg} given twice")
            else:
                opts[arg] = argv[i + 1]
            i += 2
        else:
            files.append(arg)
            i += 1
    return opts, files


def redact(text, secrets):
    for s in secrets:
        if s:
            text = text.replace(s, "[redacted]")
    return text


def redact_all(value, secrets):
    """The value with every secret removed from every string in it, however deep."""
    if isinstance(value, str):
        return redact(value, secrets)
    if isinstance(value, dict):
        return {redact_all(k, secrets): redact_all(v, secrets) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_all(v, secrets) for v in value]
    return value


def write_atomically(path, data, tmp=None):
    """Write by rename; a temporary file left by a failed write or rename is removed."""
    if tmp is None:
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), prefix=".rdfstore.")
        os.close(fd)
    try:
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def publish_all(outputs, new_folder=None):
    """Write every (path, make_bytes) output, or none of them. Each is written to a temporary file
    beside its path first; only when all are written are they renamed into place. If a write fails,
    the temporary files go; if a rename fails, so do the outputs this call already published, and a
    folder it created."""
    created = bool(new_folder) and not os.path.exists(new_folder)
    if created:
        os.makedirs(new_folder)
    staged, published = [], []
    try:
        for path, make in outputs:
            fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), prefix=".rdfstore.")
            os.close(fd)
            staged.append((tmp, path))
            with open(tmp, "wb") as f:
                f.write(make())
        for tmp, path in staged:
            os.replace(tmp, path)
            published.append(path)
    except BaseException:
        for path in published:
            if os.path.exists(path):
                os.remove(path)
        if created and os.path.isdir(new_folder):
            for name in os.listdir(new_folder):
                if name.startswith(".rdfstore."):
                    os.remove(os.path.join(new_folder, name))
            if not os.listdir(new_folder):
                os.rmdir(new_folder)
        raise
    finally:
        for tmp, _ in staged:
            if os.path.exists(tmp):
                os.remove(tmp)


def report_paths(argv):
    """Every value given to --report, read before the full parse so a bad option cannot keep an old report."""
    return [argv[i + 1] for i, a in enumerate(argv[:-1]) if a == "--report"]


def refuse_aliases(outputs, protected):
    """Every output path is distinct, and none is an input or the credential file."""
    real_out = [os.path.realpath(p) for p in outputs]
    if len(set(real_out)) != len(real_out):
        raise BadInput("two outputs share one path; give the inputs distinct file names or separate runs")
    clash = set(real_out) & {os.path.realpath(p) for p in protected}
    if clash:
        raise BadInput(f"an output would overwrite an input or the credential file: {sorted(clash)[0]}")


def store_from(opts, secrets):
    """The store kind and a factory for it. A Databricks token joins `secrets` as soon as the env file
    is read, before anything that could print a message."""
    kind = opts.get("--store")
    if kind == "fuseki":
        if "--gsp" not in opts or "--query" not in opts or "--env" in opts or "--table" in opts:
            raise BadInput("--store fuseki takes --gsp, --query and optionally --update")
        return kind, lambda: FusekiStore(opts["--gsp"], opts["--query"], opts.get("--update"))
    if kind == "databricks":
        if "--env" not in opts or any(k in opts for k in ("--gsp", "--query", "--update")):
            raise BadInput("--store databricks takes --env and optionally --table")
        token = read_env_file(opts["--env"]).get("DATABRICKS_TOKEN")
        if token:
            secrets.append(token)
        env = DatabricksStore.check_env(opts["--env"], opts.get("--table", "rdf_quads"))
        return kind, lambda: DatabricksStore.from_env(env, opts.get("--table", "rdf_quads"))
    raise BadInput("--store must be fuseki or databricks")


def nquads_text(dataset):
    return "".join(sorted(f"{q} .\n" for q in dataset)).encode("utf-8")


def main(argv):
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    command, rest = argv[0], argv[1:]
    secrets, report_tmp = [], None
    try:
        # An old report goes before anything can fail, unless the path is also another argument
        # (an input or the env file), which the parse below refuses.
        for path in report_paths(rest):
            others = {os.path.realpath(a) for a in rest if a != path and os.path.exists(a)}
            if os.path.realpath(path) not in others and os.path.isfile(path):
                os.remove(path)
        opts, files = options(command, rest)
        report_path = opts.get("--report")
        if report_path:
            refuse_aliases([report_path], files + ([opts["--env"]] if "--env" in opts else []))
            # The report's folder must take a file before any store is touched.
            fd, report_tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(report_path)), prefix=".rdfstore.")
            os.close(fd)
        if command == "compare":
            if len(files) != 2:
                raise BadInput("compare takes two N-Quads files")
            sides = [ox.Dataset(ox.parse(path=p, format=ox.RdfFormat.N_QUADS)) for p in files]
            passed, report = compare(*sides)
            print(json.dumps(report, indent=2))
            return 0 if passed else 1
        if command == "export":
            if files or "--out" not in opts:
                raise BadInput("export takes --out and no input files")
            if os.path.lexists(opts["--out"]):
                # A failed export removes what it wrote, so it must never have replaced an older file.
                raise BadInput(f"{opts['--out']} already exists; export writes only a new file")
            kind, make = store_from(opts, secrets)
            ttl = opts.get("--ttl-dir")
            if ttl and os.path.exists(ttl) and (not os.path.isdir(ttl) or os.listdir(ttl)):
                raise BadInput("--ttl-dir must be an empty folder or not exist yet, so no old graph file stays beside the new ones")
            refuse_aliases([opts["--out"]], [opts["--env"]] if "--env" in opts else [])
        else:
            if not files:
                raise BadInput(f"{command} needs input files")
            named = parse_graph_options(opts["--graph"], files)
        if command == "skolemize":
            if "--authority" not in opts or "--out" not in opts:
                raise BadInput("skolemize needs --authority and --out")
            outs = [os.path.join(opts["--out"], os.path.basename(p)) for p in files]
            refuse_aliases(outs, files)
            minted = []
            for path, out in zip(files, outs):
                if path.endswith(".nq"):
                    raise BadInput(f"skolemize takes Turtle or N-Triples, one graph per file: {path}")
                quads = read_quads(path)
                g = named.get(os.path.realpath(path)) or graph_iri(quads, path)
                minted.append((out, skolemize(quads, g, opts["--authority"])))
            os.makedirs(opts["--out"], exist_ok=True)
            for out, triples in minted:
                write_atomically(out, ox.serialize(sorted(triples, key=str), format=ox.RdfFormat.N_TRIPLES))
                print(f"wrote {out}")
            return 0
        if command == "pack":
            if "--out" not in opts:
                raise BadInput("pack needs --out")
            refuse_aliases([opts["--out"]], files)
            dataset = pack(files, named)
            write_atomically(opts["--out"], nquads_text(dataset))
            print(f"wrote {opts['--out']}: {len(dataset)} quads in {len(counts(dataset)[0])} graphs")
            return 0
        if command == "roundtrip":
            kind, make = store_from(opts, secrets)
            dataset = pack(files, named)
            if kind == "databricks":
                to_rows(dataset)
            elif shared_blank_nodes(dataset):
                raise BadInput("blank nodes occur in more than one graph, which a Graph Store Protocol store "
                               "cannot hold; skolemize them or keep each in one graph")
    except (BadInput, OSError, SyntaxError, ValueError) as exc:
        print(f"ERROR {redact(str(exc), secrets)}", file=sys.stderr)
        if report_tmp and os.path.exists(report_tmp):
            os.remove(report_tmp)
        return 2
    try:
        store = make()
        if command == "export":
            exported = store.export()
            graphs = named_graphs(exported)
            ttl = opts.get("--ttl-dir")
            side = [os.path.join(ttl, f"graph-{n}.ttl") for n in range(1, len(graphs) + 1)] + [os.path.join(ttl, "graphs.tsv")] if ttl else []
            refuse_aliases([opts["--out"]] + side, [opts["--env"]] if "--env" in opts else [])
            outputs = [(opts["--out"], lambda: nquads_text(exported))]
            if ttl:
                for path, g in zip(side, graphs):
                    triples = [ox.Triple(q.subject, q.predicate, q.object) for q in exported.quads_for_graph_name(ox.NamedNode(g))]
                    outputs.append((path, lambda t=triples: ox.serialize(t, format=ox.RdfFormat.TURTLE)))
                index = "".join(f"{os.path.basename(path)}\t{g}\n" for path, g in zip(side, graphs))
                outputs.append((side[-1], lambda: index.encode("utf-8")))
            publish_all(outputs, ttl)
            print(f"wrote {opts['--out']}: {len(exported)} quads in {len(graphs)} graphs")
            return 0
        passed, report = roundtrip(store, dataset)
        report["store"] = kind
        report = redact_all(report, secrets)
        if report_tmp:
            write_atomically(opts["--report"], json.dumps(report, indent=2).encode("utf-8"), report_tmp)
    except BadInput as exc:
        print(f"ERROR {redact(str(exc), secrets)}", file=sys.stderr)
        return 2
    except Exception as exc:  # a failed request (the store, the network, the warehouse) or a local write
        print(f"FAIL a store request or write failed: {type(exc).__name__}: {redact(str(exc), secrets)}. No report was written.")
        return 1
    finally:
        if report_tmp and os.path.exists(report_tmp):
            os.remove(report_tmp)
    print(json.dumps({k: v for k, v in report.items() if k != "graph_counts"}, indent=2))
    print("PASS the store's copy has the same RDFC-1.0 hash" if passed else "FAIL the store's copy differs")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
