"""`kb quotes`: every quotation on a page must appear verbatim in its sources.

Permitted evidence is the page's own `sources` frontmatter (each `resource:`,
resolved relative to the page), unless --source overrides it. Only the visible
body of each source counts: its frontmatter, HTML tags and attributes, and image
alt text are removed. Each source is searched on its own, never concatenated.

Checked spans: straight "..." and curly “...” quotations in prose, and blockquotes
(up to three leading spaces; status callouts such as "> Partial." are skipped).

Results per quotation:
- verified  every fragment found, in order, inside one source, on word boundaries,
            after removing only real markdown syntax (emphasis, links, escapes);
- DRIFT     found only after folding case, apostrophes, quote marks, dashes, or
            trailing punctuation. Quote character for character, or paraphrase;
- MISSING   not in any permitted source.

It fails closed: a paragraph whose quote marks do not pair is a failure, not a
skipped check. What it cannot catch: an invented paraphrase. Unquoted sentences
need the independent review.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from . import vault as V
from .report import Report

STATUS_WORDS = ("partial", "stub", "skeleton", "populated", "note", "editorial",
                "todo", "warning", "recorded", "pending")
# A status callout is the word followed by "." or ":" ("> Partial.", "> **Note:**"),
# or the word in capitals ("> STUB created at bootstrap"). "> Note this is true" is a
# quotation like any other and gets checked.
_STATUS = re.compile(rf"^(?:(?i:{'|'.join(STATUS_WORDS)})\s*[.:]|(?:{'|'.join(w.upper() for w in STATUS_WORDS)})\b)")
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_TAG = re.compile(r"<[^>\n]+>")
_AUTOLINK = re.compile(r"<((?:https?|mailto):[^>\s]+)>")
_HIDDEN = re.compile(r"<!--.*?-->|<(script|style|template|noscript)\b[^>]*>.*?</\1\s*>"
                     r"|<(\w+)\b[^>]*\b(?:hidden|aria-hidden=[\"']true[\"'])[^>]*>.*?</\2\s*>",
                     re.S | re.I)
_PROTECT = "\ue000"  # private-use marker: keeps an escaped character away from emphasis parsing
_ESCAPE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!|~>])")
# \ue000 marks an escaped character (see _PROTECT): it can never open or close emphasis.
_STRONG = re.compile("(?<!\ue000)(\\*\\*|__)(?=\\S)(.+?)(?<=[^\\s\ue000])\\1")
_EM = re.compile("(?<![\\w*\ue000])([*_])(?=\\S)(.+?)(?<=[^\\s\ue000])\\1(?![\\w*])")
_ELLIPSIS = re.compile(r"\s*(?:\[\.\.\.\]|\[…\]|\.\.\.|…)\s*")
_FOLD = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-", "‑": "-"})
_BLOCKQUOTE = re.compile(r"^ {0,3}>")
MIN_WORD_CHARS = 3  # per fragment: fewer word characters cannot be verified meaningfully
_INCH = re.compile(r'(?<=\d)"')  # 5" or 30": a measurement mark, not a quotation mark


def visible(text: str) -> str:
    """Markdown/HTML reduced to the text a reader sees. Literal characters are kept.

    Escaped characters are protected before emphasis is parsed, so `\\*danger\\*`
    stays "*danger*". Hidden HTML (comments, script/style, `hidden` elements) is
    dropped with its content; autolinks keep their URL.
    """
    t = _ESCAPE.sub(lambda m: _PROTECT + m.group(1), text)
    t = _HIDDEN.sub("", t)
    t = _IMAGE.sub("", t)
    t = _LINK.sub(lambda m: m.group(1), t)
    t = _AUTOLINK.sub(lambda m: m.group(1), t)
    t = _TAG.sub("", t)
    for _ in range(2):  # nested emphasis
        t = _STRONG.sub(lambda m: m.group(2), t)
        t = _EM.sub(lambda m: m.group(2), t)
    t = t.replace(_PROTECT, "")
    return re.sub(r"\s+", " ", t).strip()


def _fold(t: str) -> str:
    return re.sub(r"\s+", " ", t.translate(_FOLD).lower()).strip()


def _bounded(fragment: str) -> re.Pattern:
    """The fragment, never glued to a longer word on either side.

    `dependent` must not match `dependents`, and a fragment ending in punctuation
    must not match mid-token either: "uses C++" is not in "uses C++17".
    """
    return re.compile(r"(?<!\w)" + re.escape(fragment) + r"(?!\w)")


def _in_order(fragments: list[str], hay: str) -> bool:
    pos = 0
    for f in fragments:
        m = _bounded(f).search(hay, pos)
        if not m:
            return False
        pos = m.end()
    return True


def page_sources(page: Path) -> list[Path]:
    fm, _ = V.frontmatter(page)
    if not fm:
        return []
    block = re.search(r"^sources:(.*?)(?=^\S)", fm + "\nend:", re.M | re.S)
    if not block:
        return []
    vals = re.findall(r"resource:\s*(.+)", block.group(1))
    if not vals:  # legacy list form: sources: [a.md, b.md] or "- a.md" items
        vals = re.findall(r"([^\s\[\],'\"]+\.md)", block.group(1))
    out = []
    for v in vals:
        p = (page.parent / v.strip().strip('"').strip("'")).resolve()
        if p not in out:
            out.append(p)
    return out


@dataclass
class Quote:
    text: str
    line: int
    kind: str  # "inline" | "blockquote"


def extract(body: str, line_offset: int = 0) -> tuple[list[Quote], list[str]]:
    """Quotations in a page body, plus failures for paragraphs whose quote marks do not pair."""
    clean, in_fence = [], False
    for ln in body.splitlines():
        if ln.lstrip().startswith("```"):
            in_fence = not in_fence
            clean.append("")
            continue
        ln = "" if in_fence else re.sub(r"`[^`]*`", "", ln)
        ln = _AUTOLINK.sub(lambda m: m.group(1), ln)
        clean.append(_INCH.sub("″", _TAG.sub("", ln)))

    quotes, problems, prose = [], [], []
    i = 0
    while i < len(clean):  # blockquotes are checked whole, then removed from prose
        if _BLOCKQUOTE.match(clean[i]):
            start, buf = i, []
            while i < len(clean) and _BLOCKQUOTE.match(clean[i]):
                buf.append(re.sub(r"^ {0,3}(?:>\s?)+", "", clean[i]).strip())
                prose.append("")
                i += 1
            text = " ".join(b for b in buf if b)
            head = re.sub(r"^[*_\s]+", "", text)
            if text and not _STATUS.match(head):
                quotes.append(Quote(text, start + 1 + line_offset, "blockquote"))
            continue
        prose.append(clean[i])
        i += 1

    para, para_start = [], 0
    for n, ln in enumerate(prose + [""]):
        if ln.strip():
            if not para:
                para_start = n
            para.append(ln)
            continue
        if para:
            plain = [_IMAGE.sub("", _LINK.sub(lambda m: m.group(1), x)) for x in para]
            flat = " ".join(plain)
            first = para_start + 1 + line_offset

            def where(q: str) -> int:
                head = " ".join(q.split()[:4])
                for k, x in enumerate(plain):
                    if head in " ".join(x.split()):
                        return first + k
                return first

            if flat.count('"') % 2:
                problems.append(f"line {first}: straight quote marks in this paragraph do not pair; "
                                f"its quotations could not be checked")
            else:
                quotes += [Quote(q, where(q), "inline") for q in re.findall(r'"([^"]+)"', flat)]
            if flat.count("“") != flat.count("”"):
                problems.append(f"line {first}: curly quote marks in this paragraph do not pair; "
                                f"its curly quotations could not be checked")
            else:
                quotes += [Quote(q, where(q), "inline") for q in re.findall(r"“([^”]+)”", flat)]
            para = []
    return quotes, problems


def classify(quote: str, sources: list[tuple[str, str]]) -> str:
    """verified | drift | missing | short, against [(visible_text, folded_text)] per source."""
    frags = [f for f in (visible(x) for x in _ELLIPSIS.split(quote)) if f]
    if not frags or any(len(re.findall(r"\w", f)) < MIN_WORD_CHARS for f in frags):
        return "short"
    if any(_in_order(frags, exact) for exact, _ in sources):
        return "verified"
    folded = [_fold(f).strip(" .,;:!?") for f in frags]
    folded = [f for f in folded if f]
    if folded and any(_in_order(folded, fold) for _, fold in sources):
        return "drift"
    return "missing"


def run(page: Path, sources: list[Path] | None, ignore: list[str]) -> Report:
    r = Report("quotes", str(page))
    r.footer = False
    srcs = sources if sources else page_sources(page)
    if not srcs:
        r.fail("no permitted sources: the page declares no `sources` resources; pass --source")
        return r
    for s in srcs:
        if not s.exists():
            r.fail(f"declared source does not exist: {s}")
    texts = []
    for s in srcs:
        if s.exists():
            body = visible(V.split_frontmatter(V.read(s))[1])
            texts.append((body, _fold(body)))

    fm, body = V.split_frontmatter(V.read(page))
    offset = (len(fm.splitlines()) + 2) if fm is not None else 0
    quotes, problems = extract(body, offset)
    for p in problems:
        r.fail(p)
    counts = {"verified": 0, "drift": 0, "missing": 0, "short": 0, "ignored": 0}
    rows = []
    for q in quotes:
        if any(ig in q.text for ig in ignore):
            counts["ignored"] += 1
            continue
        verdict = classify(q.text, texts)
        counts[verdict] += 1
        rows.append({"line": q.line, "kind": q.kind, "verdict": verdict, "quote": q.text})
        if verdict == "drift":
            r.fail(f"line {q.line}: DRIFT (case/punctuation differs from source): \"{q.text[:140]}\"")
        elif verdict == "missing":
            r.fail(f"line {q.line}: MISSING from permitted sources: \"{q.text[:140]}\"")
        elif verdict == "short":
            r.fail(f"line {q.line}: too short to verify (a fragment under {MIN_WORD_CHARS} word "
                   f"characters): \"{q.text}\". Quote more of the source, or paraphrase.")
    r.ok(f"{len(quotes)} quotation(s) against {len(texts)} source(s): "
         f"{counts['verified']} verified, {counts['drift']} drift, {counts['missing']} missing"
         + (f", {counts['short']} too short" if counts["short"] else "")
         + (f", {counts['ignored']} ignored" if counts["ignored"] else ""))
    r.data.update({"sources": [str(s) for s in srcs], "counts": counts, "quotes": rows})
    return r
