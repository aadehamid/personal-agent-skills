"""`kb coverage`: which Raw sources no page cites.

A source counts as processed when some Wiki or Learning Path page cites its exact
filename. Frontmatter flags (fetch_status, wiki_refs) drift; the citation is the
fact. Mentions in log.md and index.md do not count: a log naming a file is not a
page using it. Files a bundle leaves uncited on purpose are listed under
`uncited_ok` in the config, each with its reason, and reported separately.
"""
from __future__ import annotations

from . import vault as V
from .config import Bundle
from .report import Report


def run(b: Bundle) -> Report:
    r = Report("coverage", b.name)
    raws = V.raw_files(b.path)
    texts = [V.read(p) for p in V.pages(b.path)]
    uncited, accepted = [], []
    for raw in raws:
        rx = V.cite_regex(raw.name)
        if any(rx.search(t) for t in texts):
            if raw.name in b.uncited_ok:
                r.warn(f"{raw.name} is listed in uncited_ok but is now cited; remove the entry")
            continue
        fm, _ = V.frontmatter(raw)
        row = {"file": raw.name, "words": V.word_count(raw),
               "fetch_status": V.fm_value(fm, "fetch_status") or V.fm_value(fm, "status"),
               "title": V.fm_value(fm, "title")}
        if raw.name in b.uncited_ok:
            accepted.append({**row, "reason": b.uncited_ok[raw.name]})
        else:
            uncited.append(row)
    stale = sorted(set(b.uncited_ok) - {p.name for p in raws})
    for name in stale:
        r.warn(f"uncited_ok names a file that is not in Raw/: {name}")
    for u in uncited:
        r.fail(f"uncited: {u['file']} ({u['words']} words, fetch_status={u['fetch_status'] or '?'})")
    r.ok(f"{len(raws) - len(uncited) - len(accepted)}/{len(raws)} Raw sources cited by a page"
         + (f"; {len(accepted)} uncited on purpose (uncited_ok)" if accepted else ""))
    r.data.update({"raw_total": len(raws), "uncited": uncited, "uncited_ok": accepted})
    r.footer = False
    return r
