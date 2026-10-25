#!/usr/bin/env python3
"""Step 7 and every external mapping: a mapping set in SSSOM/TSV is well formed (references/external-ontologies.md,
"Record mappings as SSSOM").

Run: uv run --no-project --with pyyaml python3 check_sssom.py <set.sssom.tsv>... [--allow-predicate=<CURIE>]...

The file is SSSOM/TSV with its metadata block embedded: YAML lines starting with "#" at the top, then a
tab-separated mappings block whose first line names the columns (SSSOM 1.0, and 1.1 where the set says
sssom_version: 1.1). Values in double quotes follow the format's quoting rules.

Checks:
  metadata     the metadata block parses as a YAML mapping and has mapping_set_id, license and a curie_map
  version      sssom_version, when present, is 1.1 (a set without it is a 1.0 set)
  columns      the header has subject_id, predicate_id, object_id and mapping_justification, and no column twice
  required     every row has a value in those four columns; subject_id or object_id may be empty only when
               subject_type or object_type is "rdfs literal" (a literal mapping)
  curie        every identifier in an identifier column is a CURIE, not an IRI, and its prefix is declared in
               curie_map or is a built-in prefix; a declared built-in prefix points to its built-in IRI
  predicate    predicate_id is one of the allowed mapping predicates: skos:exactMatch, skos:closeMatch,
               skos:broadMatch, skos:narrowMatch, skos:relatedMatch and rdfs:seeAlso, plus any
               --allow-predicate. SSSOM accepts any predicate; the narrower list is this skill's
               "map, don't import" policy, because owl:equivalentClass or owl:sameAs imports the other
               ontology's logic.
  modifier     predicate_modifier, when present, is "Not"
  confidence   confidence, when present, is a number from 0 to 1
  justification  mapping_justification is a SEMAPV matching process the set's SSSOM version defines: the nine of
                 sssom-schema v1.0.0, or with sssom_version 1.1 the thirteen of v1.1.0a5
  width        every row has as many cells as the header
  comment      every row whose predicate is a SKOS match other than skos:exactMatch has a comment saying what tells
               the two terms apart (external-ontologies.md, rule 9)
  source-version  the other vocabulary's version is stated: object_source_version in the metadata block, or on
               every row (rule 12)

Prints one FAIL line per failure. Exit 0 when nothing fails, 1 when anything fails, 2 when a file cannot be read
or the arguments are wrong.
"""
import argparse
import csv
import io
import sys

import yaml

BUILT_IN = {
    "owl": "http://www.w3.org/2002/07/owl#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "semapv": "https://w3id.org/semapv/vocab/",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "sssom": "https://w3id.org/sssom/",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "linkml": "https://w3id.org/linkml/",
}
MAPPING_PREDICATES = {"skos:exactMatch", "skos:closeMatch", "skos:broadMatch", "skos:narrowMatch",
                      "skos:relatedMatch", "rdfs:seeAlso"}
NON_EXACT = {"skos:closeMatch", "skos:broadMatch", "skos:narrowMatch", "skos:relatedMatch"}
REQUIRED_COLUMNS = ("subject_id", "predicate_id", "object_id", "mapping_justification")
# Columns typed EntityReference in the SSSOM schema that a set is likely to carry.
ID_COLUMNS = ("subject_id", "predicate_id", "object_id", "mapping_justification", "author_id", "reviewer_id",
              "creator_id", "subject_source", "object_source", "mapping_provider", "curation_rule")
# The mapping_justification pattern of the sssom-schema at tag v1.0.0, and the four values tag v1.1.0a5 adds.
# The development branch adds seven more (LLM-based matching among them) that no release carries yet; a set
# that uses one fails until a release defines it.
JUSTIFICATIONS_1_0 = {
    "semapv:MappingReview", "semapv:ManualMappingCuration", "semapv:LogicalReasoning", "semapv:LexicalMatching",
    "semapv:CompositeMatching", "semapv:UnspecifiedMatching", "semapv:SemanticSimilarityThresholdMatching",
    "semapv:LexicalSimilarityThresholdMatching", "semapv:MappingChaining",
}
JUSTIFICATIONS_1_1 = JUSTIFICATIONS_1_0 | {
    "semapv:MappingInversion", "semapv:StructuralMatching", "semapv:InstanceBasedMatching",
    "semapv:BackgroundKnowledgeBasedMatching",
}


def split(text):
    """Return (metadata lines, mappings block) of an embedded-metadata SSSOM/TSV file."""
    lines = text.splitlines(keepends=True)
    n = 0
    while n < len(lines) and lines[n].startswith("#"):
        n += 1
    return [line[1:] for line in lines[:n]], "".join(lines[n:])


def check_text(text, allowed=frozenset()):
    fails = []
    meta_lines, block = split(text)
    try:
        meta = yaml.safe_load("".join(meta_lines)) or {}
    except yaml.YAMLError as exc:
        return [("metadata", f"the metadata block is not valid YAML: {exc}")]
    if not isinstance(meta, dict):
        return [("metadata", "the metadata block is not a YAML mapping")]
    for key in ("mapping_set_id", "license"):
        if not meta.get(key):
            fails.append(("metadata", f"the set has no {key}"))
    curie_map = meta.get("curie_map")
    if not isinstance(curie_map, dict):
        fails.append(("metadata", "the set has no curie_map"))
        curie_map = {}
    for prefix, iri in curie_map.items():
        if prefix in BUILT_IN and iri != BUILT_IN[prefix]:
            fails.append(("curie", f"built-in prefix {prefix}: points to {iri}, not {BUILT_IN[prefix]}"))
    version = meta.get("sssom_version")
    if version is not None and str(version) != "1.1":
        fails.append(("version", f"sssom_version is {version}; a set that states it must say 1.1"))
    justifications = JUSTIFICATIONS_1_1 if str(version) == "1.1" else JUSTIFICATIONS_1_0

    rows = list(csv.reader(io.StringIO(block), delimiter="\t", quotechar='"'))
    if not rows:
        return fails + [("columns", "the file has no mappings block")]
    header, body = rows[0], [r for r in rows[1:] if r]
    for name in REQUIRED_COLUMNS:
        if name not in header:
            fails.append(("columns", f"the header has no {name} column"))
    for name in sorted({h for h in header if header.count(h) > 1}):
        fails.append(("columns", f"the header names {name} more than once"))
    if any(f[0] == "columns" for f in fails):
        return fails
    known = set(BUILT_IN) | set(curie_map)
    set_version = str(meta.get("object_source_version") or "").strip()
    if not set_version and ("object_source_version" not in header or
                            any(len(r) == len(header) and not dict(zip(header, r))["object_source_version"].strip()
                                for r in body)):
        fails.append(("source-version", "the other vocabulary's version is stated neither in the metadata block "
                                        "(object_source_version) nor on every row"))
    for number, row in enumerate(body, start=2):
        where = f"row {number}"
        if len(row) != len(header):
            fails.append(("width", f"{where} has {len(row)} cells; the header has {len(header)}"))
            continue
        cell = dict(zip(header, row))
        for name in REQUIRED_COLUMNS:
            if cell[name]:
                continue
            side = name.split("_")[0]
            if name in ("subject_id", "object_id") and cell.get(f"{side}_type") == "rdfs literal":
                continue
            fails.append(("required", f"{where} has no {name}"))
        for name in ID_COLUMNS:
            for value in (v for v in cell.get(name, "").split("|") if v):
                if "://" in value:
                    fails.append(("curie", f"{where} {name}: {value} is an IRI; SSSOM/TSV needs a CURIE"))
                elif ":" not in value:
                    fails.append(("curie", f"{where} {name}: {value} is not a CURIE"))
                elif value.split(":", 1)[0] not in known:
                    fails.append(("curie", f"{where} {name}: prefix {value.split(':', 1)[0]} is not declared"))
        if cell["predicate_id"] and cell["predicate_id"] not in MAPPING_PREDICATES | set(allowed):
            fails.append(("predicate", f"{where}: {cell['predicate_id']} is not an allowed mapping predicate"))
        if cell["predicate_id"] in NON_EXACT and not cell.get("comment", "").strip():
            fails.append(("comment", f"{where}: a {cell['predicate_id']} needs a comment saying what tells the two "
                                     f"terms apart"))
        if cell.get("predicate_modifier") and cell["predicate_modifier"] != "Not":
            fails.append(("modifier", f"{where}: predicate_modifier is {cell['predicate_modifier']}, not Not"))
        if cell.get("confidence"):
            try:
                ok = 0 <= float(cell["confidence"]) <= 1
            except ValueError:
                ok = False
            if not ok:
                fails.append(("confidence", f"{where}: confidence {cell['confidence']} is not a number from 0 to 1"))
        if cell["mapping_justification"] and cell["mapping_justification"] not in justifications:
            fails.append(("justification", f"{where}: {cell['mapping_justification']} is not a SEMAPV matching "
                                           f"process in SSSOM {version or '1.0'}"))
    return fails


def main(argv):
    p = argparse.ArgumentParser(prog="check_sssom.py")
    p.add_argument("files", nargs="+")
    p.add_argument("--allow-predicate", action="append", default=[])
    try:
        args = p.parse_args(argv)
    except SystemExit:
        return 2
    fails = []
    for path in args.files:
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except OSError as exc:
            print(f"ERROR cannot read {path}: {exc}", file=sys.stderr)
            return 2
        fails += [(name, f"{path}: {message}") for name, message in check_text(text, set(args.allow_predicate))]
    for name, message in fails:
        print(f"FAIL {name}: {message}")
    if fails:
        print(f"{len(fails)} check(s) failed", file=sys.stderr)
        return 1
    print(f"every mapping set is well-formed SSSOM ({len(args.files)} file(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
