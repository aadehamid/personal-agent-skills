"""Reading bundles: frontmatter, pages, Raw sources, and exact citation matching."""
from __future__ import annotations

import re
import urllib.parse
from pathlib import Path

# Exact vault-relative paths that mention files without citing them: the catalog,
# the log, and the generated lint report. Matched by full path, not basename, so a
# nested `Wiki/topics/index.md` is still an ordinary page.
RESERVED_PATHS = {"Wiki/index.md", "Wiki/log.md", "Wiki/lint-report.md"}


def is_reserved(rel: str) -> bool:
    return rel in RESERVED_PATHS


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


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


def fm_value(fm: str | None, key: str) -> str:
    """A top-level scalar from frontmatter, with YAML quotes stripped."""
    if not fm:
        return ""
    m = re.search(rf"^{re.escape(key)}:[ \t]*(.*)$", fm, re.M)
    return m.group(1).strip().strip('"').strip("'") if m else ""


def norm_url(url: str) -> str:
    """Exact identity: quotes, trailing slash and http/https differences only.

    Deliberately conservative. A same-URL match under this rule is a duplicate;
    looser matches (tracking params, host moves) are reported separately.
    """
    u = url.strip().strip('"').strip("'").rstrip("/")
    if u.startswith("http://"):
        u = "https://" + u[len("http://"):]
    return u


class RefsError(ValueError):
    """wiki_refs is present but not a list of strings."""


def _unquote(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return re.sub(r"\s+#.*$", "", v).strip()  # unquoted values may carry a trailing comment


_FLOW_ITEM = re.compile(r"""\s*(?:"((?:[^"\\]|\\.)*)"|'((?:[^']|'')*)'|([^,]+?))\s*(?:,|$)""")


def _flow_list(inner: str) -> list[str]:
    """Items of a YAML flow sequence, respecting quotes: ["A, B.md", c.md] is two items."""
    out, pos = [], 0
    inner = inner.strip()
    while pos < len(inner):
        m = _FLOW_ITEM.match(inner, pos)
        if not m or m.end() == pos:
            raise RefsError(f"cannot parse wiki_refs list: [{inner}]")
        dq, sq, bare = m.groups()
        val = dq if dq is not None else (sq.replace("''", "'") if sq is not None else bare.strip())
        if val:
            out.append(val)
        pos = m.end()
    return out


def wiki_refs(fm: str | None) -> list[str]:
    """The `wiki_refs` list: block form (`- item`) or flow form (`[a, "b, c.md"]`).

    Page names contain spaces, so block items run to end of line, and a trailing
    ` # comment` on an unquoted item is not part of the name. A scalar value
    (`wiki_refs: Wiki/a.md`) is the wrong type and raises RefsError.
    """
    if not fm:
        return []
    m = re.search(r"^wiki_refs:[ \t]*(.*)$", fm, re.M)
    if not m:
        return []
    inline = m.group(1).strip()
    if inline.startswith("["):
        body = re.sub(r"\]\s*(?:#.*)?$", "", inline[1:])
        return _flow_list(body)
    if re.sub(r"\s*#.*$", "", inline):
        raise RefsError(f"wiki_refs must be a list, got a scalar: {inline!r}")
    items = []
    for ln in fm[m.end():].lstrip("\n").splitlines():
        if not re.match(r"^[ \t]+-", ln):
            break
        items.append(_unquote(re.sub(r"^\s*-\s*", "", ln)))
    return [i for i in items if i]


def raw_files(vault: Path) -> list[Path]:
    d = vault / "Raw"
    if not d.is_dir():
        return []
    return sorted(p for p in d.iterdir() if p.is_file() and p.suffix.lower() == ".md")


def pages(vault: Path, *, include_reserved: bool = False) -> list[Path]:
    """Wiki and Learning Path pages. index.md and log.md are excluded unless asked."""
    out = []
    for sub in ("Wiki", "Learning Path"):
        d = vault / sub
        if d.is_dir():
            out.extend(sorted(d.rglob("*.md")))
    if not include_reserved:
        out = [p for p in out if not is_reserved(p.relative_to(vault).as_posix())]
    return out


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
    """A citation of exactly this filename, in one of the forms pages actually use.

    A bare mention in prose (`cp foo.md /tmp`, "the old foo.md") is not a citation.
    Accepted forms: a frontmatter `resource:` value, a markdown link target
    (anchors and `<...>` destinations included), the `[source: foo.md]` marker,
    and a `Raw/foo.md` path. Measured on the live corpus (2026-10-04): 883 of 884
    cited sources use one of these; the exception was a "See also" prose mention.
    """
    n = _names(filename)
    return re.compile(
        rf"(?:resource:[ \t]*[\"']?(?:[^\s\"']*/)?(?:{n})[\"']?[ \t]*$"
        rf"|\]\(<?(?:[^)>\n]*/)?(?:{n})(?:[#?][^)>\n]*)?>?(?:\s+\"[^\"]*\")?\)"
        rf"|\[source:[ \t]*(?:{n})\]"
        rf"|(?<![\w-])Raw/(?:{n})(?![\w-]|\.\w))", re.M)


def citing_lines(filename: str, page_list: list[Path], vault: Path) -> list[tuple[str, int, str, bool]]:
    """(page, line number, text, is_citation) for every line that mentions the file."""
    cite, mention = cite_regex(filename), mention_regex(filename)
    hits = []
    for p in page_list:
        for i, line in enumerate(read(p).splitlines(), 1):
            if mention.search(line):
                hits.append((p.relative_to(vault).as_posix(), i, line.strip(), bool(cite.search(line))))
    return hits


def word_count(path: Path) -> int:
    return len(split_frontmatter(read(path))[1].split())
