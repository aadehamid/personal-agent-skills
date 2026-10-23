#!/usr/bin/env python3
"""Mechanical checks for Steps 2 and 3 of the ontology skill.

Run: uv run --with rdflib python3 check_taxonomy.py [--allow-namespace=<IRI>]... <file.ttl>...

Run it on data files only (each module's and code list's Turtle), never on shapes files:
SHACL builds shapes from blank nodes (identity-taxonomy.md, Step 2, rule 5).

Checks (references/identity-taxonomy.md and references/domain-model.md):
  blank-node     no blank node anywhere (Step 2, rule 5)
  untagged       every plain literal has a language tag, except skos:notation and
                 owl:versionInfo, which are codes, not language text (foundations.md, policy 5)
  label          each concept has one skos:prefLabel per language, and at least one;
                 each class and property (annotation properties too) has an rdfs:label
  definition     each concept, class and property (annotation properties too) has a
                 skos:definition
  notation       each concept has a skos:notation, unique within each scheme
  scheme         each concept is skos:inScheme a declared scheme; skos:topConceptOf names a declared
                 scheme; a scheme's top concepts are declared concepts and say so
  parent         one skos:broader per concept except top concepts, which have none;
                 the parent is a declared concept; no cycles
  collision      no two concepts in one scheme share a preferred label (ignoring case)
  class-kind     each class is an owl:Class; an rdfs:Class without owl:Class fails
                 (domain-model.md, rule 4)
  property-kind  each property is exactly one of owl:ObjectProperty, owl:DatatypeProperty,
                 owl:AnnotationProperty (domain-model.md, rule 5); a bare rdf:Property, or a
                 property declared only by a characteristic such as owl:TransitiveProperty, fails
  domain-range   each object and datatype property has exactly one rdfs:domain and one
                 rdfs:range (annotation properties need neither); no rdfs:Literal range;
                 every domain, range and rdfs:subClassOf target is an IRI (a literal, even
                 one typed xsd:anyURI, fails) declared in the files (owl:Class, rdfs:Class, rdfs:Datatype) or sits in a
                 known namespace: XSD, RDF, RDFS, OWL, SKOS, W3C ORG, PROV-O, DCAT, DCMI
                 terms, plus each --allow-namespace given. A misspelling inside a known
                 namespace is not caught.
  kind-range     an owl:DatatypeProperty's range is a datatype (an XSD datatype,
                 rdf:langString, rdf:HTML, rdf:XMLLiteral or a declared rdfs:Datatype); an
                 owl:ObjectProperty's range is not
  untyped        every IRI used as the subject of any triple in the files has an rdf:type

Exit 0 when every check passes, 1 when any fails (one line per failure), 2 when a file
cannot be read or parsed, or when the arguments are wrong.
"""
import sys
from collections import defaultdict

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import DCAT, DCTERMS, OWL, PROV, RDF, RDFS, SKOS, XSD

CODES = {SKOS.notation, OWL.versionInfo}
PROPERTY_KINDS = (OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty)
VALUE_KINDS = (OWL.ObjectProperty, OWL.DatatypeProperty)
KNOWN_NAMESPACES = (str(XSD), str(RDF), str(RDFS), str(OWL), str(SKOS),
                    "http://www.w3.org/ns/org#", str(PROV), str(DCAT), str(DCTERMS))
RDF_DATATYPES = {RDF.langString, RDF.HTML, RDF.XMLLiteral}
CHARACTERISTICS = (OWL.TransitiveProperty, OWL.SymmetricProperty, OWL.AsymmetricProperty, OWL.ReflexiveProperty,
                   OWL.IrreflexiveProperty, OWL.FunctionalProperty, OWL.InverseFunctionalProperty)


def check(g, allowed_namespaces=()):
    """Return a list of (check name, message) pairs for every failure in graph g."""
    fails = []
    short = lambda t: t.n3(g.namespace_manager)
    known = tuple(KNOWN_NAMESPACES) + tuple(allowed_namespaces)
    declared_types = {s for kind in (OWL.Class, RDFS.Class, RDFS.Datatype)
                      for s in g.subjects(RDF.type, kind)}
    datatypes = set(g.subjects(RDF.type, RDFS.Datatype)) | RDF_DATATYPES

    def is_datatype(term):
        return term in datatypes or str(term).startswith(str(XSD))

    def resolves(term):
        return term in declared_types or any(str(term).startswith(ns) for ns in known)

    untyped = sorted({s for s in g.subjects() if isinstance(s, URIRef) and (s, RDF.type, None) not in g})
    for s in untyped:
        fails.append(("untyped", f"{short(s)} is the subject of triples but has no rdf:type"))

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
        for scheme in schemes:
            if (scheme, RDF.type, SKOS.ConceptScheme) not in g:
                fails.append(("scheme", f"{name} is in {short(scheme)}, which is not a declared skos:ConceptScheme"))
        codes = list(g.objects(c, SKOS.notation))
        if not codes:
            fails.append(("notation", f"{name} has no skos:notation"))
        for scheme in schemes:
            for lab in g.objects(c, SKOS.prefLabel):
                labels[(scheme, getattr(lab, "language", None), str(lab).casefold())].append(name)
            for code in codes:
                notations[(scheme, str(code))].append(name)

        tops = set(g.objects(c, SKOS.topConceptOf))
        for scheme in tops:
            if (scheme, RDF.type, SKOS.ConceptScheme) not in g:
                fails.append(("scheme", f"{name} is a top concept of {short(scheme)}, which is not a declared skos:ConceptScheme"))
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
            if top not in concepts:
                fails.append(("scheme", f"{short(scheme)} lists {short(top)} as a top concept, "
                                        f"but {short(top)} is not a declared skos:Concept"))
            if (top, SKOS.topConceptOf, scheme) not in g:
                fails.append(("scheme", f"{short(scheme)} lists {short(top)} as a top concept, "
                                        f"but {short(top)} has no skos:topConceptOf it"))

    for (scheme, lang, label), names in sorted(labels.items(), key=str):
        if len(names) > 1:
            fails.append(("collision", f"{', '.join(names)} share the label \"{label}\" ({lang}) in {short(scheme)}"))
    for (scheme, code), names in sorted(notations.items(), key=str):
        if len(names) > 1:
            fails.append(("notation", f"{', '.join(names)} share the notation \"{code}\" in {short(scheme)}"))

    classes = {c for kind in (OWL.Class, RDFS.Class) for c in g.subjects(RDF.type, kind) if isinstance(c, URIRef)}
    for c in sorted(classes):
        if (c, RDF.type, OWL.Class) not in g:
            fails.append(("class-kind", f"{short(c)} is an rdfs:Class; write classes as owl:Class"))
    properties = {p for kind in PROPERTY_KINDS for p in g.subjects(RDF.type, kind)}
    properties |= set(g.subjects(RDF.type, RDF.Property))
    # A characteristic (owl:TransitiveProperty and the rest) also declares a property; it still needs its kind.
    properties |= {p for kind in CHARACTERISTICS for p in g.subjects(RDF.type, kind)}
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
            fails.append(("property-kind", f"{name} is typed {len(kinds)} of owl:ObjectProperty, "
                                           f"owl:DatatypeProperty and owl:AnnotationProperty; it needs exactly one"))
        if not any((prop, RDF.type, k) in g for k in VALUE_KINDS):
            continue  # an annotation property needs a label and a definition, not a domain or range
        for axis, pred in (("domain", RDFS.domain), ("range", RDFS.range)):
            values = list(g.objects(prop, pred))
            if len(values) != 1:
                fails.append(("domain-range", f"{name} has {len(values)} rdfs:{axis} values; it needs exactly one"))
        if (prop, RDFS.range, RDFS.Literal) in g:
            fails.append(("domain-range", f"{name} has range rdfs:Literal; name a concrete datatype"))
        for rng in g.objects(prop, RDFS.range):
            if rng == RDFS.Literal or not isinstance(rng, URIRef):
                continue
            if (prop, RDF.type, OWL.DatatypeProperty) in g and not is_datatype(rng):
                fails.append(("kind-range", f"{name} is an owl:DatatypeProperty but its range {short(rng)} is not a datatype"))
            if (prop, RDF.type, OWL.ObjectProperty) in g and is_datatype(rng):
                fails.append(("kind-range", f"{name} is an owl:ObjectProperty but its range {short(rng)} is a datatype"))
    for pred, axis in ((RDFS.domain, "rdfs:domain"), (RDFS.range, "rdfs:range"), (RDFS.subClassOf, "rdfs:subClassOf")):
        for s, o in sorted(g.subject_objects(pred), key=str):
            if isinstance(o, Literal):
                fails.append(("domain-range", f"{short(s)} has {axis} {short(o)}, a literal; it must be an IRI"))
            elif isinstance(o, URIRef) and not resolves(o):
                fails.append(("domain-range", f"{short(s)} has {axis} {short(o)}, which is neither declared "
                                              f"in the files nor in a known namespace"))
    return fails


def main(argv):
    allowed = [a.split("=", 1)[1] for a in argv if a.startswith("--allow-namespace=")]
    paths = [a for a in argv if not a.startswith("--allow-namespace=")]
    if not paths or any(p.startswith("-") for p in paths) or any(not ns for ns in allowed):
        print("usage: check_taxonomy.py [--allow-namespace=<IRI>]... <file.ttl>...", file=sys.stderr)
        return 2
    g = Graph()
    for path in paths:
        try:
            g.parse(path, format="turtle")
        except Exception as exc:  # rdflib raises several parser types; any of them stops the check
            print(f"ERROR cannot read {path}: {exc}", file=sys.stderr)
            return 2
    fails = check(g, allowed)
    for name, message in fails:
        print(f"FAIL {name}: {message}")
    if fails:
        print(f"{len(fails)} check(s) failed", file=sys.stderr)
        return 1
    print(f"all checks pass ({len(g)} triples)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
