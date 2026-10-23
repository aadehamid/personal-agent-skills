#!/usr/bin/env python3
"""Check an ontology build's requirements file against its schema and for conflicts.

Run: uv run --with pyyaml python3 check_requirements.py requirements.yaml

The schema is written at the top of templates/requirements.yaml, and this script enforces
each line of it; the rule is references/governance.md, rule 2. A conflict is a competency
question that needs an area scope.in does not list, or that needs, or whose rationale
names, an area scope.out lists (a whole-word match, ignoring case), or an area listed both
in and out of scope.

Exit 0 when the file passes, 1 when any check fails (one line per failure), 2 when the
file cannot be read or parsed, or when the arguments are wrong.
"""
import re
import sys

import yaml

INPUT_KINDS = ("purpose", "competency_questions", "representative_data",
               "reusable_vocabularies", "semantic_evidence", "constraints")
TOP_KEYS = ("purpose", "users", "use_cases", "inputs", "scope",
            "competency_questions", "assumptions", "constraints")
CQ_FIELDS = ("id", "question", "priority", "rationale", "needs", "status")


def text(value):
    """True when value is a non-empty string."""
    return isinstance(value, str) and value.strip() != ""


def text_list(value, allow_empty=True):
    """True when value is a list of non-empty strings (and non-empty unless allowed)."""
    return (isinstance(value, list) and (allow_empty or bool(value))
            and all(text(v) for v in value))


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

    if not text(req["purpose"]):
        fails.append(("schema", "'purpose' must be one non-empty sentence"))
    if not text_list(req["users"], allow_empty=False):
        fails.append(("schema", "'users' must be a non-empty list of roles or systems"))
    if not text_list(req["constraints"]):
        fails.append(("schema", "'constraints' must be a list of strings (empty if none)"))

    use_cases = req["use_cases"]
    if not isinstance(use_cases, list) or not use_cases:
        fails.append(("schema", "'use_cases' must be a non-empty list of {id, text}"))
    else:
        ids = set()
        for i, uc in enumerate(use_cases):
            if not isinstance(uc, dict) or not text(uc.get("id")) or not text(uc.get("text")):
                fails.append(("schema", f"use case {i + 1} needs an 'id' and a 'text'"))
                continue
            if uc["id"] in ids:
                fails.append(("schema", f"use case {uc['id']} is used twice"))
            ids.add(uc["id"])

    inputs = req["inputs"]
    if not isinstance(inputs, dict):
        fails.append(("inputs", "'inputs' must map each of the six kinds to {status, note}"))
        inputs = {}
    for kind in INPUT_KINDS:
        entry = inputs.get(kind)
        if not isinstance(entry, dict) or entry.get("status") not in ("have", "thin", "missing"):
            fails.append(("inputs", f"input '{kind}' needs a status of have, thin or missing"))
        elif entry["status"] != "have" and not text(entry.get("note")):
            fails.append(("inputs", f"input '{kind}' is {entry['status']} and needs a note saying how the gap limits the design"))

    scope = req["scope"]
    if (not isinstance(scope, dict) or not text_list(scope.get("in"), allow_empty=False)
            or not text_list(scope.get("out", []))):
        fails.append(("schema", "'scope' needs 'in' (a non-empty list of areas) and 'out' (a list of areas)"))
        scope = {"in": [], "out": []}
    in_scope = {a.casefold() for a in scope.get("in") or []}
    out_scope = {a.casefold() for a in scope.get("out") or []}
    for area in sorted(in_scope & out_scope):
        fails.append(("conflict", f"area '{area}' is both in and out of scope"))

    cqs = req["competency_questions"]
    if not isinstance(cqs, list) or not cqs:
        fails.append(("schema", "'competency_questions' must be a non-empty list"))
        cqs = []
    seen = set()
    for i, cq in enumerate(cqs):
        cid = cq.get("id") if isinstance(cq, dict) else None
        label = cid or f"question {i + 1}"
        if not isinstance(cq, dict):
            fails.append(("schema", f"{label} is not a mapping"))
            continue
        for field in CQ_FIELDS:
            if not cq.get(field):
                fails.append(("schema", f"{label} has no '{field}'"))
        if cid in seen:
            fails.append(("schema", f"{cid} is used twice"))
        seen.add(cid)
        if cq.get("priority") and cq["priority"] not in ("must", "should", "could"):
            fails.append(("schema", f"{label} priority '{cq['priority']}' is not must, should or could"))
        if cq.get("status") and cq["status"] not in ("drafted", "locked"):
            fails.append(("schema", f"{label} status '{cq['status']}' is not drafted or locked"))
        needs = cq.get("needs") or []
        if not text_list(needs):
            fails.append(("schema", f"{label} 'needs' must be a list of area names"))
            needs = []
        for need in needs:
            need_key = need.casefold()
            if need_key in out_scope:
                fails.append(("conflict", f"{label} needs '{need}', which scope.out excludes"))
            elif need_key not in in_scope:
                fails.append(("conflict", f"{label} needs '{need}', which scope.in does not list"))
        rationale = str(cq.get("rationale") or "").casefold()
        for area in sorted(out_scope):
            if re.search(r"\b" + re.escape(area) + r"\b", rationale):
                fails.append(("conflict", f"{label} rationale names '{area}', which scope.out excludes"))

    assumptions = req["assumptions"]
    if not isinstance(assumptions, list):
        fails.append(("assumptions", "'assumptions' must be a list (empty if none)"))
        assumptions = []
    for i, a in enumerate(assumptions):
        label = (a.get("id") if isinstance(a, dict) else None) or f"assumption {i + 1}"
        if not isinstance(a, dict) or not text(a.get("id")) or not text(a.get("text")) or "record" not in a:
            fails.append(("assumptions", f"{label} needs an 'id', a 'text' and a 'record' field"))
        elif a.get("status") not in ("ASSUMED", "confirmed"):
            fails.append(("assumptions", f"{label} needs a status of ASSUMED or confirmed"))
        elif a["status"] == "confirmed" and not text(a.get("record")):
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
