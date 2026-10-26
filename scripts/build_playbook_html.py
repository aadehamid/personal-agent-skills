#!/usr/bin/env python3
"""Build the HTML versions of the two playbooks from their Markdown.

Run from the repository root:
  python3 scripts/build_playbook_html.py            write every page
  python3 scripts/build_playbook_html.py --check    exit 1 when a committed page differs from a fresh build

The Markdown is the master copy; each HTML page is generated from it through playbook_template.html (the
one file to edit for the page's look) and is never edited by hand. scripts/test_playbook_html.py drives
main(["--check"]), so a Markdown change that is not rebuilt fails scripts/check.sh. Standard library only.

The renderer covers the Markdown these files use: ATX headings, paragraphs, thematic breaks (dropped),
fenced code (also inside list items), tables, nested ordered and unordered lists, `code`, **bold**,
*italic*, [links](...) and bare https URLs. A backticked `diagrams/<name>.png` in a paragraph puts that
picture, embedded as a data URI, right after the paragraph. Anything else it can recognise (a blockquote,
a Setext heading, an image, inline HTML or an autolink, a reference-style link definition) stops the
build with the file and line, rather than turning into a plain paragraph. An indented code block outside
a list is not detected: these files indent only list content.
"""
import base64
import html
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "scripts", "playbook_template.html")

# Each page: its output, its title, one sentence on what it is, and its sources in reading order.
PAGES = [
    {
        "out": "skills/data/ontology/references/playbook.html",
        "title": "Ontology playbook",
        "scope": "The ontology skill's guide",
        "lead": "The method for building a business ontology on the W3C stack: the gated steps, the policies "
                "behind them, the standards each one uses and a worked example.",
        "sources": ["skills/data/ontology/references/playbook.md"],
    },
    {
        "out": "skills/data/ontology-to-lpg/references/playbook.html",
        "title": "Ontology-to-LPG projection playbook",
        "scope": "The ontology-to-lpg skill, version 2.3",
        "lead": "How to project an ontology built on the W3C stack into a Neo4j labelled property graph, check "
                "it, and run it with every store: the design rules, the inputs, the pipeline, running it in a "
                "repository, the add-ons and the stores.",
        "sources": [
            "skills/data/ontology-to-lpg/README.md",
            "skills/data/ontology-to-lpg/references/design-rules.md",
            "skills/data/ontology-to-lpg/references/inputs.md",
            "skills/data/ontology-to-lpg/references/pipeline.md",
            "skills/data/ontology-to-lpg/references/running.md",
            "skills/data/ontology-to-lpg/references/run-config.md",
            "skills/data/ontology-to-lpg/references/add-ons.md",
            "skills/data/ontology-to-lpg/references/multi-store.md",
            "skills/data/ontology-to-lpg/references/versions.md",
            "skills/data/ontology-to-lpg/references/learning-path.md",
        ],
    },
]

LIST_ITEM = re.compile(r"^( *)([-*]|\d+\.) (.*)$")
FENCE = re.compile(r"^( *)```(\S*)\s*$")
HEADING = re.compile(r"^(#{1,6}) (.+?)\s*#*\s*$")


UNSUPPORTED = [
    ("a blockquote", re.compile(r"^ {0,3}>")),
    ("a Setext heading underline", re.compile(r"^ {0,3}=+\s*$")),
    ("a reference-style link definition", re.compile(r"^ {0,3}\[[^\]]+\]:\s")),
    ("an image", re.compile(r"!\[")),
    ("inline HTML or an autolink", re.compile(r"<[A-Za-z/!][^>]*>")),
]


def unsupported(lines):
    """(line number, kind) for each construct the renderer does not handle, outside fenced code. Inline
    patterns are matched with code spans removed. A '---' right under a text line is a Setext heading."""
    found, fence, prev = [], False, ""
    for n, line in enumerate(lines, 1):
        if FENCE.match(line):
            fence = not fence
            prev = ""
            continue
        if fence:
            continue
        bare = re.sub(r"`[^`]*`", "", line)
        for kind, pattern in UNSUPPORTED:
            if pattern.search(bare if kind in ("an image", "inline HTML or an autolink") else line):
                found.append((n, kind))
        if (re.fullmatch(r" {0,3}-+\s*", line) and prev.strip() and not HEADING.match(prev)
                and not LIST_ITEM.match(prev) and not prev.lstrip().startswith("|")):
            found.append((n, "a Setext heading underline"))
        prev = line
    return found


def slug(text):
    """A heading's anchor: lower case, words joined by hyphens, punctuation dropped."""
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text).lower()
    text = re.sub(r"[`*_]", "", text)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "section"


class Page:
    """Renders the sources of one page; knows every source's anchor prefix and headings."""

    def __init__(self, spec):
        self.spec = spec
        self.out_dir = os.path.dirname(os.path.join(ROOT, spec["out"]))
        self.prefix = {}
        for src in spec["sources"]:
            name = os.path.splitext(os.path.basename(src))[0].lower()
            self.prefix[os.path.normpath(os.path.join(ROOT, src))] = "" if len(spec["sources"]) == 1 else name
        self.toc = []
        self.used = set()

    # ---- anchors and links

    def anchor(self, src, text):
        base = slug(text)
        pre = self.prefix[src]
        a = f"{pre}--{base}" if pre else base
        n, cand = 2, a
        while cand in self.used:
            cand, n = f"{a}-{n}", n + 1
        self.used.add(cand)
        return cand

    def link(self, src, url):
        """A relative .md link to a source on this page becomes its anchor; any other relative link is
        rewritten relative to the page; absolute URLs and anchors stay."""
        if re.match(r"^[a-z]+:", url) or url.startswith("#"):
            if url.startswith("#") and self.prefix[src]:
                return f"#{self.prefix[src]}--{url[1:]}"
            return url
        path, _, frag = url.partition("#")
        target = os.path.normpath(os.path.join(os.path.dirname(src), path))
        if target in self.prefix:
            pre = self.prefix[target]
            if frag:
                return f"#{pre}--{frag}" if pre else f"#{frag}"
            return f"#{pre}" if pre else "#top"
        rel = os.path.relpath(target, self.out_dir)
        return rel + (f"#{frag}" if frag else "")

    # ---- inline

    def inline(self, src, text):
        # Code spans become placeholders first, so bold, italics and links may hold code.
        codes = []

        def keep(m):
            codes.append(f"<code>{html.escape(m.group(1), quote=False)}</code>")
            return f"\x00{len(codes) - 1}\x00"
        s = re.sub(r"`([^`]*)`", keep, text)
        s = html.escape(s, quote=False)

        def a(m):
            url = re.sub(r"\x00(\d+)\x00", lambda c: re.sub(r"<[^>]+>", "", codes[int(c.group(1))]), m.group(2))
            return f'<a href="{html.escape(self.link(src, html.unescape(url)))}">{m.group(1)}</a>'
        s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", a, s)
        s = re.sub(r'(?<![="\w/>])(https?://[^\s<)\x00]*[^\s<).,;:\x00])',
                   lambda m: f'<a href="{m.group(1)}">{m.group(1)}</a>', s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
        return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], s)

    # ---- blocks

    def blocks(self, src, lines, depth=0):
        out, i = [], 0
        while i < len(lines):
            line = lines[i]
            if not line.strip() or re.fullmatch(r" {0,3}(-{3,}|\*{3,})\s*", line):
                # A thematic break adds nothing the next heading does not already show.
                i += 1
                continue
            m = FENCE.match(line)
            if m:
                indent, lang = len(m.group(1)), m.group(2)
                body, i = [], i + 1
                while i < len(lines) and not FENCE.match(lines[i]):
                    body.append(lines[i][indent:] if lines[i][:indent].strip() == "" else lines[i])
                    i += 1
                i += 1
                cls = f' class="lang-{html.escape(lang)}"' if lang else ""
                out.append(f"<pre><code{cls}>{html.escape(chr(10).join(body), quote=False)}</code></pre>")
                continue
            m = HEADING.match(line)
            if m and depth == 0:
                level, text = len(m.group(1)), m.group(2)
                aid = self.anchor(src, text)
                level_out = min(level + (1 if self.prefix[src] else 0), 6)
                if level_out <= 3:
                    self.toc.append((level_out, aid, text))
                out.append(f'<h{level_out} id="{aid}">{self.inline(src, text)}'
                           f'<a class="hl" href="#{aid}" aria-label="Link to this section">#</a></h{level_out}>')
                i += 1
                continue
            if line.lstrip().startswith("|"):
                rows = []
                while i < len(lines) and lines[i].lstrip().startswith("|"):
                    rows.append(lines[i].strip())
                    i += 1
                out.append(self.table(src, rows))
                continue
            if LIST_ITEM.match(line):
                html_list, i = self.list_block(src, lines, i, depth)
                out.append(html_list)
                continue
            para = [line.strip()]
            i += 1
            while (i < len(lines) and lines[i].strip() and not FENCE.match(lines[i])
                   and not HEADING.match(lines[i]) and not lines[i].lstrip().startswith("|")
                   and not LIST_ITEM.match(lines[i])):
                para.append(lines[i].strip())
                i += 1
            text = " ".join(para)
            out.append(f"<p>{self.inline(src, text)}</p>")
            for pic in re.findall(r"`(diagrams/[\w.-]+\.png)`", text):
                out.append(self.figure(src, pic))
        return "\n".join(out)

    def figure(self, src, rel):
        path = os.path.join(os.path.dirname(src), rel)
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode("ascii")
        name = os.path.splitext(os.path.basename(rel))[0].replace("-", " ")
        return (f'<figure class="pic"><img src="data:image/png;base64,{data}" alt="The {name} diagram" '
                f'loading="lazy"><figcaption>The {name} diagram ({html.escape(rel)}).</figcaption></figure>')

    def table(self, src, rows):
        def cells(row):
            row = row.strip()
            if row.startswith("|"):
                row = row[1:]
            if row.endswith("|"):
                row = row[:-1]
            parts, cur, code = [], "", False
            for ch in row:
                if ch == "`":
                    code = not code
                if ch == "|" and not code:
                    parts.append(cur)
                    cur = ""
                else:
                    cur += ch
            parts.append(cur)
            return [p.strip() for p in parts]
        head = cells(rows[0])
        body = [cells(r) for r in rows[2:]] if len(rows) > 1 and re.match(r"^\|?[\s:|-]+\|?$", rows[1]) else \
            [cells(r) for r in rows[1:]]
        # A column whose every body cell is a figure is right-aligned (tabular figures come from the CSS).
        numeric = [bool(body) and all(re.fullmatch(r"[-+]?[\d.,]+%?", (r[k] if k < len(r) else "").strip())
                                      for r in body) for k in range(len(head))]
        cls = lambda k: ' class="num"' if k < len(numeric) and numeric[k] else ""
        th = "".join(f"<th{cls(k)}>{self.inline(src, c)}</th>" for k, c in enumerate(head))
        trs = "".join("<tr>" + "".join(f"<td{cls(k)}>{self.inline(src, c)}</td>" for k, c in enumerate(r)) + "</tr>"
                      for r in body)
        return f'<div class="tblwrap"><table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div>'

    def list_block(self, src, lines, i, depth):
        m = LIST_ITEM.match(lines[i])
        base = len(m.group(1))
        ordered = m.group(2)[0].isdigit()
        start = int(m.group(2)[:-1]) if ordered else 1
        items = []
        while i < len(lines):
            m = LIST_ITEM.match(lines[i])
            if not m or len(m.group(1)) != base or m.group(2)[0].isdigit() != ordered:
                break
            content_col = base + len(m.group(2)) + 1
            body = [m.group(3)]
            i += 1
            while i < len(lines):
                ln = lines[i]
                if not ln.strip():
                    nxt = next((x for x in lines[i + 1:] if x.strip()), None)
                    if nxt is not None and len(nxt) - len(nxt.lstrip()) > base:
                        body.append("")
                        i += 1
                        continue
                    break
                ind = len(ln) - len(ln.lstrip())
                if ind <= base and (LIST_ITEM.match(ln) or HEADING.match(ln) or ln.lstrip().startswith("|")):
                    break
                if ind <= base and not body[-1].strip():
                    break
                cut = min(ind, content_col)
                body.append(ln[cut:])
                i += 1
            items.append(body)
        lis = []
        for body in items:
            first, rest = [], []
            for k, ln in enumerate(body):
                if k == 0 or (not rest and ln.strip() and not LIST_ITEM.match(ln) and not FENCE.match(ln)
                              and not ln.startswith(" ")):
                    first.append(ln.strip())
                else:
                    rest = body[k:]
                    break
            inner = self.inline(src, " ".join(first))
            if rest:
                inner += "\n" + self.blocks(src, rest, depth + 1)
            lis.append(f"<li>{inner}</li>")
        tag = "ol" if ordered else "ul"
        attr = f' start="{start}"' if ordered and start != 1 else ""
        return f"<{tag}{attr}>{''.join(lis)}</{tag}>", i

    # ---- the page

    def render(self):
        sections = []
        for src_rel in self.spec["sources"]:
            src = os.path.normpath(os.path.join(ROOT, src_rel))
            with open(src, encoding="utf-8") as f:
                lines = f.read().split("\n")
            bad = unsupported(lines)
            if bad:
                raise ValueError("; ".join(f"{src_rel}:{n}: {kind} is not supported" for n, kind in bad))
            pre = self.prefix[src]
            if pre:
                # One section per source file; its own h1 becomes the section heading (h2).
                title = next((HEADING.match(x).group(2) for x in lines if HEADING.match(x)
                              and HEADING.match(x).group(1) == "#"), pre)
                lines = [x for x in lines if not (HEADING.match(x) and HEADING.match(x).group(1) == "#")]
                self.used.add(pre)
                self.toc.append((2, pre, title))
                label = os.path.relpath(src, os.path.join(ROOT, os.path.dirname(os.path.dirname(src_rel))))
                body = (f'<section class="src" id="{pre}"><h2>{self.inline(src, title)}'
                        f'<a class="hl" href="#{pre}" aria-label="Link to this section">#</a></h2>'
                        f'<p class="from">From <code>{html.escape(label)}</code></p>\n'
                        + self.blocks(src, lines) + "</section>")
            else:
                lines = [x for x in lines if not (HEADING.match(x) and HEADING.match(x).group(1) == "#")]
                body = self.blocks(src, lines)
            sections.append(body)
        toc = "\n".join(f'<li class="l{lvl}"><a href="#{aid}">{self.inline_plain(text)}</a></li>'
                        for lvl, aid, text in self.toc if lvl <= 2 or len(self.spec["sources"]) == 1)
        srcs = ", ".join(f"<code>{html.escape(os.path.relpath(os.path.join(ROOT, s), self.out_dir))}</code>"
                         for s in self.spec["sources"])
        with open(TEMPLATE, encoding="utf-8") as f:
            page = f.read()
        values = {
            "{{TITLE}}": html.escape(self.spec["title"]),
            "{{SCOPE}}": html.escape(self.spec["scope"]),
            "{{LEAD}}": html.escape(self.spec["lead"]),
            "{{SOURCES}}": srcs,
            "{{TOC}}": toc,
            "{{BODY}}": "\n".join(sections),
        }
        for k, v in values.items():
            page = page.replace(k, v)
        return page

    def inline_plain(self, text):
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        text = text.replace("`", "").replace("**", "")
        return html.escape(text, quote=False)


def build(spec):
    return Page(spec).render()


def main(argv, out_root=ROOT):
    """Write every page under out_root, or with --check return 1 when a page there is missing or differs."""
    check = "--check" in argv
    stale = []
    for spec in PAGES:
        page = build(spec)
        out = os.path.join(out_root, spec["out"])
        if check:
            try:
                with open(out, encoding="utf-8") as f:
                    current = f.read()
            except FileNotFoundError:
                current = None
            if current != page:
                stale.append(spec["out"])
        else:
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, "w", encoding="utf-8") as f:
                f.write(page)
            print(f"wrote {spec['out']}")
    if stale:
        for s in stale:
            print(f"FAIL {s} differs from a fresh build of its Markdown: run python3 scripts/build_playbook_html.py")
        return 1
    if check:
        print("ok  every playbook page matches its Markdown")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
