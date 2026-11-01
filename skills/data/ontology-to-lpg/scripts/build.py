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
  cypher    --config <config.json> --shapes <shapes.ttl>... --output load.cypher <data.ttl>...
            Writes the generated load script for n10s (references/pipeline.md, rules 8 to 11).
  manifest  --config <config.json> --shapes <shapes.ttl>... --loadable loadable.nt
            --inferred inferred.nt --output manifest.json [--verify] <data.ttl>...
            Writes the manifest, or with --verify fails when the committed one differs. File paths
            are recorded relative to the manifest's own folder, so moving the tree changes nothing.
  check-serialised --loadable loadable.nt --inferred inferred.nt
            Fails unless both files are in byte order without duplicates, and inferred.nt holds only
            rdf:type and rdfs:subClassOf triples between two IRIs whose object is outside the OWL and
            RDFS namespaces (the step 4 gate in SKILL.md).
  graph-type --config <config.json> --shapes <shapes.ttl>... --output graph-type.cypher [--separator _] <data.ttl>...
            Writes an ALTER CURRENT GRAPH TYPE SET statement generated from the shapes (Cypher 25,
            Enterprise Edition, introduced in Neo4j 2026.02), with what it leaves out as comments
            (add-ons.md, H).
  data-model --config <config.json> --shapes <shapes.ttl>... --output data-model.json [--separator _] <data.ttl>...
            Writes the same element types as a DataModel for the Neo4j Data Modeling MCP server
            (mcp-neo4j-data-modeling 0.8.2), checked against its validators first (add-ons.md, L).
  check-report --manifest manifest.json --report report.json
            Fails unless the report names the manifest's fingerprints and every verify check passed.

graph-type and data-model name labels, relationship types and property keys as the kept graph does:
n10s's prefix, two underscores, local name, or with --separator (underscores only) the separator a
load_verify.py run renamed them to, so the artifacts describe the graph that exists. Both refuse a
prefix the rename could not handle (check_prefixes), as the load does. The load script (cypher) always
uses n10s's names.

Definitions (references/pipeline.md, rule 5):
  sorted            lines ordered by their UTF-8 bytes, duplicates removed (the order of LC_ALL=C sort -u)
  input fingerprint SHA-256 of the bytes of loadable.nt followed directly by the bytes of inferred.nt
  shapes fingerprint SHA-256 of the bytes of every shape file, concatenated in the order given

Exit 0 on success, 1 when --verify, check-serialised, data-model or check-report finds a difference or a failed check, 2 when a
file cannot be read or the arguments are wrong.
"""
import hashlib
import json
import os
import sys
from collections import namedtuple

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS

import check_projection_rules as cpr
from shell import Refusal, comment, q

# The command list, printed when no command is given: fixed text, not input.
USAGE = __doc__.split("\n\n")[1]

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


SEPARATOR = "_" * 2   # what n10s writes between a prefix and a local name (SHORTEN); --separator names another


def separator(opts):
    """--separator: what sits between a prefix and a local name in the kept graph. n10s writes two
    underscores; another value, underscores only, is what load_verify.py renamed every label, type and
    key to after the checks."""
    sep = opts.get("--separator", SEPARATOR)
    if not isinstance(sep, str) or not sep or not all(c == "_" for c in sep):
        raise Refusal("--separator takes underscores only, such as _ or __")
    return sep


def prefixes_holding(prefixes, sep):
    """The configured prefixes a rename to sep cannot handle: those that contain the separator (a renamed
    name could not be split back into prefix and local name at the first separator: my_ns_x reads as
    my, ns_x) and those that contain n10s's own two-underscore delimiter (the rename replaces the first one
    it finds, which would then sit inside the prefix, not between prefix and name). The scripts refuse the pair
    before anything is loaded. With n10s's own separator nothing is renamed, so nothing is refused."""
    if sep == SEPARATOR:
        return []
    return sorted(p for p in prefixes if sep in p or SEPARATOR in p)


def check_prefixes(prefixes, sep):
    """Refuses when prefixes_holding finds any; the count, never the prefix (a configured value)."""
    clash = prefixes_holding(prefixes, sep)
    if clash:
        raise Refusal(f"the separator, or two underscores, appears inside {len(clash)} of the configured prefixes, "
                      "so a renamed name could not be split back into prefix and local name; use a separator "
                      "no prefix holds, or rename that prefix")


def rename_proof_problems(rep):
    """The failures of a report's separator and rename proof: the one rule load_verify.passed (the
    producer) and report_earned (every consumer) apply. separator, when present, is a string of
    underscores (absent means n10s's own); renamed, when present, is an object of counts; and
    rename_lossless is exactly true whenever the separator is not n10s's, renamed counts anything, or
    the field is stated at all. A report that names none of the three is from before the fields
    existed: n10s's names, unrenamed."""
    fails = []
    sep = rep.get("separator", SEPARATOR)
    if not isinstance(sep, str) or not sep or any(c != "_" for c in sep):
        fails.append(f"report separator is not a string of underscores ({sep!r})")
    renamed = rep.get("renamed", {})
    counts = isinstance(renamed, dict) and all(isinstance(v, int) and not isinstance(v, bool) and v >= 0
                                               for v in renamed.values())
    if not counts:
        fails.append("report renamed is not an object of counts")
    renames = not counts or any(renamed.values())
    if (fails or sep != SEPARATOR or renames or "rename_lossless" in rep) and rep.get("rename_lossless") is not True:
        fails.append("report rename_lossless is not true: the rename of the graph's names was not proven lossless, "
                     "so the graph's names are not the verified ones")
    return fails


def shorten(iri, cfg, sep=SEPARATOR):
    ns = cpr.namespace(iri)
    for prefix, value in cfg.prefixes.items():
        if value == ns:
            return f"{prefix}{sep}{str(iri)[len(ns):]}"
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


# A typed property of a node element type: the Cypher base type (STRING, INTEGER, ...), whether the
# load stores it as an array, and whether sh:minCount is 1 or more. Each serializer renders it.
PropertyType = namedtuple("PropertyType", "base listed required")


def element_types(cfg, shapes, data, sep=SEPARATOR):
    """(nodes, rels, left out) read from the shapes, the one mapping behind graph_type and data_model.

    nodes maps each sh:targetClass label to {key: PropertyType}; rels maps each relationship key to
    its {(source label, target label)}. Everything the shapes give no typed form is listed in left
    out, in graph_type's words. What only a GRAPH TYPE cannot hold is graph_type_omissions'. Names
    are prefix, sep, local name: the kept graph's names, so n10s's unless a run renamed them."""
    from rdflib import BNode
    from rdflib.namespace import SH, XSD
    multi = set(multivalued(data, shapes))
    nodes, rels, left_out = {}, {}, []
    for ns in sorted(set(shapes.subjects(SH.targetClass, None)), key=str):
        for cls in sorted(shapes.objects(ns, SH.targetClass), key=str):
            label = shorten(cls, cfg, sep)
            props = nodes.setdefault(label, {})
            for ps in sorted(shapes.objects(ns, SH.property), key=str):
                path = shapes.value(ps, SH.path)
                if isinstance(path, BNode) or path is None:
                    left_out.append(f"{label}: a property shape with a non-predicate path ({ps})")
                    continue
                key = shorten(path, cfg, sep)
                dt, target = shapes.value(ps, SH.datatype), shapes.value(ps, SH["class"])
                min_c, max_c = shapes.value(ps, SH.minCount), shapes.value(ps, SH.maxCount)
                for term in ("in", "hasValue", "pattern", "minInclusive", "maxInclusive", "minExclusive",
                             "maxExclusive", "minLength", "maxLength", "disjoint", "nodeKind"):
                    if (ps, SH[term], None) in shapes:
                        left_out.append(f"{label}.{key}: sh:{term} (no GRAPH TYPE form)")
                if max_c is not None and int(max_c) > 1 or (min_c is not None and int(min_c) > 1):
                    left_out.append(f"{label}.{key}: a count other than 0 or 1")
                if dt is not None:
                    if str(dt) == LANG_STRING:
                        base = "STRING"
                    elif str(dt).startswith(str(XSD)) and str(dt)[len(str(XSD)):] in GRAPH_TYPE_TYPES:
                        base = GRAPH_TYPE_TYPES[str(dt)[len(str(XSD)):]]
                    else:
                        left_out.append(f"{label}.{key}: sh:datatype {dt} has no GRAPH TYPE property type"
                                        + (f"; its sh:class {target} is left out too" if target is not None else ""))
                        continue
                    if target is not None:
                        left_out.append(f"{label}.{key}: sh:class {target} beside sh:datatype; the property is typed, "
                                        "the relationship left out")
                    typed = PropertyType(base, str(path) in multi, min_c is not None and int(min_c) >= 1)
                    if key in props and props[key] != typed:
                        left_out.append(f"{label}.{key}: a second property shape maps it as {_spec(key, typed)}; "
                                        f"kept {_spec(key, props[key])}")
                    else:
                        props.setdefault(key, typed)
                elif target is not None:
                    rels.setdefault(key, set()).add((label, shorten(target, cfg, sep)))
                    if min_c is not None or max_c is not None:
                        left_out.append(f"{label}.{key}: relationship counts (no GRAPH TYPE form)")
                else:
                    left_out.append(f"{label}.{key}: no sh:datatype or sh:class to map")
            if (ns, SH.closed, None) in shapes:
                left_out.append(f"{label}: sh:closed (a graph type is open)")
    return nodes, rels, left_out


def _spec(key, typed):
    kind = f"LIST<{typed.base} NOT NULL>" if typed.listed else typed.base
    return f"{_q(key)} :: {kind}" + (" NOT NULL" if typed.required else "")


def graph_type_omissions(nodes, rels):
    """What a GRAPH TYPE cannot hold of the element types: a node type with no typed property (Aura
    rejects an empty one) and a relationship type used between several label pairs (one identifying
    pair only). data_model keeps both and lists them under metadata.not_in_graph_type."""
    omitted = [f"{label}: no typed property, so no node element type" for label, props in sorted(nodes.items())
               if not props]
    omitted += [f"{key}: relationship type used between several label pairs "
                f"({', '.join(f'{a}->{b}' for a, b in sorted(ends))}); one identifying pair only"
                for key, ends in sorted(rels.items()) if len(ends) > 1]
    return omitted


def graph_type(cfg, shapes, data, sep=SEPARATOR):
    """(statement, left out) for the shapes: one node element type per sh:targetClass that has at
    least one typed property, and one relationship element type per predicate whose property shapes
    name one sh:class, from the shapes' target class to that class. An endpoint may name a label
    with no node element type of its own (Aura Free accepted it on 2026-10-23); an empty node element
    type `(:Label =>)` is a syntax error there, so none is written.

    A property is typed from a mappable sh:datatype. It is a LIST<T NOT NULL> exactly when the load
    stores it as an array, which is the global multivalued decision of the load script
    (multivalued(data, shapes), references/pipeline.md, rule 10), and a scalar otherwise. It is NOT
    NULL when sh:minCount is at least 1 (Aura Free accepted `LIST<STRING NOT NULL> NOT NULL`). When two property shapes on one target map one key
    differently, the first (by shape IRI) is kept and the other is listed. Everything that has no
    GRAPH TYPE form is listed in left out. sep is the kept graph's separator (element_types)."""
    nodes, rels, left_out = element_types(cfg, shapes, data, sep)
    left_out += graph_type_omissions(nodes, rels)
    elements = [f"  (:{_q(label)} => {{" + ", ".join(_spec(k, props[k]) for k in sorted(props)) + "})"
                for label, props in sorted(nodes.items()) if props]
    for key, ends in sorted(rels.items()):
        if len(ends) == 1:
            (source, target), = ends
            elements.append(f"  (:{_q(source)})-[:{_q(key)} =>]->(:{_q(target)})")
    if not elements:
        raise ValueError("the shapes give no node or relationship element type; there is no GRAPH TYPE to write")
    statement = "CYPHER 25\nALTER CURRENT GRAPH TYPE SET {\n" + ",\n".join(elements) + "\n}"
    return statement, sorted(set(left_out))



def data_model(cfg, shapes, data, sep=SEPARATOR):
    """The shapes' element types as a DataModel of the Neo4j Data Modeling MCP server
    (mcp-neo4j-data-modeling 0.8.2, data_model.py at commit 0eaf613e0f), so its validate_data_model,
    export_to_arrows_json and get_mermaid_config_str can run on the projection (add-ons.md, L).

    It holds every element type of element_types, which is more than graph_type writes: one node per
    label that a shape targets or a relationship reaches, keyed on n10s's uri, typed properties or
    none; one property per typed key, a list typed LIST with its element type and NOT NULL in the
    description; one relationship per (source, key, target), every label pair kept. Labels and types
    are the kept graph's names (element_types, sep). metadata.left_out is element_types' list (what the shapes give no typed
    form); metadata.not_in_graph_type is graph_type_omissions' (what this model holds and a GRAPH TYPE
    cannot). graph_type's comments are exactly the two lists together."""
    nodes, rels, left_out = element_types(cfg, shapes, data, sep)
    omitted = graph_type_omissions(nodes, rels)
    for ends in rels.values():
        for source, target in ends:
            nodes.setdefault(source, {})
            nodes.setdefault(target, {})

    def prop(key, typed):
        notes = ([f"LIST<{typed.base} NOT NULL>"] if typed.listed else []) + (["NOT NULL"] if typed.required else [])
        return {"name": key, "type": "LIST" if typed.listed else typed.base,
                "description": "; ".join(notes) if notes else None}

    return {
        "nodes": [{"label": label, "key_property": {"name": "uri", "type": "STRING",
                                                    "description": "n10s_unique_uri: the resource's IRI"},
                   "properties": [prop(k, props[k]) for k in sorted(props)]}
                  for label, props in sorted(nodes.items())],
        "relationships": [{"type": key, "start_node_label": source, "end_node_label": target}
                          for key, ends in sorted(rels.items()) for source, target in sorted(ends)],
        "metadata": {"source": "ontology-to-lpg build.py data-model", "left_out": sorted(set(left_out)),
                     "not_in_graph_type": omitted},
    }


def _str(value, empty=True):
    return isinstance(value, str) and (empty or value != "")


def _property_problems(prop, where):
    """Property's fields under strict validation: a str name, an optional str type, a str or null
    description, a dict or null source."""
    if not isinstance(prop, dict):
        return [f"{where}: a property is not an object"]
    problems = []
    if not _str(prop.get("name")):
        problems.append(f"{where}: a property has no str name")
    for field, ok in (("type", lambda v: _str(v)), ("description", lambda v: v is None or _str(v)),
                      ("source", lambda v: v is None or isinstance(v, dict))):
        if field in prop and not ok(prop[field]):
            problems.append(f"{where}: property {prop.get('name')!r} has a bad {field}")
    return problems


def data_model_problems(model):
    """The DataModel rules of mcp-neo4j-data-modeling 0.8.2 (data_model.py at 0eaf613e0f: the Node,
    Relationship and DataModel fields under DataModel.model_validate(..., strict=True), and their
    validators), so a model this skill writes passes validate_data_model. test_modeling checks this
    list against that package on every case: fields of the right type (str names, labels and types,
    lists, dicts); a non-empty label and relationship type; a key property on every node; no property
    name repeated within one node or relationship, the key excepted; no repeated label; every
    relationship's start and end label a node of the model."""
    if not isinstance(model, dict):
        return ["the model is not an object"]
    problems, labels = [], []
    nodes, rels = model.get("nodes", []), model.get("relationships", [])
    if not isinstance(nodes, list) or not isinstance(rels, list) or not isinstance(model.get("metadata", {}), dict):
        return ["nodes and relationships must be lists, and metadata an object"]
    for node in nodes:
        if not isinstance(node, dict):
            problems.append("a node is not an object")
            continue
        label = node.get("label")
        if not _str(label, empty=False):
            problems.append(f"a node has no non-empty str label ({label!r})")
        key = node.get("key_property")
        if not isinstance(key, dict):
            problems.append(f"node {label!r} has no key property")
            key = {}
        else:
            problems += _property_problems(key, f"node {label!r} key")
        if not isinstance(node.get("properties", []), list):
            problems.append(f"node {label!r}: properties is not a list")
            continue
        for p in node.get("properties", []):
            problems += _property_problems(p, f"node {label!r}")
        if not (node.get("description") is None or _str(node.get("description"))) or \
                not isinstance(node.get("metadata", {}), dict):
            problems.append(f"node {label!r} has a bad description or metadata")
        names = [p.get("name") for p in node.get("properties", []) if isinstance(p, dict) and p.get("name") != key.get("name")]
        problems += [f"property {n!r} appears {names.count(n)} times in node {label!r}"
                     for n in sorted(set(names), key=str) if names.count(n) > 1]
        labels.append(label)
    problems += [f"node label {lb!r} appears {labels.count(lb)} times" for lb in sorted(set(labels), key=str)
                 if labels.count(lb) > 1]
    for rel in rels:
        if not isinstance(rel, dict):
            problems.append("a relationship is not an object")
            continue
        pattern = f"({rel.get('start_node_label')})-[{rel.get('type')}]->({rel.get('end_node_label')})"
        if not _str(rel.get("type"), empty=False):
            problems.append(f"relationship {pattern} has no non-empty str type")
        for end in ("start_node_label", "end_node_label"):
            if not _str(rel.get(end)) or rel.get(end) not in labels:
                problems.append(f"relationship {pattern}: its {end.split('_')[0]} node is not in the model")
        key = rel.get("key_property")
        if key is not None:
            problems += _property_problems(key, f"relationship {pattern} key")
        props = rel.get("properties", [])
        if not isinstance(props, list):
            problems.append(f"relationship {pattern}: properties is not a list")
            continue
        for p in props:
            problems += _property_problems(p, f"relationship {pattern}")
        key_name = key.get("name") if isinstance(key, dict) else None
        names = [p.get("name") for p in props if isinstance(p, dict) and p.get("name") != key_name]
        problems += [f"property {n!r} appears {names.count(n)} times in relationship {pattern}"
                     for n in sorted(set(names), key=str) if names.count(n) > 1]
    return problems


def check_report(man, rep):
    """report_earned(rep), plus the input and shapes fingerprints against the manifest."""
    fails = []
    for key in ("input_fingerprint", "shapes_fingerprint"):
        if rep.get(key) != man.get(key):
            fails.append(f"report {key} {rep.get(key)} does not match the manifest's {man.get(key)}: rerun load and verify")
    return fails + report_earned(rep)


def report_earned(rep):
    """Every check of a projection report that needs no manifest: the numbers, the two hashes, the
    shape counts, passed, a passing or no-op fail case for every compiled row (and compiled rows to
    exist), and the mutant. copy_graph.py and triplestore.py call it too, so neither trusts passed
    alone. Returns a list of failures."""
    fails = []
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
    fails += rename_proof_problems(rep)
    cases = rep.get("fail_cases")
    if not isinstance(cases, list) or not cases:
        fails.append("report has no fail cases (pipeline.md, rule 14)")
    compiled = rep.get("compiled")
    if not isinstance(compiled, list) or not compiled:
        fails.append("report lists no compiled rows (pipeline.md, rule 13)")
    else:
        def key(r):
            return (r.get("target"), r.get("path"), r.get("param"), json.dumps(r.get("value"), sort_keys=True, default=str))
        missing = {key(r) for r in compiled} - {key(c) for c in cases or [] if isinstance(c, dict)}
        if missing:
            fails.append(f"report has no fail case for {q(len(missing))} compiled row(s), such as {sorted(missing)[0]}")
    failed = [f"{c.get('target')} {c.get('path')} {c.get('param')}" for c in cases or []
              if not isinstance(c, dict) or c.get("status") not in ("passed", "no-op")]
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


def named_paths(argv, flag):
    """Every path argv names for flag, as `flag PATH` or `flag=PATH`, read before any flag is checked."""
    paths = []
    for i, arg in enumerate(argv):
        if arg == flag and i + 1 < len(argv) and not argv[i + 1].startswith("--"):
            paths.append(argv[i + 1])
        elif arg.startswith(flag + "=") and len(arg) > len(flag) + 1:
            paths.append(arg[len(flag) + 1:])
    return paths


def options(argv, multi=("--shapes",), flags=("--verify",)):
    opts, positional, args = {}, [], list(argv)
    while args:
        a = args.pop(0)
        if a in flags:
            opts[a] = True
        elif a.startswith("--"):
            if not args:
                raise Refusal("the last option has no value")
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
        raise Refusal("missing " + ", ".join(missing))


def load_config(path):
    with open(path, encoding="utf-8") as f:
        return cpr.Config(json.load(f))


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def main(argv):
    if not argv:
        print(q(USAGE), file=sys.stderr)
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
            print(f"wrote {q(opts['--output'])}: {q(len(merged))} triples from {q(len(data))} file(s)")
        elif command == "loadable":
            need(opts, "--output")
            if not data:
                raise ValueError("no data files")
            text = sorted_nt(parse(data))
            write(opts["--output"], text)
            print(f"wrote {q(opts['--output'])}: {q(text.count(chr(10)))} triples")
        elif command == "inferred":
            need(opts, "--input", "--reasoned", "--output")
            text = sorted_nt(inferred(parse([opts["--input"]]), parse([opts["--reasoned"]])))
            write(opts["--output"], text)
            print(f"wrote {q(opts['--output'])}: {q(text.count(chr(10)))} triples")
        elif command == "cypher":
            need(opts, "--config", "--output")
            if not data:
                raise ValueError("no data files")
            cfg = load_config(opts["--config"])
            if cfg.rule4 == "4b":
                print(q(cpr.RULE_4B_STOP.format(script="build.py cypher")), file=sys.stderr)
                return 2
            text = cypher(cfg, parse(data), parse(opts.get("--shapes", [])))
            write(opts["--output"], text)
            print(f"wrote {q(opts['--output'])}: {q(text.count(chr(10)))} statements")
        elif command == "manifest":
            need(opts, "--config", "--loadable", "--inferred", "--output")
            root = os.path.dirname(os.path.abspath(opts["--output"]))
            text = dump(manifest(load_config(opts["--config"]), data, opts.get("--shapes", []),
                                 opts["--loadable"], opts["--inferred"], root))
            if opts.get("--verify"):
                current = b""
                if os.path.exists(opts["--output"]):
                    with open(opts["--output"], "rb") as f:  # bytes, so a changed line ending is a difference too
                        current = f.read()
                if current != text.encode("utf-8"):
                    print(f"FAIL {q(opts['--output'])} is not current: rerun build.py manifest and commit it")
                    return 1
                print(f"{q(opts['--output'])} is current")
            else:
                write(opts["--output"], text)
                print(f"wrote {q(opts['--output'])}")
        elif command == "check-serialised":
            need(opts, "--loadable", "--inferred")
            fails = check_serialised(read_bytes(opts["--loadable"]), read_bytes(opts["--inferred"]))
            for message in fails:
                print(f"FAIL {q(message)}")
            if fails:
                return 1
            print("loadable.nt and inferred.nt are in byte order, and inferred.nt holds only kept inferences")
        elif command == "graph-type":
            need(opts, "--config", "--output")
            if not data:
                raise ValueError("give the data files: the property types follow the load's multivalued list")
            cfg, sep = load_config(opts["--config"]), separator(opts)
            check_prefixes(cfg.prefixes, sep)   # as the load refuses it: such names could not be read back
            statement, left_out = graph_type(cfg, parse(opts.get("--shapes", [])), parse(data), sep)
            # The statement goes to a file, never to the terminal; each left-out line is one quoted
            # Cypher comment, so a shapes term cannot break out of it.
            write(opts["--output"], statement + "\n" + "".join(comment("left out: " + line) + "\n" for line in left_out))
            print(f"wrote {q(opts['--output'])}: {q(statement.count(' =>'))} element types, {q(len(left_out))} left out")
        elif command == "data-model":
            need(opts, "--config", "--output")
            if not data:
                raise ValueError("give the data files: the property types follow the load's multivalued list")
            cfg, sep = load_config(opts["--config"]), separator(opts)
            check_prefixes(cfg.prefixes, sep)
            model = data_model(cfg, parse(opts.get("--shapes", [])), parse(data), sep)
            problems = data_model_problems(model)
            for message in problems:
                print(f"FAIL {q(message)}")
            if problems:
                return 1
            write(opts["--output"], dump(model))
            print(f"wrote {q(opts['--output'])}: {q(len(model['nodes']))} nodes, "
                  f"{q(len(model['relationships']))} relationships, {q(len(model['metadata']['left_out']))} left out")
        elif command == "check-report":
            need(opts, "--manifest", "--report")
            with open(opts["--manifest"], encoding="utf-8") as f:
                man = json.load(f)
            with open(opts["--report"], encoding="utf-8") as f:
                rep = json.load(f)
            fails = check_report(man, rep)
            for message in fails:
                print(f"FAIL {q(message)}")
            if fails:
                return 1
            print("the report is current and passed")
        else:
            raise ValueError(f"unknown command {command!r}")
    except (OSError, ValueError) as exc:
        print(f"ERROR {q(exc)}", file=sys.stderr)
        return 2
    except Exception as exc:  # rdflib raises several parser types; any of them stops the run
        print(f"ERROR cannot read the RDF files: {q(exc)}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
