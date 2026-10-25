#!/usr/bin/env python3
"""Review a loaded projection against the graph anti-patterns of Neo4j's neo4j-modeling-skill
(version 1.0.7: "Defaults", "Anti-Patterns Table", "Supernode Detection and Mitigation"; severity as
its "Output Format": ERROR stops, WARNING is reported, INFO is surfaced).

Run after step 6 (or after a copy, add-on I), against any Neo4j:
    NEO4J_PASSWORD=... uv run --no-project --with rdflib --with neo4j python3 model_review.py \
        --uri bolt://127.0.0.1:<port> [--report model-review.json] [options]
    uv run --no-project --with rdflib --with neo4j python3 model_review.py --env <target.env> [...]

--env names a file of NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD and optionally NEO4J_DATABASE (the
format copy_graph.py reads). The password is never printed.

The rules, each one finding per offender:
  missing-key-constraint  ERROR    no uniqueness or node-key constraint on --key-label(--key-property),
                                   by default n10s's Resource(uri) (the skill's default 4: every node
                                   type used in MERGE has one; its table: "duplicate nodes silently created")
  generic-label           WARNING  a label whose local name (after the SHORTEN "prefix__") is Entity,
                                   Node or Thing (default 6 and the table)
  generic-type            WARNING  a relationship type whose local name is RELATED_TO or HAS, in any case
                                   or spelling (relatedTo, has)
  supernode               WARNING  a node with more than --max-degree relationships (default 100000:
                                   "Any node with >100K relationships will degrade traversal")
  supernode-candidate     INFO     a node whose degree is at least --factor (default 10) times the median
                                   of its label and at least --min-degree (default 50) ("degree >> median
                                   for its label"); a concept scheme or a code-list value is expected here
  both-directions         WARNING  one relationship type used from label A to B and from B to A, A and B
                                   different (default 8: "Rel direction encodes semantic meaning")

n10s's own nodes and labels are not domain data and are skipped: Resource (on every node), the
configuration labels (_GraphConfig, _NsPrefDef, _n10sValidatorConfig) and the schema labels
(n4sch__*). Where the projection departs from the skill on purpose (SKOS concepts as nodes,
properties on relationships), design-rules.md says so; this script checks only rules the projection
keeps.

Exit 0 when no ERROR was found, 1 when one was, 2 on bad input or a failed query. Every printed value
is shell-quoted.
"""
import json
import os
import statistics
import sys

from shell import q, redact

SKIPPED_LABELS = {"Resource", "_GraphConfig", "_NsPrefDef", "_n10sValidatorConfig"}
GENERIC_LABELS = {"entity", "node", "thing"}
GENERIC_TYPES = {"relatedto", "has"}

LABELS = "CALL db.labels() YIELD label RETURN label"
TYPES = "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType AS type"
CONSTRAINTS = "SHOW CONSTRAINTS YIELD type, entityType, labelsOrTypes, properties RETURN type, entityType, labelsOrTypes, properties"
DEGREES = "MATCH (n) RETURN n.uri AS uri, labels(n) AS labels, count{ (n)--() } AS degree"
PATTERNS = ("MATCH (a)-[r]->(b) RETURN DISTINCT type(r) AS type, labels(a) AS source, labels(b) AS target")


def local(name):
    """The local part of a SHORTEN name (lib__Work -> Work), squashed for comparison."""
    return name.split("__", 1)[-1].replace("_", "").lower()


def domain(labels):
    return sorted(lb for lb in labels if lb not in SKIPPED_LABELS and not lb.startswith("n4sch__"))


def finding(severity, rule, message):
    return {"severity": severity, "rule": rule, "message": message}


def review(run, key_label="Resource", key_property="uri", max_degree=100000, factor=10, min_degree=50):
    """The findings for the graph behind run(statement) -> list of row dicts, most severe first."""
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
        if label not in SKIPPED_LABELS and local(label) in GENERIC_LABELS:
            found.append(finding("WARNING", "generic-label", f"label {label} is generic; use the domain class"))
    for row in run(TYPES):
        if local(row["type"]) in GENERIC_TYPES:
            found.append(finding("WARNING", "generic-type",
                                 f"relationship type {row['type']} is generic; use the domain property"))
    rows = run(DEGREES)
    by_label = {}
    for row in rows:
        for label in domain(row["labels"]):
            by_label.setdefault(label, []).append(row["degree"])
    medians = {label: statistics.median(values) for label, values in by_label.items()}
    for row in sorted(rows, key=lambda r: (-r["degree"], str(r.get("uri")))):
        who = row.get("uri") or ":".join(row["labels"])
        if row["degree"] > max_degree:
            found.append(finding("WARNING", "supernode", f"{who} has {row['degree']} relationships (over {max_degree})"))
            continue
        for label in domain(row["labels"]):
            median = medians[label]
            if row["degree"] >= min_degree and row["degree"] >= factor * max(median, 1):
                found.append(finding("INFO", "supernode-candidate",
                                     f"{who} has {row['degree']} relationships, {factor}x or more the median "
                                     f"{median:g} of {label}"))
                break
    pairs = {}
    for row in run(PATTERNS):
        for a in domain(row["source"]):
            for b in domain(row["target"]):
                if a != b:
                    pairs.setdefault(row["type"], set()).add((a, b))
    for rel_type, ends in sorted(pairs.items()):
        both = sorted((a, b) for a, b in ends if (b, a) in ends and a < b)
        for a, b in both:
            found.append(finding("WARNING", "both-directions",
                                 f"{rel_type} runs from {a} to {b} and from {b} to {a}; give each direction its meaning"))
    order = {"ERROR": 0, "WARNING": 1, "INFO": 2}
    return sorted(found, key=lambda f: (order[f["severity"]], f["rule"], f["message"]))


def options(argv):
    opts, numbers = {}, {"--max-degree": 100000, "--factor": 10, "--min-degree": 50}
    known = {"--uri", "--env", "--report", "--key-label", "--key-property", *numbers}
    i = 0
    while i < len(argv):
        flag = argv[i]
        if flag not in known or i + 1 >= len(argv):
            raise ValueError(f"unknown flag or missing value: {flag}")
        opts[flag] = argv[i + 1]
        i += 2
    if ("--uri" in opts) == ("--env" in opts):
        raise ValueError("give exactly one of --uri and --env")
    for flag, default in numbers.items():
        try:
            numbers[flag] = int(opts.get(flag, default))
        except ValueError:
            raise ValueError(f"{flag} needs a whole number") from None
        if numbers[flag] < 1:
            raise ValueError(f"{flag} needs a number of at least 1")
    return opts, numbers


def connection(opts):
    """(uri, auth, database) from --uri with NEO4J_PASSWORD, or from --env."""
    if "--env" in opts:
        from copy_graph import read_env_file
        values = read_env_file(opts["--env"])
        return values["NEO4J_URI"], (values["NEO4J_USERNAME"], values["NEO4J_PASSWORD"]), values.get("NEO4J_DATABASE")
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        raise ValueError("set NEO4J_PASSWORD for --uri")
    return opts["--uri"], ("neo4j", password), None


def main(argv):
    try:
        opts, numbers = options(argv)
        uri, auth, database = connection(opts)
    except (OSError, ValueError) as exc:
        print(f"ERROR {q(exc)}", file=sys.stderr)
        return 2
    try:
        from neo4j import GraphDatabase
        with GraphDatabase.driver(uri, auth=auth) as driver, driver.session(database=database) as session:
            found = review(lambda stmt: session.run(stmt).data(),
                           key_label=opts.get("--key-label", "Resource"), key_property=opts.get("--key-property", "uri"),
                           max_degree=numbers["--max-degree"], factor=numbers["--factor"], min_degree=numbers["--min-degree"])
    except Exception as exc:  # the driver raises several types; any of them stops the review
        # The driver's own text can carry the URI with its password, so only the type is printed.
        print(f"ERROR the review query failed on {q(redact(uri))} ({q(type(exc).__name__)})", file=sys.stderr)
        return 2
    for f in found:
        print(f"{q(f['severity'])} {q(f['rule'])}: {q(f['message'])}")
    errors = sum(f["severity"] == "ERROR" for f in found)
    print(f"{q(len(found))} finding(s), {q(errors)} error(s)")
    if "--report" in opts:
        with open(opts["--report"], "w", encoding="utf-8") as fh:
            json.dump({"findings": found, "errors": errors}, fh, indent=2, sort_keys=True)
            fh.write("\n")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
