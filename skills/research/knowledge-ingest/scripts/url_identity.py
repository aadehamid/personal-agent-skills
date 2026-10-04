#!/usr/bin/env python3
"""Diff an external saved-links source against a corpus inventory.

Answers: what is saved in an external tool that never entered this corpus?

    # from a file of URLs (one per line, or CSV/JSON containing URLs)
    python3 scripts/compare_recall.py --recall recall_export.json

    # or paste URLs on stdin
    pbpaste | python3 scripts/compare_recall.py --recall -

URL matching is deliberate, not naive. Stripping query strings collapses every
YouTube link to "youtube.com/watch", which in this project once produced a
5-overlap answer where the truth was 35. Video ids are preserved; tracking
parameters are dropped.
"""
import argparse
import csv
import json
import re
import sys
import urllib.parse
from collections import defaultdict
from pathlib import Path

# No project defaults live here. The reusable parts of this file are norm() and
# the alias table; where a project keeps its inventory is the project's business,
# so those paths are required arguments rather than baked-in guesses.

# norm() and the alias tables live in the kb package (cli/kb/urls.py) so the kb CLI
# and this script share one copy.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cli"))
from kb.urls import norm  # noqa: E402


def urls_from(path: str) -> list[str]:
    """Pull URLs out of whatever the external tool exported: txt, csv, json, markdown."""
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8",
                                                                    errors="ignore")
    found: list[str] = []
    stripped = text.lstrip()
    if stripped.startswith(("{", "[")):
        try:
            def walk(o):
                if isinstance(o, dict):
                    for k, v in o.items():
                        if isinstance(v, str) and v.startswith("http") and \
                           k.lower() in ("url", "link", "source", "source_url", "href", "uri"):
                            found.append(v)
                        else:
                            walk(v)
                elif isinstance(o, list):
                    for i in o:
                        walk(i)
            walk(json.loads(text))
        except json.JSONDecodeError:
            pass
    if not found:
        found = re.findall(r"https?://[^\s\"'<>)\]},]+", text)
    seen, out = set(), []
    for u in found:
        u = u.rstrip(".,;)")
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def load_inventory(path: Path) -> dict[str, dict]:
    """key -> record, from the corpus inventory TSV."""
    recs: dict[str, dict] = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            k = norm(row.get("url", ""))
            if k:
                recs.setdefault(k, row)
    return recs


def load_subjects(path: Path) -> dict[str, str]:
    """key -> subject it was routed to, when the routing table is available."""
    if not path.exists():
        return {}
    out = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            k = norm(row.get("url", ""))
            if k:
                out[k] = row.get("subject", "")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--external", "--recall", dest="external", required=True,
                    help="file of URLs from the external source (txt/csv/json/md), or - for stdin")
    ap.add_argument("--inventory", required=True,
                    help="TSV of what the corpus already holds; needs a 'url' column")
    ap.add_argument("--routing", default=None,
                    help="optional TSV mapping url -> subject, for the overlap breakdown")
    ap.add_argument("--sources", default=None,
                    help="directory of <subject>/urls.txt files already queued in the pipeline")
    ap.add_argument("--out", help="write the external-only URLs here, one per line")
    args = ap.parse_args()

    dt = load_inventory(Path(args.inventory))
    # The corpus is whatever the pipeline already knows about: the
    # inventory PLUS every <sources>/*/urls.txt when --sources is given. Comparing
    # against the inventory alone reports sources as missing when already queued.
    for uf in sorted(Path(args.sources).glob("*/urls.txt")) if args.sources else []:
        subject = uf.parent.name
        for line in uf.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            k = norm(line.split("|")[0])
            if k:
                dt.setdefault(k, {"url": line.split("|")[0].strip(),
                                  "title": "", "_from": f"urls.txt:{subject}"})
    subjects = load_subjects(Path(args.routing)) if args.routing else {}
    external_urls = urls_from(args.external)
    external = {}
    for u in external_urls:
        k = norm(u)
        if k:
            external.setdefault(k, u)

    only_external = sorted(set(external) - set(dt))
    only_dt = sorted(set(dt) - set(external))
    both = sorted(set(dt) & set(external))

    print(f"external URLs read : {len(external_urls)} ({len(external)} unique resources)")
    print(f"corpus resources   : {len(dt)} unique resources")
    print()
    print(f"  in BOTH           : {len(both)}")
    print(f"  external only     : {len(only_external)}   <- not in the corpus")
    print(f"  corpus only       : {len(only_dt)}")
    print()

    if only_external:
        by_host = defaultdict(list)
        for k in only_external:
            by_host[urllib.parse.urlparse(external[k]).netloc.lower().removeprefix("www.")
                    or "?"].append(external[k])
        print("=" * 72)
        print("EXTERNAL ONLY — candidates to add to the pipeline")
        print("=" * 72)
        for host, urls in sorted(by_host.items(), key=lambda kv: -len(kv[1])):
            print(f"\n  {host}  ({len(urls)})")
            for u in sorted(urls):
                print(f"    {u}")

    if both and subjects:
        print()
        print("=" * 72)
        print("OVERLAP by the subject the corpus routed it to")
        print("=" * 72)
        counts = defaultdict(int)
        for k in both:
            counts[subjects.get(k, "(unrouted)")] += 1
        for s, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            print(f"  {s:<32}{n:>5}")

    if args.out:
        Path(args.out).write_text("\n".join(external[k] for k in only_external) + "\n",
                                  encoding="utf-8")
        print(f"\nExternal-only URLs written to {args.out}")
        print("These are ready to append to a resources/sources/<subject>/urls.txt "
              "after routing.")


if __name__ == "__main__":
    main()
