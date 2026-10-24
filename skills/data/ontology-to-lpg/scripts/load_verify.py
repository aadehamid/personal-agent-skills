#!/usr/bin/env python3
"""The load and verify steps against a running Neo4j with n10s and APOC, ending in the report.

Run: NEO4J_PASSWORD=... uv run --no-project --with rdflib --with neo4j python3 load_verify.py \
         --config <config.json> --shapes <shapes.ttl>... --bolt bolt://127.0.0.1:<port> \
         --import-dir <folder mounted at /import> --merged merged.ttl --loadable loadable.nt \
         --inferred inferred.nt --report projection-report.json [--plugins-dir <folder>]
         [--manual-cases <cases.json>] [--container <name> | --compose-project <name>] <data.ttl>...

The container name only goes into the printed clean-up line: with --compose-project (the -p name the
services were started under from docker/compose.yaml) it is `docker compose -p <name> ... down -v`;
else `docker rm -f -v` of --container, $LPG_CONTAINER or lpg-projection. Every value printed for
pasting is shell-quoted; a NOT COMPILED line is one quoted JSON object.

The gate is what n10s says it compiled. What it does, in order (references/pipeline.md, rules 8 to 17):
  1. Writes the import-safe shapes (in_graph_shapes.subset) and copies merged.ttl, loadable.nt and
     inferred.nt into the import folder.
  2. Empties the database: every node, then every constraint; checks both are gone.
  3. Runs the load script build.py generates, one statement at a time. onto.import and both
     rdf.import calls must return terminationStatus OK; the shapes import must return as many rows as
     n10s.validation.shacl.listShapes() lists, and more than zero.
  4. Reads listShapes() back (columns target, propertyOrRelationshipPath, param, value) and compares
     it with the shapes file by target, path, param and value: every constraint the file states that
     n10s did not compile is printed and listed in the report (not_compiled). It does not fail the
     run: validate_data.py ran all of them before the load. The in_graph_shapes.py prediction is
     compared too (prediction_differences), for information only.
  5. Validates in the graph (zero violations required).
  6. Runs one fail case per compiled row (target, path, param, value), each in a transaction that is
     rolled back. A case creates its own node with the target label and breaks only that row, so it
     needs no matching data. It passes when validate() reports that node with one of the param's
     expected components (the propertyShape column) on the row's path (resultPath). A row the
     generator cannot build a case for fails the run unless --manual-cases gives one, which runs the
     same way. sh:disjoint, which n10s 2025.06.1 lists as an sh:hasValue row whose value is the
     other property, gets its own disjoint case.
  7. Commits the deliberate mutant (removes one required literal), requires a violation on its focus
     node, restores the value, and requires zero violations again.
  8. Exports the resources, leaves out schema rows, rebuilds tagged literals, normalises values and
     diffs against loadable.nt plus inferred.nt.
  9. Hashes the graph, empties it, overwrites the import copy of loadable.nt with its lines shuffled
     (random.Random(12)), loads again, hashes again, and puts the sorted file back.
 10. Writes the report. It deletes any report at --report when it starts, writes a temporary file,
     and renames it to --report only when every check passed (exit 0). It deletes <report>.failed
     at the start too. Any other outcome leaves no report at --report: a failed check writes its
     details to <report>.failed (exit 1); a driver or file error writes nothing (exit 1); bad
     input writes nothing (exit 2).

The graph hash (graph_hash): every :Resource node as [uri, sorted labels, properties] and every
relationship between two :Resource nodes as [source uri, type, target uri, relationship uri or "",
relationship properties]; both lists sorted (nodes by uri, relationships by their first four fields,
a missing uri counting as ""); property maps with sorted keys; list values in their stored order (the
load sorts them); any value JSON cannot hold (dates, times, durations, points) written as {"type": <module.Type>,
"value": str()}, so it never equals a string;
the whole serialised with json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False),
encoded as UTF-8 and hashed with SHA-256. Schema nodes from onto.import are :Resource nodes and are
included: they come from the same files on both loads.
"""
import json
import os
import random
import re
import shutil
import sys
import tempfile

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import OWL, RDF, RDFS, SH, XSD

import build
from shell import q
import check_projection_rules as cpr
import in_graph_shapes as igs

SCHEMA_NS = "neo4j://graph.schema#"
EXPORT = ("CALL n10s.rdf.export.cypher('MATCH (n:Resource) OPTIONAL MATCH (n)-[r]->(m) RETURN n, r, m') "
          "YIELD subject, predicate, object, isLiteral, literalType, literalLang "
          "RETURN subject, predicate, object, isLiteral, literalType, literalLang")
VALIDATE = ("CALL n10s.validation.shacl.validate() YIELD focusNode, propertyShape, resultPath, resultMessage "
            "RETURN focusNode, propertyShape, resultPath, resultMessage")
# n10s 2025.06.1 sometimes exports a tagged string, notably one that holds a newline, as an
# xsd:string "text@en" with no literalLang. DOTALL lets the text span lines. Safe because the check
# step refuses any source string that ends like a tag (pipeline.md, rule 3).
TAGGED_TEXT = re.compile(r"^(.*)@([A-Za-z]{1,8}(?:-[A-Za-z0-9]{1,8})*)$", re.S)
INTEGERS = {XSD.integer, XSD.long, XSD.int, XSD.short, XSD.byte, XSD.nonNegativeInteger, XSD.positiveInteger}


class Failed(Exception):
    pass


# ---------- pure parts (tested without Neo4j) ----------

def canonical(term):
    """One spelling per value: plain = xsd:string; integer types as xsd:integer; decimal, double and
    float as a double (pipeline.md, rule 16)."""
    if not isinstance(term, Literal) or term.language:
        return term
    if term.datatype in (None, XSD.string):
        return Literal(str(term))
    if term.datatype in INTEGERS:
        return Literal(int(term), datatype=XSD.integer)
    if term.datatype in (XSD.decimal, XSD.double, XSD.float):
        return Literal(repr(float(term)), datatype=XSD.double)
    return term


def canonical_graph(g):
    out = Graph()
    for s, p, o in g:
        out.add((s, p, canonical(o)))
    return out


def is_schema_row(row):
    return (str(row["subject"]).startswith(SCHEMA_NS) or str(row["predicate"]).startswith(SCHEMA_NS)
            or (not row["isLiteral"] and str(row["object"]).startswith(SCHEMA_NS)))


def row_object(row):
    if not row["isLiteral"]:
        return URIRef(row["object"])
    text, lang, dtype = row["object"], row.get("literalLang"), row.get("literalType")
    if lang:
        return Literal(text, lang=lang)
    if dtype in (None, "", str(XSD.string)):
        m = TAGGED_TEXT.match(str(text))
        if m:
            return Literal(m.group(1), lang=m.group(2))
        return Literal(str(text))
    return Literal(text, datatype=URIRef(dtype))


def rows_to_graph(rows):
    """The exported data as a graph, schema rows left out. Returns (graph, schema rows skipped)."""
    g, skipped = Graph(), 0
    for row in rows:
        if is_schema_row(row):
            skipped += 1
            continue
        g.add((URIRef(row["subject"]), URIRef(row["predicate"]), row_object(row)))
    return g, skipped


def diff(source, exported):
    from rdflib.compare import graph_diff, to_isomorphic
    _, lost, added = graph_diff(to_isomorphic(canonical_graph(source)), to_isomorphic(canonical_graph(exported)))
    return sorted(" ".join(t.n3() for t in x) for x in lost), sorted(" ".join(t.n3() for t in x) for x in added)


def _plain(value):
    """A property value as JSON. A value JSON cannot hold (a date, a time, a duration, a point) is
    written as {"type": <its Python type, module included>, "value": <its str()>}, so a date and the
    string of the same text hash differently."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return {"type": f"{type(value).__module__}.{type(value).__qualname__}", "value": str(value)}


def graph_hash(nodes, edges):
    """SHA-256 of the canonical JSON described in the module docstring."""
    node_list = sorted(([n["uri"], sorted(n["labels"]), {k: _plain(v) for k, v in n["props"].items()}]
                        for n in nodes), key=lambda x: x[0])
    edge_list = sorted(([e["s"], e["t"], e["o"], e["u"] or "", {k: _plain(v) for k, v in (e["props"] or {}).items()}]
                        for e in edges), key=lambda x: x[:4])
    text = json.dumps({"nodes": node_list, "relationships": edge_list}, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)
    return build.sha_bytes(text.encode("utf-8"))


def shuffled(text, seed=12):
    lines = text.splitlines()
    random.Random(seed).shuffle(lines)
    return "".join(line + "\n" for line in lines)


# Each listShapes param's components; a case passes on any one of them. n10s 2025.06.1 names the
# node-kind param "sh:NodeKind" and lists a closed shape as "sh:ignoredProperties" with no path.
EXPECTED = {
    "sh:minCount": {"CountConstraintComponent", "MinCountConstraintComponent"},
    "sh:maxCount": {"CountConstraintComponent", "MaxCountConstraintComponent"},
    "sh:datatype": {"DatatypeConstraintComponent"},
    "sh:class": {"ClassConstraintComponent"},
    "sh:in": {"InConstraintComponent"},
    "sh:NodeKind": {"NodeKindConstraintComponent"},
    "sh:hasValue": {"HasValueConstraintComponent"},
    "sh:disjoint": {"DisjointConstraintComponent"},
    "sh:minInclusive": {"ValueRangeConstraintComponent", "MinInclusiveConstraintComponent"},
    "sh:maxInclusive": {"ValueRangeConstraintComponent", "MaxInclusiveConstraintComponent"},
    "sh:minExclusive": {"ValueRangeConstraintComponent", "MinExclusiveConstraintComponent"},
    "sh:maxExclusive": {"ValueRangeConstraintComponent", "MaxExclusiveConstraintComponent"},
    "sh:minLength": {"LengthConstraintComponent", "MinLengthConstraintComponent"},
    "sh:maxLength": {"LengthConstraintComponent", "MaxLengthConstraintComponent"},
    "sh:ignoredProperties": {"ClosedConstraintComponent"},
}
# How a term of the shapes file appears as a listShapes param.
LISTED_AS = {**igs.LISTED_AS, SH.closed: "sh:ignoredProperties"}
UNREAD_TERMS = (SH.languageIn, SH.uniqueLang, SH.lessThan, SH.lessThanOrEquals, SH.equals, SH.qualifiedValueShape,
                SH.qualifiedMinCount, SH.qualifiedMaxCount, SH.qualifiedValueShapesDisjoint, SH["not"], SH["and"], SH["or"], SH.xone, SH.sparql, SH.targetNode, SH.targetSubjectsOf,
                SH.targetObjectsOf)
FILE_TERMS = (SH.minCount, SH.maxCount, SH.datatype, SH["class"], SH.nodeKind, SH["in"], SH.hasValue, SH.disjoint,
              SH.minInclusive, SH.maxInclusive, SH.minExclusive, SH.maxExclusive, SH.minLength, SH.maxLength)


def component(value):
    return str(value).rsplit("#", 1)[-1]


def name_of(iri, cfg):
    """The SHORTEN name n10s gives an IRI, or the IRI in angle brackets when no prefix covers it."""
    try:
        return build.shorten(URIRef(iri), cfg)
    except ValueError:
        return f"<{iri}>"


def iri_of(name, cfg):
    prefix, sep, local = str(name).partition("__")
    if sep and prefix in cfg.prefixes:
        return URIRef(cfg.prefixes[prefix] + local)
    return None


# ---------- the shapes file against the engine ----------

def _targets(g, shape, seen=None):
    """The class targets SHACL applies a shape to: its sh:targetClass, itself when it is an
    rdfs:Class, and those of every shape that reaches it through sh:property or sh:node."""
    seen = set() if seen is None else seen
    if shape in seen:
        return set()
    seen.add(shape)
    found = set(g.objects(shape, SH.targetClass))
    if (shape, RDF.type, RDFS.Class) in g:
        found.add(shape)
    # sh:node from a node shape keeps the focus; from a property shape it applies to the values.
    node_parents = {p for p in g.subjects(SH.node, shape) if (p, SH.path, None) not in g}
    for parent in set(g.subjects(SH.property, shape)) | node_parents:
        found |= _targets(g, parent, seen)
    return found


def _listed_value(g, term, value, cfg):
    """The value as n10s 2025.06.1 lists it: a class as its SHORTEN name, an sh:in list as its
    members' IRIs, sh:hasValue and sh:disjoint as a one-member list, anything else as written."""
    if term == SH["class"]:
        return name_of(value, cfg)
    if term == SH["in"]:
        return [str(m) for m in Collection(g, value)]
    if term in (SH.hasValue, SH.disjoint):
        return [str(value)]
    return value.toPython() if isinstance(value, Literal) else str(value)


def _shown(g, value):
    """A term as the report shows it: an RDF list as its members, anything else as text."""
    if isinstance(value, BNode) and (value, RDF.first, None) in g:
        return [str(m) for m in Collection(g, value)]
    return str(value)


def value_key(value):
    """One spelling of a listed or stated value for comparing them: lists sorted, numbers as text."""
    if isinstance(value, (list, tuple)):
        return json.dumps(sorted(str(v) for v in value))
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return repr(float(value))
    return str(value)


def file_constraints(g, cfg):
    """Every constraint the shapes file states, as dicts with target (a SHORTEN name, or a note when
    nothing gives the shape a class target), path (None for a node-level constraint), term (as
    listShapes names it), file_term, value (as listShapes would list it; for sh:closed the
    sh:ignoredProperties names, which is what its row lists), raw, inverse and shape."""
    out = []

    def add(shape, targets, **c):
        for target in targets or [f"(no class target: {shape.n3(g.namespace_manager)})"]:
            out.append(dict(c, target=target, shape=shape.n3(g.namespace_manager)))

    for ps in sorted(set(g.subjects(SH.path, None)), key=str):
        path = g.value(ps, SH.path)
        inverse = g.value(path, SH.inversePath) if isinstance(path, BNode) else None
        path_name = name_of(inverse or path, cfg) if isinstance(inverse or path, URIRef) else "(a complex path)"
        targets = sorted(name_of(t, cfg) for t in _targets(g, ps))
        for term in FILE_TERMS:
            for value in g.objects(ps, term):
                add(ps, targets, path=path_name, term=LISTED_AS.get(term, "sh:" + component(term)),
                    file_term="sh:" + component(term), value=_listed_value(g, term, value, cfg), raw=str(value),
                    inverse=inverse is not None)
    for shape in sorted(set(g.subjects(SH["class"], None)) - set(g.subjects(SH.path, None)), key=str):
        for value in g.objects(shape, SH["class"]):
            add(shape, sorted(name_of(t, cfg) for t in _targets(g, shape)), path=None, term="sh:class",
                file_term="sh:class", value=name_of(value, cfg), raw=str(value), inverse=False)
    # Terms n10s 2025.06.1 never compiles: they cannot match a listShapes row, so each is reported.
    for s_, p_, o_ in sorted(g.triples((None, None, None)), key=lambda t: tuple(str(x) for x in t)):
        if p_ in UNREAD_TERMS or (p_ == SH.node and (s_, SH.path, None) in g):
            path = g.value(s_, SH.path)
            add(s_, sorted(name_of(t, cfg) for t in _targets(g, s_)),
                path=name_of(path, cfg) if isinstance(path, URIRef) else None, term="sh:" + component(p_),
                file_term="sh:" + component(p_), value=_shown(g, o_), raw=str(_shown(g, o_)), inverse=False)
    for shape in sorted(set(g.subjects(SH.closed, Literal(True))), key=str):
        ignored = sorted(name_of(m, cfg) for lst in g.objects(shape, SH.ignoredProperties) for m in Collection(g, lst))
        add(shape, sorted(name_of(t, cfg) for t in _targets(g, shape)), path=None, term="sh:ignoredProperties",
            file_term="sh:closed", value=ignored, raw=f"true, ignoring {ignored}", inverse=False)
    return out


def listed_rows(session):
    return [{"target": r["target"], "path": r["propertyOrRelationshipPath"], "param": r["param"], "value": r["value"]}
            for r in session.run("CALL n10s.validation.shacl.listShapes()").data()]


def not_compiled(constraints, rows):
    """The constraints of the shapes file with no listShapes row for the same target, path, param
    and value (for sh:closed, the value is its sh:ignoredProperties list, compared exactly). Each
    row answers at most one constraint, so a second shape stating the same thing on the same target
    is still found when n10s compiled only one of them."""
    left = {}
    for r in rows:
        key = (r["target"], r["path"], r["param"])
        left.setdefault(key, []).append(value_key(r["value"]))
    missing = []
    for c in constraints:
        values = left.get((c["target"], c["path"], c["term"]), [])
        want = value_key(c["value"])
        match = next((v for v in values if v == want), None)
        if match is None:
            missing.append(c)
        else:
            values.remove(match)
    return missing


# ---------- fail cases, one per compiled row ----------
#
# Every case creates its own node in a transaction that is rolled back, so it needs no matching data:
# a node with the target label and a known uri (the focus), given exactly what breaks the one row.
# A case passes when validate() reports that focus with one of the row's components on the row's
# path (resultPath, the path's full IRI). A node carrying only what the case gives it violates other
# rows too; matching the path and the component keeps those apart.

def _literal(value):
    return json.dumps(value)


FOCUS = "urn:lpg-projection:fail-case:"
SAMPLES = {str(XSD.integer): "{i}", str(XSD.decimal): "{i}.5", str(XSD.float): "{i}.5", str(XSD.double): "{i}.5",
           str(XSD.boolean): "true", str(XSD.date): "date('2020-01-{i:02d}')",
           str(XSD.dateTime): "datetime('2020-01-{i:02d}T00:00:00Z')"}


def sample(datatype, i=1):
    """A Cypher literal of the datatype n10s stores for it (text for anything else), numbered i."""
    return SAMPLES.get(str(datatype), "'value {i}'").format(i=i)


def is_literal(target, path, constraints, literal_preds, cfg):
    """Whether n10s stores the path as a property (True) or a relationship (False) on this target:
    from the shapes when they say (sh:datatype or sh:minLength/maxLength or a range means a value;
    sh:class or sh:nodeKind sh:IRI means a node), else from the data and the ontology."""
    mine = [c for c in constraints if c["target"] == target and c["path"] == path]
    if any(c["file_term"] in ("sh:datatype", "sh:minLength", "sh:maxLength", "sh:minInclusive", "sh:maxInclusive",
                              "sh:minExclusive", "sh:maxExclusive") for c in mine):
        return True
    if any(c["file_term"] == "sh:class" or (c["file_term"] == "sh:nodeKind" and c["raw"] == str(SH.IRI))
           for c in mine):
        return False
    return iri_of(path, cfg) in literal_preds


def case_for(row, constraints, literal_preds, cfg, index=1):
    """(param whose components count, expected resultPath IRI or None for any, Cypher returning the
    focus uri; the Cypher is None for a row nothing can violate and "" when no case can be generated)."""
    T, k, param, value = row["target"], row["path"], row["param"], row["value"]
    focus = FOCUS + str(index)
    base = f"CREATE (n:Resource:`{T}` {{uri: {_literal(focus)}}}) "
    end = "RETURN n.uri AS focus"

    def new_node(i):
        return f"(:Resource {{uri: {_literal(focus + '/value-' + str(i))}}})"

    if param == "sh:ignoredProperties":
        key_iri = URIRef(cfg.own[0] + "notInTheShape")
        return param, str(key_iri), base + f"SET n.`{name_of(key_iri, cfg)}` = 'not in the shape' " + end
    if k is None:
        if param == "sh:class":
            return param, None, (None if value == T else base + end)
        return param, None, ""
    path_iri = str(iri_of(k, cfg) or "")
    mine = [c for c in constraints if c["target"] == T and c["path"] == k]
    inverse = bool(mine) and all(c["inverse"] for c in mine)
    literal = is_literal(T, k, constraints, literal_preds, cfg)
    dtype = next((c["raw"] for c in mine if c["file_term"] == "sh:datatype"), None)
    if param == "sh:hasValue" and isinstance(value, list) and len(value) == 1 and \
            any(c["file_term"] == "sh:disjoint" and c["raw"] == str(value[0]) for c in mine):
        k2 = name_of(URIRef(value[0]), cfg)
        if literal:
            v = sample(dtype)
            return "sh:disjoint", path_iri, base + f"SET n.`{k}` = {v}, n.`{k2}` = {v} " + end
        return "sh:disjoint", path_iri, base + f"CREATE (n)-[:`{k}`]->(m{new_node(1)[1:]} CREATE (n)-[:`{k2}`]->(m) " + end
    if param in ("sh:minCount", "sh:minLength") and int(value) < 1:
        return param, path_iri, None
    # A minimum gets one value fewer than it asks for, a maximum one more: the near miss, so a check
    # that enforced a weaker bound would not fire.
    short = int(value) - 1 if param == "sh:minCount" else 0
    if inverse:
        if param == "sh:minCount":
            edges = " ".join(f"CREATE (n)<-[:`{k}`]-{new_node(i)}" for i in range(1, short + 1))
            return param, path_iri, base + edges + (" " if edges else "") + end
        if param == "sh:maxCount":
            edges = " ".join(f"CREATE (n)<-[:`{k}`]-{new_node(i)}" for i in range(1, int(value) + 2))
            return param, path_iri, base + edges + " " + end
        return param, path_iri, ""
    if param == "sh:minCount":
        if short == 0:
            return param, path_iri, base + end
        if literal:
            values = [sample(dtype, i) for i in range(1, short + 1)]
            stored = values[0] if short == 1 else "[" + ", ".join(values) + "]"
            return param, path_iri, base + f"SET n.`{k}` = {stored} " + end
        edges = " ".join(f"CREATE (n)-[:`{k}`]->{new_node(i)}" for i in range(1, short + 1))
        return param, path_iri, base + edges + " " + end
    if param == "sh:maxCount":
        extra = int(value) + 1
        if literal:
            values = [sample(dtype, i) for i in range(1, extra + 1)]
            stored = values[0] if extra == 1 else "[" + ", ".join(values) + "]"
            return param, path_iri, base + f"SET n.`{k}` = {stored} " + end
        edges = " ".join(f"CREATE (n)-[:`{k}`]->{new_node(i)}" for i in range(1, extra + 1))
        return param, path_iri, base + edges + " " + end
    if param == "sh:datatype" and literal:
        wrong = "0" if value == str(XSD.string) else "'not a value of this datatype'"
        return param, path_iri, base + f"SET n.`{k}` = {wrong} " + end
    if param in ("sh:class", "sh:in") and not literal:
        return param, path_iri, base + f"CREATE (n)-[:`{k}`]->{new_node(1)} " + end
    if param == "sh:NodeKind":
        if value in (str(SH.IRI), str(SH.BlankNodeOrIRI)) and not literal:
            return param, path_iri, base + f"SET n.`{k}` = 'not an IRI' " + end
        if value == str(SH.Literal) and literal:
            return param, path_iri, base + f"CREATE (n)-[:`{k}`]->{new_node(1)} " + end
        return param, path_iri, ""
    if param == "sh:hasValue" and not literal:
        return param, path_iri, base + end
    deltas = {"sh:minInclusive": "- 1", "sh:maxInclusive": "+ 1", "sh:minExclusive": "- 0", "sh:maxExclusive": "+ 0"}
    if param in deltas and literal and isinstance(value, (int, float)) and not isinstance(value, bool):
        return param, path_iri, base + f"SET n.`{k}` = {value} {deltas[param]} " + end
    if param == "sh:minLength" and literal:
        return param, path_iri, base + f"SET n.`{k}` = {_literal('x' * (int(value) - 1))} " + end
    if param == "sh:maxLength" and literal:
        return param, path_iri, base + f"SET n.`{k}` = {_literal('x' * (int(value) + 1))} " + end
    return param, path_iri, ""


def row_key(row):
    return (row["target"], row["path"], row["param"], json.dumps(row["value"], sort_keys=True, default=str))


def plan_cases(rows, constraints, literal_preds, cfg, manual=()):
    """One planned case per compiled row: dicts with the row, the param whose components count, the
    path validate() must report, and the Cypher (None for a row nothing can violate, "" when no
    case can be generated and --manual-cases gives none). A manual case's Cypher must return the uri
    of the node it breaks as focus; any path is accepted for it."""
    by_key = {(m["target"], m.get("path"), m["param"]): m["cypher"] for m in manual}
    planned, seen = [], set()
    for row in sorted(rows, key=lambda r: tuple(str(x) for x in row_key(r))):
        if row_key(row) in seen:
            continue
        seen.add(row_key(row))
        param, path, cypher = case_for(row, constraints, literal_preds, cfg, len(planned) + 1)
        source = "generated"
        if cypher == "" and (row["target"], row["path"], row["param"]) in by_key:
            cypher, path, source = by_key[(row["target"], row["path"], row["param"])], None, "manual"
        case = {"target": row["target"], "path": row["path"], "param": row["param"], "value": row["value"],
                "expected_param": param, "expected_path": path, "cypher": cypher, "source": source}
        if row["param"] == "sh:ignoredProperties":
            # The compiled ignore-lists on this target must equal the file's, both ways: a compiled list
            # the file does not state, or a file list with no equal compiled row (a wider row compiled
            # in its place), would let n10s accept properties the file forbids, while the case below
            # still fires on a property neither list names.
            file_lists = {value_key(c["value"]) for c in constraints
                          if c["term"] == "sh:ignoredProperties" and c["target"] == row["target"]}
            compiled_lists = {value_key(r["value"]) for r in rows
                              if r["param"] == "sh:ignoredProperties" and r["target"] == row["target"]}
            if value_key(row["value"]) not in file_lists or file_lists - compiled_lists:
                case["mismatch"] = ("the compiled sh:ignoredProperties on this target differ from the closed shapes' "
                                    "lists in the shapes file")
        planned.append(case)
    return planned


def mutant_targets(rows, constraints, literal_preds, cfg):
    """The candidates for the deliberate mutant, in order: every compiled minCount of at least 1 on a
    literal value that is not an inverse path. run() takes the first one some node holds."""
    out = []
    for row in sorted(rows, key=lambda r: tuple(str(x) for x in row_key(r))):
        if row["param"] == "sh:minCount" and row["path"] and int(row["value"]) >= 1 \
                and iri_of(row["path"], cfg) in literal_preds:
            mine = [c for c in constraints if c["target"] == row["target"] and c["path"] == row["path"]]
            if not (mine and all(c["inverse"] for c in mine)) and (row["target"], row["path"]) not in out:
                out.append((row["target"], row["path"]))
    return out


def read_manual_cases(path):
    if not path:
        return []
    with open(path, encoding="utf-8") as f:
        cases = json.load(f)
    if not isinstance(cases, list) or not all(isinstance(c, dict) and c.get("target") and c.get("param")
                                              and str(c.get("cypher") or "").strip() for c in cases):
        raise ValueError(f"{path} must be a JSON list of objects with target, path, param and cypher")
    return cases


# ---------- the database ----------

def wipe(session):
    session.run("MATCH (n) DETACH DELETE n").consume()
    for name in session.run("SHOW CONSTRAINTS YIELD name RETURN name").value():
        session.run(f"DROP CONSTRAINT `{name}`").consume()
    left = session.run("MATCH (n) RETURN count(n) AS n").single()["n"]
    constraints = session.run("SHOW CONSTRAINTS YIELD name RETURN count(*) AS n").single()["n"]
    if left or constraints:
        raise Failed(f"the database is not empty after the wipe: {left} nodes, {constraints} constraints")


def load(session, statements):
    """Run the load script; check each import. Returns (shapes import rows, listShapes count)."""
    shapes_rows = None
    for stmt in statements:
        result = session.run(stmt)
        rows = result.data()
        if "n10s.validation.shacl.import" in stmt:
            shapes_rows = len(rows)
        elif "n10s.rdf.import" in stmt or "n10s.onto.import" in stmt:
            status = rows[0].get("terminationStatus") if rows else None
            if status != "OK":
                raise Failed(f"{stmt} returned terminationStatus {status!r}: {rows[:1]}")
    listed = session.run("CALL n10s.validation.shacl.listShapes() YIELD target RETURN count(*) AS n").single()["n"]
    if not shapes_rows or shapes_rows != listed:
        raise Failed(f"the shapes import returned {shapes_rows} rows but listShapes() lists {listed}")
    return shapes_rows, listed


def violations(runner):
    return runner.run(VALIDATE).data()


def case_result(case, focus, rows):
    """The status of one case from validate()'s rows: passed when a row names the focus, one of the
    expected components and, when the case gives one, the expected path."""
    expected = EXPECTED.get(case["expected_param"], set())
    seen = sorted({component(r["propertyShape"]) for r in rows if r["focusNode"] == focus
                   and (case.get("expected_path") is None or r.get("resultPath") == case["expected_path"])})
    return seen, ("passed" if focus and set(seen) & expected else "failed")


def run_cases(session, planned):
    results = []
    for case in planned:
        result = dict(case, focus=None, components=[], expected=sorted(EXPECTED.get(case["expected_param"], set())))
        if case.get("mismatch"):
            result["status"] = "failed"
        elif case["cypher"] is None:
            result["status"] = "no-op"
        elif case["cypher"] == "":
            result["status"] = "no case"
        else:
            tx = session.begin_transaction()
            try:
                record = tx.run(case["cypher"]).single()
                focus = record["focus"] if record else None
                rows = violations(tx) if focus else []
            finally:
                tx.rollback()
            seen, status = case_result(case, focus, rows)
            result.update(focus=focus, components=seen, status=status)
        results.append(result)
    return results


def mutant(session, label, key):
    """The committed mutant on the first node holding the key, or None when no node holds it."""
    record = session.run(f"MATCH (n:`{label}`) WHERE n.`{key}` IS NOT NULL WITH n ORDER BY n.uri LIMIT 1 "
                         f"RETURN n.uri AS uri, n.`{key}` AS value").single()
    if record is None:
        return None
    uri, value = record["uri"], record["value"]
    session.run(f"MATCH (n:Resource {{uri: $uri}}) REMOVE n.`{key}`", uri=uri).consume()
    caught = [r for r in violations(session) if r["focusNode"] == uri]
    session.run(f"MATCH (n:Resource {{uri: $uri}}) SET n.`{key}` = $value", uri=uri, value=value).consume()
    after = violations(session)
    return {"focus": uri, "removed": key, "violations": len(caught), "after_restore": len(after)}


def hash_graph(session):
    nodes = session.run("MATCH (n:Resource) RETURN n.uri AS uri, labels(n) AS labels, properties(n) AS props").data()
    edges = session.run("MATCH (a:Resource)-[r]->(b:Resource) RETURN a.uri AS s, type(r) AS t, b.uri AS o, "
                        "r.uri AS u, properties(r) AS props").data()
    schema = sum(1 for e in edges if e["t"].startswith("n4sch__"))
    return graph_hash(nodes, edges), len(nodes), len(edges), schema


def plugin_checksums(folder):
    if not folder:
        return {}
    return {name: build.sha_bytes(build.read_bytes(os.path.join(folder, name)))
            for name in sorted(os.listdir(folder)) if name.endswith(".jar")}


# ---------- the run ----------

def run(driver, cfg, data_paths, shape_paths, import_dir, merged, loadable, inferred, plugins_dir=None, manual=()):
    data, shapes = build.parse(data_paths), build.parse(shape_paths)
    safe, left_out = igs.subset(shapes)
    safe.serialize(os.path.join(import_dir, "shapes-in-graph.ttl"), format="turtle")
    for src, name in ((merged, "merged.ttl"), (loadable, "loadable.nt"), (inferred, "inferred.nt")):
        shutil.copyfile(src, os.path.join(import_dir, name))
    statements = [line for line in build.cypher(cfg, data, shapes).splitlines() if line.strip()]
    loadable_text = open(loadable, encoding="utf-8").read()
    inferred_text = open(inferred, encoding="utf-8").read()
    literal_preds = {p for _, p, o in data if isinstance(o, Literal)} | set(data.subjects(RDF.type, OWL.DatatypeProperty))
    constraints = file_constraints(safe, cfg)
    report = {
        "input_fingerprint": build.sha_bytes(build.read_bytes(loadable), build.read_bytes(inferred)),
        "shapes_fingerprint": build.sha_bytes(*(build.read_bytes(p) for p in shape_paths)),
        "left_out_before_import": [{"shape": str(s), "constraint": str(p), "reason": r} for s, p, r in left_out],
        "versions": cfg.versions,
        "plugin_jars_sha256": plugin_checksums(plugins_dir),
    }
    with driver.session() as session:
        wipe(session)
        report["shapes_import_rows"], report["in_graph_shape_constraints"] = load(session, statements)
        rows = listed_rows(session)
        report["compiled"] = rows
        report["not_compiled"] = not_compiled(constraints, rows)
        predicted = igs.predict(safe, lambda iri: name_of(iri, cfg))
        listed = {(r["target"], r["path"], r["param"]) for r in rows}
        report["prediction_differences"] = {"predicted_not_listed": sorted(map(list, predicted - listed), key=str),
                                            "listed_not_predicted": sorted(map(list, listed - predicted), key=str)}
        found = violations(session)
        report["shacl_violations_in_graph"] = len(found)
        report["fail_cases"] = run_cases(session, plan_cases(rows, constraints, literal_preds, cfg, manual))
        m = None
        for target in mutant_targets(rows, constraints, literal_preds, cfg):
            m = mutant(session, *target)
            if m is not None:
                break
        if m is None:
            raise Failed("no node holds a value for any compiled minCount of at least 1 on a literal, so there "
                         "is no mutant")
        report["mutant"] = m
        report["in_graph_mutant_violations"] = m["violations"]
        exported_rows = session.run(EXPORT).data()
        exported, skipped = rows_to_graph(exported_rows)
        source = Graph().parse(data=loadable_text + inferred_text, format="nt")
        lost, added = diff(source, exported)
        report.update({"export_rows": len(exported_rows), "schema_rows_skipped": skipped,
                       "roundtrip_lost": len(lost), "roundtrip_added": len(added),
                       "export_predicate_counts": predicate_counts(exported)})
        sorted_hash, nodes, rels, schema = hash_graph(session)
        report.update({"determinism_hash_sorted": sorted_hash, "nodes": nodes, "relationships": rels,
                       "schema_relationships": schema})
        wipe(session)
        target_file = os.path.join(import_dir, "loadable.nt")
        try:
            with open(target_file, "w", encoding="utf-8") as f:
                f.write(shuffled(loadable_text))
            load(session, statements)
            report["determinism_hash_shuffled"] = hash_graph(session)[0]
        finally:
            shutil.copyfile(loadable, target_file)
    report["samples"] = {"violations": found[:5], "lost": lost[:10], "added": added[:10],
                         "failed_cases": [c for c in report["fail_cases"] if c["status"] in ("failed", "no case")][:10]}
    report["passed"] = passed(report)
    return report


def predicate_counts(g):
    """Triples per predicate IRI, for the three-way count check of the triple-store add-on."""
    counts = {}
    for _, p, _ in g:
        counts[str(p)] = counts.get(str(p), 0) + 1
    return dict(sorted(counts.items()))


def passed(report):
    return (report["shacl_violations_in_graph"] == 0 and report["in_graph_mutant_violations"] > 0
            and report["mutant"]["after_restore"] == 0
            and report["roundtrip_lost"] == 0 and report["roundtrip_added"] == 0
            and report["determinism_hash_sorted"] == report["determinism_hash_shuffled"]
            and all(c["status"] in ("passed", "no-op") for c in report["fail_cases"]))


def check_report_command(report_path):
    """The next step, safe to paste; projection-manifest.json is the manifest's name in running.md."""
    return f"build.py check-report --manifest projection-manifest.json --report {q(report_path)}"


DEFAULT_CONTAINER = "lpg-projection"


def container_name(opts):
    """The container the printed next steps name: --container, else $LPG_CONTAINER, else lpg-projection."""
    return opts.get("--container") or os.environ.get("LPG_CONTAINER") or DEFAULT_CONTAINER


def remove_command(opts):
    """The clean-up line: `docker compose -p <project> ... down -v` when --compose-project names the
    project the services were started under (docker/compose.yaml), else `docker rm -f -v`."""
    if opts.get("--compose-project"):
        return f"docker compose -p {q(opts['--compose-project'])} --profile neo4j --profile fuseki down -v"
    return f"docker rm -f -v {q(container_name(opts))}"


def write_atomically(path, report):
    """Write the report to a temporary file beside path, then rename it into place."""
    folder = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".report-", suffix=".tmp", dir=folder)
    try:
        umask = os.umask(0)
        os.umask(umask)
        os.fchmod(fd, 0o666 & ~umask)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def remove_report(path):
    """Delete the report and the details of an earlier failed run, so neither outlives this run.
    A path that exists and cannot be deleted raises OSError: the caller stops with exit 2."""
    if path:
        for name in (path, path + ".failed"):
            try:
                os.remove(name)
            except FileNotFoundError:
                pass


def main(argv):
    opts = {}
    # Delete the report first, before the flags are checked: a run that stops on a bad flag must not
    # leave an earlier report standing (--report PATH and --report=PATH both name one).
    try:
        for path in build.named_paths(argv, "--report"):
            remove_report(path)
    except OSError as exc:
        print(f"ERROR cannot delete the earlier report: {q(exc)}", file=sys.stderr)
        return 2
    try:
        opts, data = build.options(argv)
        build.need(opts, "--config", "--bolt", "--import-dir", "--merged", "--loadable", "--inferred", "--report")
        if not data or not opts.get("--shapes"):
            raise ValueError("give the data files and at least one --shapes file")
        password = os.environ.get("NEO4J_PASSWORD")
        if not password:
            raise ValueError("set NEO4J_PASSWORD")
        cfg = build.load_config(opts["--config"])
        manual = read_manual_cases(opts.get("--manual-cases"))
    except (OSError, ValueError) as exc:
        print(f"ERROR {q(exc)}", file=sys.stderr)
        return 2
    if cfg.rule4 == "4b":
        print(cpr.RULE_4B_STOP.format(script="load_verify.py"), file=sys.stderr)
        return 2
    report_path = opts["--report"]
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(opts["--bolt"], auth=("neo4j", password))
        try:
            report = run(driver, cfg, data, opts["--shapes"], opts["--import-dir"], opts["--merged"],
                         opts["--loadable"], opts["--inferred"], opts.get("--plugins-dir"), manual)
        finally:
            driver.close()
    except Exception as exc:  # Failed, a driver error or a file error: no report
        remove_report(report_path)
        print(f"FAIL {q(exc)}")
        print(f"Stop: no report was written at {q(report_path)}. "
              "Fix the cause and rerun this command while the container is up: it empties the database itself. "
              f"If you stop instead, remove the container ({remove_command(opts)}).")
        return 1
    summary = {k: report[k] for k in ("shapes_import_rows", "in_graph_shape_constraints", "shacl_violations_in_graph",
                                      "in_graph_mutant_violations", "roundtrip_lost", "roundtrip_added", "nodes",
                                      "relationships", "determinism_hash_sorted", "determinism_hash_shuffled")}
    summary["fail_cases"] = {status: sum(1 for c in report["fail_cases"] if c["status"] == status)
                             for status in ("passed", "no-op", "failed", "no case")}
    summary["not_compiled"] = len(report["not_compiled"])
    print("summary: " + q(json.dumps(summary)))
    for c in report["not_compiled"]:
        # One line, quoted: a shapes literal can hold a newline or $(...).
        print("NOT COMPILED by n10s (validate_data.py checked it before the load): " + q(json.dumps(
            {k: c[k] for k in ("target", "path", "file_term", "raw", "shape")}, ensure_ascii=False)))
    if not report["passed"]:
        failed_path = report_path + ".failed"
        write_atomically(failed_path, report)
        print(f"FAIL the verify step did not pass. No report was written at {q(report_path)}; the details are in "
              f"{q(failed_path)}. A row with status 'no case' needs a case in --manual-cases. "
              "Fix the cause and rerun this command while the container is up: it empties the database itself. "
              f"If you stop instead, remove the container ({remove_command(opts)}).")
        return 1
    write_atomically(report_path, report)
    print(f"wrote {q(report_path)}: every check passed. Next: run {check_report_command(report_path)}, "
          f"then remove the container ({remove_command(opts)}) (running.md, rule 5).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
