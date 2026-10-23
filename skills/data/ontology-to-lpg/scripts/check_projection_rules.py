#!/usr/bin/env python3
"""The design-rule checks a property-graph projection runs before it loads anything.

Run: uv run --with rdflib python3 check_projection_rules.py --config <config.json> [--shapes <shapes.ttl>]...
         [--releases <folder>] <data.ttl>...

Give it the released data files (each package's module Turtle) and every shape file. The
configuration is described in references/inputs.md; templates/projection-config.json is an example.

Checks (references/design-rules.md and references/inputs.md):
  rule-1     every property in an own namespace (used as a predicate, or declared) has exactly one
             kind: owl:ObjectProperty, owl:DatatypeProperty or owl:AnnotationProperty; an object or
             datatype property has exactly one rdfs:range, an IRI other than rdfs:Literal and
             rdfs:Resource; a datatype property's range is a datatype and an object property's is not
  rule-2     every own property has a property shape whose sh:path is that property and that states
             sh:minCount or sh:maxCount
  rule-3     no blank node in the data; the namespace of every predicate and every rdf:type object
             has a prefix; every own namespace has a prefix; no namespace has two prefixes
  rule-4a    every node of a registered qualified-relation class has exactly one value for each end,
             and is the object of exactly one link for each inverse end
  rule-5     no two terms share a value of the configured lpg_name_property (when one is configured)
  inputs     with --releases: each module's pin is its newest release folder (<folder>/<module>/<X.Y.Z>/)
  exceptions a failure whose exact message is a key of release_exceptions is allowed; a listed
             exception that no longer occurs, or one with an empty fix, fails

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

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SH, XSD

KINDS = (OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty)
DECLARED = KINDS + (RDF.Property,)
VAGUE_RANGES = (RDFS.Literal, RDFS.Resource)
RDF_DATATYPES = {RDF.langString, RDF.HTML, RDF.XMLLiteral, URIRef(str(RDF) + "dirLangString")}
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


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
        self.exceptions = {str(k): str(v) for k, v in exceptions.items()}

    def expand(self, term):
        term = str(term)
        if "://" in term:
            return URIRef(term)
        prefix, sep, local = term.partition(":")
        if not sep or prefix not in self.prefixes:
            raise ConfigError(f"cannot expand {term!r}: no such prefix")
        return URIRef(self.prefixes[prefix] + local)

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


def own_properties(data, cfg):
    used = {p for p in data.predicates() if isinstance(p, URIRef)}
    declared = {s for kind in DECLARED for s in data.subjects(RDF.type, kind) if isinstance(s, URIRef)}
    return sorted(p for p in used | declared if str(p).startswith(cfg.own))


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
        if kinds[0] == OWL.DatatypeProperty and not is_datatype(rng, data):
            fails.append(("rule-1", f"Rule 1: {name} is a datatype property but its range {cfg.short(rng)} "
                                    "is not a datatype"))
        if kinds[0] == OWL.ObjectProperty and is_datatype(rng, data):
            fails.append(("rule-1", f"Rule 1: {name} is an object property but its range {cfg.short(rng)} "
                                    "is a datatype"))
    return fails


def check_rule_2(shapes, cfg, props):
    stated = {shapes.value(s, SH.path) for s in shapes.subjects(SH.path, None)
              if (s, SH.minCount, None) in shapes or (s, SH.maxCount, None) in shapes}
    return [("rule-2", f"Rule 2: no cardinality stated for {cfg.short(p)}") for p in props if p not in stated]


def check_rule_3(data, cfg):
    fails = []
    for s, p, o in sorted(data, key=lambda t: tuple(str(x) for x in t)):
        if isinstance(s, BNode) or isinstance(o, BNode):
            fails.append(("rule-3", f"Rule 3: blank node in {cfg.short(s)} {cfg.short(p)} {cfg.short(o)}"))
    registered = set(cfg.prefixes.values())
    terms = {p for p in data.predicates() if isinstance(p, URIRef)}
    terms |= {o for o in data.objects(None, RDF.type) if isinstance(o, URIRef)}
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


def check_rule_4a(data, cfg):
    fails = []
    for cls, ends, inverse in cfg.qualified:
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
        if not os.path.isdir(os.path.join(releases, module, pin)):
            fails.append(("inputs", f"Inputs: {module} is pinned at {pin}, which has no release folder"))
    return fails


def check(data, shapes, cfg, releases=None):
    """Return a list of (check name, message) pairs for every failure, after the release exceptions."""
    props = own_properties(data, cfg)
    found = (check_rule_1(data, cfg, props) + check_rule_2(shapes, cfg, props) + check_rule_3(data, cfg)
             + check_rule_4a(data, cfg) + check_rule_5(data, cfg))
    if releases is not None:
        found += check_packages(releases, cfg)
    messages = {m for _, m in found}
    fails = [(n, m) for n, m in found if m not in cfg.exceptions]
    for message, fix in sorted(cfg.exceptions.items()):
        if message not in messages:
            fails.append(("exceptions", f"listed release exception no longer occurs: {message}"))
        elif not fix.strip():
            fails.append(("exceptions", f"listed release exception has no fix: {message}"))
    return fails


def parse(paths):
    g = Graph()
    for path in paths:
        g.parse(path, format="turtle")
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
    if releases is not None and not os.path.isdir(releases):
        print(f"ERROR {releases} is not a folder", file=sys.stderr)
        return 2
    try:
        data_graph, shapes_graph = parse(data), parse(shapes)
    except Exception as exc:  # rdflib raises several parser types; any of them stops the check
        print(f"ERROR cannot read the Turtle files: {exc}", file=sys.stderr)
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
