"""Reading bundles: frontmatter, pages, Raw sources, links, and exact citation matching."""
from __future__ import annotations

import os
import re
import urllib.parse
from pathlib import Path

import yaml

# Exact vault-relative paths that mention files without citing them: the catalog,
# the log, and the generated lint report. Matched by full path, not basename, so a
# nested `Wiki/topics/index.md` is still an ordinary page.
RESERVED_PATHS = {"Wiki/index.md", "Wiki/log.md", "Wiki/lint-report.md"}


class VaultError(ValueError):
    """A file kb cannot read faithfully: invalid UTF-8 or invalid YAML frontmatter."""


class RefsError(VaultError):
    """wiki_refs is present but not a list of strings."""


def is_reserved(rel: str) -> bool:
    return rel in RESERVED_PATHS


def read(path: Path) -> str:
    """File text. Undecodable bytes become U+FFFD; `undecodable()` reports such files."""
    return path.read_text(encoding="utf-8", errors="replace")


def undecodable(path: Path) -> bool:
    try:
        path.read_bytes().decode("utf-8")
        return False
    except UnicodeDecodeError:
        return True


def split_frontmatter(text: str) -> tuple[str | None, str]:
    """(frontmatter, body), or (None, text) when the file has no frontmatter block."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return None, text
    return "\n".join(lines[1:end]), "\n".join(lines[end + 1:])


def frontmatter(path: Path) -> tuple[str | None, str]:
    return split_frontmatter(read(path))


def fm_data(fm: str | None) -> dict:
    """Frontmatter parsed as YAML. Invalid YAML raises VaultError; never a silent guess."""
    if not fm:
        return {}
    try:
        data = yaml.safe_load(fm)
    except yaml.YAMLError as e:
        raise VaultError(f"frontmatter is not valid YAML: {str(e).splitlines()[0]}") from e
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise VaultError("frontmatter is not a YAML mapping")
    return data


def fm_value(fm: str | None, key: str) -> str:
    """A top-level string value from frontmatter ("" if absent). Non-strings raise VaultError."""
    v = fm_data(fm).get(key)
    if v is None:
        return ""
    if not isinstance(v, str):
        raise VaultError(f"frontmatter `{key}` must be a string, got {type(v).__name__}")
    return v.strip()


def norm_url(url: str) -> str:
    """Exact identity: trailing slash and http/https differences only.

    Deliberately conservative. A same-URL match under this rule is a duplicate;
    looser matches (tracking params, host moves) are reported separately.
    """
    u = url.strip().rstrip("/")
    if u.lower().startswith("http://"):
        u = "https://" + u[len("http://"):]
    return u


def wiki_refs(fm: str | None) -> list[str]:
    """The `wiki_refs` list, parsed as YAML. Absent or null is []; anything other
    than a list of strings raises RefsError."""
    data = fm_data(fm)
    if "wiki_refs" not in data or data["wiki_refs"] is None:
        return []
    refs = data["wiki_refs"]
    if not isinstance(refs, list):
        raise RefsError(f"wiki_refs must be a list, got {type(refs).__name__}: {refs!r}")
    bad = [r for r in refs if not isinstance(r, str)]
    if bad:
        raise RefsError(f"wiki_refs items must be strings, got {bad!r}")
    return [r.strip() for r in refs if r.strip()]


def raw_files(vault: Path) -> list[Path]:
    d = vault / "Raw"
    if not d.is_dir():
        return []
    return sorted(p for p in d.iterdir() if p.is_file() and p.suffix.lower() == ".md")


def pages(vault: Path, *, include_reserved: bool = False) -> list[Path]:
    """Wiki and Learning Path pages. Reserved paths are excluded unless asked."""
    out = []
    for sub in ("Wiki", "Learning Path"):
        d = vault / sub
        if d.is_dir():
            out.extend(sorted(p for p in d.rglob("*") if p.is_file() and p.suffix.lower() == ".md"))
    if not include_reserved:
        out = [p for p in out if not is_reserved(p.relative_to(vault).as_posix())]
    return out


def bundle_problems(vault: Path) -> list[str]:
    """Reasons a bundle cannot be checked at all. A missing folder must never read as clean."""
    if not vault.is_dir():
        return [f"bundle path does not exist: {vault}"]
    if not (vault / "Raw").is_dir():
        return [f"bundle has no Raw/ folder: {vault}"]
    return []


# ---------------------------------------------------------------- markdown text

_COMMENT = re.compile(r"<!--.*?(?:-->|\Z)", re.S)
_STRIKE = re.compile(r"~~(?=\S)(.+?)(?<=\S)~~", re.S)
_FENCE_OPEN = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_HIDDEN_OPEN = re.compile(
    r"<(script|style|template|noscript)\b[^>]*>"
    r"|<([a-zA-Z][a-zA-Z0-9-]*)\b[^>]*\b(?:hidden|aria-hidden=[\"']true[\"']"
    r"|style=[\"'][^\"']*(?:display\s*:\s*none|visibility\s*:\s*hidden)[^\"']*[\"'])[^>]*>", re.I)


def strip_fences(text: str) -> str:
    """Remove fenced code blocks: up to 3 spaces of indent, ``` or ~~~, closed by the same
    character at least as long. An unclosed fence runs to the end, as in CommonMark."""
    out, fence = [], None
    for line in text.splitlines(keepends=True):
        if fence is None:
            m = _FENCE_OPEN.match(line)
            if m:
                fence = m.group(1)
                continue
            out.append(line)
        else:
            if re.match(r"^ {0,3}" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}\s*$", line):
                fence = None
    return "".join(out)


def strip_hidden_html(text: str) -> str:
    """Remove hidden HTML subtrees (script/style/template/noscript, `hidden`,
    aria-hidden, display:none, visibility:hidden), counting nested same-name tags so
    text after an inner close tag is not leaked. An unclosed one runs to the end."""
    while True:
        m = _HIDDEN_OPEN.search(text)
        if not m:
            return text
        tag = (m.group(1) or m.group(2)).lower()
        depth, pos = 1, m.end()
        tok = re.compile(rf"<(/?){re.escape(tag)}\b[^>]*?(/?)>", re.I)
        end = len(text)
        for t in tok.finditer(text, pos):
            if t.group(1):
                depth -= 1
            elif not t.group(2):
                depth += 1
            if depth == 0:
                end = t.end()
                break
        text = text[:m.start()] + text[end:]


def citable_text(text: str) -> str:
    """Text where a citation can appear: HTML comments, fenced code (indented and
    unclosed fences too), hidden HTML and strikethrough removed. An example or a
    struck-out reference never counts as citing anything."""
    t = _COMMENT.sub("", text)
    t = strip_fences(t)
    t = strip_hidden_html(t)
    return _STRIKE.sub("", t)


_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
_DEST = r"(?:<([^<>\n]+)>|((?:[^\s()\\]|\\.|\((?:[^\s()\\]|\\.)*\))+))"
_TITLE = r"""(?:\s+(?:"[^"\n]*"|'[^'\n]*'|\([^()\n]*\)))?"""
_INLINE_LINK = re.compile(r"(?<!\\)!?\[(?:[^\[\]\\]|\\.)*\]\(\s*" + _DEST + _TITLE + r"\s*\)")
_REF_DEF = re.compile(r"^ {0,3}\[(?:[^\[\]\\]|\\.)+\]:\s*" + _DEST + _TITLE + r"\s*$", re.M)


def md_link_targets(text: str) -> list[str]:
    """Local link destinations (inline and reference definitions), decoded, with
    any #fragment or ?query removed. Code (fenced and inline), HTML comments and
    escaped brackets are skipped; any URL scheme (http, HTTPS, mailto, ...) is external."""
    t = citable_text(text)
    t = re.sub(r"`[^`\n]*`", "", t)  # links inside inline code are examples
    out = []
    for rx in (_INLINE_LINK, _REF_DEF):
        for m in rx.finditer(t):
            dest = m.group(1) or m.group(2) or ""
            dest = re.sub(r"\\(.)", r"\1", dest)
            if not dest or dest.startswith("#") or _SCHEME.match(dest):
                continue
            dest = re.split(r"[#?]", dest, maxsplit=1)[0]
            if dest:
                out.append(urllib.parse.unquote(dest))
    return out


# ---------------------------------------------------------------- citations

def _names(filename: str) -> str:
    names = {filename, urllib.parse.quote(filename)}
    return "|".join(re.escape(n) for n in sorted(names))


def mention_regex(filename: str) -> re.Pattern:
    """Any mention of exactly this filename, citation or not (for `kb citers`).

    Exact, not substring: `foo.md` is a substring of `x-foo.md` and of the hashed
    duplicate `foo-0041df.md`. A sentence-ending period is fine; `foo.md.bak` is not.
    """
    return re.compile(rf"(?<![\w-])(?:{_names(filename)})(?![\w-]|\.\w)")


def cite_regex(filename: str) -> re.Pattern:
    """Line-level hint used only to label lines in `kb citers` output. Whether a page
    cites a file is decided by `cited_raw_files()`, which resolves targets."""
    n = _names(filename)
    return re.compile(
        rf"(?:resource:[ \t]*[\"']?(?:[^\s\"']*/)?Raw/(?:{n})[\"']?[ \t]*$"
        rf"|\]\(<?(?:[^)>\n]*/)?Raw/(?:{n})(?:[#?][^)>\n]*)?>?(?:\s+[\"'(][^\n)]*)?\)"
        rf"|\[source:[ \t]*(?:{n})\])", re.M)


_SOURCE_MARKER = re.compile(r"\[source:[ \t]*([^\]\n]+?\.md)[ \t]*\]", re.I)


def cited_raw_files(vault: Path, page: Path, text: str | None = None) -> set[str]:
    """Names of this vault's Raw files that a page cites.

    A citation is a target that resolves, from the page's own folder, to a file
    directly in THIS vault's Raw/: a frontmatter `sources[].resource` (parsed as YAML)
    or a markdown link in live text. The `[source: <file>.md]` marker also counts,
    including inside inline code, which is how catalog pages write it. Nothing inside
    comments, fenced code, hidden HTML or strikethrough counts, nor does a bare mention
    or a link into another vault. Measured on the live corpus (2026-10-04): identical
    results to the earlier pattern-based rule, with the false positives removed.
    """
    text = read(page) if text is None else text
    raw_dir = (vault / "Raw").resolve()
    fm, body = split_frontmatter(text)
    targets = []
    try:
        for s in fm_data(fm).get("sources") or []:
            if isinstance(s, dict) and isinstance(s.get("resource"), str):
                targets.append(s["resource"])
            elif isinstance(s, str):
                targets.append(s)
    except VaultError:
        pass  # check_readable reports it
    targets += md_link_targets(body)
    out = set()
    for t in targets:
        q = Path(os.path.normpath(page.parent / urllib.parse.unquote(t)))
        if q.parent.resolve() == raw_dir:
            out.add(q.name)
    out |= {m.strip() for m in _SOURCE_MARKER.findall(citable_text(body))}
    return out


def citing_lines(filename: str, page_list: list[Path], vault: Path) -> list[tuple[str, int, str, bool]]:
    """(page, line number, text, is_citation) for every line that mentions the file.
    A line counts as a citation only if its page truly cites the file
    (`cited_raw_files`) and the line carries a citation form."""
    hint, mention = cite_regex(filename), mention_regex(filename)
    hits = []
    for p in page_list:
        text = read(p)
        page_cites = filename in cited_raw_files(vault, p, text)
        for i, line in enumerate(text.splitlines(), 1):
            if mention.search(line):
                hits.append((p.relative_to(vault).as_posix(), i, line.strip(),
                             page_cites and bool(hint.search(line))))
    return hits


def word_count(path: Path) -> int:
    return len(split_frontmatter(read(path))[1].split())
