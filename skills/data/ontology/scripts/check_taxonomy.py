#!/usr/bin/env python3
"""Mechanical checks for Steps 2 and 3 of the ontology skill.

Run: uv run --with rdflib python3 check_taxonomy.py <file.ttl> [<file.ttl> ...]

Checks (references/identity-taxonomy.md and references/domain-model.md):
  blank-node     no blank node anywhere (Step 2, rule 5)
  untagged       every plain literal has a language tag, except skos:notation and
                 owl:versionInfo, which are codes, not language text (foundations.md, policy 5)
  label          each concept has one skos:prefLabel per language, and at least one;
                 each class and property has an rdfs:label
  definition     each concept, class and property has a skos:definition
  notation       each concept has a skos:notation, unique within each scheme
  scheme         each concept is skos:inScheme a scheme; a scheme's top concepts say so
  parent         one skos:broader per concept except top concepts, which have none;
                 the parent is a declared concept; no cycles
  collision      no two concepts in one scheme share a preferred label (ignoring case)
  property-kind  each property is exactly one of owl:ObjectProperty, owl:DatatypeProperty
  domain-range   each property has exactly one rdfs:domain and one rdfs:range;
                 no rdfs:Literal range

Exit 0 when every check passes, 1 when any fails (one line per failure), 2 when a file
cannot be read or parsed.
"""
import sys
from collections import defaultdict

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS, XSD

CODES = {SKOS.notation, OWL.versionInfo}
PROPERTY_KINDS = (OWL.ObjectProperty, OWL.DatatypeProperty)


def check(g):
    """Return a list of (check name, message) pairs for every failure in graph g."""
    fails = []
    short = lambda t: t.n3(g.namespace_manager)

    for s, p, o in g:
        if isinstance(s, BNode) or isinstance(o, BNode):
            fails.append(("blank-node", f"{short(s)} {short(p)} {short(o)}"))
        if (isinstance(o, Literal) and o.language is None
                and o.datatype in (None, XSD.string) and p not in CODES):
            fails.append(("untagged", f"{short(s)} {short(p)} \"{o}\" has no language tag"))

    concepts = {c for c in g.subjects(RDF.type, SKOS.Concept) if isinstance(c, URIRef)}
    labels = defaultdict(list)     # (scheme, lang, lower label) -> concepts
    notations = defaultdict(list)  # (scheme, notation) -> concepts
    for c in sorted(concepts):
        name = short(c)
        per_lang = defaultdict(int)
        for lab in g.objects(c, SKOS.prefLabel):
            per_lang[getattr(lab, "language", None)] += 1
        if not per_lang:
            fails.append(("label", f"{name} has no skos:prefLabel"))
        for lang, n in per_lang.items():
            if n > 1:
                fails.append(("label", f"{name} has {n} skos:prefLabel values in language {lang}"))
        if not any(True for _ in g.objects(c, SKOS.definition)):
            fails.append(("definition", f"{name} has no skos:definition"))
        schemes = set(g.objects(c, SKOS.inScheme))
        if not schemes:
            fails.append(("scheme", f"{name} is in no skos:ConceptScheme (skos:inScheme)"))
        codes = list(g.objects(c, SKOS.notation))
        if not codes:
            fails.append(("notation", f"{name} has no skos:notation"))
        for scheme in schemes:
            for lab in g.objects(c, SKOS.prefLabel):
                labels[(scheme, getattr(lab, "language", None), str(lab).casefold())].append(name)
            for code in codes:
                notations[(scheme, str(code))].append(name)

        tops = set(g.objects(c, SKOS.topConceptOf))
        parents = list(g.objects(c, SKOS.broader))
        if tops and parents:
            fails.append(("parent", f"{name} is a top concept and also has skos:broader"))
        elif not tops and len(parents) != 1:
            fails.append(("parent", f"{name} has {len(parents)} skos:broader parents; it needs exactly one"))
        for parent in parents:
            if parent not in concepts:
                fails.append(("parent", f"{name} has parent {short(parent)}, which is not a declared skos:Concept"))
        seen, current = {c}, c
        while True:
            up = list(g.objects(current, SKOS.broader))
            if not up:
                break
            current = up[0]
            if current in seen:
                fails.append(("parent", f"{name} is in a skos:broader cycle"))
                break
            seen.add(current)

    for scheme in g.subjects(RDF.type, SKOS.ConceptScheme):
        for top in g.objects(scheme, SKOS.hasTopConcept):
            if (top, SKOS.topConceptOf, scheme) not in g:
                fails.append(("scheme", f"{short(scheme)} lists {short(top)} as a top concept, "
                                        f"but {short(top)} has no skos:topConceptOf it"))

    for (scheme, lang, label), names in sorted(labels.items(), key=str):
        if len(names) > 1:
            fails.append(("collision", f"{', '.join(names)} share the label \"{label}\" ({lang}) in {short(scheme)}"))
    for (scheme, code), names in sorted(notations.items(), key=str):
        if len(names) > 1:
            fails.append(("notation", f"{', '.join(names)} share the notation \"{code}\" in {short(scheme)}"))

    classes = {c for c in g.subjects(RDF.type, OWL.Class) if isinstance(c, URIRef)}
    properties = {p for kind in PROPERTY_KINDS for p in g.subjects(RDF.type, kind)}
    properties |= set(g.subjects(RDF.type, RDF.Property))
    for term in sorted(classes | properties):
        name = short(term)
        if not any(True for _ in g.objects(term, RDFS.label)):
            fails.append(("label", f"{name} has no rdfs:label"))
        if not any(True for _ in g.objects(term, SKOS.definition)):
            fails.append(("definition", f"{name} has no skos:definition"))
    for prop in sorted(properties):
        name = short(prop)
        kinds = [k for k in PROPERTY_KINDS if (prop, RDF.type, k) in g]
        if len(kinds) != 1:
            fails.append(("property-kind", f"{name} is typed {len(kinds)} of owl:ObjectProperty and "
                                           f"owl:DatatypeProperty; it needs exactly one"))
        for axis, pred in (("domain", RDFS.domain), ("range", RDFS.range)):
            values = list(g.objects(prop, pred))
            if len(values) != 1:
                fails.append(("domain-range", f"{name} has {len(values)} rdfs:{axis} values; it needs exactly one"))
        if (prop, RDFS.range, RDFS.Literal) in g:
            fails.append(("domain-range", f"{name} has range rdfs:Literal; name a concrete datatype"))
    return fails


def main(paths):
    if not paths:
        print("usage: check_taxonomy.py <file.ttl> [<file.ttl> ...]", file=sys.stderr)
        return 2
    g = Graph()
    for path in paths:
        try:
            g.parse(path, format="turtle")
        except Exception as exc:  # rdflib raises several parser types; any of them stops the check
            print(f"ERROR cannot read {path}: {exc}", file=sys.stderr)
            return 2
    fails = check(g)
    for name, message in fails:
        print(f"FAIL {name}: {message}")
    if fails:
        print(f"{len(fails)} check(s) failed", file=sys.stderr)
        return 1
    print(f"all checks pass ({len(g)} triples)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
