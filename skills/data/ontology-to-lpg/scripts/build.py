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

from rdflib import BNode, Graph, Literal, URIRef
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


QUERY_SUFFIX = " (sh:targetQuery)"
EXPECTED = {
    "minCount": {"CountConstraintComponent", "MinCountConstraintComponent"},
    "maxCount": {"CountConstraintComponent", "MaxCountConstraintComponent"},
    "inverseMinCount": {"CountConstraintComponent", "MinCountConstraintComponent"},
    "inverseMaxCount": {"CountConstraintComponent", "MaxCountConstraintComponent"},
    "closed": {"ClosedConstraintComponent"},
    "nodeClass": {"ClassConstraintComponent"},
    "disjoint": {"DisjointConstraintComponent"},
    "datatype": {"DatatypeConstraintComponent"},
    "class": {"ClassConstraintComponent"},
    "in": {"InConstraintComponent"},
    "nodeKind": {"NodeKindConstraintComponent"},
    "hasValue": {"HasValueConstraintComponent"},
    "minInclusive": {"ValueRangeConstraintComponent", "MinInclusiveConstraintComponent"},
    "maxInclusive": {"ValueRangeConstraintComponent", "MaxInclusiveConstraintComponent"},
    "minExclusive": {"ValueRangeConstraintComponent", "MinExclusiveConstraintComponent"},
    "maxExclusive": {"ValueRangeConstraintComponent", "MaxExclusiveConstraintComponent"},
    "minLength": {"LengthConstraintComponent", "MinLengthConstraintComponent"},
    "maxLength": {"LengthConstraintComponent", "MaxLengthConstraintComponent"},
}


def expected_components(kind):
    """The components a case of this kind must report. A kind on a sh:targetQuery shape has the
    same components as the class-targeted kind."""
    base = kind[:-len(QUERY_SUFFIX)] if kind.endswith(QUERY_SUFFIX) else kind
    for family in ("datatype", "nodeKind"):
        if base.startswith(family):
            return EXPECTED[family]
    return EXPECTED.get(base, set())


def component_name(value):
    return str(value).rsplit("#", 1)[-1].strip()


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
        if len(one) != 1 or line != line.strip():
            fails.append(f"{name} line {number} is not exactly one N-Triples triple: {line[:80]!r}")
        graph += one
    return [line.encode("utf-8") for line in lines], graph


def check_serialised(loadable_bytes, inferred_bytes):
    """The step 4 gate: each file holds one triple per line, in byte order, without duplicates;
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
    failed = [c.get("kind") for c in rep.get("fail_cases") or [] if not c.get("passed")]
    if failed:
        fails.append(f"report fail cases did not fail as expected: {', '.join(map(str, failed))}")
    # A manual case counts only when it records what it ran and what it saw: the Cypher change, the
    # focus node, and at least one component validate() reported on that node.
    # It counts only when it reported a component the kind expects (EXPECTED).
    by_hand = {c.get("kind") for c in rep.get("manual_cases") or []
               if c.get("passed") is True and str(c.get("cypher") or "").strip() and str(c.get("focus") or "").strip()
               and isinstance(c.get("components"), list)
               and {component_name(x) for x in c["components"]} & expected_components(str(c.get("kind")))}
    if rep.get("invalidated"):
        fails.append(f"report was invalidated: {rep['invalidated']}")
    listed = rep.get("kinds_without_case")
    if not isinstance(listed, list):
        fails.append("report has no kinds_without_case list (load_verify.py writes one, empty or not)")
        listed = []
    missing = [k for k in listed if k not in by_hand]
    if missing:
        fails.append("report lists constraint kinds left in the graph with no fail case: "
                     + ", ".join(missing) + " (pipeline.md, rule 14)")
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
