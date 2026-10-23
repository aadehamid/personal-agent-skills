#!/usr/bin/env python3
"""The check step's validation: every shape over the data, plus the round-trip refusals.

Run: uv run --no-project --with rdflib --with pyshacl python3 validate_data.py --config <config.json>
         --shapes <shapes.ttl>... <data.ttl or .nt>...

Before serialising, give it the released data files. After serialising, and after build.py
check-serialised has passed on them, give it loadable.nt and inferred.nt together (references/pipeline.md, rules 1 to 3). It runs pySHACL with SHACL-AF on
(advanced=True, so SPARQL targets and constraints run) and no inference, then the refusals of
check_projection_rules.roundtrip_refusals: a plain or xsd:string literal that ends like a language
tag (the pattern @[A-Za-z]{1,8}(-[A-Za-z0-9]{1,8})*$), and an xsd:decimal whose nearest double,
printed in its shortest form and read back as a decimal, is not equal to its value ("1" and "0.64"
pass; "0.1000000000000000055" does not). Release exceptions never waive either.

Exit 0 when the data conforms and nothing is refused, 1 otherwise (the pySHACL report, then one line
per refusal), 2 when a file cannot be read or the arguments are wrong.
"""
import json
import sys

from pyshacl import validate

import check_projection_rules as cpr

USAGE = "usage: validate_data.py --config <config.json> --shapes <shapes.ttl>... <data>..."


def run(data, shapes, cfg):
    """Return (conforms, report text, refusals)."""
    conforms, _, text = validate(data, shacl_graph=shapes, advanced=True, inference="none")
    return conforms, text, cpr.roundtrip_refusals(data, cfg)


def main(argv):
    config, shapes, data, args = None, [], [], list(argv)
    while args:
        a = args.pop(0)
        if a in ("--config", "--shapes") and args:
            if a == "--config":
                config = args.pop(0)
            else:
                shapes.append(args.pop(0))
        elif a.startswith("-"):
            print(USAGE, file=sys.stderr)
            return 2
        else:
            data.append(a)
    if config is None or not shapes or not data:
        print(USAGE, file=sys.stderr)
        return 2
    try:
        with open(config, encoding="utf-8") as f:
            cfg = cpr.Config(json.load(f))
        if cfg.rule4 == "4b":
            print(cpr.RULE_4B_STOP.format(script="validate_data.py"), file=sys.stderr)
            return 2
        data_graph, shapes_graph = cpr.parse(data), cpr.parse(shapes)
    except (OSError, ValueError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # rdflib raises several parser types; any of them stops the check
        print(f"ERROR cannot read the RDF files: {exc}", file=sys.stderr)
        return 2
    conforms, text, refusals = run(data_graph, shapes_graph, cfg)
    if not conforms:
        print(text)
    for _, message in refusals:
        print(f"FAIL refusal: {message}")
    if not conforms or refusals:
        return 1
    print(f"the data conforms to every shape and nothing is refused ({len(data_graph)} triples)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
