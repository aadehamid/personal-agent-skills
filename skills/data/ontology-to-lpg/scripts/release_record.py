#!/usr/bin/env python3
"""One release record per module in a loaded projection: which release the graph holds, whether it
passed, and which rules loaded it.

    uv run --no-project --with rdflib python3 release_record.py records --report <projection-report.json> --manifest <run-manifest.json> --output <release-records.json> [--loaded-at <time>] <package.ttl>...
    uv run --no-project --with rdflib --with neo4j python3 release_record.py write --records <release-records.json> (--uri U | --env E)
    uv run --no-project --with rdflib --with neo4j python3 release_record.py check --records <release-records.json> (--uri U | --env E)

Each package file sits beside its release's shapes.ttl and catalog.ttl. `records` reads no database. It
refuses a report that did not earn its pass (build.report_earned, as copy_graph.py does), and any package,
shapes or catalog file whose path and SHA-256 are not together in the run's run-manifest.json, so a record cannot
describe a file edited or swapped after the load. It reads each file once, and hashes and parses those same bytes. It then writes one record per package, every field taken from those files or the report:

  ontology, version_iri                    the package file's owl:Ontology and its owl:versionIRI
  module, version                          catalog.ttl's dcat:Dataset of that version IRI: the last part of its
                                           dcterms:isVersionOf, which must equal the ontology, and owl:versionInfo
  download_url                             the dcat:downloadURL in catalog.ttl that names the package file
  conforms, in_graph_constraints, violations   the report: these describe the whole load, because the shapes
                                           run over every module together
  shapes_sha256                            SHA-256 of the release's shapes.ttl
  projection_version                       the report's versions.method: the rules that loaded the graph
  loaded_at                                --loaded-at, else the time `records` ran, in UTC

`write` replaces every :ModuleRelease node with the file's records, in one transaction, and links each to its module's
owl:Ontology node with (:ModuleRelease)-[:DESCRIBES]->(:Resource). A record has no :Resource label, so the
graph hash, the counts, the module tags and the round trip do not read it, nor the link, whose start is not a
:Resource. No field goes into any hash. `write` proves it: it stops before writing unless the graph hash equals
the one the file carries (the report's), and rolls back, keeping the earlier records, if a record finds no
owl:Ontology node or the hash moved.

`check` fails unless the graph holds exactly the file's records, field for field, each with its link, and the
graph hash still equals the file's.

Exit 0 on a pass, 1 on a failed check, 2 on bad input or a failed query. An error prints a fixed context and the
exception's type, never its text (shell.error_line). Every printed value is quoted.
"""
import datetime as dt
import hashlib
import json
import os
import pathlib
import sys

from rdflib import Graph, URIRef
from rdflib.namespace import DCAT, DCTERMS, OWL, RDF

import build
import load_verify as lv
from shell import Refusal, error_line, q, unverified_report

LABEL = "ModuleRelease"
LINK = "DESCRIBES"
CLEAR = f"MATCH (r:{LABEL}) DETACH DELETE r"
WRITE = (f"UNWIND $rows AS row CREATE (r:{LABEL}) SET r = row WITH r "
         f"MATCH (o:Resource {{uri: r.ontology}}) CREATE (r)-[:{LINK}]->(o) RETURN count(*) AS linked")
READ = (f"MATCH (r:{LABEL}) OPTIONAL MATCH (r)-[:{LINK}]->(o:Resource) "
        "RETURN properties(r) AS fields, collect(o.uri) AS links ORDER BY fields.version_iri")


def checked_bytes(path, recorded, where):
    """The file's bytes, read once, when the run manifest records that path with their SHA-256. Returns (bytes, digest)."""
    with open(path, "rb") as f:
        body = f.read()
    digest = hashlib.sha256(body).hexdigest()
    if recorded.get(os.path.realpath(path)) != digest:
        raise Refusal(f"{where}: {os.path.basename(path)} is not the file the run read; run project and load again")
    return body, digest


def parsed(path, body):
    """Turtle bytes as the file at path means them: a relative IRI resolves against that file."""
    return Graph().parse(data=body, format="turtle", publicID=pathlib.Path(os.path.abspath(path)).as_uri())


def one(values, what, where):
    found = sorted({str(v) for v in values})
    if len(found) != 1:
        raise Refusal(f"{where}: expected one {what}, found {len(found)}")
    return found[0]


def record(path, report, loaded_at, loaded):
    """The record of one package file, from the files beside it and the report. loaded maps a kind of file in the
    run manifest (data, shapes, catalogs) to {real path: the SHA-256 that run read}."""
    folder, name = os.path.split(path)
    where = name
    data = parsed(path, checked_bytes(path, loaded["data"], where)[0])
    shapes_digest = checked_bytes(os.path.join(folder, "shapes.ttl"), loaded["shapes"], where)[1]
    ontology = one(data.subjects(RDF.type, OWL.Ontology), "owl:Ontology", where)
    version_iri = one(data.objects(URIRef(ontology), OWL.versionIRI), "owl:versionIRI", where)
    catalog_path = os.path.join(folder, "catalog.ttl")
    catalog = parsed(catalog_path, checked_bytes(catalog_path, loaded["catalogs"], where)[0])
    dataset = URIRef(version_iri)
    if (dataset, RDF.type, DCAT.Dataset) not in catalog:
        raise Refusal(f"{where}: its catalog.ttl has no dcat:Dataset named by its owl:versionIRI")
    of = one(catalog.objects(dataset, DCTERMS.isVersionOf), "dcterms:isVersionOf", where)
    if of != ontology:
        raise Refusal(f"{where}: its catalog.ttl says it is a version of another module")
    urls = [str(u) for d in catalog.objects(dataset, DCAT.distribution) for u in catalog.objects(d, DCAT.downloadURL)]
    return {"module": of.rstrip("/").rsplit("/", 1)[-1],
            "version": one(catalog.objects(dataset, OWL.versionInfo), "owl:versionInfo", where),
            "version_iri": version_iri,
            "ontology": ontology,
            "download_url": one([u for u in urls if u.rsplit("/", 1)[-1] == name], f"dcat:downloadURL ending {name}", where),
            "conforms": report["passed"] is True and report["shacl_violations_in_graph"] == 0,
            "in_graph_constraints": report["in_graph_shape_constraints"],
            "violations": report["shacl_violations_in_graph"],
            "shapes_sha256": shapes_digest,
            "projection_version": report["versions"]["method"],
            "loaded_at": loaded_at}


def now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_records(paths, report, loaded_at, manifest):
    fails = build.report_earned(report)
    if fails:
        raise unverified_report(fails)
    if "catalogs" not in manifest:
        raise Refusal("the run manifest lists no catalogs; run project again")
    loaded = {kind: {os.path.realpath(e["path"]): e["sha256"] for e in manifest[kind]} for kind in ("data", "shapes", "catalogs")}
    records = sorted((record(p, report, loaded_at, loaded) for p in paths), key=lambda r: r["version_iri"])
    for field, what in (("module", "one module"), ("version_iri", "one release")):
        if len({r[field] for r in records}) != len(records):
            raise Refusal(f"two package files are {what}; give one release per module")
    return {"graph_hash": report["determinism_hash_sorted"], "records": records}


def write(session, content):
    """Replaces the records in one transaction, with the graph hash checked before and after; any problem or error
    rolls back, so the earlier records stay. Returns (problems, links written)."""
    tx = session.begin_transaction()
    committed = False
    try:
        hash_of = lambda: lv.hash_graph(tx)[0]   # noqa: E731
        if hash_of() != content["graph_hash"]:
            return ["the graph is not the verified graph: its hash differs from the report's; nothing was written"], 0
        tx.run(CLEAR).consume()
        linked = tx.run(WRITE, {"rows": content["records"]}).single()["linked"]
        problems = []
        if linked != len(content["records"]):
            problems.append(f"{linked} of {len(content['records'])} records found their owl:Ontology node; nothing was written")
        if hash_of() != content["graph_hash"]:
            problems.append("the graph hash moved when the records were written; nothing was written")
        if not problems:
            tx.commit()
            committed = True
        return problems, linked
    finally:
        if not committed:
            tx.rollback()


def compare(read, content):
    """What differs between the records read back as [{fields, links}] and the file's. Module names and field names
    only, never a value."""
    problems = []
    want = {r["version_iri"]: r for r in content["records"]}
    got = {row["fields"].get("version_iri"): row for row in read}
    if len(got) != len(read):
        problems.append("two records name one release")
    for iri in sorted(set(want) - set(got), key=str):
        problems.append(f"no record of {want[iri]['module']}")
    for iri in sorted(set(got) - set(want), key=str):
        problems.append(f"a record of a release the file does not list: {iri}")
    for iri in sorted(set(want) & set(got), key=str):
        fields = got[iri]["fields"]
        moved = sorted(k for k in set(fields) | set(want[iri]) if fields.get(k) != want[iri].get(k))
        if moved:
            problems.append(f"{want[iri]['module']}: {', '.join(moved)} differ")
        if got[iri]["links"] != [want[iri]["ontology"]]:
            problems.append(f"{want[iri]['module']}: not linked to its owl:Ontology node alone")
    return problems


def check(session, content):
    problems = compare(session.run(READ).data(), content)
    if lv.hash_graph(session)[0] != content["graph_hash"]:
        problems.append("the graph hash is not the verified graph's")
    return problems


def options(argv):
    opts, files, i = {}, [], 0
    known = {"--report", "--manifest", "--output", "--loaded-at", "--records", "--uri", "--env", "--query-timeout"}
    while i < len(argv):
        if argv[i].startswith("--"):
            if argv[i] not in known or i + 1 >= len(argv):
                raise Refusal("an unknown flag, or a flag without its value")
            opts[argv[i]] = argv[i + 1]
            i += 2
        else:
            files.append(argv[i])
            i += 1
    return opts, files


def main(argv):
    if not argv or argv[0] not in ("records", "write", "check"):
        print("usage: release_record.py records|write|check [options] [<package.ttl>...]", file=sys.stderr)
        return 2
    command = argv[0]
    try:
        opts, files = options(argv[1:])
        if command == "records":
            build.need(opts, "--report", "--manifest", "--output")
            if not files:
                raise Refusal("give the package files")
            with open(opts["--report"], encoding="utf-8") as f:
                report = json.load(f)
            with open(opts["--manifest"], encoding="utf-8") as f:
                manifest = json.load(f)
            content = build_records(files, report, opts.get("--loaded-at") or now(), manifest)
            with open(opts["--output"], "w", encoding="utf-8") as f:
                json.dump(content, f, indent=2, sort_keys=True)
                f.write("\n")
            print(f"wrote {q(len(content['records']))} release record(s) to {q(opts['--output'])}")
            return 0
        build.need(opts, "--records")
        if files:
            raise Refusal(f"{command} takes no package files")
        if ("--uri" in opts) == ("--env" in opts):
            raise Refusal("give exactly one of --uri and --env")
        with open(opts["--records"], encoding="utf-8") as f:
            content = json.load(f)
        timeout = lv.query_timeout(opts)
        from model_review import connection
        uri, auth, database = connection(opts)
    except (OSError, ValueError, KeyError) as exc:
        print(f"ERROR {q(error_line('the arguments, the release files or the report could not be read', exc))}",
              file=sys.stderr)
        return 2
    try:
        from neo4j import GraphDatabase
        with GraphDatabase.driver(uri, auth=auth) as driver, driver.session(database=database) as raw:
            session = lv.Timed(raw, timeout)
            if command == "write":
                problems, linked = write(session, content)
                if not problems:
                    print(f"wrote {q(len(content['records']))} release record(s), {q(linked)} linked to their "
                          "owl:Ontology node; the graph hash did not move")
            else:
                problems = check(session, content)
                if not problems:
                    print(f"the graph holds exactly the {q(len(content['records']))} release record(s) and the verified graph")
    except Exception as exc:  # the driver raises several types; any of them stops the run
        print(f"ERROR {q(error_line('a graph query failed', exc))}", file=sys.stderr)
        return 2
    for problem in problems:
        print(f"FAIL {q(problem)}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
