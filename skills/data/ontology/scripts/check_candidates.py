#!/usr/bin/env python3
"""Steps 0 and 3: candidate terms drawn from a document stay grounded in that document and stay candidates
(references/governance.md, "Candidates from documents"; rules 18 and 19).

Run: uv run --no-project --with pyyaml python3 check_candidates.py --source <document.txt>
         [--ontogpt <result.yaml>]... [--candidates <register.yaml>]...

--ontogpt reads the result of `ontogpt extract` (OntoGPT's ExtractionResult: input_text, named_entities with
label and original_spans, each span "start:end", inclusive and zero-based). --candidates reads the skill's
candidate register (templates/intake/candidates.yaml): a source_document and a list of candidates, each with
term, proposed_kind, proposed_definition, source_passage, found_by and status.

Checks:
  input-text  the result's input_text is the supplied document, so its spans point into it
  span        every named entity has at least one span, each of the form start:end inside the document
  grounded    the text at each span is the entity's label (ignoring case and runs of white space)
  register    the register names the supplied document and lists candidates, each with every field
  passage     every candidate's source_passage appears in the document word for word (runs of white space,
              line breaks included, count as one space)
  candidate   every candidate's status is "candidate": approval happens at the human gate, not here

Warning, not a failure:
  term        each content word of the candidate's term (four letters or more) occurs in its passage; a term
              the passage never names is likely a model's paraphrase, and the reviewer should look first

What this proves, and what it does not: the passage is in the document and each candidate is well formed. It
cannot tell whether the proposed definition says what the passage says; that re-check of meaning (governance
rule 19) is a person's step at the human gate (references/quality.md). A definition rewritten into a claim the
passage does not support, next to an unchanged valid passage, passes this script; test_candidates.py shows it.

Prints one FAIL line per failure and one WARN line per warning. Exit 0 when nothing fails (warnings included), 1 when anything fails, 2 when a file cannot be read
or parsed, or the arguments are wrong.
"""
import argparse
import os
import re
import sys

import yaml

FIELDS = ("term", "proposed_kind", "proposed_definition", "source_passage", "found_by", "status")


def squash(text):
    return re.sub(r"\s+", " ", text).strip()


def check_result(result, document):
    fails = []
    if not isinstance(result, dict) or result.get("input_text") is None:
        return [("input-text", "the result has no input_text")]
    # Offsets count characters of input_text with line breaks as single characters (OntoGPT's core schema), so
    # both sides are normalised to "\n" once, and every span is read from that one string.
    document = document.replace("\r\n", "\n")
    if str(result["input_text"]).replace("\r\n", "\n") != document:
        fails.append(("input-text", "the result's input_text is not the supplied document"))
        return fails
    for entity in result.get("named_entities") or []:
        label = str(entity.get("label", ""))
        spans = entity.get("original_spans") or []
        if not spans:
            fails.append(("span", f"entity {label!r} has no original_spans"))
        for span in spans:
            m = re.fullmatch(r"(\d+):(\d+)", str(span))
            if not m or int(m.group(1)) > int(m.group(2)) or int(m.group(2)) >= len(document):
                fails.append(("span", f"entity {label!r}: span {span} is not start:end inside the document"))
                continue
            found = document[int(m.group(1)):int(m.group(2)) + 1]
            if squash(found).casefold() != squash(label).casefold():
                fails.append(("grounded", f"entity {label!r}: span {span} reads {found!r}"))
    return fails


def term_warnings(register):
    """WARN for each candidate whose term has a content word its passage never uses."""
    warnings = []
    for row in register.get("candidates") or [] if isinstance(register, dict) else []:
        if not isinstance(row, dict) or not row.get("term") or not row.get("source_passage"):
            continue
        # Whole words only: "renew" inside "renewal" is not the term. A plural "s" either way still counts.
        words = set(re.findall(r"[a-z]+", squash(str(row["source_passage"])).casefold()))
        missing = [w for w in re.findall(r"[A-Za-z]{4,}", str(row["term"]))
                   if not {w.casefold(), w.casefold() + "s", w.casefold().removesuffix("s")} & words]
        if missing:
            warnings.append(("term", f"{row['term']!r}: its passage never uses {', '.join(missing)}"))
    return warnings


def check_register(register, document, document_name):
    fails = []
    if not isinstance(register, dict) or not isinstance(register.get("candidates"), list):
        return [("register", "the register has no list of candidates")]
    if register.get("source_document") != document_name:
        fails.append(("register", f"the register names {register.get('source_document')!r}, not {document_name!r}"))
    text = squash(document)
    for n, row in enumerate(register["candidates"], start=1):
        term = row.get("term", f"candidate {n}") if isinstance(row, dict) else f"candidate {n}"
        missing = [f for f in FIELDS if not isinstance(row, dict) or not str(row.get(f) or "").strip()]
        if missing:
            fails.append(("register", f"{term!r} has no {', '.join(missing)}"))
            continue
        if squash(str(row["source_passage"])) not in text:
            fails.append(("passage", f"{term!r}: its source_passage is not in the document"))
        if row["status"] != "candidate":
            fails.append(("candidate", f"{term!r} has status {row['status']!r}; only the human gate approves"))
    return fails


def main(argv):
    p = argparse.ArgumentParser(prog="check_candidates.py")
    p.add_argument("--source", required=True)
    p.add_argument("--ontogpt", action="append", default=[])
    p.add_argument("--candidates", action="append", default=[])
    try:
        args = p.parse_args(argv)
    except SystemExit:
        return 2
    if not args.ontogpt and not args.candidates:
        print("ERROR give at least one --ontogpt or --candidates file", file=sys.stderr)
        return 2
    try:
        with open(args.source, encoding="utf-8") as f:
            document = f.read()
        loaded = []
        for kind, paths in (("ontogpt", args.ontogpt), ("candidates", args.candidates)):
            for path in paths:
                with open(path, encoding="utf-8") as f:
                    # BaseLoader reads every scalar as text, so a span such as 21:24 stays "21:24" instead of
                    # YAML 1.1's sexagesimal integer 1284.
                    loaded.append((kind, path, yaml.load(f, Loader=yaml.BaseLoader) if kind == "ontogpt"
                                   else yaml.safe_load(f)))
    except (OSError, yaml.YAMLError) as exc:
        print(f"ERROR cannot read the input: {exc}", file=sys.stderr)
        return 2
    fails, warnings = [], []
    for kind, path, data in loaded:
        if kind == "candidates":
            warnings += [(name, f"{path}: {message}") for name, message in term_warnings(data)]
        found = check_result(data, document) if kind == "ontogpt" else \
            check_register(data, document, os.path.basename(args.source))
        fails += [(name, f"{path}: {message}") for name, message in found]
    for name, message in warnings:
        print(f"WARN {name}: {message}")
    for name, message in fails:
        print(f"FAIL {name}: {message}")
    if fails:
        print(f"{len(fails)} check(s) failed", file=sys.stderr)
        return 1
    print(f"every passage is in {args.source} and every candidate is well formed and still a candidate; "
          f"a person still checks each definition against its passage")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
