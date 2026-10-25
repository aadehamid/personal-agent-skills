#!/usr/bin/env python3
"""Mechanical checks for Steps 2 and 3 of the ontology skill.

Run: uv run --with rdflib python3 check_taxonomy.py [--allow-namespace=<IRI>]... [--code-property=<IRI>]... <file.ttl>...

Run it on data files only (each module's and code list's Turtle), never on shapes files:
SHACL builds shapes from blank nodes (identity-taxonomy.md, Step 2, rule 5).

Checks (references/identity-taxonomy.md and references/domain-model.md):
  blank-node     no blank node anywhere (Step 2, rule 5)
  untagged       every plain literal has a language tag, except skos:notation, owl:versionInfo
                 and each --code-property given, which carry codes, not language text
                 (foundations.md, policy 5)
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
                 owl:AnnotationProperty (domain-model.md, rule 5); a bare rdf:Property, a property
                 declared only by a characteristic such as owl:TransitiveProperty, or a predicate
                 outside the known namespaces that is used but never declared, fails
  domain-range   each object and datatype property has exactly one rdfs:domain and one
                 rdfs:range; an annotation property has neither and fails if it has one; no rdfs:Literal range;
                 every domain, range and rdfs:subClassOf target is an IRI (a literal, even
                 one typed xsd:anyURI, fails) declared in the files (owl:Class, rdfs:Class, rdfs:Datatype) or sits in a
                 known namespace: XSD, RDF, RDFS, OWL, SKOS, W3C ORG, PROV-O, DCAT, DCMI
                 terms, plus each --allow-namespace given. A misspelling inside a known
                 namespace is not caught.
  kind-range     an owl:DatatypeProperty's range is a datatype (an XSD datatype,
                 rdf:langString, rdf:HTML, rdf:XMLLiteral or a declared rdfs:Datatype); an
                 owl:ObjectProperty's range is not
  untyped        every IRI used as the subject of any triple in the files has an rdf:type

qSKOS checks (references/quality.md, "The qSKOS issues", has the table and what is left out):
  lang-tag       every language tag is a well-formed BCP 47 tag (qSKOS: Omitted or Invalid Language Tags)
  language       a concept with a skos:prefLabel has one in every language any concept's skos:prefLabel
                 uses (Incomplete Language Coverage, No Common Language)
  label          (also) no skos:prefLabel, skos:altLabel or skos:hiddenLabel is empty after removing
                 whitespace (Empty Labels); each concept scheme and collection has a skos:prefLabel,
                 rdfs:label or dcterms:title (Missing Labels)
  label-chars    no SKOS label holds a character of Unicode category Zl, Zp or C, such as a newline
                 (Unprintable Characters in Labels)
  collision      (also) no concept's skos:altLabel or skos:hiddenLabel equals, ignoring case,
                 another concept's preferred or alternative label in the same scheme and language
                 (Overlapping Labels)
  disjoint-labels  no resource has the same literal in two of skos:prefLabel, skos:altLabel and
                 skos:hiddenLabel (Disjoint Labels Violation, SKOS S13)
  related        no concept is skos:related to itself (Reflexive Relations), to a sibling under the
                 same skos:broader parent (Valueless Associative Relations), or to an ancestor or
                 descendant (Relation Clashes, SKOS S27)
  reciprocal     a skos:related is stated both ways; a skos:topConceptOf a declared scheme is listed
                 by that scheme's skos:hasTopConcept; a stated skos:narrower has its skos:broader
                 (Unidirectionally Related Concepts)
  transitive     no skos:broaderTransitive or skos:narrowerTransitive is stated without the
                 skos:broader or skos:narrower that makes it (Solely Transitively Related Concepts)
  scheme         (also) each concept scheme has a top concept (Omitted Top Concepts)
  mapping        no concept maps to itself; skos:exactMatch is not stated with skos:broadMatch or
                 skos:relatedMatch between the same pair (Mapping Clashes, SKOS S46); no mapping
                 joins two concepts declared in the files that share a scheme (Mapping Relations Misuse)
  skos-term      every IRI in the SKOS namespace is a term the SKOS Reference defines (Undefined SKOS
                 Resources); a misspelled or deprecated SKOS term fails
  uri-scheme     every IRI used as a subject is an http or https IRI (HTTP URI Scheme Violation)

Exit 0 when every check passes, 1 when any fails (one line per failure), 2 when a file
cannot be read or parsed, or when the arguments are wrong.
"""
import re
import sys
import unicodedata
from collections import defaultdict

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import DCAT, DCTERMS, OWL, PROV, RDF, RDFS, SKOS, XSD

CODES = {SKOS.notation, OWL.versionInfo}
PROPERTY_KINDS = (OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty)
VALUE_KINDS = (OWL.ObjectProperty, OWL.DatatypeProperty)
KNOWN_NAMESPACES = (str(XSD), str(RDF), str(RDFS), str(OWL), str(SKOS),
                    "http://www.w3.org/ns/org#", str(PROV), str(DCAT), str(DCTERMS))
# The ontology-to-lpg skill's check_projection_rules.py checks kinds and ranges too, more strictly: a
# projected datatype range must be one its loader maps. Keep the two lists of RDF datatypes in step.
RDF_DATATYPES = {RDF.langString, RDF.HTML, RDF.XMLLiteral, URIRef(str(RDF) + "dirLangString")}
CHARACTERISTICS = (OWL.TransitiveProperty, OWL.SymmetricProperty, OWL.AsymmetricProperty, OWL.ReflexiveProperty,
                   OWL.IrreflexiveProperty, OWL.FunctionalProperty, OWL.InverseFunctionalProperty)
LABELS = (SKOS.prefLabel, SKOS.altLabel, SKOS.hiddenLabel)
MAPPINGS = (SKOS.mappingRelation, SKOS.closeMatch, SKOS.exactMatch, SKOS.broadMatch, SKOS.narrowMatch, SKOS.relatedMatch)
# Every class and property the SKOS Reference (W3C Recommendation, 18 August 2009) defines; anything
# else in its namespace is a misspelling or one of the deprecated terms of its Appendix D.
SKOS_TERMS = {URIRef(str(SKOS) + t) for t in (
    "Concept ConceptScheme Collection OrderedCollection inScheme hasTopConcept topConceptOf "
    "prefLabel altLabel hiddenLabel notation note changeNote definition editorialNote example "
    "historyNote scopeNote semanticRelation broader narrower related broaderTransitive "
    "narrowerTransitive member memberList mappingRelation closeMatch exactMatch broadMatch "
    "narrowMatch relatedMatch").split()}
# A well-formed BCP 47 tag (RFC 5646, section 2.1), without the grandfathered tags: language,
# optional script, region and variants, extensions, private use; or private use alone.
BCP47 = re.compile(r"^(?:[a-z]{2,3}(?:-[a-z]{3}){0,3}|[a-z]{5,8})(?:-[a-z]{4})?(?:-(?:[a-z]{2}|[0-9]{3}))?"
                   r"(?:-(?:[a-z0-9]{5,8}|[0-9][a-z0-9]{3}))*(?:-[0-9a-wyz](?:-[a-z0-9]{2,8})+)*"
                   r"(?:-x(?:-[a-z0-9]{1,8})+)?$|^x(?:-[a-z0-9]{1,8})+$", re.IGNORECASE)


def check(g, allowed_namespaces=(), code_properties=()):
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
                and o.datatype in (None, XSD.string) and p not in CODES
                and str(p) not in code_properties):
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

    fails += qskos(g, concepts, short)

    classes = {c for kind in (OWL.Class, RDFS.Class) for c in g.subjects(RDF.type, kind) if isinstance(c, URIRef)}
    for c in sorted(classes):
        if (c, RDF.type, OWL.Class) not in g:
            fails.append(("class-kind", f"{short(c)} is an rdfs:Class; write classes as owl:Class"))
    properties = {p for kind in PROPERTY_KINDS for p in g.subjects(RDF.type, kind)}
    properties |= set(g.subjects(RDF.type, RDF.Property))
    # A characteristic (owl:TransitiveProperty and the rest) also declares a property; it still needs its kind.
    properties |= {p for kind in CHARACTERISTICS for p in g.subjects(RDF.type, kind)}
    # A predicate outside the known namespaces that the files use but never declare is a local property
    # with no kind, label or definition.
    for pred in sorted({p for p in g.predicates() if isinstance(p, URIRef)} - properties):
        if not str(pred).startswith(known):
            fails.append(("property-kind", f"{short(pred)} is used as a predicate but is not declared as a property"))
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
            # An annotation property takes neither a domain nor a range (domain-model.md, rule 6).
            for axis, pred in (("domain", RDFS.domain), ("range", RDFS.range)):
                if (prop, RDF.type, OWL.AnnotationProperty) in g and (prop, pred, None) in g:
                    fails.append(("domain-range", f"{name} is an annotation property and has an rdfs:{axis}; "
                                                  f"annotation properties take neither a domain nor a range"))
            continue
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


def qskos(g, concepts, short):
    """The qSKOS quality issues the checks above do not already cover (the docstring's second list)."""
    fails = []
    for s, p, o in g:
        if isinstance(o, Literal) and o.language and not BCP47.match(o.language):
            fails.append(("lang-tag", f"{short(s)} {short(p)} has the language tag {o.language!r}, "
                                      f"which is not a well-formed BCP 47 tag"))
        for term in (s, p, o):
            if isinstance(term, URIRef) and str(term).startswith(str(SKOS)) and term not in SKOS_TERMS:
                fails.append(("skos-term", f"{short(term)} is in the SKOS namespace but is not a SKOS term"))
    for s in sorted({s for s in g.subjects() if isinstance(s, URIRef)}):
        if not str(s).startswith(("http://", "https://")):
            fails.append(("uri-scheme", f"{short(s)} is not an http or https IRI"))

    langs = {lab.language for c in concepts for lab in g.objects(c, SKOS.prefLabel) if isinstance(lab, Literal)}
    for c in sorted(concepts):
        have = {lab.language for lab in g.objects(c, SKOS.prefLabel) if isinstance(lab, Literal)}
        if have and langs - have:
            missing = ", ".join(sorted(str(lang) for lang in langs - have))
            fails.append(("language", f"{short(c)} has no skos:prefLabel in {missing}, which other concepts use"))

    for s, p, o in sorted((t for pred in LABELS for t in g.triples((None, pred, None))), key=str):
        if isinstance(o, Literal):
            if not str(o).strip():
                fails.append(("label", f"{short(s)} has an empty {short(p)}"))
            bad = sorted({unicodedata.category(ch) for ch in str(o)
                          if unicodedata.category(ch) in ("Zl", "Zp") or unicodedata.category(ch).startswith("C")})
            if bad:
                fails.append(("label-chars", f"{short(s)} {short(p)} \"{o}\" holds unprintable characters ({', '.join(bad)})"))
    for kind in (SKOS.ConceptScheme, SKOS.Collection, SKOS.OrderedCollection):
        for s in sorted(g.subjects(RDF.type, kind)):
            if not any((s, pred, None) in g for pred in (SKOS.prefLabel, RDFS.label, DCTERMS.title)):
                fails.append(("label", f"{short(s)} is a {short(kind)} with no skos:prefLabel, rdfs:label or dcterms:title"))

    for s in sorted({s for pred in LABELS for s in g.subjects(pred, None)}):
        seen = defaultdict(list)
        for pred in LABELS:
            for lab in g.objects(s, pred):
                seen[lab].append(short(pred))
        for lab, preds in sorted(seen.items(), key=str):
            if len(preds) > 1:
                fails.append(("disjoint-labels", f"{short(s)} has \"{lab}\" as both {' and '.join(preds)}"))

    # Overlapping labels: an alternative or hidden label of one concept that is another concept's label.
    names = defaultdict(set)  # (scheme, lang, lower label) -> concepts with it as a preferred or alternative label
    for c in concepts:
        for scheme in g.objects(c, SKOS.inScheme):
            for pred in (SKOS.prefLabel, SKOS.altLabel):
                for lab in g.objects(c, pred):
                    names[(scheme, getattr(lab, "language", None), str(lab).casefold())].add(c)
    for c in sorted(concepts):
        for scheme in g.objects(c, SKOS.inScheme):
            for pred in (SKOS.altLabel, SKOS.hiddenLabel):
                for lab in g.objects(c, pred):
                    others = names[(scheme, getattr(lab, "language", None), str(lab).casefold())] - {c}
                    if others:
                        fails.append(("collision", f"{short(c)} {short(pred)} \"{lab}\" is also a label of "
                                                   f"{', '.join(short(o) for o in sorted(others))} in {short(scheme)}"))

    def ancestors(c):
        found, todo = set(), [c]
        while todo:
            for up in g.objects(todo.pop(), SKOS.broader):
                if up not in found:
                    found.add(up)
                    todo.append(up)
        return found

    # The relation checks look only at concepts the files declare; an undeclared subject fails "untyped".
    for a, b in sorted(((a, b) for a, b in g.subject_objects(SKOS.related) if a in concepts), key=str):
        if a == b:
            fails.append(("related", f"{short(a)} is skos:related to itself"))
            continue
        if set(g.objects(a, SKOS.broader)) & set(g.objects(b, SKOS.broader)):
            fails.append(("related", f"{short(a)} and {short(b)} are siblings and also skos:related"))
        elif b in ancestors(a) or a in ancestors(b):
            fails.append(("related", f"{short(a)} and {short(b)} are hierarchically related and also skos:related"))
        if (b, SKOS.related, a) not in g:
            fails.append(("reciprocal", f"{short(a)} skos:related {short(b)} is not stated the other way"))
    for c, scheme in sorted(g.subject_objects(SKOS.topConceptOf), key=str):
        if (scheme, RDF.type, SKOS.ConceptScheme) in g and (scheme, SKOS.hasTopConcept, c) not in g:
            fails.append(("reciprocal", f"{short(c)} is a skos:topConceptOf {short(scheme)}, "
                                        f"but {short(scheme)} has no skos:hasTopConcept {short(c)}"))
    for a, b in sorted(((a, b) for a, b in g.subject_objects(SKOS.narrower) if a in concepts), key=str):
        if (b, SKOS.broader, a) not in g:
            fails.append(("reciprocal", f"{short(a)} skos:narrower {short(b)} has no matching skos:broader"))
    for pred, direct, flip in ((SKOS.broaderTransitive, SKOS.broader, SKOS.narrower),
                               (SKOS.narrowerTransitive, SKOS.narrower, SKOS.broader)):
        for a, b in sorted(g.subject_objects(pred), key=str):
            if (a, direct, b) not in g and (b, flip, a) not in g:
                fails.append(("transitive", f"{short(a)} {short(pred)} {short(b)} is stated without "
                                            f"{short(direct)}; the transitive properties are not for assertions"))

    for scheme in sorted(g.subjects(RDF.type, SKOS.ConceptScheme)):
        if (scheme, SKOS.hasTopConcept, None) not in g and (None, SKOS.topConceptOf, scheme) not in g:
            fails.append(("scheme", f"{short(scheme)} has no top concept"))

    for pred in MAPPINGS:
        for a, b in sorted(g.subject_objects(pred), key=str):
            if a == b:
                fails.append(("mapping", f"{short(a)} {short(pred)} itself"))
            elif a in concepts and b in concepts:
                shared = set(g.objects(a, SKOS.inScheme)) & set(g.objects(b, SKOS.inScheme))
                if shared:
                    fails.append(("mapping", f"{short(a)} {short(pred)} {short(b)}, but both are in "
                                             f"{short(sorted(shared)[0])}; a mapping joins different schemes"))
    for a, b in sorted(g.subject_objects(SKOS.exactMatch), key=str):
        for clash in (SKOS.broadMatch, SKOS.relatedMatch):
            if (a, clash, b) in g or (b, clash, a) in g:
                fails.append(("mapping", f"{short(a)} skos:exactMatch {short(b)} and also {short(clash)}"))
    return fails


def main(argv):
    allowed = [a.split("=", 1)[1] for a in argv if a.startswith("--allow-namespace=")]
    codes = [a.split("=", 1)[1] for a in argv if a.startswith("--code-property=")]
    paths = [a for a in argv if not a.startswith(("--allow-namespace=", "--code-property="))]
    if not paths or any(p.startswith("-") for p in paths) or any(not v for v in allowed + codes):
        print("usage: check_taxonomy.py [--allow-namespace=<IRI>]... [--code-property=<IRI>]... <file.ttl>...",
              file=sys.stderr)
        return 2
    g = Graph()
    for path in paths:
        try:
            g.parse(path, format="turtle")
        except Exception as exc:  # rdflib raises several parser types; any of them stops the check
            print(f"ERROR cannot read {path}: {exc}", file=sys.stderr)
            return 2
    fails = check(g, allowed, codes)
    for name, message in fails:
        print(f"FAIL {name}: {message}")
    if fails:
        print(f"{len(fails)} check(s) failed", file=sys.stderr)
        return 1
    print(f"all checks pass ({len(g)} triples)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
