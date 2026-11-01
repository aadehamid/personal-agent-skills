#!/usr/bin/env python3
"""Review a loaded projection against the graph anti-patterns of Neo4j's neo4j-modeling-skill
(version 1.0.7: "Defaults", "Anti-Patterns Table", "Supernode Detection and Mitigation"; severity as
its "Output Format": ERROR is a correctness failure, WARNING a performance or extensibility risk, INFO
a style or convention point).

Run after step 6 (or after a copy, add-on I), against any Neo4j:
    NEO4J_PASSWORD=... uv run --no-project --with rdflib --with neo4j python3 model_review.py \
        --uri bolt://127.0.0.1:<port> [--report model-review.json] [--separator _] [options]
    uv run --no-project --with rdflib --with neo4j python3 model_review.py --env <target.env> [...]

--env names a file of NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD and optionally NEO4J_DATABASE (the
format copy_graph.py reads). An error prints a fixed context and the exception's type, never its
text (shell.error_line), so no password or credential-bearing URI is printed. --separator (underscores
only) is what the graph puts between a prefix and a local name: n10s's two underscores unless the load
renamed the names (load_verify.py --separator); give the same value here, or every local name and the
schema labels are read wrongly.

The rules, from the skill, each one finding per offender:
  missing-key-constraint  ERROR    no uniqueness or node-key constraint on --key-label(--key-property),
                                   by default n10s's Resource(uri) (default 4: every node type used in
                                   MERGE has one; the table: "Duplicate nodes silently created")
  generic-label           WARNING  a label whose local name (after the prefix and the separator) is Entity,
                                   Node or Thing (default 6 and the table: no filtering benefit)
  generic-type            WARNING  a relationship type whose local name is RELATED_TO, HAS or
                                   CONNECTED_TO, in any case, with or without "_" or "-"
  supernode               WARNING  a node with more than --max-degree relationships (default 100000:
                                   "Any node with >100K relationships will degrade traversal")
  supernode-candidate     WARNING  a node whose degree is at least --factor (default 10) times the
                                   median of one of its labels and at least --min-degree (default 50)
                                   ("degree >> median for its label"; a performance risk)
and one local heuristic, not from the skill (design-rules.md says why):
  reciprocal-type         INFO     one relationship type used from label A to B and from B to A, where A
                                   is on one end and not the other and B the reverse: often one ontology
                                   property stated both ways

Degree is total degree, both directions. Only domain labels count: n10s's own (Resource, the
configuration labels, the n4sch schema labels under the graph's separator) are left out before any degree rule, and a node with no domain label
is not reviewed. Medians, offenders and reciprocal pairs are computed in Cypher, so only label
statistics, offenders and reciprocal pairs (each at most --limit, default 100) come back. Every statement carries a
server-side timeout, --query-timeout seconds (default 120).

Exit 0 when no ERROR was found, 1 when one was, 2 on bad input, a failed query or an unwritten report.
The report is written atomically. Every printed value is shell-quoted.
"""
import json
import os
import sys
import tempfile

import load_verify as lv
from shell import Refusal, error_line, q

SKIPPED_LABELS = ["Resource", "_GraphConfig", "_NsPrefDef", "_n10sValidatorConfig"]
GENERIC_LABELS = {"entity", "node", "thing"}
GENERIC_TYPES = {"relatedto", "has", "connectedto"}

# $schema_prefix is n4sch plus the graph's separator: the schema labels n10s.onto.import writes.
DOMAIN = "[l IN labels(n) WHERE NOT l IN $skipped AND NOT l STARTS WITH $schema_prefix]"
LABELS = "CALL db.labels() YIELD label RETURN label"
TYPES = "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType AS type"
CONSTRAINTS = ("SHOW CONSTRAINTS YIELD type, entityType, labelsOrTypes, properties "
               "RETURN type, entityType, labelsOrTypes, properties")
LABEL_MEDIANS = (f"MATCH (n) WITH n, {DOMAIN} AS dl WHERE size(dl) > 0 "
                 "WITH dl, count{ (n)--() } AS degree UNWIND dl AS label "
                 "RETURN label, percentileCont(degree, 0.5) AS median")
OFFENDERS = (f"MATCH (n) WITH n, {DOMAIN} AS dl WHERE size(dl) > 0 "
             "WITH n, dl, count{ (n)--() } AS degree "
             "WHERE degree > $max_degree OR (degree >= $min_degree AND any(l IN dl WHERE "
             "degree >= $factor * CASE WHEN coalesce($medians[l], 0) < 1 THEN 1 ELSE $medians[l] END)) "
             "RETURN n.uri AS uri, dl AS labels, degree ORDER BY degree DESC, uri LIMIT $limit")
# One row per (type, label, label) the graph uses, a set the size of the schema, not of the data. A pair
# counts only with labels that tell the two ends apart: x on the source and not the target, y on the
# target and not the source, so one edge between two nodes that share labels (two concepts that are
# both skos:Concept and a narrower class) is never read as both directions. Each pair with x < y is
# kept only when an edge of that type also runs from a y-and-not-x node to an x-and-not-y node (an
# existence check with dynamic labels and type, Cypher 5.26 and later; run on Neo4j 2025.06.2 on
# 2026-10-25).
RECIPROCAL = ("MATCH (a)-[r]->(b) "
              f"WITH DISTINCT type(r) AS t, {DOMAIN.replace('(n)', '(a)')} AS la, {DOMAIN.replace('(n)', '(b)')} AS lb "
              "WITH t, [x IN la WHERE NOT x IN lb] AS la, [y IN lb WHERE NOT y IN la] AS lb "
              "UNWIND la AS x UNWIND lb AS y WITH DISTINCT t, x, y WHERE x < y "
              "AND EXISTS { MATCH (b2:$(y))-[:$(t)]->(a2:$(x)) WHERE NOT x IN labels(b2) AND NOT y IN labels(a2) } "
              "RETURN t AS type, x AS a, y AS b ORDER BY type, a, b LIMIT $limit")


SEP = lv.N10S_SEP   # n10s's separator; --separator names another when the graph was renamed (load_verify.py)


def local(name, sep=None):
    """The local part of a prefixed name (prefix, separator, Work -> work), squashed for comparison."""
    return name.split(sep or SEP, 1)[-1].replace("_", "").replace("-", "").lower()


def finding(severity, rule, message):
    return {"severity": severity, "rule": rule, "message": message}


def review(run, key_label="Resource", key_property="uri", max_degree=100000, factor=10, min_degree=50, limit=100,
           sep=None):
    """(findings most severe first, whether the offender list reached limit) for the graph behind
    run(statement, **parameters) -> list of row dicts. sep is the graph's separator (SEP unless given):
    it splits each local name and names the schema labels every Cypher analysis leaves out."""
    sep = sep or SEP
    schema = "n4sch" + sep
    found = []
    unique = [c for c in run(CONSTRAINTS)
              if c.get("type") in ("UNIQUENESS", "NODE_KEY") and c.get("entityType", "NODE") == "NODE"
              and list(c.get("labelsOrTypes") or []) == [key_label] and list(c.get("properties") or []) == [key_property]]
    if not unique:
        found.append(finding("ERROR", "missing-key-constraint",
                             f"no uniqueness constraint on :{key_label}({key_property}); "
                             f"add CREATE CONSTRAINT IF NOT EXISTS FOR (n:{key_label}) REQUIRE n.{key_property} IS UNIQUE"))
    for row in run(LABELS):
        label = row["label"]
        if label not in SKIPPED_LABELS and not label.startswith(schema) and local(label, sep) in GENERIC_LABELS:
            found.append(finding("WARNING", "generic-label", f"label {label} is generic; use the domain class"))
    for row in run(TYPES):
        if local(row["type"], sep) in GENERIC_TYPES:
            found.append(finding("WARNING", "generic-type",
                                 f"relationship type {row['type']} is generic; use the domain property"))
    medians = {row["label"]: row["median"] for row in run(LABEL_MEDIANS, skipped=SKIPPED_LABELS, schema_prefix=schema)}
    offenders = run(OFFENDERS, skipped=SKIPPED_LABELS, schema_prefix=schema, max_degree=max_degree, min_degree=min_degree,
                    factor=factor, medians=medians, limit=limit)
    for row in offenders:
        who = row.get("uri") or ":".join(row["labels"])
        if row["degree"] > max_degree:
            found.append(finding("WARNING", "supernode", f"{who} has {row['degree']} relationships (over {max_degree})"))
            continue
        label = next(lb for lb in row["labels"] if row["degree"] >= factor * max(medians.get(lb, 0), 1))
        found.append(finding("WARNING", "supernode-candidate",
                             f"{who} has {row['degree']} relationships, {factor}x or more the median "
                             f"{medians[label]:g} of {label}"))
    for row in run(RECIPROCAL, skipped=SKIPPED_LABELS, schema_prefix=schema, limit=limit):
        found.append(finding("INFO", "reciprocal-type",
                             f"{row['type']} runs from {row['a']} to {row['b']} and from {row['b']} to {row['a']}; "
                             "check whether the ontology states one property both ways (local heuristic)"))
    order = {"ERROR": 0, "WARNING": 1, "INFO": 2}
    return sorted(found, key=lambda f: (order[f["severity"]], f["rule"], f["message"])), len(offenders) >= limit


def options(argv):
    opts, numbers = {}, {"--max-degree": 100000, "--factor": 10, "--min-degree": 50, "--limit": 100}
    known = {"--uri", "--env", "--report", "--key-label", "--key-property", "--query-timeout", "--separator", *numbers}
    i = 0
    while i < len(argv):
        flag = argv[i]
        if flag not in known or i + 1 >= len(argv):
            raise Refusal("an unknown flag, or a flag without its value")
        opts[flag] = argv[i + 1]
        i += 2
    if ("--uri" in opts) == ("--env" in opts):
        raise Refusal("give exactly one of --uri and --env")
    for flag, default in numbers.items():
        try:
            numbers[flag] = int(opts.get(flag, default))
        except ValueError:
            raise Refusal(f"{flag} needs a whole number") from None
        if numbers[flag] < 1:
            raise Refusal(f"{flag} needs a number of at least 1")
    numbers["--query-timeout"] = lv.query_timeout(opts)
    return opts, numbers


def connection(opts):
    """(uri, auth, database) from --uri with NEO4J_PASSWORD, or from --env."""
    if "--env" in opts:
        from copy_graph import read_env_file
        values = read_env_file(opts["--env"])
        return values["NEO4J_URI"], (values["NEO4J_USERNAME"], values["NEO4J_PASSWORD"]), values.get("NEO4J_DATABASE")
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        raise Refusal("set NEO4J_PASSWORD for --uri")
    return opts["--uri"], ("neo4j", password), None


def write_report(path, report):
    """The report through a temporary file in the same folder and a rename: a failed write leaves an
    earlier report as it was."""
    folder = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".model-review.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def main(argv):
    try:
        opts, numbers = options(argv)
        uri, auth, database = connection(opts)
        sep = lv.separator(opts)
    except (OSError, ValueError) as exc:
        print(f"ERROR {q(error_line('the arguments or the --env file could not be read', exc))}", file=sys.stderr)
        return 2
    try:
        from neo4j import GraphDatabase
        with GraphDatabase.driver(uri, auth=auth) as driver, driver.session(database=database) as raw:
            session = lv.Timed(raw, numbers["--query-timeout"])
            found, capped = review(lambda stmt, **params: session.run(stmt, params).data(),
                                   key_label=opts.get("--key-label", "Resource"),
                                   key_property=opts.get("--key-property", "uri"), max_degree=numbers["--max-degree"],
                                   factor=numbers["--factor"], min_degree=numbers["--min-degree"],
                                   limit=numbers["--limit"], sep=sep)
    except Exception as exc:  # the driver raises several types; any of them stops the review
        print(f"ERROR {q(error_line('the review query failed', exc))}", file=sys.stderr)
        return 2
    for f in found:
        print(f"{q(f['severity'])} {q(f['rule'])}: {q(f['message'])}")
    if capped:
        print(f"the degree rules stopped at {q(numbers['--limit'])} offenders; raise --limit to see more")
    errors = sum(f["severity"] == "ERROR" for f in found)
    print(f"{q(len(found))} finding(s), {q(errors)} error(s)")
    if "--report" in opts:
        try:
            write_report(opts["--report"], {"findings": found, "errors": errors, "offenders_capped": capped})
        except OSError as exc:
            print(f"ERROR {q(error_line('the report was not written', exc))}", file=sys.stderr)
            return 2
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
