#!/usr/bin/env python3
"""Check an ontology build's requirements file against its schema and for conflicts.

Run: uv run --with pyyaml python3 check_requirements.py requirements.yaml

The schema is written at the top of templates/requirements.yaml; the rule is
references/governance.md, "Before modelling". A conflict is a competency question that
needs, or whose rationale names, an area the file puts out of scope, or an area listed
both in and out of scope.

Exit 0 when the file passes, 1 when any check fails (one line per failure), 2 when the
file cannot be read or parsed.
"""
import re
import sys

import yaml

INPUT_KINDS = ("purpose", "competency_questions", "representative_data",
               "reusable_vocabularies", "semantic_evidence", "constraints")
TOP_KEYS = ("purpose", "users", "use_cases", "inputs", "scope",
            "competency_questions", "assumptions", "constraints")


def check(req):
    """Return a list of (check name, message) pairs for every failure."""
    fails = []
    if not isinstance(req, dict):
        return [("schema", "the file is not a mapping of the fields in the schema")]
    for key in TOP_KEYS:
        if key not in req:
            fails.append(("schema", f"missing field '{key}'"))
    if fails:
        return fails

    inputs = req["inputs"] or {}
    for kind in INPUT_KINDS:
        entry = inputs.get(kind)
        if not isinstance(entry, dict) or entry.get("status") not in ("have", "thin", "missing"):
            fails.append(("inputs", f"input '{kind}' needs a status of have, thin or missing"))
        elif entry["status"] != "have" and not str(entry.get("note") or "").strip():
            fails.append(("inputs", f"input '{kind}' is {entry['status']} and needs a note saying how the gap limits the design"))

    scope = req["scope"] or {}
    in_scope = {str(a).casefold() for a in scope.get("in") or []}
    out_scope = {str(a).casefold() for a in scope.get("out") or []}
    for area in sorted(in_scope & out_scope):
        fails.append(("conflict", f"area '{area}' is both in and out of scope"))

    seen = set()
    for i, cq in enumerate(req["competency_questions"] or []):
        cid = cq.get("id") if isinstance(cq, dict) else None
        label = cid or f"question {i + 1}"
        if not isinstance(cq, dict):
            fails.append(("schema", f"{label} is not a mapping"))
            continue
        for field in ("id", "question", "priority", "rationale", "needs", "status"):
            if not cq.get(field):
                fails.append(("schema", f"{label} has no '{field}'"))
        if cid in seen:
            fails.append(("schema", f"{cid} is used twice"))
        seen.add(cid)
        if cq.get("priority") and cq["priority"] not in ("must", "should", "could"):
            fails.append(("schema", f"{label} priority '{cq['priority']}' is not must, should or could"))
        if cq.get("status") and cq["status"] not in ("drafted", "locked"):
            fails.append(("schema", f"{label} status '{cq['status']}' is not drafted or locked"))
        for need in cq.get("needs") or []:
            need_key = str(need).casefold()
            if need_key in out_scope:
                fails.append(("conflict", f"{label} needs '{need}', which scope.out excludes"))
            elif need_key not in in_scope:
                fails.append(("conflict", f"{label} needs '{need}', which scope.in does not list"))
        rationale = str(cq.get("rationale") or "").casefold()
        for area in sorted(out_scope):
            if re.search(r"\b" + re.escape(area) + r"\b", rationale):
                fails.append(("conflict", f"{label} rationale names '{area}', which scope.out excludes"))

    for i, a in enumerate(req["assumptions"] or []):
        label = (a.get("id") if isinstance(a, dict) else None) or f"assumption {i + 1}"
        if not isinstance(a, dict) or a.get("status") not in ("ASSUMED", "confirmed"):
            fails.append(("assumptions", f"{label} needs a status of ASSUMED or confirmed"))
        elif a["status"] == "confirmed" and not str(a.get("record") or "").strip():
            fails.append(("assumptions", f"{label} is confirmed but names no decision record"))
    return fails


def main(argv):
    if len(argv) != 1:
        print("usage: check_requirements.py requirements.yaml", file=sys.stderr)
        return 2
    try:
        with open(argv[0], encoding="utf-8") as f:
            req = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as exc:
        print(f"ERROR cannot read {argv[0]}: {exc}", file=sys.stderr)
        return 2
    fails = check(req)
    for name, message in fails:
        print(f"FAIL {name}: {message}")
    if fails:
        print(f"{len(fails)} check(s) failed", file=sys.stderr)
        return 1
    print("requirements pass")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
