"""`kb citers`: exactly which pages and lines cite a Raw file.

Run it before moving, renaming or deleting a source. A source can look
off-topic and still be the reference a core page depends on.
"""
from __future__ import annotations

from pathlib import Path

from . import vault as V
from .config import Bundle, ConfigError
from .report import Report


def run(b: Bundle, raw_ref: str) -> Report:
    name = Path(raw_ref).name
    if not name.endswith(".md"):
        name += ".md"
    raw = b.path / "Raw" / name
    if not raw.exists():
        raise ConfigError(f"no Raw file {name} in {b.name}")
    r = Report("citers", f"{b.name}/Raw/{name}")
    r.footer = False
    hits = V.citing_lines(name, V.pages(b.path, include_reserved=True), b.path)
    texts = {p.relative_to(b.path).as_posix(): V.read(p) for p in V.pages(b.path)}
    rx = V.cite_regex(name)
    pages = sorted(rel for rel, t in texts.items() if rx.search(t))
    try:
        refs = V.wiki_refs(V.frontmatter(raw)[0])
    except V.RefsError as e:
        refs = []
        r.fail(f"wiki_refs is malformed: {e}")
    for rel, line, text, is_cite in hits:
        r.ok(f"{rel}:{line}  [{'citation' if is_cite else 'mention'}]  {text[:110]}")
    mentions_only = sorted({h[0] for h in hits if not V.is_reserved(h[0])} - set(pages))
    for p in mentions_only:
        r.warn(f"{p} mentions it without a citation form (link, resource:, [source: ...], Raw/ path)")
    for p in pages:
        if p not in refs:
            r.warn(f"{p} cites it but is not in its wiki_refs")
    for ref in refs:
        if ref not in pages:
            r.warn(f"wiki_refs lists {ref}, which does not cite it")
    if not pages:
        r.ok("no page cites this file (mentions, if any, are listed above)")
    r.data.update({"citing_pages": pages, "mentioning_pages": mentions_only,
                   "lines": [{"page": a, "line": n, "text": t, "citation": c} for a, n, t, c in hits],
                   "wiki_refs": refs})
    return r
