#!/usr/bin/env python3
"""The serialise step, the generated load script, the manifest and the report check.

Run with: uv run --no-project --with rdflib python3 build.py <command> ...

  merge     --output merged.ttl <data.ttl>...
            The reasoner's input: every released data file, merged. No shapes, no inferred triples.
  loadable  --output loadable.nt <data.ttl>...
            The asserted data as sorted, de-duplicated N-Triples.
  inferred  --input merged.ttl --reasoned reasoned.ttl --output inferred.nt
            The triples in the reasoner's output and not in its input, kept only when they are
            rdf:type or rdfs:subClassOf between two IRIs and the object is outside the OWL and RDFS
            namespaces. Both graphs are parsed and compared as triples, not as lines.
  cypher    --config <config.json> --shapes <shapes.ttl>... <data.ttl>...
            The generated load script for n10s (references/pipeline.md, rules 8 to 11).
  manifest  --config <config.json> --shapes <shapes.ttl>... --loadable loadable.nt
            --inferred inferred.nt --output manifest.json [--verify] <data.ttl>...
            Writes the manifest, or with --verify fails when the committed one differs. File paths
            are recorded relative to the manifest's own folder, so moving the tree changes nothing.
  check-serialised --loadable loadable.nt --inferred inferred.nt
            Fails unless both files are in byte order without duplicates, and inferred.nt holds only
            rdf:type and rdfs:subClassOf triples between two IRIs whose object is outside the OWL and
            RDFS namespaces (the step 4 gate in SKILL.md).
  graph-type --config <config.json> --shapes <shapes.ttl>...
            Prints an ALTER CURRENT GRAPH TYPE SET statement generated from the shapes (Cypher 25,
            Enterprise Edition, introduced in Neo4j 2026.02), with what it leaves out as comments
            (add-ons.md, H).
  check-report --manifest manifest.json --report report.json
            Fails unless the report names the manifest's fingerprints and every verify check passed.

Definitions (references/pipeline.md, rule 5):
  sorted            lines ordered by their UTF-8 bytes, duplicates removed (the order of LC_ALL=C sort -u)
  input fingerprint SHA-256 of the bytes of loadable.nt followed directly by the bytes of inferred.nt
  shapes fingerprint SHA-256 of the bytes of every shape file, concatenated in the order given

Exit 0 on success, 1 when --verify, check-serialised or check-report finds a difference or a failed check, 2 when a
file cannot be read or the arguments are wrong.
"""
import hashlib
import json
import os
import sys

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS

import check_projection_rules as cpr

KEPT_PREDICATES = (RDF.type, RDFS.subClassOf)
BUILTIN = (str(OWL), str(RDFS))


def parse(paths):
    g = Graph()
    for path in paths:
        g.parse(path, format="nt" if path.endswith(".nt") else "turtle")
    return g


def sorted_nt(g):
    """Sorted, de-duplicated N-Triples: one serialiser for every file the pipeline compares."""
    lines = {line for line in g.serialize(format="nt", encoding="utf-8").decode("utf-8").splitlines() if line.strip()}
    return "".join(line + "\n" for line in sorted(lines, key=lambda s: s.encode("utf-8")))


def sha_bytes(*chunks):
    h = hashlib.sha256()
    for c in chunks:
        h.update(c)
    return h.hexdigest()


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def inferred(reasoner_input, reasoner_output):
    keep = Graph()
    for s, p, o in reasoner_output:
        if (s, p, o) in reasoner_input:
            continue
        if p in KEPT_PREDICATES and isinstance(s, URIRef) and isinstance(o, URIRef) and not str(o).startswith(BUILTIN):
            keep.add((s, p, o))
    return keep


def multivalued(data, shapes):
    """Literal-valued predicates that load as arrays (references/pipeline.md, rule 10).

    A predicate is literal-valued when any of its objects in the data is a literal. It loads as an
    array unless an applied property shape gives its path sh:maxCount 1; it also loads as an array
    when one subject holds more than one literal value for it. A standard predicate with no shape
    (rdfs:label, skos:prefLabel, dcterms:title, owl:versionInfo) therefore loads as an array."""
    single = {path for path, node in cpr.applied_property_shapes(shapes)
              if (node, cpr.SH.maxCount, Literal(1)) in shapes}
    counts = {}
    for s, p, o in data:
        if isinstance(o, Literal):
            counts[(s, p)] = counts.get((s, p), 0) + 1
    literal_predicates = {p for (_, p) in counts}
    many = {p for (_, p), n in counts.items() if n > 1}
    return sorted(str(p) for p in literal_predicates if p not in single or p in many)


def shorten(iri, cfg):
    ns = cpr.namespace(iri)
    for prefix, value in cfg.prefixes.items():
        if value == ns:
            return f"{prefix}__{str(iri)[len(ns):]}"
    raise ValueError(f"no prefix for {iri}")


def cypher(cfg, data, shapes):
    multival = multivalued(data, shapes)
    lines = ["CREATE CONSTRAINT n10s_unique_uri IF NOT EXISTS FOR (r:Resource) REQUIRE r.uri IS UNIQUE;",
             "CALL n10s.graphconfig.init({handleVocabUris: 'SHORTEN', handleRDFTypes: 'LABELS_AND_NODES', "
             f"handleMultival: 'ARRAY', multivalPropList: {json.dumps(multival)}, "
             "keepLangTag: true, keepCustomDataTypes: true});"]
    lines += [f"CALL n10s.nsprefixes.add({json.dumps(p)}, {json.dumps(ns)});" for p, ns in cfg.prefixes.items()]
    lines += ["CALL n10s.onto.import.fetch('file:///import/merged.ttl', 'Turtle');",
              "CALL n10s.validation.shacl.import.fetch('file:///import/shapes-in-graph.ttl', 'Turtle');",
              "CALL n10s.rdf.import.fetch('file:///import/loadable.nt', 'N-Triples');",
              "CALL n10s.rdf.import.fetch('file:///import/inferred.nt', 'N-Triples');"]
    for iri in multival:
        key = shorten(URIRef(iri), cfg)
        lines.append(f"MATCH (n:Resource) WHERE n.`{key}` IS NOT NULL SET n.`{key}` = apoc.coll.sort(n.`{key}`);")
    return "\n".join(lines) + "\n"


def relative(path, root):
    """A path as the manifest records it: relative to root, with forward slashes, so the manifest
    does not change when the whole tree moves or the command runs from another folder."""
    return os.path.relpath(os.path.abspath(path), os.path.abspath(root)).replace(os.sep, "/")


def manifest(cfg, data_paths, shape_paths, loadable_path, inferred_path, root="."):
    loadable, inferred_text = read_bytes(loadable_path), read_bytes(inferred_path)
    return {
        "inputs": {relative(p, root): sha_bytes(read_bytes(p)) for p in data_paths},
        "shapes": {relative(p, root): sha_bytes(read_bytes(p)) for p in shape_paths},
        "loadable_triples": loadable.count(b"\n"),
        "inferred_triples": inferred_text.count(b"\n"),
        "input_fingerprint": sha_bytes(loadable, inferred_text),
        "shapes_fingerprint": sha_bytes(*(read_bytes(p) for p in shape_paths)),
        "rule4": cfg.rule4,
        "rule4_reason": cfg.rule4_reason,
        "release_exceptions": cfg.exceptions,
        "versions": cfg.versions,
    }


def dump(obj):
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


REPORT_CHECKS = (
    ("shacl_violations_in_graph", lambda v: v == 0, "is not 0"),
    ("in_graph_mutant_violations", lambda v: isinstance(v, int) and v > 0, "is not above 0: the mutant was not caught"),
    ("roundtrip_lost", lambda v: v == 0, "is not 0"),
    ("roundtrip_added", lambda v: v == 0, "is not 0"),
)


def _lines_and_graph(name, data, fails):
    """Every line of an N-Triples file must be exactly one triple: no blank line, no comment, no
    other text. Returns (lines, graph)."""
    text = data.decode("utf-8")
    if text and not text.endswith("\n"):
        fails.append(f"{name} does not end with a newline")
    lines = text.split("\n")[:-1] if text.endswith("\n") else text.split("\n") if text else []
    graph = Graph()
    for number, line in enumerate(lines, 1):
        one = Graph()
        try:
            one.parse(data=line + "\n", format="nt")
        except Exception:  # rdflib raises several parser types
            one = Graph()
        # Exactly one triple and nothing else: the line must equal rdflib's own N-Triples spelling of
        # that triple, so a trailing comment, extra spaces or any other text fails.
        if len(one) != 1 or sorted_nt(one).rstrip("\n") != line:
            fails.append(f"{name} line {number} is not exactly one N-Triples triple and nothing else: {line[:80]!r}")
        graph += one
    return [line.encode("utf-8") for line in lines], graph


def check_serialised(loadable_bytes, inferred_bytes):
    """The step 4 gate: each line is exactly one triple and nothing else (no comment), in byte order,
    without duplicates;
    inferred.nt holds only kept inferences, none of them already asserted in loadable.nt."""
    fails = []
    graphs = {}
    for name, data in (("loadable.nt", loadable_bytes), ("inferred.nt", inferred_bytes)):
        lines, graphs[name] = _lines_and_graph(name, data, fails)
        if lines != sorted(set(lines)):
            fails.append(f"{name} is not in byte order without duplicates (LC_ALL=C sort -u)")
    inferred_graph, loadable_graph = graphs["inferred.nt"], graphs["loadable.nt"]
    for s, p, o in sorted(inferred_graph, key=lambda t: tuple(str(x) for x in t)):
        if (s, p, o) in loadable_graph:
            fails.append(f"inferred.nt repeats an asserted triple from loadable.nt: {s.n3()} {p.n3()} {o.n3()}")
        if p not in KEPT_PREDICATES or not isinstance(s, URIRef) or not isinstance(o, URIRef) \
                or str(o).startswith(BUILTIN):
            fails.append(f"inferred.nt holds a triple the inferred filter drops: {s.n3()} {p.n3()} {o.n3()}")
    return fails


# XSD datatype to the GRAPH TYPE property type (the XSD to Cypher table in design-rules.md).
GRAPH_TYPE_TYPES = {
    "string": "STRING", "token": "STRING", "normalizedString": "STRING", "anyURI": "STRING",
    "boolean": "BOOLEAN", "integer": "INTEGER", "long": "INTEGER", "int": "INTEGER",
    "nonNegativeInteger": "INTEGER", "double": "FLOAT", "float": "FLOAT", "decimal": "FLOAT",
    "date": "DATE", "dateTimeStamp": "ZONED DATETIME", "duration": "DURATION",
}
LANG_STRING = "http://www.w3.org/1999/02/22-rdf-syntax-ns#langString"


def _q(name):
    return "`" + name.replace("`", "``") + "`"


def graph_type(cfg, shapes):
    """(statement, left out) for the shapes: one node element type per sh:targetClass, with a typed
    property for each literal property shape that names a mappable sh:datatype (NOT NULL when
    sh:minCount is at least 1 and sh:maxCount is 1, LIST<T> when there is no sh:maxCount 1), and one
    relationship element type per predicate whose property shapes name one sh:class, from the
    shapes' target class to that class. Everything else is listed in left out."""
    from rdflib import BNode
    from rdflib.namespace import SH, XSD
    nodes, rels, left_out = {}, {}, []
    for ns in sorted(set(shapes.subjects(SH.targetClass, None)), key=str):
        for cls in sorted(shapes.objects(ns, SH.targetClass), key=str):
            label = shorten(cls, cfg)
            props = nodes.setdefault(label, {})
            for ps in sorted(shapes.objects(ns, SH.property), key=str):
                path = shapes.value(ps, SH.path)
                if isinstance(path, BNode) or path is None:
                    left_out.append(f"{label}: a property shape with a non-predicate path ({ps})")
                    continue
                key = shorten(path, cfg)
                dt, target = shapes.value(ps, SH.datatype), shapes.value(ps, SH["class"])
                min_c, max_c = shapes.value(ps, SH.minCount), shapes.value(ps, SH.maxCount)
                single = max_c is not None and int(max_c) == 1
                if dt is not None:
                    if str(dt) == LANG_STRING:
                        base = "STRING"
                    elif str(dt).startswith(str(XSD)) and str(dt)[len(str(XSD)):] in GRAPH_TYPE_TYPES:
                        base = GRAPH_TYPE_TYPES[str(dt)[len(str(XSD)):]]
                    else:
                        left_out.append(f"{label}.{key}: sh:datatype {dt} has no GRAPH TYPE property type")
                        continue
                    kind = base if single else f"LIST<{base} NOT NULL>"
                    required = single and min_c is not None and int(min_c) >= 1
                    props[key] = f"{_q(key)} :: {kind}" + (" NOT NULL" if required else "")
                elif target is not None:
                    rels.setdefault(key, set()).add((label, shorten(target, cfg)))
                else:
                    left_out.append(f"{label}.{key}: no sh:datatype or sh:class to map")
                for term in ("in", "hasValue", "pattern", "minInclusive", "maxInclusive", "minExclusive",
                             "maxExclusive", "minLength", "maxLength", "disjoint", "nodeKind"):
                    if (ps, SH[term], None) in shapes:
                        left_out.append(f"{label}.{key}: sh:{term} (no GRAPH TYPE form)")
                if max_c is not None and int(max_c) > 1 or (min_c is not None and int(min_c) > 1):
                    left_out.append(f"{label}.{key}: a count other than 0 or 1")
                if target is not None and (min_c is not None or max_c is not None):
                    left_out.append(f"{label}.{key}: relationship counts (no GRAPH TYPE form)")
            if (ns, SH.closed, None) in shapes:
                left_out.append(f"{label}: sh:closed (a graph type is open)")
    elements = [f"  (:{_q(label)} =>" + (" {" + ", ".join(props[k] for k in sorted(props)) + "}" if props else "") + ")"
                for label, props in sorted(nodes.items())]
    for key, ends in sorted(rels.items()):
        if len(ends) > 1:
            left_out.append(f"{key}: relationship type used between several label pairs "
                            f"({', '.join(f'{a}->{b}' for a, b in sorted(ends))}); one identifying pair only")
            continue
        (source, target), = ends
        elements.append(f"  (:{_q(source)})-[:{_q(key)} =>]->(:{_q(target)})")
    statement = "CYPHER 25\nALTER CURRENT GRAPH TYPE SET {\n" + ",\n".join(elements) + "\n}"
    return statement, sorted(set(left_out))


def check_report(man, rep):
    fails = []
    for key in ("input_fingerprint", "shapes_fingerprint"):
        if rep.get(key) != man.get(key):
            fails.append(f"report {key} {rep.get(key)} does not match the manifest's {man.get(key)}: rerun load and verify")
    for key, ok, why in REPORT_CHECKS:
        if not ok(rep.get(key)):
            fails.append(f"report {key} {why} ({rep.get(key)!r})")
    a, b = rep.get("determinism_hash_sorted"), rep.get("determinism_hash_shuffled")
    if not a or a != b:
        fails.append(f"report determinism hashes differ or are missing ({a!r}, {b!r})")
    if not rep.get("in_graph_shape_constraints") or rep.get("in_graph_shape_constraints") != rep.get("shapes_import_rows"):
        fails.append("report in_graph_shape_constraints is missing or differs from shapes_import_rows")
    if rep.get("passed") is not True:
        fails.append("report does not say passed: true (load_verify.py writes a report only when every check passed)")
    cases = rep.get("fail_cases")
    if not isinstance(cases, list) or not cases:
        fails.append("report has no fail cases (pipeline.md, rule 14)")
    failed = [f"{c.get('target')} {c.get('path')} {c.get('param')}" for c in cases or []
              if c.get("status") not in ("passed", "no-op")]
    if failed:
        fails.append("report fail cases did not pass: " + "; ".join(failed))
    mutant = rep.get("mutant")
    if not isinstance(mutant, dict):
        fails.append("report has no mutant object (pipeline.md, rule 15)")
    else:
        if not isinstance(mutant.get("violations"), int) or mutant["violations"] < 1:
            fails.append("report mutant caught no violation")
        if mutant.get("after_restore") != 0:
            fails.append("report mutant was not restored to zero violations")
    return fails


def options(argv, multi=("--shapes",), flags=("--verify",)):
    opts, positional, args = {}, [], list(argv)
    while args:
        a = args.pop(0)
        if a in flags:
            opts[a] = True
        elif a.startswith("--"):
            if not args:
                raise ValueError(f"{a} needs a value")
            if a in multi:
                opts.setdefault(a, []).append(args.pop(0))
            else:
                opts[a] = args.pop(0)
        else:
            positional.append(a)
    return opts, positional


def need(opts, *keys):
    missing = [k for k in keys if k not in opts]
    if missing:
        raise ValueError("missing " + ", ".join(missing))


def load_config(path):
    with open(path, encoding="utf-8") as f:
        return cpr.Config(json.load(f))


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def main(argv):
    if not argv:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    command, rest = argv[0], argv[1:]
    try:
        opts, data = options(rest)
        if command == "merge":
            need(opts, "--output")
            if not data:
                raise ValueError("no data files")
            merged = parse(data)
            merged.serialize(opts["--output"], format="turtle")
            print(f"wrote {opts['--output']}: {len(merged)} triples from {len(data)} file(s)")
        elif command == "loadable":
            need(opts, "--output")
            if not data:
                raise ValueError("no data files")
            text = sorted_nt(parse(data))
            write(opts["--output"], text)
            print(f"wrote {opts['--output']}: {text.count(chr(10))} triples")
        elif command == "inferred":
            need(opts, "--input", "--reasoned", "--output")
            text = sorted_nt(inferred(parse([opts["--input"]]), parse([opts["--reasoned"]])))
            write(opts["--output"], text)
            print(f"wrote {opts['--output']}: {text.count(chr(10))} triples")
        elif command == "cypher":
            need(opts, "--config")
            if not data:
                raise ValueError("no data files")
            cfg = load_config(opts["--config"])
            if cfg.rule4 == "4b":
                print(cpr.RULE_4B_STOP.format(script="build.py cypher"), file=sys.stderr)
                return 2
            print(cypher(cfg, parse(data), parse(opts.get("--shapes", []))), end="")
        elif command == "manifest":
            need(opts, "--config", "--loadable", "--inferred", "--output")
            root = os.path.dirname(os.path.abspath(opts["--output"]))
            text = dump(manifest(load_config(opts["--config"]), data, opts.get("--shapes", []),
                                 opts["--loadable"], opts["--inferred"], root))
            if opts.get("--verify"):
                current = open(opts["--output"], encoding="utf-8").read() if os.path.exists(opts["--output"]) else ""
                if current != text:
                    print(f"FAIL {opts['--output']} is not current: rerun build.py manifest and commit it")
                    return 1
                print(f"{opts['--output']} is current")
            else:
                write(opts["--output"], text)
                print(f"wrote {opts['--output']}")
        elif command == "check-serialised":
            need(opts, "--loadable", "--inferred")
            fails = check_serialised(read_bytes(opts["--loadable"]), read_bytes(opts["--inferred"]))
            for message in fails:
                print(f"FAIL {message}")
            if fails:
                return 1
            print("loadable.nt and inferred.nt are in byte order, and inferred.nt holds only kept inferences")
        elif command == "graph-type":
            need(opts, "--config")
            statement, left_out = graph_type(load_config(opts["--config"]), parse(opts.get("--shapes", [])))
            print(statement)
            for line in left_out:
                print(f"// left out: {line}")
        elif command == "check-report":
            need(opts, "--manifest", "--report")
            with open(opts["--manifest"], encoding="utf-8") as f:
                man = json.load(f)
            with open(opts["--report"], encoding="utf-8") as f:
                rep = json.load(f)
            fails = check_report(man, rep)
            for message in fails:
                print(f"FAIL {message}")
            if fails:
                return 1
            print("the report is current and passed")
        else:
            raise ValueError(f"unknown command {command!r}")
    except (OSError, ValueError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # rdflib raises several parser types; any of them stops the run
        print(f"ERROR cannot read the RDF files: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
