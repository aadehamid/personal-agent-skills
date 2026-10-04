"""`kb dupes`: Raw files that are the same source.

Two levels, reported differently:
- exact: same URL after stripping quotes, trailing slash and http/https. These
  are duplicates (FAIL). Hashed-suffix names (`-0041df`) are the usual sign.
- normalized: same URL under kb.urls.norm() (tracking params dropped, known
  host/path moves), but not exact. Likely duplicates; verify (WARN). A URL that
  cannot be normalized is a FAIL: an incomplete scan must never look complete.

The same URL in two different bundles can be deliberate cross-filing, so it is
only reported with --cross, as information.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from . import vault as V
from .config import Bundle
from .report import Report
from .urls import norm as loose_norm


def _urls(b: Bundle) -> dict[Path, str]:
    out = {}
    for raw in V.raw_files(b.path):
        fm, _ = V.frontmatter(raw)
        u = V.fm_value(fm, "url")
        if u:
            out[raw] = u
    return out


def run(bundles: list[Bundle], cross: bool = False) -> list[Report]:
    reports, by_url_all = [], defaultdict(list)
    for b in bundles:
        r = Report("dupes", b.name)
        r.footer = False
        urls = _urls(b)
        exact, normed, unnormalized = defaultdict(list), defaultdict(list), []
        for raw, u in urls.items():
            exact[V.norm_url(u)].append(raw.name)
            by_url_all[V.norm_url(u)].append(f"{b.name}/Raw/{raw.name}")
            try:
                normed[loose_norm(u)].append(raw.name)
            except Exception as e:  # report, never swallow: the scan is incomplete
                unnormalized.append(f"{raw.name} ({u!r}: {type(e).__name__})")
        groups = {u: sorted(v) for u, v in exact.items() if len(v) > 1}
        for u, files in groups.items():
            r.fail(f"same URL: {files}  ({u})")
        exact_sets = {frozenset(v) for v in groups.values()}
        likely = {u: sorted(v) for u, v in normed.items()
                  if len(v) > 1 and frozenset(v) not in exact_sets}
        for u, files in likely.items():
            r.warn(f"likely same source (normalized URL), verify: {files}  ({u})")
        for u in unnormalized:
            r.fail(f"URL could not be normalized, so the duplicate scan is incomplete: {u}")
        r.ok(f"{len(urls)} Raw sources with a URL; {len(groups)} exact duplicate group(s)")
        r.data.update({"exact": groups, "likely": likely})
        reports.append(r)
    if cross:
        r = Report("dupes --cross", "across bundles")
        r.footer = False
        shared = {u: v for u, v in by_url_all.items()
                  if len({x.split('/Raw/')[0] for x in v}) > 1}
        for u, files in shared.items():
            r.ok(f"in more than one bundle (may be deliberate): {files}")
        r.data["cross"] = shared
        reports.append(r)
    return reports
