#!/usr/bin/env python3
"""Run the projection, every store and every check from one run configuration, so no project needs
its own scripts around this skill's.

    uv run --no-project --with rdflib python3 run_projection.py --config <run.json> [--only a,b] [--skip a,b]
    uv run --no-project --with rdflib python3 run_projection.py --config <run.json> --plan
    uv run --no-project --with rdflib python3 run_projection.py compare-triples <rebuild out> <baseline out>
    uv run --no-project --with rdflib python3 run_projection.py compare-reports <rebuild report> <baseline report>

The steps, in this order (references/run-config.md has the run configuration and every check):
  project      check the rules and pins, validate, reason with ELK through ROBOT (its SHA-256 checked
               first), serialise, check and validate the serialised files, write the manifest, and the
               advisory in-graph shapes (steps 2 to 4, checks V1 to V5)
  load         start Neo4j with n10s from docker/compose.yaml, run load_verify.py, then build.py
               check-report (steps 5 and 6, V6 to V12); a failure removes the container
  review       model_review.py on the local Neo4j
  tags         module_tags.py tag, check and modules on the local Neo4j (add-on F)
  release-record  release_record.py records, write and check: one :ModuleRelease node per module on the
               local Neo4j, from catalog.ttl, shapes.ttl and the report; releases mode only
  graph-type   build.py graph-type (add-on H); it applies nothing
  triplestore  triplestore.py: the inputs in Jena Fuseki, counts tied to the report (add-on J)
  copy         copy_graph.py to the target env file (add-on I; the hash must match), then the tag
               check, the module graph, the release records and model_review.py there
  jena         the rdf-store skill's roundtrip of the release (data plus its release graphs) through
               Jena Fuseki: the store's export must hash equal to the files (RDFC-1.0)
  databricks   the same roundtrip through a Databricks Delta table (add-on K)
  explore      the inputs and inferred.nt in Jena Fuseki, then explore.py compare against the local
               Neo4j and, when this run copied, the target: every saved walk and the module map (add-on F)
  rebuild      export the release from a store (jena or databricks) or take the repository files, run
               project and load on them into another output folder, require loadable.nt and
               inferred.nt to hold this run's triples (RDF 1.1 terms) and the report's two graph hashes
               to equal this run's, then tag, write the release records, copy (when configured) and explore
A step whose configuration is absent is skipped and says so; --only and --skip name steps by the
names above. --plan prints the steps that would run and runs nothing. The local Neo4j is removed when
the run ends, pass or fail, unless the configuration sets "keep_neo4j"; every Fuseki is removed, except
that "keep_jena" leaves the jena step's Fuseki running, loaded, once its round trip has passed.

Secrets: the local Neo4j password is generated, written only to <out>/neo4j-run/run.env (mode 600)
and passed to the scripts in their environment; the target and Databricks env files are passed by
path, never read here. Every printed value goes through shell.q.

compare-triples and compare-reports are the rebuild's two checks, runnable on their own. Exit codes:
0 every step passed, 1 a step or check failed, 2 bad configuration or arguments.
"""
import csv
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request

from shell import Refusal, error_line, q

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
STEPS = ("project", "load", "review", "tags", "release-record", "graph-type", "triplestore", "copy", "jena", "databricks",
         "explore", "rebuild")
# references/running.md, rule 2
ROBOT_SHA256 = "16a73c074f3df359a7338a84b4e0788785fe06117f931bb9796e9619ea776105"
INFERRED_GRAPH = "urn:ontology-to-lpg:inferred"
RECORDS = "release-records.json"   # the run's release records (release_record.py)
MODES = ("releases", "files")
# The ontology skill's guided walk-through that packages an ontology as releases.
PACKAGING = "skills/data/ontology/scripts/build_package.py"
# Files mode: the RDF files rdfstore.py reads as one graph each, and the graph name of a file with no
# owl:versionIRI and no graphs entry (its path relative to the run configuration, percent-encoded).
RDF_SUFFIXES = (".ttl", ".nt")
FILE_GRAPH = "urn:ontology-to-lpg:file:"
# The graph hashes of the sorted and shuffled loads (load_verify.py's report); both reports must hold
# exactly these hash fields, so a changed report cannot skip one.
REPORT_HASHES = ("determinism_hash_sorted", "determinism_hash_shuffled")
PY = ("uv", "run", "-q", "--no-project", "--with", "rdflib", "--with", "pyshacl", "--with", "neo4j", "python3")
RS = ("uv", "run", "-q", "--no-project", "--with", "pyoxigraph", "--with", "databricks-sql-connector", "python3")
DEFAULTS = {"neo4j": {"compose_project": "lpg-local", "bolt_port": 17711},
            "jena": {"compose_project": "lpg-jena", "port": 13031},
            "explore_fuseki": {"compose_project": "lpg-explore", "port": 13032},
            "triplestore_fuseki": {"compose_project": "lpg-triplestore", "port": 13030}}


class Failed(Exception):
    """A step or check failed; the message says which."""


class NoMode(Refusal):
    """The run configuration names no mode: the user chooses one first (print_choice)."""


def print_choice():
    print("Choose what to project, and set \"mode\" in the run configuration:")
    print("  releases (recommended): versioned packages, each with an owl:versionIRI and its pinned requirements.")
    print("    + the pins and the closure of requirements are checked, every node is tagged with its release,")
    print("      the module graph shows what requires what, and a store copy traces back to a release")
    print("    - you need packages first; the ontology skill's guided packaging walk-through builds them")
    print(f"      ({q(PACKAGING)})")
    print("  files: any Turtle or N-Triples files or folders, as they are.")
    print("    + works on what you have now, with the same loads, hashes, round trips and rebuild")
    print("    - no version pins or closure check; graph names come from owl:versionIRI, the graphs mapping or")
    print("      the file name; without SHACL shapes the projection uses defaults derived from the data")


# The run configuration --------------------------------------------------------------------------

def read_config(path):
    """The run configuration with every path made absolute against the configuration's own folder."""
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    if not isinstance(cfg, dict):
        raise Refusal("the run configuration is not a JSON object")
    base = os.path.dirname(os.path.abspath(path))

    def path_of(value):
        if not isinstance(value, str) or not value:
            raise Refusal("a path in the run configuration is not a non-empty string")
        return os.path.normpath(os.path.join(base, os.path.expanduser(value)))

    known = {"mode", "projection_config", "data", "shapes", "releases", "inputs_script", "files", "graphs", "out",
             "robot_jar", "manual_cases", "release_graphs", "queries", "target_env", "replace_target", "databricks",
             "rdf_store", "rebuild", "keep_neo4j", "keep_jena", "separator"} | set(DEFAULTS)
    unknown = sorted(set(cfg) - known)
    if unknown:
        raise Refusal("the run configuration has a key it does not know; references/run-config.md lists them")
    if cfg.get("mode") not in MODES:
        raise NoMode("the run configuration needs \"mode\": \"releases\" or \"files\"")
    for key in ("projection_config", "out"):
        if key not in cfg:
            raise Refusal(f"the run configuration lacks {key}")
    cfg["base"] = base
    for key in ("projection_config", "out", "releases", "inputs_script", "robot_jar", "manual_cases",
                "queries", "target_env", "rdf_store"):
        if key in cfg:
            cfg[key] = path_of(cfg[key])
    for key in ("data", "shapes", "files"):
        if key in cfg:
            if not isinstance(cfg[key], list) or not cfg[key]:
                raise Refusal(f"{key} must be a non-empty list of paths")
            cfg[key] = [path_of(p) for p in cfg[key]]
    if cfg["mode"] == "releases":
        if "files" in cfg or "graphs" in cfg:
            raise Refusal("files and graphs belong to files mode")
        if ("inputs_script" in cfg) == ("data" in cfg or "shapes" in cfg):
            raise Refusal("give either inputs_script or data and shapes")
        if not has_releases(cfg.get("releases")):
            raise Refusal("releases mode needs the folder of released packages (releases/<module>/<X.Y.Z>/), and "
                          f"none was found. Build them with the ontology skill's guided packaging walk-through "
                          f"({PACKAGING}), or set \"mode\": \"files\"")
    else:
        for key in ("data", "inputs_script", "releases", "release_graphs"):
            if key in cfg:
                raise Refusal(f"{key} belongs to releases mode; files mode takes files, graphs and shapes")
        if "files" not in cfg:
            raise Refusal("files mode needs files: RDF files or folders")
        graphs = cfg.get("graphs", {})
        if not isinstance(graphs, dict) or not all(isinstance(v, str) and ":" in v for v in graphs.values()):
            raise Refusal("graphs must map a file to a graph IRI")
        cfg["graphs"] = {path_of(k): v for k, v in graphs.items()}
    if "databricks" in cfg:
        d = cfg["databricks"]
        if not isinstance(d, dict) or set(d) != {"env", "table"}:
            raise Refusal("databricks takes exactly env and table")
        cfg["databricks"] = {"env": path_of(d["env"]), "table": str(d["table"])}
    if "rebuild" in cfg:
        r = cfg["rebuild"]
        if not isinstance(r, dict) or set(r) != {"source", "out"} or r["source"] not in ("repo", "jena", "databricks"):
            raise Refusal("rebuild takes exactly source (repo, jena or databricks) and out")
        cfg["rebuild"] = {"source": r["source"], "out": path_of(r["out"])}
        if r["source"] == "databricks" and "databricks" not in cfg:
            raise Refusal("a rebuild from databricks needs the databricks key")
        if cfg["rebuild"]["out"] == cfg["out"]:
            raise Refusal("rebuild.out must differ from out")
    graphs = cfg.setdefault("release_graphs", [])
    if not isinstance(graphs, list) or not all(isinstance(g, str) and g and "/" not in g for g in graphs):
        raise Refusal("release_graphs must be a list of file names without .ttl, such as shapes")
    if "separator" in cfg:
        # The rule the scripts apply (build.separator), checked here so --plan and every step refuse it first.
        import build
        try:
            build.separator({"--separator": cfg["separator"]})
        except Refusal:
            raise Refusal("separator must be a non-empty string of underscores only, such as \"_\"") from None
    for key, default in DEFAULTS.items():
        cfg[key] = {**default, **cfg.get(key, {})}
    cfg.setdefault("rdf_store", os.path.join(os.path.dirname(SKILL), "rdf-store"))
    for out in (cfg["out"], cfg.get("rebuild", {}).get("out")):
        if out and inside_repository(out, base):
            raise Refusal("out and rebuild.out must be outside the repository that holds the configuration")
    return cfg


# The variables Git sets for a hook. Inherited, they change which repository git answers for (with
# GIT_WORK_TREE set too, the hook's worktree instead of the folder it is pointed at), so a repository check
# run from a pre-push hook could look at the wrong one; `git init` under them re-initialises the hook's
# repository, which is how the shared checkout became bare.
HOOK_GIT_VARS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_PREFIX")


def git_env():
    """The environment without the variables Git sets for a hook."""
    return {k: v for k, v in os.environ.items() if k not in HOOK_GIT_VARS}


def inside_repository(out, base):
    try:
        top = subprocess.run(["git", "-C", base, "rev-parse", "--show-toplevel"], capture_output=True,
                             text=True, check=True, stdin=subprocess.DEVNULL, env=git_env()).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return False
    top = os.path.realpath(top)
    probe = os.path.realpath(out)
    return probe == top or probe.startswith(top + os.sep)


def plan(cfg, only=None, skip=()):
    """(step, reason) pairs: reason None means the step runs."""
    needs = {"project": "robot_jar", "copy": "target_env", "databricks": "databricks", "explore": "queries",
             "rebuild": "rebuild"}
    rows = []
    for step in STEPS:
        if only is not None and step not in only:
            rows.append((step, "not in --only"))
        elif step in skip:
            rows.append((step, "--skip"))
        elif step in needs and needs[step] not in cfg:
            rows.append((step, f"no {needs[step]} in the run configuration"))
        elif step == "release-record" and cfg["mode"] == "files":
            rows.append((step, "files mode has no catalog.ttl to read"))
        else:
            rows.append((step, None))
    return rows


def step_names(text):
    names = [s for s in text.split(",") if s]
    bad = [s for s in names if s not in STEPS]
    if bad or not names:
        raise Refusal(f"an unknown step name; the steps are {', '.join(STEPS)}")
    return set(names)


# Inputs, release graphs and the rebuild's input list -----------------------------------------------

def version_iri(path):
    from rdflib import Graph
    from rdflib.namespace import OWL, RDF
    g = Graph().parse(path)
    found = {str(v) for s in g.subjects(RDF.type, OWL.Ontology) for v in g.objects(s, OWL.versionIRI)}
    if len(found) != 1:
        raise Failed(f"{os.path.basename(path)}: expected one owl:versionIRI")
    return found.pop()


def has_releases(folder):
    """True when the folder holds at least one released package, <module>/<X.Y.Z>/."""
    import re
    if not folder or not os.path.isdir(folder):
        return False
    for module in os.listdir(folder):
        path = os.path.join(folder, module)
        if os.path.isdir(path) and any(re.fullmatch(r"\d+\.\d+\.\d+", v) and os.path.isdir(os.path.join(path, v))
                                       for v in os.listdir(path)):
            return True
    return False


def file_version_iri(path):
    """The file's one owl:versionIRI, or None when it has none; two distinct values refuse."""
    from rdflib import Graph
    from rdflib.namespace import OWL, RDF
    g = Graph().parse(path)
    found = {str(v) for s in g.subjects(RDF.type, OWL.Ontology) for v in g.objects(s, OWL.versionIRI)}
    if len(found) > 1:
        raise Failed(f"{os.path.basename(path)}: more than one owl:versionIRI")
    return found.pop() if found else None


def expand_files(paths):
    """Files mode: each listed file, and every .ttl and .nt file under each listed folder, in path order."""
    out = []
    for path in paths:
        if os.path.isdir(path):
            found = sorted(os.path.join(d, f) for d, _, names in os.walk(path) for f in names if f.endswith(RDF_SUFFIXES))
            if not found:
                raise Failed(f"no .ttl or .nt file under {os.path.basename(path)}")
            out += found
        elif os.path.isfile(path) and path.endswith(RDF_SUFFIXES):
            out.append(path)
        else:
            raise Failed(f"{os.path.basename(path)} is neither a folder nor a .ttl or .nt file")
    if len(set(out)) != len(out):
        raise Failed("a file is listed twice in files")
    return out


def graph_names(files, mapping, base):
    """Files mode: {file: (graph IRI, where the name came from)}. A file's owl:versionIRI names it; else
    its entry in the graphs mapping; else its path relative to the run configuration's folder, as
    FILE_GRAPH plus the percent-encoded path. A mapping entry for a file with an owl:versionIRI, or for
    a file not listed, refuses, as do two files with one graph name."""
    stray = sorted(set(mapping) - set(files))
    if stray:
        raise Failed(f"graphs names a file that files does not list: {os.path.basename(stray[0])}")
    names = {}
    for path in files:
        v = file_version_iri(path)
        if v is not None and path in mapping:
            raise Failed(f"{os.path.basename(path)} has an owl:versionIRI, which names its graph; drop its graphs entry")
        if v is not None:
            names[path] = (v, "owl:versionIRI")
        elif path in mapping:
            names[path] = (mapping[path], "graphs")
        else:
            names[path] = (FILE_GRAPH + urllib.parse.quote(os.path.relpath(path, base), safe="/"), "file name")
    taken = [g for g, _ in names.values()]
    if len(set(taken)) != len(taken):
        raise Failed("two files would have the same graph name; name one in graphs")
    return names


# Namespaces whose classes are vocabulary, not data: no default shape targets them.
VOCABULARY = ("http://www.w3.org/1999/02/22-rdf-syntax-ns#", "http://www.w3.org/2000/01/rdf-schema#",
              "http://www.w3.org/2002/07/owl#", "http://www.w3.org/ns/shacl#", "http://www.w3.org/2001/XMLSchema#")


def default_shapes(paths, inverse=None):
    """Files mode without shapes: one sh:NodeShape per class the data types a node with (outside the RDF,
    RDFS, OWL, SHACL and XSD namespaces), and for each predicate its instances use, a property shape
    with the counts the data shows over the class's instances, its subclasses' included: sh:maxCount the most values one instance has, and sh:minCount 1 when
    every instance has one. inverse maps a class IRI to predicate IRIs (the inverse ends of the
    qualified-relation classes the projection configuration registers, which Rule 4a requires a shape
    for): each gets a property shape on sh:inversePath, counted the same way. The data conforms by
    construction; the shapes give the load's gates (the compiled rows, a fail case each, the mutant)
    something to check. Returns (graph, node shapes)."""
    from rdflib import BNode, Graph, Literal, Namespace, URIRef
    from rdflib.namespace import RDF, RDFS, XSD
    SH = Namespace("http://www.w3.org/ns/shacl#")
    data = Graph()
    for path in paths:
        data.parse(path)
    shapes = Graph()
    shapes.bind("sh", SH)
    classes = sorted({o for o in data.objects(None, RDF.type)
                      if isinstance(o, URIRef) and not str(o).startswith(VOCABULARY)})
    for c in classes:
        # sh:targetClass reaches the instances of every subclass too (SHACL 2.1.3.1)
        sub = set(data.transitive_subjects(RDFS.subClassOf, c))
        instances = sorted({s for k in sub for s in data.subjects(RDF.type, k) if isinstance(s, URIRef)})
        counts, back = {}, {}
        for s in instances:
            for pred in set(data.predicates(s)) - {RDF.type}:
                counts.setdefault(pred, []).append(len(set(data.objects(s, pred))))
            for pred in (inverse or {}).get(str(c), []):
                n = len(set(data.subjects(URIRef(pred), s)))
                if n:
                    back.setdefault(URIRef(pred), []).append(n)
        node = URIRef("urn:ontology-to-lpg:default-shape:" + urllib.parse.quote(str(c), safe=""))
        shapes.add((node, RDF.type, SH.NodeShape))
        shapes.add((node, SH.targetClass, c))
        for pred in sorted(counts):
            prop = BNode()
            shapes.add((node, SH.property, prop))
            shapes.add((prop, SH.path, pred))
            shapes.add((prop, SH.maxCount, Literal(max(counts[pred]), datatype=XSD.integer)))
            if len(counts[pred]) == len(instances):
                shapes.add((prop, SH.minCount, Literal(1, datatype=XSD.integer)))
        for pred in sorted(back):
            prop, path = BNode(), BNode()
            shapes.add((node, SH.property, prop))
            shapes.add((prop, SH.path, path))
            shapes.add((path, SH.inversePath, pred))
            shapes.add((prop, SH.maxCount, Literal(max(back[pred]), datatype=XSD.integer)))
            if len(back[pred]) == len(instances):
                shapes.add((prop, SH.minCount, Literal(1, datatype=XSD.integer)))
    return shapes, len(classes)


def inverse_ends(projection_config):
    """{class IRI: [inverse end IRIs]} from the projection configuration's qualified_relations, CURIEs
    expanded by its prefixes."""
    with open(projection_config, encoding="utf-8") as f:
        raw = json.load(f)
    prefixes = raw.get("prefixes", {})

    def expand(term):
        prefix, sep, local = term.partition(":")
        return prefixes[prefix] + local if sep and prefix in prefixes else term
    return {expand(r["class"]): [expand(e) for e in r.get("inverse_ends", [])]
            for r in raw.get("qualified_relations", [])}


def sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def release_graph_args(data, names):
    """rdfstore.py arguments for the release: each data file, and beside it <name>.ttl for each name in
    release_graphs, named <version IRI>/<name>."""
    args = []
    for path in data:
        args.append(path)
        v = version_iri(path)
        for name in names:
            extra = os.path.join(os.path.dirname(path), name + ".ttl")
            if not os.path.isfile(extra):
                raise Failed(f"release graph {name}.ttl is missing beside {os.path.basename(path)}")
            args += ["--graph", f"{extra}={v}/{name}", extra]
    return args


def input_list(export_dir, data, shapes, names, graph_of=None):
    """The rebuild's inputs from a store export (rdfstore.py export --ttl-dir: graph files listed in
    graphs.tsv): a data file maps to the graph named by its owl:versionIRI, a release graph's shapes
    file (<name>.ttl beside a data file, name in release_graphs) to <version IRI>/<name>. A shapes file
    that is no release graph was never in the store and is read from the repository; it is marked so.
    In files mode, graph_of gives each data file's graph name and names is empty. Raises Failed when an
    expected graph is missing from the export."""
    with open(os.path.join(export_dir, "graphs.tsv"), encoding="utf-8") as f:
        by_graph = {row[1]: os.path.join(export_dir, row[0]) for row in csv.reader(f, delimiter="\t") if row}
    rows, versions = [], {}
    for path in data:
        v = graph_of[path] if graph_of else version_iri(path)
        versions[os.path.dirname(path)] = v
        if v not in by_graph:
            raise Failed(f"the export has no graph {v}")
        rows.append(("data", by_graph[v], False))
    for path in shapes:
        v = versions.get(os.path.dirname(path))
        name = os.path.basename(path)[:-len(".ttl")] if path.endswith(".ttl") else None
        if v is not None and name in names:
            if f"{v}/{name}" not in by_graph:
                raise Failed(f"the export has no graph {v}/{name}")
            rows.append(("shapes", by_graph[f"{v}/{name}"], False))
        else:
            rows.append(("shapes", path, True))
    return rows


# The rebuild's two checks ---------------------------------------------------------------------------

def literal_terms(path):
    from rdflib import Graph, Literal
    from rdflib.namespace import XSD

    def plain(t):
        return Literal(str(t)) if isinstance(t, Literal) and t.datatype == XSD.string else t
    return {tuple(plain(t) for t in triple) for triple in Graph().parse(path, format="nt")}


def compare_triples(rebuild, baseline):
    """loadable.nt and inferred.nt of the rebuild hold the baseline's triples, compared as RDF 1.1
    terms: a store export may write a literal typed xsd:string as a plain literal, which RDF 1.1 says
    is the same term (rdflib keeps them apart). Returns (problems, lines)."""
    problems, lines = [], []
    for name in ("loadable.nt", "inferred.nt"):
        new, old = literal_terms(os.path.join(rebuild, name)), literal_terms(os.path.join(baseline, name))
        if new != old:
            problems.append(f"{name}: {len(new - old)} triple(s) only in the rebuild, {len(old - new)} only in the baseline")
        else:
            lines.append(f"{name}: the same {len(new)} triples as the baseline (RDF 1.1 terms)")
    return problems, lines


def compare_reports(rebuild, baseline):
    """Both reports hold exactly the hash fields REPORT_HASHES, non-empty and equal: the proof that
    Neo4j holds the same graph. Returns (problems, lines)."""
    with open(rebuild, encoding="utf-8") as f:
        new = json.load(f)
    with open(baseline, encoding="utf-8") as f:
        old = json.load(f)
    keys = list(REPORT_HASHES)
    for name, report in (("the rebuilt report", new), ("the baseline report", old)):
        found = sorted(k for k in report if "hash" in k)
        if found != sorted(keys):
            return [f"{name} has hash fields {found}, not exactly {sorted(keys)}"], []
    diff = [k for k in keys if not new[k] or new[k] != old[k]]
    if diff:
        return [f"the reports differ in {', '.join(diff)}"], []
    return [], [f"the report's graph hashes equal the baseline's: {', '.join(k + '=' + old[k] for k in keys)}"]


# Running ------------------------------------------------------------------------------------------

def run_command(cmd, cwd=None, env=None, capture=False):
    """Runs one command with stdin closed; returns (exit code, captured stdout or None)."""
    result = subprocess.run(cmd, cwd=cwd, env=env, stdin=subprocess.DEVNULL, text=True,
                            capture_output=capture)
    return result.returncode, (result.stdout if capture else None)


def http_ready(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.status == 200
    except OSError:
        return False


class Driver:
    """One run. run(cmd, cwd, env, capture) and ready(url) are replaceable, so the tests drive every
    step without Docker, a database or a store."""

    def __init__(self, cfg, run=run_command, ready=http_ready, sleep=time.sleep, log=print, inputs=None):
        self.cfg, self.run, self.ready, self.sleep, self.log = cfg, run, ready, sleep, log
        self.out = cfg["out"]
        self.sk = HERE
        self.compose = os.path.join(SKILL, "docker", "compose.yaml")
        self.rs_dir = os.path.join(cfg["rdf_store"], "scripts")
        self.files = cfg["mode"] == "files"
        self.default_shapes = False
        # graphs: files mode's {data file: (graph IRI, where the name came from)}; empty for releases
        self.data, self.shapes, self.graphs = inputs if inputs else self.read_inputs()
        # The package files the release records read and the manifest that proves them; a rebuild keeps the original's,
        # with catalog.ttl and shapes.ttl beside them, because a store's export holds each graph as a file of its own.
        self.package_files = self.data
        self.package_manifest = self.out_file("run-manifest.json")
        self.local_up = False
        self.copied = False
        self.fusekis = []
        self.jena = None
        self.jena_handle = None
        self.passed = []
        self.not_removed = 0

    # inputs
    def read_inputs(self):
        if self.files:
            data = expand_files(self.cfg["files"])
            graphs = graph_names(data, self.cfg.get("graphs", {}), self.cfg["base"])
            if "shapes" in self.cfg:
                return data, list(self.cfg["shapes"]), graphs
            shapes, count = default_shapes(data, inverse_ends(self.cfg["projection_config"]))
            os.makedirs(self.out, exist_ok=True)
            path = self.out_file("default-shapes.ttl")
            shapes.serialize(path, format="turtle")
            self.default_shapes = True
            self.log(f"no shapes given: wrote {q(path)}, {q(count)} node shape(s) from the classes the data uses")
            return data, [path], graphs
        if "inputs_script" not in self.cfg:
            return list(self.cfg["data"]), list(self.cfg["shapes"]), {}
        lists = []
        for kind in ("data", "shapes"):
            code, text = self.run(list(PY) + [self.cfg["inputs_script"], kind], capture=True)
            if code != 0:
                raise Failed(f"inputs_script {kind} exited {code}")
            paths = [line for line in text.splitlines() if line]
            if not paths or not all(os.path.isabs(p) for p in paths):
                raise Failed(f"inputs_script {kind} must print one absolute path per line")
            lists.append(paths)
        return lists[0], lists[1], {}

    def shape_args(self):
        args = []
        for s in self.shapes:
            args += ["--shapes", s]
        return args

    def plain(self):
        """module_tags.py --graph arguments for each file named by something other than its owl:versionIRI."""
        args = []
        for path, (graph, how) in self.graphs.items():
            if how != "owl:versionIRI":
                args += ["--graph", f"{path}={graph}"]
        return args

    def store_args(self, release_graphs=True):
        """rdfstore.py arguments for the dataset a store holds: the release (each data file and, unless
        release_graphs is false, its release graphs) or, in files mode, each file under its graph name."""
        if not self.files:
            return release_graph_args(self.data, self.cfg["release_graphs"] if release_graphs else [])
        args = []
        for path in self.data:
            args += ["--graph", f"{path}={self.graphs[path][0]}", path]
        return args

    def catalogs(self):
        """Each release's catalog.ttl: the release records read it. Files mode has none."""
        beside = (os.path.join(os.path.dirname(p), "catalog.ttl") for p in self.package_files)
        return [] if self.files else [c for c in beside if os.path.isfile(c)]

    def write_manifest(self):
        """<out>/run-manifest.json: the mode, each input's SHA-256 (and graph name in files mode), and
        what files mode leaves out, so a later rebuild can prove its source unchanged."""
        notes = []
        if self.files:
            notes.append("files mode: version pins and the closure of requirements are not checked; plain files carry no pins")
        if self.default_shapes:
            notes.append("no SHACL shapes were given: default-shapes.ttl was derived from the data (one node shape per "
                         "class used, each predicate's observed counts), and n10s's defaults apply: literals become "
                         "properties, IRIs relationships")
        manifest = {"mode": self.cfg["mode"],
                    "data": [{"path": p, "sha256": sha256_file(p), **({"graph": self.graphs[p][0], "graph_from": self.graphs[p][1]}
                                                                      if self.files else {})} for p in self.data],
                    "shapes": [{"path": p, "sha256": sha256_file(p)} for p in self.shapes],
                    "catalogs": [{"path": c, "sha256": sha256_file(c)} for c in self.catalogs()],
                    "default_shapes": self.default_shapes, "notes": notes}
        with open(self.out_file("run-manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
            f.write("\n")
        for note in notes:
            self.log(f"note: {q(note)}")

    # helpers
    def call(self, what, cmd, cwd=None, env=None):
        code, _ = self.run(cmd, cwd=cwd if cwd else self.sk, env=env)
        if code != 0:
            raise Failed(f"{what} exited {code}")

    def py(self, what, *args, env=None):
        self.call(what, list(PY) + list(args), env=env)

    def rdfstore(self, what, *args):
        self.call(what, list(RS) + ["rdfstore.py"] + list(args), cwd=self.rs_dir)

    def out_file(self, name):
        return os.path.join(self.out, name)

    def need(self, *names):
        missing = [n for n in names if not os.path.isfile(self.out_file(n))]
        if missing:
            raise Failed(f"no {', '.join(missing)} in out: run the earlier steps first")

    # the local Neo4j
    def run_dir(self):
        return self.out_file("neo4j-run")

    def neo4j_env(self, password="unused"):
        return {**os.environ, "LPG_RUN": self.run_dir(), "NEO4J_PASSWORD": password,
                "LPG_BOLT_PORT": str(self.cfg["neo4j"]["bolt_port"])}

    def neo4j_compose(self):
        return ["docker", "compose", "-f", self.compose, "-p", self.cfg["neo4j"]["compose_project"]]

    def neo4j_down(self):
        code, _ = self.run(self.neo4j_compose() + ["--profile", "neo4j", "--profile", "fuseki", "down", "-v"],
                           env=self.neo4j_env(), capture=True)
        if code != 0:
            raise Failed(f"docker compose down (Neo4j) exited {code}")
        self.local_up = False

    def password(self):
        values = {}
        with open(os.path.join(self.run_dir(), "run.env"), encoding="utf-8") as f:
            for line in f:
                key, _, value = line.strip().partition("=")
                values[key] = value
        return values["PASSWORD"]

    def local(self):
        """(arguments naming the local Neo4j, environment holding its password)."""
        if not self.local_up:
            raise Failed("the local Neo4j is not up: run the load step in this run")
        return ["--uri", f"bolt://127.0.0.1:{self.cfg['neo4j']['bolt_port']}"], {**os.environ, "NEO4J_PASSWORD": self.password()}

    # Fuseki
    def fuseki_up(self, compose, project, port, port_var, profile=None):
        env = {**os.environ, port_var: str(port)}
        base = ["docker", "compose", "-f", compose, "-p", project] + (["--profile", profile] if profile else [])
        self.run(base + ["down", "-v"], env=env, capture=True)
        self.fusekis.append((base, env))
        self.call("docker compose up (Fuseki)", base + ["up", "-d", "--build"], env=env)
        ask = f"http://127.0.0.1:{port}/ds/query?" + urllib.parse.urlencode({"query": "ASK {}"})
        for _ in range(60):
            if self.ready(ask):
                return f"http://127.0.0.1:{port}/ds"
            self.sleep(2)
        raise Failed("Fuseki did not start")

    def fuseki_down(self, base_env):
        base, env = base_env
        code, _ = self.run(base + ["down", "-v"], env=env, capture=True)
        if code != 0:
            raise Failed(f"docker compose down (Fuseki) exited {code}")
        if base_env in self.fusekis:   # tracked until removed, so finish() retries a failed removal
            self.fusekis.remove(base_env)

    def rdf_store_fuseki(self, key):
        c = self.cfg[key]
        return self.fuseki_up(os.path.join(self.cfg["rdf_store"], "docker", "compose.yaml"), c["compose_project"],
                              c["port"], "RDF_FUSEKI_PORT")

    # the steps
    def step_project(self):
        jar = self.cfg["robot_jar"]
        with open(jar, "rb") as f:
            if hashlib.sha256(f.read()).hexdigest() != ROBOT_SHA256:
                raise Failed("the ROBOT jar's SHA-256 is not the pinned one (references/running.md, rule 2)")
        os.makedirs(self.out, exist_ok=True)
        c, sh = self.cfg["projection_config"], self.shape_args()
        o = self.out_file
        self.write_manifest()
        releases = [] if self.files else ["--releases", self.cfg["releases"]]
        self.py("check_projection_rules.py", "check_projection_rules.py", "--config", c, *sh, *releases, *self.data)
        self.py("validate_data.py", "validate_data.py", "--config", c, *sh, *self.data)
        self.py("build.py merge", "build.py", "merge", "--output", o("merged.ttl"), *self.data)
        self.call("ROBOT reason", ["java", "-jar", jar, "reason", "--reasoner", "ELK", "--input", o("merged.ttl"),
                                   "--axiom-generators", "SubClass ClassAssertion", "--include-indirect", "true",
                                   "--output", o("reasoned.ttl")])
        self.py("build.py inferred", "build.py", "inferred", "--input", o("merged.ttl"), "--reasoned", o("reasoned.ttl"),
                "--output", o("inferred.nt"))
        self.py("build.py loadable", "build.py", "loadable", "--output", o("loadable.nt"), *self.data)
        self.py("build.py check-serialised", "build.py", "check-serialised", "--loadable", o("loadable.nt"),
                "--inferred", o("inferred.nt"))
        self.py("validate_data.py (serialised)", "validate_data.py", "--config", c, *sh, o("loadable.nt"), o("inferred.nt"))
        self.py("build.py manifest", "build.py", "manifest", "--config", c, *sh, "--loadable", o("loadable.nt"),
                "--inferred", o("inferred.nt"), "--output", o("projection-manifest.json"), *self.data)
        self.py("in_graph_shapes.py", "in_graph_shapes.py", "--output", o("shapes-in-graph.ttl"), *self.shapes)

    def step_load(self):
        self.need("merged.ttl", "loadable.nt", "inferred.nt", "projection-manifest.json")
        records = self.out_file(RECORDS)
        if os.path.isfile(records):   # the records describe the load they were written for
            os.remove(records)
        run = self.run_dir()
        self.neo4j_down()
        if os.path.isdir(run):
            import shutil
            shutil.rmtree(run)
        os.makedirs(run)
        os.chmod(run, 0o711)
        for sub in ("plugins", "import"):
            os.makedirs(os.path.join(run, sub))
            os.chmod(os.path.join(run, sub), 0o755)
        password = os.urandom(12).hex()
        fd = os.open(os.path.join(run, "run.env"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(f"PROJECT={self.cfg['neo4j']['compose_project']}\nPORT={self.cfg['neo4j']['bolt_port']}\n"
                    f"PASSWORD={password}\n")
        env = self.neo4j_env(password)
        self.local_up = True   # from here on, the end of the run removes it
        self.call("docker compose up (Neo4j)", self.neo4j_compose() + ["--profile", "neo4j", "up", "-d"], env=env)
        for _ in range(100):
            _, logs = self.run(self.neo4j_compose() + ["logs", "neo4j"], env=env, capture=True)
            if "Started." in (logs or ""):
                break
            self.sleep(3)
        else:
            raise Failed("Neo4j did not start")
        self.sleep(5)
        o = self.out_file
        manual = ["--manual-cases", self.cfg["manual_cases"]] if "manual_cases" in self.cfg else []
        manual += self.sep_args()
        self.py("load_verify.py", "load_verify.py", "--config", self.cfg["projection_config"], *self.shape_args(),
                "--bolt", f"bolt://127.0.0.1:{self.cfg['neo4j']['bolt_port']}", "--import-dir", os.path.join(run, "import"),
                "--plugins-dir", os.path.join(run, "plugins"), "--compose-project", self.cfg["neo4j"]["compose_project"],
                "--merged", o("merged.ttl"), "--loadable", o("loadable.nt"), "--inferred", o("inferred.nt"),
                "--report", o("projection-report.json"), *manual, *self.data, env={**os.environ, "NEO4J_PASSWORD": password})
        self.py("build.py check-report", "build.py", "check-report", "--manifest", o("projection-manifest.json"),
                "--report", o("projection-report.json"))

    def sep_args(self):
        """--separator for every script that reads or describes the kept graph's names (load, review, tags,
        graph-type, the copy's checks and review, explore, and the rebuild's run of each), when the
        configuration names one."""
        return ["--separator", self.cfg["separator"]] if "separator" in self.cfg else []

    def step_review(self):
        target, env = self.local()
        self.py("model_review.py", "model_review.py", *target, "--report", self.out_file("model-review.json"),
                *self.sep_args(), env=env)

    def tag_checks(self, target, env, write):
        c, inferred = self.cfg["projection_config"], self.out_file("inferred.nt")
        if write:
            self.py("module_tags.py tag", "module_tags.py", "tag", "--config", c, "--inferred", inferred, *target,
                    *self.plain(), *self.sep_args(), *self.data, env=env)
        self.py("module_tags.py check", "module_tags.py", "check", "--config", c, "--inferred", inferred, *target,
                *self.plain(), *self.sep_args(), *self.data, env=env)
        self.py("module_tags.py modules", "module_tags.py", "modules", *target, *self.plain(), *self.sep_args(), *self.data, env=env)

    def step_tags(self):
        self.need("inferred.nt")
        target, env = self.local()
        self.tag_checks(target, env, write=True)

    def step_release_record(self):
        self.need("projection-report.json")
        target, env = self.local()
        self.py("release_record.py records", "release_record.py", "records", "--report", self.out_file("projection-report.json"),
                "--manifest", self.package_manifest,
                "--output", self.out_file(RECORDS), *self.package_files)
        self.record_checks(target, env)

    def record_checks(self, target, env):
        """Writes the run's release records to a Neo4j and reads them back there."""
        for command in ("write", "check"):
            self.py(f"release_record.py {command}", "release_record.py", command, "--records", self.out_file(RECORDS),
                    *target, env=env)

    def step_graph_type(self):
        self.py("build.py graph-type", "build.py", "graph-type", "--config", self.cfg["projection_config"],
                *self.shape_args(), "--output", self.out_file("graph-type.cypher"), *self.sep_args(), *self.data)

    def step_triplestore(self):
        self.need("inferred.nt", "projection-report.json")
        c = self.cfg["triplestore_fuseki"]
        ds = self.fuseki_up(self.compose, c["compose_project"], c["port"], "LPG_FUSEKI_PORT", profile="fuseki")
        try:
            self.py("triplestore.py", "triplestore.py", "--gsp", ds, "--query", ds + "/query",
                    "--inferred", self.out_file("inferred.nt"), "--projection-report", self.out_file("projection-report.json"),
                    "--report", self.out_file("triplestore-report.json"), *self.data)
        finally:
            self.remove(lambda b=self.fusekis[-1]: self.fuseki_down(b))

    def step_copy(self):
        self.need("projection-report.json", "inferred.nt")
        source, env = self.local()
        target_env = self.cfg["target_env"]
        replace = ["--replace"] if self.cfg.get("replace_target") else []
        self.py("copy_graph.py", "copy_graph.py", "--source", source[1], "--target-env", target_env,
                "--report", self.out_file("projection-report.json"), *replace, env=env)
        self.copied = True
        target = ["--env", target_env]
        self.tag_checks(target, None, write=False)
        if os.path.isfile(self.out_file(RECORDS)):
            self.record_checks(target, None)
        self.py("model_review.py (target)", "model_review.py", *target, "--report", self.out_file("model-review-target.json"),
                *self.sep_args())

    def step_jena(self):
        os.makedirs(self.out, exist_ok=True)   # rdfstore.py needs its report's folder, and --only jena may be first
        ds = self.jena_ds()
        self.rdfstore("rdfstore.py roundtrip (Jena)", "roundtrip", "--store", "fuseki", "--gsp", ds + "/data",
                      "--query", ds + "/query", "--update", ds + "/update", "--report", self.out_file("jena-roundtrip.json"),
                      *self.store_args())
        if self.cfg.get("keep_jena") and self.jena_handle in self.fusekis:
            self.fusekis.remove(self.jena_handle)   # no longer this run's to remove: it holds the proven copy
            self.log(f"Jena left standing, loaded, on port {q(self.cfg['jena']['port'])}: its dataset is in memory, so a restart empties it")

    def jena_ds(self):
        if not self.jena:
            self.jena = self.rdf_store_fuseki("jena")
            self.jena_handle = self.fusekis[-1]
        return self.jena

    def step_databricks(self):
        os.makedirs(self.out, exist_ok=True)
        d = self.cfg["databricks"]
        self.rdfstore("rdfstore.py roundtrip (Databricks)", "roundtrip", "--store", "databricks", "--env", d["env"],
                      "--table", d["table"], "--report", self.out_file("databricks-roundtrip.json"), *self.store_args())

    def step_explore(self):
        self.need("inferred.nt")
        inferred = self.out_file("inferred.nt")
        ds = self.rdf_store_fuseki("explore_fuseki")
        try:
            self.rdfstore("rdfstore.py roundtrip (explore)", "roundtrip", "--store", "fuseki", "--gsp", ds + "/data",
                          "--query", ds + "/query", "--update", ds + "/update", "--report", self.out_file("explore-roundtrip.json"),
                          "--graph", f"{inferred}={INFERRED_GRAPH}", *self.store_args(release_graphs=False), inferred)
            sides = []
            if self.local_up:
                sides.append(("local", *self.local()))
            if self.copied:
                sides.append(("target", ["--env", self.cfg["target_env"]], None))
            if not sides:
                raise Failed("explore needs the local Neo4j (load) or a copy in this run")
            for name, target, env in sides:
                report = self.out_file("explore-report.json" if name == "local" else "explore-report-target.json")
                self.py(f"explore.py compare ({name})", "explore.py", "compare", "--config", self.cfg["projection_config"],
                        *target, "--sparql", ds + "/query", "--queries", self.cfg["queries"], "--report", report,
                        *(["--files"] if self.files else []), *self.sep_args(), env=env)
        finally:
            self.remove(lambda b=self.fusekis[-1]: self.fuseki_down(b))

    def step_rebuild(self):
        r = self.cfg["rebuild"]
        self.need("loadable.nt", "inferred.nt", "projection-report.json")
        if self.local_up:
            self.neo4j_down()   # the rebuild loads its own Neo4j on the same port
        os.makedirs(r["out"], exist_ok=True)
        self.same_source()
        if r["source"] == "repo":
            data, shapes, graphs = self.data, self.shapes, self.graphs
        else:
            export = os.path.join(r["out"], f"{r['source']}-export")
            if os.path.isdir(export):
                import shutil
                shutil.rmtree(export)
            os.makedirs(export)
            if r["source"] == "jena":
                if "jena" not in self.passed:
                    self.step_jena()   # the store must hold the release before it is exported
                ds = self.jena_ds()
                store = ["--store", "fuseki", "--gsp", ds + "/data", "--query", ds + "/query"]
            else:
                d = self.cfg["databricks"]
                store = ["--store", "databricks", "--env", d["env"], "--table", d["table"]]
            self.rdfstore("rdfstore.py export", "export", *store, "--out", os.path.join(export, "store.nq"),
                          "--ttl-dir", os.path.join(export, "ttl"))
            self.rdfstore("rdfstore.py pack", "pack", "--out", os.path.join(export, "release.nq"), *self.store_args())
            self.rdfstore("rdfstore.py compare", "compare", os.path.join(export, "release.nq"), os.path.join(export, "store.nq"))
            self.log(f"the {q(r['source'])} export has the inputs' RDFC-1.0 hash")
            graph_of = {p: g for p, (g, _) in self.graphs.items()} if self.files else None
            rows = input_list(os.path.join(export, "ttl"), self.data, self.shapes,
                              [] if self.files else self.cfg["release_graphs"], graph_of)
            data = [p for kind, p, _ in rows if kind == "data"]
            shapes = [p for kind, p, _ in rows if kind == "shapes"]
            # each exported file keeps its original's graph name
            graphs = {new: self.graphs[old] for old, new in zip(self.data, data)} if self.files else {}
            for kind, p, repo in rows:
                if repo:
                    self.log(f"  {q(os.path.basename(p))} was not in the store, so it comes from the repository")
        child = Driver({**self.cfg, "out": r["out"]}, run=self.run, ready=self.ready, sleep=self.sleep, log=self.log,
                       inputs=(data, shapes, graphs))
        child.default_shapes = self.default_shapes
        child.package_files = self.package_files
        child.package_manifest = self.package_manifest
        steps = ["project", "load", "compare", "tags"] + ([] if self.files else ["release-record"]) + \
                (["copy"] if "target_env" in self.cfg else []) + \
                (["explore"] if "queries" in self.cfg else [])
        try:
            for step in steps:
                if step == "compare":
                    problems, lines = compare_triples(r["out"], self.out)
                    more, lines2 = compare_reports(child.out_file("projection-report.json"), self.out_file("projection-report.json"))
                    for line in lines + lines2:
                        self.log(f"  {q(line)}")
                    if problems + more:
                        raise Failed("; ".join(problems + more))
                else:
                    self.log(f"== rebuild: {q(step)}")
                    getattr(child, "step_" + step.replace("-", "_"))()
        finally:
            child.finish()
            # what the child could not remove becomes this run's to retry: its Fuseki handles, and its
            # Neo4j, which shares this run's compose project
            self.fusekis += child.fusekis
            self.local_up = self.local_up or child.local_up

    def same_source(self):
        """The rebuild compares with out's run, so the inputs must be the ones that run read: every SHA-256
        in out/run-manifest.json still holds."""
        path = self.out_file("run-manifest.json")
        if not os.path.isfile(path):
            raise Failed("no run-manifest.json in out: run project first")
        with open(path, encoding="utf-8") as f:
            manifest = json.load(f)
        recorded = {e["path"]: e["sha256"] for e in manifest["data"] + manifest["shapes"]}
        now = {p: sha256_file(p) for p in self.data + self.shapes if os.path.isfile(p)}
        if recorded != now:
            raise Failed("the inputs differ from the ones out/run-manifest.json records: run project again first")
        catalogs = {c: sha256_file(c) for c in self.catalogs()}
        if {e["path"]: e["sha256"] for e in manifest.get("catalogs", [])} != catalogs:
            raise Failed("the catalogs differ from the ones out/run-manifest.json records: run project again first")

    def finish(self):
        """Removes every container this run started, each attempt independent of the others, so one
        failed removal leaves no other running; a failure is said and does not hide the step's own."""
        teardowns = [lambda b=base_env: self.fuseki_down(b) for base_env in list(self.fusekis)]
        if self.local_up and not self.cfg.get("keep_neo4j"):
            teardowns.append(self.neo4j_down)
        for teardown in teardowns:
            self.remove(teardown)

    def remove(self, teardown):
        """Runs one container removal; a failure is said, never raised, so it cannot hide a step's own."""
        try:
            teardown()
        except Failed as exc:
            self.not_removed += 1
            self.log(f"WARNING {q(str(exc))}")
        except Exception as exc:  # noqa: BLE001 (any failure; the next removal still runs)
            self.not_removed += 1
            self.log(f"WARNING {q(error_line('a container could not be removed', exc))}")

    def run_steps(self, steps):
        """Runs the steps, then removes the containers. A step's failure propagates; with every step
        passed, a removal that failed fails the run, so a pass leaves up only what keep_neo4j and keep_jena keep."""
        self.not_removed = 0
        try:
            for step in steps:
                self.log(f"== {q(step)}")
                getattr(self, "step_" + step.replace("-", "_"))()
                self.passed.append(step)
        finally:
            self.finish()
        if self.not_removed:
            raise Failed(f"{self.not_removed} container removal(s) failed; remove them with docker compose down -v")


def compare_main(argv):
    if len(argv) != 3:
        print(f"usage: run_projection.py {q(argv[0])} <rebuild> <baseline>", file=sys.stderr)
        return 2
    try:
        problems, lines = (compare_triples if argv[0] == "compare-triples" else compare_reports)(argv[1], argv[2])
    except (OSError, ValueError) as exc:
        print(f"ERROR {q(error_line('the files could not be read', exc))}", file=sys.stderr)
        return 2
    for line in lines:
        print(q(line))
    for p in problems:
        print(f"FAIL {q(p)}")
    return 1 if problems else 0


def main(argv):
    if argv and argv[0] in ("compare-triples", "compare-reports"):
        return compare_main(argv)
    usage = "usage: run_projection.py --config <run.json> [--only a,b] [--skip a,b] [--plan]"
    opts, i, show_plan = {}, 0, False
    while i < len(argv):
        if argv[i] == "--plan":
            show_plan, i = True, i + 1
        elif argv[i] in ("--config", "--only", "--skip") and i + 1 < len(argv):
            opts[argv[i]], i = argv[i + 1], i + 2
        else:
            print(q(usage), file=sys.stderr)
            return 2
    if "--config" not in opts:
        print(q(usage), file=sys.stderr)
        return 2
    try:
        cfg = read_config(opts["--config"])
    except NoMode:
        print_choice()
        return 2
    except (OSError, ValueError) as exc:
        print(f"ERROR {q(error_line('the run configuration could not be read', exc))}", file=sys.stderr)
        return 2
    try:
        only = step_names(opts["--only"]) if "--only" in opts else None
        skip = step_names(opts["--skip"]) if "--skip" in opts else set()
    except (OSError, ValueError) as exc:
        print(f"ERROR {q(error_line('the run configuration could not be read', exc))}", file=sys.stderr)
        return 2
    rows = plan(cfg, only, skip)
    for step, reason in rows:
        if reason is None:
            print(f"{q(step)}: runs")
        else:
            print(f"{q(step)}: skipped, {q(reason)}")
    if show_plan:
        return 0
    try:
        driver = Driver(cfg)
        driver.run_steps([s for s, reason in rows if reason is None])
    except Failed as exc:
        print(f"FAIL {q(str(exc))}")
        return 1
    except (OSError, ValueError) as exc:
        print(f"ERROR {q(error_line('the run stopped', exc))}", file=sys.stderr)
        return 2
    print(f"every step passed; outputs in {q(cfg['out'])}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)   # this run's lines stay in order with the scripts' output
    sys.exit(main(sys.argv[1:]))
