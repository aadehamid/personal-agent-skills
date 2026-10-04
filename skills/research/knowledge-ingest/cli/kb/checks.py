"""`kb check`: structural Gate A for one bundle. Fails closed.

Ported from scripts/check_ingest.py, then hardened after review:
- citation matching uses exact filenames (vault.cite_regex), not substrings;
- a page that cites a source but is missing from its wiki_refs is a FAILURE;
- a Learning Path stage in wiki_refs passes only if the stage links a Wiki page
  that itself cites the source (stages link summaries, not Raw files);
- only the exact paths in vault.RESERVED_PATHS mention files without citing them;
- a missing validator is a FAILURE, not a skipped check.
"""
from __future__ import annotations

import datetime as dt
import os
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

from . import vault as V
from .config import Bundle, Config
from .report import Report


def check_validator(r: Report, b: Bundle, cfg: Config, override: Path | None = None) -> None:
    script = override or cfg.validator
    if script is None:
        r.fail("no schema validator: set `validator` in knowledge-ingest.config.json or pass "
               "--validator. Gate A cannot pass without it.")
        return
    if not script.exists():
        r.fail(f"validator not found at {script}; schema conformance not checked")
        return
    p = subprocess.run([sys.executable, str(script), str(b.path)], capture_output=True, text=True)
    out = (p.stdout.strip() or p.stderr.strip()).replace("\n", " | ")
    (r.ok if p.returncode == 0 else r.fail)(f"validator: {out}")


def check_links(r: Report, b: Bundle) -> None:
    checked = broken = 0
    for p in V.pages(b.path, include_reserved=True):
        text = re.sub(r"`[^`]*`", "", V.read(p))
        for m in re.finditer(r"\[[^\]]*\]\((?:<([^>\n]+)>|([^)\s]+))(?:\s+\"[^\"]*\")?\)", text):
            href = re.split(r"[#?]", m.group(1) or m.group(2), maxsplit=1)[0]
            if not href or href.startswith(("http://", "https://", "mailto:")):
                continue
            if not href.lower().endswith(".md"):
                continue
            checked += 1
            target = os.path.normpath(os.path.join(p.parent, urllib.parse.unquote(href)))
            if not os.path.exists(target):
                broken += 1
                r.fail(f"broken link: {p.relative_to(b.path)} -> {href}")
    r.ok(f"{checked} internal links checked, {broken} broken")


def _resolve_ref(ref: str, texts: dict[str, str]) -> str | None:
    """The page a wiki_refs entry means, tolerating a missing `.md` or `Wiki/` prefix."""
    for cand in (ref, f"{ref}.md", f"Wiki/{ref}", f"Wiki/{ref}.md"):
        if cand in texts:
            return cand
    return None


def _stage_wiki_links(stage_text: str) -> list[str]:
    """Vault-relative Wiki pages a Learning Path stage links to."""
    out = []
    for href in re.findall(r"\]\(\.\./(Wiki/[^)#?\s]+\.md)", stage_text):
        out.append(urllib.parse.unquote(href))
    return out


def check_wiki_refs(r: Report, b: Bundle) -> None:
    """wiki_refs must name pages that cite the Raw file, and every citing page must be listed.

    Low-severity patterns that recur across a bundle (malformed but resolvable
    entries, repeated entries) are reported once, with the full list under
    `details` in --json, so they do not bury real failures.
    """
    texts = {p.relative_to(b.path).as_posix(): V.read(p) for p in V.pages(b.path, include_reserved=True)}
    listed = consistent = 0
    repeated, malformed = [], []
    for raw in V.raw_files(b.path):
        try:
            refs = V.wiki_refs(V.frontmatter(raw)[0])
        except V.RefsError as e:
            r.fail(f"{raw.name}: {e}")
            continue
        rx = V.cite_regex(raw.name)
        resolved = []
        for ref in refs:
            listed += 1
            page = _resolve_ref(ref, texts)
            if page is None:
                r.fail(f"wiki_refs points at a missing page: {raw.name} -> {ref}")
                continue
            if page != ref:
                malformed.append(f"{raw.name}: {ref!r} should be {page!r}")
            resolved.append(page)
            if rx.search(texts[page]):
                consistent += 1
            elif page.startswith("Learning Path/"):
                via = [w for w in _stage_wiki_links(texts[page]) if w in texts and rx.search(texts[w])]
                if via:
                    consistent += 1
                else:
                    r.fail(f"wiki_refs lists {page} for {raw.name}, but that stage neither cites it "
                           f"nor links a Wiki page that does")
            else:
                r.fail(f"wiki_refs not reciprocated: {raw.name} lists {page}, which does not cite it")
        if len(set(resolved)) < len(resolved):
            repeated.append(raw.name)
        citers = [rel for rel, t in texts.items() if not V.is_reserved(rel) and rx.search(t)]
        missing = [c for c in citers if c not in resolved]
        if missing:
            r.fail(f"{raw.name} is cited by {missing} but they are not in its wiki_refs")
    details = {}
    if malformed:
        r.warn(f"{len(malformed)} wiki_refs entr(y/ies) missing `.md` or the `Wiki/` prefix, "
               f"e.g. {malformed[0]}")
        details["malformed_refs"] = malformed
    if repeated:
        r.warn(f"{len(repeated)} Raw file(s) list the same page more than once in wiki_refs "
               f"(cosmetic), e.g. {repeated[0]}")
        details["repeated_refs"] = repeated
    if details:
        r.data.setdefault("details", {}).update(details)
    r.ok(f"wiki_refs: {consistent}/{listed} entries reciprocated")


def check_stamps(r: Report, b: Bundle, since: str | None) -> None:
    now = dt.datetime.now(dt.timezone.utc)
    stamped = 0
    for p in V.pages(b.path):
        fm, _ = V.frontmatter(p)
        if fm is None:
            continue
        rel = p.relative_to(b.path)
        updated = V.fm_value(fm, "updated")
        gen = re.search(r'generated:\s*\{[^}]*at:\s*"?([0-9T:\-Z]+)"?', fm)
        if since and updated and updated >= since and not gen:
            r.fail(f"missing `generated` stamp on a page updated since {since}: {rel}")
        if not gen:
            continue
        stamped += 1
        try:
            at = dt.datetime.strptime(gen.group(1), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
        except ValueError:
            r.fail(f"unparseable generated timestamp: {rel}")
            continue
        mtime = dt.datetime.fromtimestamp(p.stat().st_mtime, dt.timezone.utc)
        if at > now + dt.timedelta(minutes=1):
            r.fail(f"generated stamp is in the future: {rel} ({gen.group(1)})")
        elif at > mtime + dt.timedelta(hours=1):
            r.warn(f"generated stamp is well after the file mtime (guessed?): {rel}")
    r.ok(f"{stamped} pages carry a generated stamp")


def check_learning_path(r: Report, b: Bundle) -> None:
    lp = b.path / "Learning Path"
    if not lp.is_dir():
        return
    for p in sorted(lp.glob("*.md")):
        if p.name == "README.md":
            continue
        text = V.read(p)
        populated = "_None yet._" not in text
        if populated and "> SKELETON" in text:
            r.fail(f"stage is populated but still marked SKELETON: {p.name}")
        if populated and "Populated with" not in text:
            r.fail(f"stage is populated but has no `> Populated with N ...` line: {p.name}")
        m = re.search(r"> Populated with (\d+) (?:sources?|summar(?:y|ies))", text)
        if m:
            links = len(set(re.findall(r"\]\(\.\./Wiki/(?:summaries|papers)/[^)]+\)", text)))
            if links < int(m.group(1)):
                r.warn(f"{p.name}: claims {m.group(1)} but links {links} summary/paper pages. "
                       f"Fine if sources were folded into one summary; do not pad the list.")
    r.ok("Learning Path markers checked")


def check_index(r: Report, b: Bundle) -> None:
    idx = b.path / "Wiki" / "index.md"
    if not idx.exists():
        r.fail("Wiki/index.md is missing")
        return
    text = V.read(idx)
    orphans = 0
    for p in (b.path / "Wiki").rglob("*.md"):
        if p.name in ("index.md", "log.md", "overview.md"):
            continue
        if p.stem not in text and urllib.parse.quote(p.stem) not in text:
            orphans += 1
            r.fail(f"page not listed in Wiki/index.md: {p.relative_to(b.path)}")
    r.ok(f"index coverage checked, {orphans} orphan(s)")


def check_log(r: Report, b: Bundle) -> None:
    log = b.path / "Wiki" / "log.md"
    if not log.exists():
        r.fail("Wiki/log.md is missing")
        return
    fm, body = V.frontmatter(log)
    if fm is not None:
        r.fail("Wiki/log.md must be frontmatter-free (OKF reserved file)")
    dates = re.findall(r"^## (\d{4}-\d{2}-\d{2})\s*$", body, re.M)
    if dates != sorted(dates, reverse=True):
        r.fail("Wiki/log.md date headings are not newest-first")
    if len(dates) != len(set(dates)):
        r.fail("Wiki/log.md has duplicate date headings; merge them")
    r.ok(f"log.md: {len(dates)} date headings")


def run(b: Bundle, cfg: Config, since: str | None, validator: Path | None = None) -> Report:
    r = Report("check", b.name)
    if not b.path.is_dir():
        r.fail(f"bundle path does not exist: {b.path}")
        return r
    check_validator(r, b, cfg, validator)
    check_links(r, b)
    check_wiki_refs(r, b)
    check_stamps(r, b, since)
    check_learning_path(r, b)
    check_index(r, b)
    check_log(r, b)
    return r
