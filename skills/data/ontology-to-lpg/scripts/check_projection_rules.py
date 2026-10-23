#!/usr/bin/env python3
"""The design-rule checks a property-graph projection runs before it loads anything.

Run: uv run --no-project --with rdflib python3 check_projection_rules.py --config <config.json>
         [--shapes <shapes.ttl>]... [--releases <folder>] <data.ttl>...

Give it the released data files (each package's module Turtle) and every shape file. The
configuration is described in references/inputs.md; templates/projection-config.json is an example.

Checks (references/design-rules.md and references/inputs.md):
  rule-1     every property in an own namespace (used as a predicate, declared with a property kind,
             or the subject of rdfs:domain, rdfs:range or rdfs:subPropertyOf) has exactly one kind:
             owl:ObjectProperty, owl:DatatypeProperty or owl:AnnotationProperty; an object or datatype
             property has exactly one rdfs:range, an IRI other than rdfs:Literal and rdfs:Resource; a
             datatype property's range is a row of the XSD to Cypher table; an object property's
             range is not a datatype
  rule-2     every own property the data uses as a predicate is the sh:path of a property shape that
             an applied shape uses, and that property shape states sh:minCount or sh:maxCount. A shape
             is applied when it has any target (sh:targetClass, sh:targetNode, sh:targetSubjectsOf,
             sh:targetObjectsOf, a SPARQL sh:target), is itself a class, or is reached from an applied
             shape through sh:node, sh:and, sh:or or sh:xone. A declared property the data never
             uses loads nothing, so Rule 2 skips it; Rule 1 still checks it
  rule-3     no blank node in the data; every namespace a predicate or a class uses (in the data or
             the shapes, including predicates inside property paths and superproperties) has a prefix;
             every own namespace has a prefix; no namespace has two prefixes
  rule-4a    every node of a registered qualified-relation class has exactly one value for each end,
             and is the object of exactly one link for each inverse end; an applied shape on the class
             gives each end (sh:path end) and each inverse end (sh:path [sh:inversePath end])
             sh:minCount 1 and sh:maxCount 1
  rule-5     no two terms share a value of the configured lpg_name_property (when one is configured)
  refusal    no plain or xsd:string literal ends like a language tag, and every xsd:decimal survives
             as a double (references/pipeline.md, rule 3)
  inputs     with --releases: each module's pin is an X.Y.Z release and its newest release folder
             (<folder>/<module>/<X.Y.Z>/)
  exceptions a rule-1, rule-2 or rule-5 failure whose exact message is a key of release_exceptions is
             allowed (a key may name terms by full IRI or by CURIE); a listed exception that no longer occurs, has an empty fix, or names a failure
             of any other check, fails

This checker reads RDF 1.1 with rdflib, so it checks Rule 4a only. With "rule4": "4b" it stops
with exit 2: run the Rule 4b checks in Jena 6.1.0+ or RDF4J 6.0.0+.

The ontology skill's check_taxonomy.py checks the same property kinds and ranges for modelling; this
checker is stricter on purpose: a datatype range must be one the projection's loader maps.

The namespace of an IRI is split as RDF4J (and so n10s) splits it: up to the first '#', else up to
the last '/', else up to the last ':'.

Exit 0 when every check passes, 1 when any fails (one line per failure), 2 when a file cannot be
read or parsed, the configuration is invalid, or the arguments are wrong.
"""
import json
import os
import re
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SH, XSD

KINDS = (OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty)
DECLARED = KINDS + (RDF.Property,)
VAGUE_RANGES = (RDFS.Literal, RDFS.Resource)
DIR_LANG_STRING = URIRef(str(RDF) + "dirLangString")
# The rows of the XSD to Cypher table in references/design-rules.md: the only ranges the loader maps.
LOADER_DATATYPES = {XSD[n] for n in ("string", "token", "normalizedString", "boolean", "integer", "long", "int",
                                     "nonNegativeInteger", "double", "float", "decimal", "date", "dateTime",
                                     "dateTimeStamp", "duration", "anyURI")} | {RDF.langString, DIR_LANG_STRING}
RDF_DATATYPES = {RDF.langString, RDF.HTML, RDF.XMLLiteral, DIR_LANG_STRING}
PROPERTY_AXIOMS = (RDFS.domain, RDFS.range, RDFS.subPropertyOf)
CLASS_OBJECTS = (RDFS.subClassOf, RDFS.domain, RDFS.range, OWL.equivalentClass, OWL.disjointWith)
CLASS_KINDS = (OWL.Class, RDFS.Class)
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
# A string that ends like a BCP 47 language tag: n10s's keepLangTag stores "text@en", so such a
# source string cannot be told apart from a tagged one on the way back.
LANG_TAG_SUFFIX = re.compile(r"@[A-Za-z]{1,8}(-[A-Za-z0-9]{1,8})*$")
WAIVABLE = {"rule-1", "rule-2", "rule-5"}
# Every script of this skill reads RDF 1.1 with rdflib and implements Rule 4a only, so each stops on 4b.
RULE_4B_STOP = ("ERROR the configuration records Rule 4b; {script} reads RDF 1.1 with rdflib and implements Rule 4a "
                "only. Run the Rule 4b steps in Jena 6.1.0+ or RDF4J 6.0.0+ (references/pipeline.md, rule 1).")
PATH_LISTS = (SH.alternativePath,)
PATH_WRAPPERS = (SH.inversePath, SH.zeroOrMorePath, SH.oneOrMorePath, SH.zeroOrOnePath)
IRI_IN_TEXT = re.compile(r"<?(https?://[^\s<>\"]+)>?")
# Every way SHACL selects focus nodes. A shape reached from an applied shape through sh:node,
# sh:and, sh:or or sh:xone applies to the same nodes.
TARGET_PREDICATES = (SH.targetClass, SH.targetNode, SH.targetSubjectsOf, SH.targetObjectsOf, SH.target)
REUSE_PREDICATES = (SH.node,)
LIST_PREDICATES = (SH["and"], SH["or"], SH.xone)


class ConfigError(ValueError):
    pass


def namespace(iri):
    """The namespace part of an IRI, as RDF4J's URIUtil.getLocalNameIndex splits it."""
    s = str(iri)
    for i in (s.find("#"), s.rfind("/"), s.rfind(":")):
        if i >= 0:
            return s[:i + 1]
    return ""


class Config:
    def __init__(self, raw):
        if not isinstance(raw, dict):
            raise ConfigError("the configuration must be a JSON object")
        if raw.get("rule4") not in ("4a", "4b"):
            raise ConfigError('"rule4" must be "4a" or "4b"')
        self.rule4 = raw["rule4"]
        reason = raw.get("rule4_reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ConfigError('"rule4_reason" must say why the Rule 4 option was chosen')
        self.rule4_reason = reason
        prefixes = raw.get("prefixes")
        if not isinstance(prefixes, dict) or not prefixes:
            raise ConfigError('"prefixes" must be a non-empty object of prefix to namespace')
        self.prefixes = {str(k): str(v) for k, v in prefixes.items()}
        own = raw.get("own_namespaces")
        if not isinstance(own, list) or not own:
            raise ConfigError('"own_namespaces" must be a non-empty list')
        self.own = tuple(str(n) for n in own)
        self.qualified = []
        for q in raw.get("qualified_relations", []):
            if not isinstance(q, dict) or "class" not in q:
                raise ConfigError('each "qualified_relations" entry needs a "class"')
            ends = [self.expand(e) for e in q.get("ends", [])]
            inverse = [self.expand(e) for e in q.get("inverse_ends", [])]
            if not ends and not inverse:
                raise ConfigError(f'qualified relation {q["class"]} names no ends')
            self.qualified.append((self.expand(q["class"]), ends, inverse))
        name_property = raw.get("lpg_name_property")
        self.name_property = self.expand(name_property) if name_property else None
        packages = raw.get("packages", {})
        if not isinstance(packages, dict):
            raise ConfigError('"packages" must be an object of module to version')
        self.packages = {str(k): str(v) for k, v in packages.items()}
        exceptions = raw.get("release_exceptions", {})
        if not isinstance(exceptions, dict):
            raise ConfigError('"release_exceptions" must be an object of message to fix')
        # A key may name terms by full IRI or by CURIE; both match the checker's CURIE message.
        self.exceptions = {self.curies(str(k)): str(v) for k, v in exceptions.items()}
        versions = raw.get("versions", {})
        if not isinstance(versions, dict):
            raise ConfigError('"versions" must be an object of tool to version')
        self.versions = {str(k): str(v) for k, v in versions.items()}

    def expand(self, term):
        term = str(term)
        if "://" in term:
            return URIRef(term)
        prefix, sep, local = term.partition(":")
        if not sep or prefix not in self.prefixes:
            raise ConfigError(f"cannot expand {term!r}: no such prefix")
        return URIRef(self.prefixes[prefix] + local)

    def curies(self, text):
        """Rewrite every full IRI in text (bare or in angle brackets) the way messages name it."""
        def one(m):
            iri, tail = m.group(1), ""
            while iri and iri[-1] in ",;.":
                iri, tail = iri[:-1], iri[-1] + tail
            return self.short(URIRef(iri)) + tail
        return IRI_IN_TEXT.sub(one, text)

    def short(self, term):
        """A CURIE for a term in a registered namespace, else the full IRI. Messages use this, so an
        exception key stays readable and stable."""
        if isinstance(term, URIRef):
            ns = namespace(term)
            for prefix, value in self.prefixes.items():
                if value == ns:
                    return f"{prefix}:{str(term)[len(ns):]}"
            return str(term)
        if isinstance(term, BNode):
            return "_:" + str(term)
        return term.n3()


def applied_node_shapes(shapes):
    """Shapes a SHACL validator applies: those with any target (sh:targetClass, sh:targetNode,
    sh:targetSubjectsOf, sh:targetObjectsOf, or a SHACL-SPARQL sh:target), those that are themselves
    a class (the implicit class target), and every shape reached from one of these through sh:node,
    sh:and, sh:or or sh:xone. This is what pySHACL validates, not what n10s runs in the graph: Rule 2
    and the multivalued list follow SHACL, which runs before the load on every shape. What n10s runs
    is in_graph_shapes.applied_node_shapes and hop_source."""
    from rdflib.collection import Collection
    applied = {s for p in TARGET_PREDICATES for s in shapes.subjects(p, None)}
    applied |= {s for kind in CLASS_KINDS for s in shapes.subjects(RDF.type, kind)
                if (s, RDF.type, SH.NodeShape) in shapes or (s, SH.property, None) in shapes}
    frontier = list(applied)
    while frontier:
        shape = frontier.pop()
        reached = [o for p in REUSE_PREDICATES for o in shapes.objects(shape, p)]
        for p in LIST_PREDICATES:
            for head in shapes.objects(shape, p):
                reached += list(Collection(shapes, head))
        for ps in shapes.objects(shape, SH.property):
            reached += [o for p in REUSE_PREDICATES for o in shapes.objects(ps, p)]
        for r in reached:
            if r not in applied:
                applied.add(r)
                frontier.append(r)
    return applied


def targets(shapes, node_shape):
    found = set(shapes.objects(node_shape, SH.targetClass))
    if any((node_shape, RDF.type, kind) in shapes for kind in CLASS_KINDS):
        found.add(node_shape)
    return found


def applied_property_shapes(shapes):
    """(path, property shape) for every property shape an applied node shape uses."""
    out = []
    for ns in applied_node_shapes(shapes):
        for ps in shapes.objects(ns, SH.property):
            path = shapes.value(ps, SH.path)
            if path is not None:
                out.append((path, ps))
    return out


def used_own_properties(data, cfg):
    """Own properties the data uses as predicates: the ones that load values, so Rule 2 applies."""
    return sorted({p for p in data.predicates() if isinstance(p, URIRef) and str(p).startswith(cfg.own)})


def own_properties(data, cfg):
    """Own properties the data uses, declares with a kind, or gives a domain, range or parent: Rule 1."""
    used = {p for p in data.predicates() if isinstance(p, URIRef)}
    declared = {s for kind in DECLARED for s in data.subjects(RDF.type, kind) if isinstance(s, URIRef)}
    axioms = {s for p in PROPERTY_AXIOMS for s in data.subjects(p, None) if isinstance(s, URIRef)}
    return sorted(p for p in used | declared | axioms if str(p).startswith(cfg.own))


def is_datatype(term, data):
    return str(term).startswith(str(XSD)) or term in RDF_DATATYPES or (term, RDF.type, RDFS.Datatype) in data


def check_rule_1(data, cfg, props):
    fails = []
    for p in props:
        name = cfg.short(p)
        kinds = [k for k in KINDS if (p, RDF.type, k) in data]
        if len(kinds) != 1:
            fails.append(("rule-1", f"Rule 1: {name} has {len(kinds)} kinds; it needs exactly one of "
                                    "owl:ObjectProperty, owl:DatatypeProperty and owl:AnnotationProperty"))
            continue
        if kinds[0] == OWL.AnnotationProperty:
            continue
        ranges = list(data.objects(p, RDFS.range))
        if len(ranges) != 1 or not isinstance(ranges[0], URIRef) or ranges[0] in VAGUE_RANGES:
            fails.append(("rule-1", f"Rule 1: {name} has no single concrete range"))
            continue
        rng = ranges[0]
        if kinds[0] == OWL.DatatypeProperty and rng not in LOADER_DATATYPES:
            fails.append(("rule-1", f"Rule 1: {name} is a datatype property but its range {cfg.short(rng)} "
                                    "is not a datatype the XSD to Cypher table maps"))
        if kinds[0] == OWL.ObjectProperty and is_datatype(rng, data):
            fails.append(("rule-1", f"Rule 1: {name} is an object property but its range {cfg.short(rng)} "
                                    "is a datatype"))
    return fails


def check_rule_2(shapes, cfg, props):
    stated = {path for path, ps in applied_property_shapes(shapes)
              if (ps, SH.minCount, None) in shapes or (ps, SH.maxCount, None) in shapes}
    return [("rule-2", f"Rule 2: no cardinality stated for {cfg.short(p)}") for p in props if p not in stated]


def check_rule_3(data, shapes, cfg):
    fails = []
    for s, p, o in sorted(data, key=lambda t: tuple(str(x) for x in t)):
        if isinstance(s, BNode) or isinstance(o, BNode):
            fails.append(("rule-3", f"Rule 3: blank node in {cfg.short(s)} {cfg.short(p)} {cfg.short(o)}"))
    registered = set(cfg.prefixes.values())
    terms = {p for p in data.predicates()}
    terms |= set(data.objects(None, RDF.type))
    terms |= {o for p in CLASS_OBJECTS for o in data.objects(None, p)}
    terms |= {s for kind in CLASS_KINDS for s in data.subjects(RDF.type, kind)}
    terms |= set(shapes.objects(None, SH.targetClass)) | set(shapes.objects(None, SH["class"]))
    terms |= {iri for path in shapes.objects(None, SH.path) for iri in path_iris(shapes, path)}
    terms |= set(data.objects(None, RDFS.subPropertyOf))
    terms = {t for t in terms if isinstance(t, URIRef)}
    missing = sorted({namespace(t) for t in terms} - registered)
    fails += [("rule-3", f"Rule 3: no fixed prefix for the namespace {ns}") for ns in missing]
    fails += [("rule-3", f"Rule 3: no fixed prefix for the own namespace {ns}")
              for ns in cfg.own if ns not in registered]
    by_ns = defaultdict(list)
    for prefix, ns in cfg.prefixes.items():
        by_ns[ns].append(prefix)
    fails += [("rule-3", f"Rule 3: the namespace {ns} has {len(ps)} prefixes: {', '.join(sorted(ps))}")
              for ns, ps in sorted(by_ns.items()) if len(ps) > 1]
    return fails


def path_iris(shapes, path, seen=None):
    """Every predicate IRI in a SHACL property path: a direct IRI, the members of a sequence path (an
    RDF list), of an sh:alternativePath list, and the IRI inside an inverse or repetition path."""
    seen = set() if seen is None else seen
    if isinstance(path, URIRef):
        return {path}
    if path in seen:
        return set()
    seen.add(path)
    from rdflib.collection import Collection
    found = set()
    if (path, RDF.first, None) in shapes:
        for member in Collection(shapes, path):
            found |= path_iris(shapes, member, seen)
    for p in PATH_LISTS:
        for head in shapes.objects(path, p):
            for member in Collection(shapes, head):
                found |= path_iris(shapes, member, seen)
    for p in PATH_WRAPPERS:
        for inner in shapes.objects(path, p):
            found |= path_iris(shapes, inner, seen)
    return found


def _end_shape_is_exact(shapes, cls, matches_path):
    for ns in applied_node_shapes(shapes):
        if cls not in targets(shapes, ns):
            continue
        for ps in shapes.objects(ns, SH.property):
            path = shapes.value(ps, SH.path)
            if path is not None and matches_path(path) \
                    and (ps, SH.minCount, Literal(1)) in shapes and (ps, SH.maxCount, Literal(1)) in shapes:
                return True
    return False


def check_rule_4a(data, shapes, cfg):
    fails = []
    for cls, ends, inverse in cfg.qualified:
        for end in ends:
            if not _end_shape_is_exact(shapes, cls, lambda path, end=end: path == end):
                fails.append(("rule-4a", f"Rule 4a: no shape on {cfg.short(cls)} gives {cfg.short(end)} "
                                         "sh:minCount 1 and sh:maxCount 1"))
        for end in inverse:
            if not _end_shape_is_exact(shapes, cls, lambda path, end=end: shapes.value(path, SH.inversePath) == end):
                fails.append(("rule-4a", f"Rule 4a: no shape on {cfg.short(cls)} gives the inverse of "
                                         f"{cfg.short(end)} sh:minCount 1 and sh:maxCount 1"))
        for node in sorted(data.subjects(RDF.type, cls), key=str):
            for end in ends:
                n = len(list(data.objects(node, end)))
                if n != 1:
                    fails.append(("rule-4a", f"Rule 4a: {cfg.short(node)} has {n} values of {cfg.short(end)}; "
                                             "it needs exactly one"))
            for end in inverse:
                n = len(list(data.subjects(end, node)))
                if n != 1:
                    fails.append(("rule-4a", f"Rule 4a: {cfg.short(node)} is the object of {n} "
                                             f"{cfg.short(end)} links; it needs exactly one"))
    return fails


def check_rule_5(data, cfg):
    if cfg.name_property is None:
        return []
    named = defaultdict(set)
    for term, name in data.subject_objects(cfg.name_property):
        named[str(name)].add(cfg.short(term))
    return [("rule-5", f"Rule 5: the name {name!r} is given to {', '.join(sorted(terms))}")
            for name, terms in sorted(named.items()) if len(terms) > 1]


def decimal_survives(lexical):
    """True when an xsd:decimal comes back from a Neo4j FLOAT with the same value: the shortest
    rendering of the nearest double, read as a decimal, equals the lexical value. So "1" (back as
    1.0) and "0.64" survive, and "0.1000000000000000055" (back as 0.1) does not."""
    try:
        return Decimal(repr(float(lexical))) == Decimal(lexical)
    except (InvalidOperation, ValueError):
        return False


def roundtrip_refusals(data, cfg):
    """The values the round trip cannot carry (references/pipeline.md, rule 3)."""
    fails = []
    for s, p, o in sorted(data, key=lambda t: tuple(str(x) for x in t)):
        if not isinstance(o, Literal) or o.language:
            continue
        where = f"{cfg.short(s)} {cfg.short(p)}"
        if o.datatype in (None, XSD.string) and LANG_TAG_SUFFIX.search(str(o)):
            fails.append(("refusal", f"Refused: {where} {o.n3()} ends like a language tag"))
        elif o.datatype == XSD.decimal and not decimal_survives(str(o)):
            fails.append(("refusal", f"Refused: {where} {o.n3()} does not survive as a double; "
                                     "adopt add-on C or change the value"))
    return fails


def check_packages(releases, cfg):
    """Each module's pin must be its newest X.Y.Z folder under releases/<module>/."""
    fails, newest = [], {}
    for module in sorted(os.listdir(releases)):
        folder = os.path.join(releases, module)
        if not os.path.isdir(folder):
            continue
        versions = [v for v in os.listdir(folder) if SEMVER.match(v) and os.path.isdir(os.path.join(folder, v))]
        if versions:
            newest[module] = max(versions, key=lambda v: tuple(map(int, v.split("."))))
    for module, version in sorted(newest.items()):
        pin = cfg.packages.get(module)
        if pin is None:
            fails.append(("inputs", f"Inputs: {module} has a release ({version}) but no pin"))
        elif pin != version:
            if os.path.isdir(os.path.join(releases, module, pin)):
                fails.append(("inputs", f"Inputs: {module} is pinned at {pin} but its newest release is {version}"))
    for module, pin in sorted(cfg.packages.items()):
        if not SEMVER.match(pin):
            fails.append(("inputs", f"Inputs: {module} is pinned at {pin}, which is not a release (X.Y.Z)"))
        elif not os.path.isdir(os.path.join(releases, module, pin)):
            fails.append(("inputs", f"Inputs: {module} is pinned at {pin}, which has no release folder"))
    return fails


def check(data, shapes, cfg, releases=None):
    """Return a list of (check name, message) pairs for every failure, after the release exceptions."""
    props = own_properties(data, cfg)
    found = (check_rule_1(data, cfg, props) + check_rule_2(shapes, cfg, used_own_properties(data, cfg))
             + check_rule_3(data, shapes, cfg)
             + check_rule_4a(data, shapes, cfg) + check_rule_5(data, cfg) + roundtrip_refusals(data, cfg))
    if releases is not None:
        found += check_packages(releases, cfg)
    names = {m: n for n, m in found}
    fails = [(n, m) for n, m in found if not (n in WAIVABLE and m in cfg.exceptions)]
    for message, fix in sorted(cfg.exceptions.items()):
        if message not in names:
            fails.append(("exceptions", f"listed release exception no longer occurs: {message}"))
        elif names[message] not in WAIVABLE:
            fails.append(("exceptions", "a release exception cannot waive a blank node, a missing prefix, a broken "
                                        f"qualified relation, a refused value or a package pin: {message}"))
        elif not fix.strip():
            fails.append(("exceptions", f"listed release exception has no fix: {message}"))
    return fails


def parse(paths):
    g = Graph()
    for path in paths:
        g.parse(path, format="nt" if path.endswith(".nt") else "turtle")
    return g


USAGE = ("usage: check_projection_rules.py --config <config.json> [--shapes <shapes.ttl>]... "
         "[--releases <folder>] <data.ttl>...")


def main(argv):
    config, shapes, releases, data = None, [], None, []
    args = list(argv)
    while args:
        a = args.pop(0)
        if a in ("--config", "--shapes", "--releases"):
            if not args:
                print(USAGE, file=sys.stderr)
                return 2
            value = args.pop(0)
            if a == "--config":
                config = value
            elif a == "--shapes":
                shapes.append(value)
            else:
                releases = value
        elif a.startswith("-"):
            print(USAGE, file=sys.stderr)
            return 2
        else:
            data.append(a)
    if config is None or not data:
        print(USAGE, file=sys.stderr)
        return 2
    try:
        with open(config, encoding="utf-8") as f:
            cfg = Config(json.load(f))
    except (OSError, ValueError) as exc:
        print(f"ERROR cannot use {config}: {exc}", file=sys.stderr)
        return 2
    if cfg.rule4 == "4b":
        print(RULE_4B_STOP.format(script="check_projection_rules.py"), file=sys.stderr)
        return 2
    if releases is not None and not os.path.isdir(releases):
        print(f"ERROR {releases} is not a folder", file=sys.stderr)
        return 2
    try:
        data_graph, shapes_graph = parse(data), parse(shapes)
    except Exception as exc:  # rdflib raises several parser types; any of them stops the check
        print(f"ERROR cannot read the RDF files: {exc}", file=sys.stderr)
        return 2
    fails = check(data_graph, shapes_graph, cfg, releases)
    for name, message in fails:
        print(f"FAIL {name}: {message}")
    if fails:
        print(f"{len(fails)} check(s) failed", file=sys.stderr)
        return 1
    print(f"all projection rules pass ({len(data_graph)} triples, {len(cfg.exceptions)} listed release exception(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
