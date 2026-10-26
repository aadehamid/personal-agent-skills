"""The playbooks' HTML pages match a fresh build of their Markdown, stand alone, stay neutral, and the renderer
handles what they use and refuses what it does not.

Run from the repository root: python3 scripts/test_playbook_html.py
"""
import base64
import contextlib
import glob
import io
import os
import re
import sys
import tempfile
import unittest
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "skills", "data", "ontology", "scripts"))
import build_playbook_html as b  # noqa: E402
import test_playbook_guide as guide  # noqa: E402

ONTOLOGY, PROJECTION = b.PAGES


def read(rel):
    with open(os.path.join(b.ROOT, rel), encoding="utf-8") as f:
        return f.read()


def quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


class Fresh(unittest.TestCase):
    """The public command, `build_playbook_html.py --check`, is what check.sh relies on."""

    def test_check_passes_on_the_committed_pages(self):
        self.assertEqual(quiet(b.main, ["--check"]), 0)

    def test_check_fails_on_a_stale_or_missing_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(quiet(b.main, [], out_root=tmp), 0)
            self.assertEqual(quiet(b.main, ["--check"], out_root=tmp), 0)
            stale = os.path.join(tmp, ONTOLOGY["out"])
            with open(stale, "a", encoding="utf-8") as f:
                f.write("<!-- edited by hand -->")
            self.assertEqual(quiet(b.main, ["--check"], out_root=tmp), 1)
            os.remove(stale)
            self.assertEqual(quiet(b.main, ["--check"], out_root=tmp), 1)

    def test_every_committed_page_equals_a_fresh_build(self):
        for spec in b.PAGES:
            with self.subTest(page=spec["out"]):
                self.assertEqual(read(spec["out"]), b.build(spec))


def readme_problems(readme, sources):
    """Each references/*.md the README's file table names that the page lacks, and the reverse."""
    listed = set(re.findall(r"^\| \[?`(references/[\w.-]+\.md)`", readme, re.M))
    on_page = {s.split("ontology-to-lpg/", 1)[1] for s in sources if "/references/" in s}
    return ([f"{p} is in the README but not on the page" for p in sorted(listed - on_page)]
            + [f"{p} is on the page but not in the README" for p in sorted(on_page - listed)])


class Inventory(unittest.TestCase):
    """The README tables, the reference folders and PAGES name the same sources."""

    def test_every_projection_reference_is_on_the_page(self):
        refs = sorted(os.path.relpath(p, b.ROOT) for p in
                      glob.glob(os.path.join(b.ROOT, "skills/data/ontology-to-lpg/references/*.md")))
        self.assertEqual(refs, sorted(s for s in PROJECTION["sources"] if "/references/" in s))
        self.assertIn("skills/data/ontology-to-lpg/README.md", PROJECTION["sources"])

    def test_the_readme_lists_exactly_the_page_sources(self):
        self.assertEqual(readme_problems(read("skills/data/ontology-to-lpg/README.md"), PROJECTION["sources"]), [])

    def test_a_readme_row_missing_from_the_page_is_reported(self):
        text = "| `references/pipeline.md` | x | y |\n| `references/new.md` | x | y |\n"
        problems = readme_problems(text, ["skills/data/ontology-to-lpg/references/pipeline.md"])
        self.assertEqual(problems, ["references/new.md is in the README but not on the page"])

    def test_the_ontology_page_holds_the_playbook(self):
        self.assertEqual(ONTOLOGY["sources"], ["skills/data/ontology/references/playbook.md"])

    def test_each_readme_links_its_page(self):
        for readme in ("skills/data/ontology/README.md", "skills/data/ontology-to-lpg/README.md"):
            with self.subTest(readme=readme):
                self.assertIn("[`references/playbook.html`](references/playbook.html)", read(readme))


REMOTE_CSS = re.compile(r"url\s*\(|@import", re.I)
REMOTE_JS = re.compile(r"\bfetch\s*\(|XMLHttpRequest|WebSocket|EventSource|sendBeacon|\bimport\s*\(|importScripts"
                       r"|new\s+(?:Image|Worker|SharedWorker)\b|\.src\s*=|\.href\s*=|location\s*=|window\.open", re.I)
LOADING_RELS = {"stylesheet", "preload", "prefetch", "preconnect", "dns-prefetch", "icon", "modulepreload",
                "manifest", "apple-touch-icon", "prerender"}


class Resources(HTMLParser):
    """What a page would fetch: any src, srcset, data, poster or background attribute other than an embedded
    PNG; a link whose rel holds a loading token (case-insensitive, 'alternate stylesheet' included); a frame or
    media element; a style attribute or <style> block with url() or @import (any case); and inline script that
    opens a request. images lists every img src, for the diagram test."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.fetched, self.images, self._in = [], [], None
        self._script, self._style = [], []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "img":
            self.images.append(a.get("src", ""))
        for key in ("src", "srcset", "data", "poster", "background", "lowsrc", "dynsrc"):
            if key in a and not (tag == "img" and key == "src" and a[key].startswith("data:image/png;base64,")):
                self.fetched.append(f"{tag} {key}={a[key][:60]}")
        if tag == "link" and set(a.get("rel", "").lower().split()) & LOADING_RELS:
            self.fetched.append(f"link rel={a.get('rel')} href={a.get('href')}")
        if tag in ("iframe", "frame", "embed", "object", "video", "audio", "source", "track", "base"):
            self.fetched.append(tag)
        if REMOTE_CSS.search(a.get("style", "")):
            self.fetched.append(f"{tag} style={a['style'][:60]}")
        if tag in ("script", "style"):
            self._in = tag

    def handle_endtag(self, tag):
        if tag == self._in:
            self._in = None

    def handle_data(self, data):
        if self._in == "script":
            self._script.append(data)
        elif self._in == "style":
            self._style.append(data)

    def close(self):
        super().close()
        if REMOTE_CSS.search("".join(self._style)):
            self.fetched.append("style block with url() or @import")
        for m in REMOTE_JS.finditer("".join(self._script)):
            self.fetched.append(f"script {m.group(0)}")


def network_loads(text):
    p = Resources()
    p.feed(text)
    p.close()
    return p.fetched


class Standalone(unittest.TestCase):
    def test_no_page_loads_anything_from_the_network(self):
        for spec in b.PAGES:
            with self.subTest(page=spec["out"]):
                self.assertEqual(network_loads(read(spec["out"])), [])

    def test_each_kind_of_network_load_is_caught(self):
        # Kimi round 2, findings 3 and 11: each canary must be reported.
        for canary in ('<img src="data:image/png;base64,AA" srcset="https://example.invalid/a.png 2x">',
                       '<link rel="alternate stylesheet" href="https://example.invalid/a.css">',
                       '<link rel="StyleSheet" href="a.css">',
                       '<style>body { background: URL(https://example.invalid/a.png) }</style>',
                       '<style>@IMPORT "https://example.invalid/a.css";</style>',
                       '<p style="background-image:url(https://example.invalid/a.png)">x</p>',
                       '<script>fetch("https://example.invalid/data")</script>',
                       '<script>new XMLHttpRequest()</script>',
                       '<script>navigator.sendBeacon("https://example.invalid")</script>',
                       '<script>var i = new Image(); i.src = "https://example.invalid/p.png"</script>',
                       '<script src="https://example.invalid/a.js"></script>',
                       '<video poster="https://example.invalid/p.png"></video>'):
            with self.subTest(canary=canary):
                self.assertNotEqual(network_loads(f"<html><body>{canary}</body></html>"), [])

    def test_an_embedded_png_and_a_plain_link_are_not_loads(self):
        self.assertEqual(network_loads('<img src="data:image/png;base64,AA"><a href="https://example.org">x</a>'), [])

    def test_the_projection_page_embeds_both_diagrams_byte_for_byte(self):
        named = sorted(set(re.findall(r"`(diagrams/[\w.-]+\.png)`",
                                      "".join(read(s) for s in PROJECTION["sources"]))))
        self.assertEqual(named, ["diagrams/data-flow.png", "diagrams/validation-path.png"])
        p = Resources()
        p.feed(read(PROJECTION["out"]))
        p.close()
        embedded = [base64.b64decode(s.split(",", 1)[1]) for s in p.images]
        expected = []
        for rel in named:
            with open(os.path.join(b.ROOT, "skills/data/ontology-to-lpg/references", rel), "rb") as f:
                expected.append(f.read())
        self.assertEqual(embedded, expected)

    def test_figure_embeds_the_file_with_its_alt_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "diagrams"))
            png = b"\x89PNG\r\n\x1a\nfake"
            with open(os.path.join(tmp, "diagrams", "a-b.png"), "wb") as f:
                f.write(png)
            out = b.Page(ONTOLOGY).figure(os.path.join(tmp, "x.md"), "diagrams/a-b.png")
            self.assertIn(f'src="data:image/png;base64,{base64.b64encode(png).decode()}"', out)
            self.assertIn('alt="The a b diagram"', out)

    def test_no_page_holds_a_credential(self):
        pattern = (r"dapi[0-9a-f]{20,}|\bsk-[A-Za-z0-9]{20,}|\bgh[pousr]_[A-Za-z0-9]{20,}|\bAKIA[0-9A-Z]{16}\b"
                   r"|(?i:password|passwd|secret|api[_-]?key|token)\s*[=:]\s*['\"]?[A-Za-z0-9/+_-]{12,}")
        for spec in b.PAGES:
            with self.subTest(page=spec["out"]):
                text = re.sub(r"data:image/png;base64,[A-Za-z0-9+/=]+", "", read(spec["out"]))
                self.assertEqual(re.findall(pattern, text), [])


class Neutral(unittest.TestCase):
    """Both pages and the projection's diagram sources name no project's records, companies, paths or industry.
    'This repository' is allowed on the projection page: there it means the skills repository itself (its
    check script), not a project's build."""

    def check(self, text, allow=()):
        return [p for p in guide.problems(text) if p[1] not in allow]

    def test_the_projection_page_and_its_diagram_sources_are_neutral(self):
        allow = ("a reference to one project's build",)
        self.assertEqual(self.check(read(PROJECTION["out"]), allow), [])
        sources = glob.glob(os.path.join(b.ROOT, "skills/data/ontology-to-lpg/references/diagrams/*.eraser"))
        self.assertEqual(len(sources), 2)
        for src in sources:
            with self.subTest(source=src):
                with open(src, encoding="utf-8") as f:
                    self.assertEqual(self.check(f.read(), allow), [])

    def test_the_ontology_page_is_neutral(self):
        self.assertEqual(self.check(read(ONTOLOGY["out"])), [])


class Renderer(unittest.TestCase):
    def page(self):
        return b.Page(PROJECTION)

    def src(self, name):
        return os.path.normpath(os.path.join(b.ROOT, "skills/data/ontology-to-lpg/references", name))

    def test_bold_may_hold_code(self):
        self.assertEqual(self.page().inline(self.src("pipeline.md"), "**Write `a.nt` now.**"),
                         "<strong>Write <code>a.nt</code> now.</strong>")

    def test_a_link_to_a_source_on_the_page_becomes_its_anchor(self):
        p = self.page()
        self.assertIn('href="#running--rule-2"', p.inline(self.src("pipeline.md"), "[x](running.md#rule-2)"))
        self.assertIn('href="#design-rules"', p.inline(self.src("pipeline.md"), "[x](design-rules.md)"))

    def test_a_link_to_another_file_stays_relative_to_the_page(self):
        self.assertIn('href="../SKILL.md"', self.page().inline(self.src("pipeline.md"), "[x](../SKILL.md)"))

    def test_markup_in_text_is_escaped(self):
        self.assertEqual(self.page().inline(self.src("pipeline.md"), "a <b> & `<c>`"),
                         "a &lt;b&gt; &amp; <code>&lt;c&gt;</code>")

    def test_a_list_item_keeps_its_nested_list_and_code_block(self):
        lines = ["1. **Rule.** Text", "   more text.", "", "   ```sh", "   run it", "   ```", "",
                 "    - a nested point", "2. Next."]
        out = self.page().blocks(self.src("pipeline.md"), lines)
        self.assertIn("<li><strong>Rule.</strong> Text more text.", out)
        self.assertIn('<pre><code class="lang-sh">run it</code></pre>', out)
        self.assertIn("<ul><li>a nested point</li></ul>", out)
        self.assertIn("<li>Next.</li></ol>", out)

    def test_an_ordered_list_keeps_its_start(self):
        self.assertIn('<ol start="5">', self.page().blocks(self.src("pipeline.md"), ["5. Five.", "6. Six."]))

    def test_a_repeated_heading_gets_its_own_anchor(self):
        out = self.page().blocks(self.src("pipeline.md"), ["## Notes", "## Notes"])
        self.assertIn('id="pipeline--notes"', out)
        self.assertIn('id="pipeline--notes-2"', out)

    def test_a_table_right_aligns_a_column_of_figures(self):
        out = self.page().table(self.src("pipeline.md"), ["| Item | Count |", "|---|---|", "| a | 12 |"])
        self.assertIn('<th class="num">Count</th>', out)
        self.assertIn('<td class="num">12</td>', out)

    def test_a_thematic_break_is_dropped(self):
        self.assertEqual(self.page().blocks(self.src("pipeline.md"), ["---"]), "")


class Unsupported(unittest.TestCase):
    """Markdown the renderer does not handle stops the build with its line, instead of becoming a paragraph."""

    def test_each_construct_is_reported_with_its_line(self):
        for line, kind in (("> quoted", "a blockquote"),
                           ("![alt](a.png)", "an image"),
                           ("text <span>x</span>", "inline HTML or an autolink"),
                           ("see <https://example.org>", "inline HTML or an autolink"),
                           ("[ref]: https://example.org", "a reference-style link definition")):
            with self.subTest(kind=kind):
                self.assertIn((2, kind), b.unsupported(["intro", line]))

    def test_round_two_bypasses_are_reported(self):
        # Kimi round 2: a tilde fence, a compact definition, a blockquote in list content, a tag split over lines.
        for lines, expected in ((["~~~", "x", "~~~"], (1, "a tilde code fence")),
                                (["[ref]:https://example.org"], (1, "a reference-style link definition")),
                                (["- item", "    > quoted"], (2, "a blockquote")),
                                (["Before <span", 'class="x">after.'], (1, "inline HTML or an autolink")),
                                (["- item", "  text <div", "  >x"], (2, "inline HTML or an autolink"))):
            with self.subTest(lines=lines):
                self.assertIn(expected, b.unsupported(lines))

    def test_the_build_reports_each_bypass_with_its_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "bad.md")
            with open(src, "w", encoding="utf-8") as f:
                f.write("# Title\n\n- item\n    > quoted\n\n[r]:https://example.org\n")
            spec = {"out": os.path.join(tmp, "bad.html"), "title": "t", "scope": "s", "lead": "l", "sources": [src]}
            with self.assertRaisesRegex(ValueError, r"bad\.md:4: a blockquote.*bad\.md:6: a reference-style"):
                b.build(spec)

    def test_a_setext_heading_is_reported(self):
        self.assertIn((2, "a Setext heading underline"), b.unsupported(["Heading", "==="]))
        self.assertIn((2, "a Setext heading underline"), b.unsupported(["Heading", "---"]))

    def test_code_and_thematic_breaks_are_not_reported(self):
        self.assertEqual(b.unsupported(["`<b>` and `![x]`", "", "---", "```", "> in code", "<tag>", "```"]), [])

    def test_the_build_stops_on_an_unsupported_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "bad.md")
            with open(src, "w", encoding="utf-8") as f:
                f.write("# Title\n\n> quoted\n")
            spec = {"out": os.path.join(tmp, "bad.html"), "title": "t", "scope": "s", "lead": "l", "sources": [src]}
            with self.assertRaisesRegex(ValueError, r"bad\.md:3: a blockquote is not supported"):
                b.build(spec)


if __name__ == "__main__":
    unittest.main()
