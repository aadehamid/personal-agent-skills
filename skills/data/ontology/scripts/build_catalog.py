#!/usr/bin/env python3
"""Step 10: one combined catalog of every release on disk (references/release.md, rule 19).

Run (uv run --no-project --with rdflib --with pyshacl python3 build_catalog.py ...; pySHACL because the
package layout and manifest reader come from check_packages.py):
  build_catalog.py build  --releases <dir> --title <text> --description <text> [--out <file>]
  build_catalog.py verify --releases <dir> --title <text> --description <text> [--out <file>]

The catalog is the union of every package's catalog.ttl under <dir> (release.md, rule 8: each package
sits at <dir>/<module>/<version>/ and build_package.py writes its DCAT record as catalog.ttl) plus the
catalog's own dcterms:title and dcterms:description, written as Turtle to <out>, which defaults to
<dir>/catalog.ttl. `build` writes it; `verify` fails unless the written file equals a fresh build byte
for byte, so a release missing from the catalog, a package added since, or a hand edit fails the check,
and the catalog can hold nothing but the packages' own records and the two values given here.

Checks, before anything is written or compared (one FAIL line each):
  packages       <dir> holds at least one package, and each package's manifest.json and catalog.ttl
                 can be read
  one-catalog    every package names the same dcat:Catalog IRI (set catalog_iri in the answers file
                 of a package that names another)
  one-dataset    each package's catalog.ttl holds exactly one dcat:Dataset, which is the package's
                 own release (the manifest's version_iri) and which the catalog lists
  distribution   every distribution a dataset links to is described (typed dcat:Distribution, with at
                 least one dcat:downloadURL, every one an IRI) and the last path segment of each
                 download URL names a file the package's manifest lists

Exit 0 when the catalog is written or equals a fresh build, 1 when a check fails (an unreadable
manifest or record included) or the written catalog differs, 2 when the arguments are wrong or <dir>
is not a directory.
"""
import argparse
import os
import sys

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, RDF

import check_packages

DCAT = Namespace("http://www.w3.org/ns/dcat#")


def package_record(releases, module, version):
    """(graph, manifest) of one package; raises OSError or ValueError."""
    folder = os.path.join(releases, module, version)
    manifest = check_packages.read_manifest(releases, module, version)
    g = Graph()
    try:
        g.parse(os.path.join(folder, "catalog.ttl"), format="turtle")
    except Exception as exc:  # a missing file or an rdflib parser error
        raise ValueError(f"cannot read catalog.ttl: {exc}")
    return g, manifest


def check_record(where, g, manifest):
    """Failures of one package's record, each a string."""
    fails = []
    catalogs = sorted(set(g.subjects(RDF.type, DCAT.Catalog)), key=str)
    if len(catalogs) != 1:
        fails.append(f"{where}: catalog.ttl names {len(catalogs)} dcat:Catalog, not one")
    datasets = sorted(set(g.subjects(RDF.type, DCAT.Dataset)), key=str)
    if len(datasets) != 1:
        fails.append(f"{where}: catalog.ttl holds {len(datasets)} dcat:Dataset, not one")
    release = manifest.get("version_iri")
    if not isinstance(release, str) or not release:
        fails.append(f"{where}: the manifest names no version_iri")
    else:
        for ds in datasets:
            if ds != URIRef(release):
                fails.append(f"{where}: catalog.ttl describes {ds}, not this package's release {release}")
    for cat in catalogs:
        for ds in datasets:
            if (cat, DCAT.dataset, ds) not in g:
                fails.append(f"{where}: {cat} does not list {ds}")
    files = set(manifest.get("files") or {})
    for ds in datasets:
        for dist in sorted(g.objects(ds, DCAT.distribution), key=str):
            urls = sorted(g.objects(dist, DCAT.downloadURL), key=str)
            if (dist, RDF.type, DCAT.Distribution) not in g or not urls or not all(isinstance(u, URIRef) for u in urls):
                fails.append(f"{where}: distribution {dist} is not described (dcat:Distribution with a dcat:downloadURL IRI)")
                continue
            for url in urls:
                name = str(url).rstrip("/").rsplit("/", 1)[-1]
                if name not in files:
                    fails.append(f"{where}: distribution {dist} downloads {name}, which the manifest does not list")
    return fails


def build(releases, title, description):
    """(catalog text, failures). The text is empty when anything fails."""
    found = check_packages.on_disk(releases)
    if not found:
        return "", [f"no release package under {releases}"]
    union = Graph()
    union.bind("dcat", DCAT)
    union.bind("dcterms", DCTERMS)
    union.bind("owl", Namespace("http://www.w3.org/2002/07/owl#"))
    fails, catalogs = [], {}
    for module, version in sorted(found):
        where = f"{module} {version}"
        try:
            g, manifest = package_record(releases, module, version)
        except (OSError, ValueError) as exc:
            fails.append(f"{where}: {exc}")
            continue
        fails += check_record(where, g, manifest)
        for cat in g.subjects(RDF.type, DCAT.Catalog):
            catalogs.setdefault(cat, []).append(where)
        union += g
    if len(catalogs) > 1:
        fails.append("the packages name different catalog IRIs: " + "; ".join(
            f"{cat} ({', '.join(pkgs)})" for cat, pkgs in sorted(catalogs.items(), key=lambda kv: str(kv[0]))))
    if fails:
        return "", fails
    cat = next(iter(catalogs))
    union.add((cat, DCTERMS.title, Literal(title, lang="en")))
    union.add((cat, DCTERMS.description, Literal(description, lang="en")))
    return union.serialize(format="turtle"), []


def main(argv):
    p = argparse.ArgumentParser(prog="build_catalog.py")
    p.add_argument("command", choices=("build", "verify"))
    p.add_argument("--releases", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--description", required=True)
    p.add_argument("--out")
    try:
        args = p.parse_args(argv)
    except SystemExit:
        return 2
    if not os.path.isdir(args.releases):
        print(f"ERROR not a directory: {args.releases}", file=sys.stderr)
        return 2
    if not args.title.strip() or not args.description.strip():
        print("ERROR --title and --description must hold text", file=sys.stderr)
        return 2
    out = args.out or os.path.join(args.releases, "catalog.ttl")
    text, fails = build(args.releases, args.title.strip(), args.description.strip())
    for line in fails:
        print("FAIL", line)
    if fails:
        print(f"{len(fails)} failure(s)", file=sys.stderr)
        return 1
    count = len(check_packages.on_disk(args.releases))
    if args.command == "build":
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print(f"wrote {out}: {count} releases from {count} packages")
        return 0
    if not os.path.isfile(out):
        print(f"FAIL no written catalog at {out}")
        return 1
    with open(out, "rb") as f:  # bytes, so a changed line ending is a difference too
        if f.read() != text.encode("utf-8"):
            print(f"FAIL {out} differs from a fresh build of the {count} packages under {args.releases}")
            return 1
    print(f"{out} equals a fresh build: {count} releases from {count} packages")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
