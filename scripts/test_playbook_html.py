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
    """Each references/*.md the README's file table names that the page lacks, and the reverse. The first cell
    is read whatever its form: plain, in backticks, or a Markdown link with or without backticks."""
    listed = set()
    for row in re.findall(r"^\|([^|\n]*)\|", readme, re.M):
        cell = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", row).replace("`", "").strip()
        if re.fullmatch(r"references/[\w.-]+\.md", cell):
            listed.add(cell)
        else:  # a link whose label is not the path: read its target
            listed.update(t for t in re.findall(r"\]\(([^)]*)\)", row) if re.fullmatch(r"references/[\w.-]+\.md", t))
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

    def test_a_readme_row_missing_from_the_page_is_reported_in_any_form(self):
        # Kimi round 2, finding 8: plain, linked and backticked first cells all count.
        for cell in ("`references/new.md`", "references/new.md", "[references/new.md](references/new.md)",
                     "[`references/new.md`](references/new.md)"):
            with self.subTest(cell=cell):
                text = f"| `references/pipeline.md` | x | y |\n| {cell} | x | y |\n"
                problems = readme_problems(text, ["skills/data/ontology-to-lpg/references/pipeline.md"])
                self.assertEqual(problems, ["references/new.md is in the README but not on the page"])

    def test_the_ontology_page_holds_the_playbook(self):
        self.assertEqual(ONTOLOGY["sources"], ["skills/data/ontology/references/playbook.md"])

    def test_each_readme_links_its_page(self):
        # Each page is named for what it holds, so the two pages never share a file name.
        for readme, page in (("skills/data/ontology/README.md", "ontology-build-playbook.html"),
                             ("skills/data/ontology-to-lpg/README.md", "ontology-to-neo4j-playbook.html")):
            with self.subTest(readme=readme):
                self.assertIn(f"[`references/{page}`](references/{page})", read(readme))


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



DIAGRAMS = os.path.join(b.ROOT, "skills/data/ontology-to-lpg/references/diagrams")
INLINE = {"a", "abbr", "b", "code", "em", "i", "kbd", "mark", "q", "s", "small", "span", "strong", "sub", "sup", "u"}


class Visible(HTMLParser):
    """The text a reader sees: no script or style, inline tags joined without a gap (so Mar<b>athon</b> reads
    Marathon), block tags separated by a line break."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self._skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag not in INLINE:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip -= 1
        elif tag not in INLINE:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def visible_text(text):
    p = Visible()
    p.feed(text)
    p.close()
    return "".join(p.parts)


CREDENTIALS = [
    ("a Databricks token", r"\bdapi[0-9a-f]{20,}"),
    ("an OpenAI-style key", r"\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}"),
    ("a GitHub token", r"\bgh[pousr]_[A-Za-z0-9]{20,}|\bgithub_pat_[A-Za-z0-9_]{22,}"),
    ("a Slack token", r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    ("an AWS access key ID", r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    ("an AWS secret access key", r"(?i)aws_secret_access_key\s*[=:]\s*['\"]?[A-Za-z0-9/+=]{40}"),
    ("a private key", r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----"),
    ("a Google API key", r"\bAIza[0-9A-Za-z_-]{35}\b"),
    ("a credential assignment", r"(?i)\b(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?key|auth[_-]?token|token)"
                                r"\b\s*[=:]\s*['\"]?(?=[^\s'\"<>]*[0-9])[^\s'\"<>{}$%]{12,}"),
]


def credentials(text):
    """(kind, matched text) for each credential-shaped string in text."""
    return [(kind, m.group(0)) for kind, pattern in CREDENTIALS for m in re.finditer(pattern, text)]


def diagram_inputs():
    """Every text file that makes the two diagrams: the .eraser sources, the .excalidraw scenes the PNGs are
    rendered from, and the generators that write the scenes."""
    found = {ext: sorted(glob.glob(os.path.join(DIAGRAMS, pattern)))
             for ext, pattern in (("eraser", "*.eraser"), ("excalidraw", "*.excalidraw"), ("generator", "make_*.py"))}
    return found


def png_chunks(data):
    """The chunk types of a PNG, in order."""
    out, i = [], 8
    while i < len(data):
        length = int.from_bytes(data[i:i + 4], "big")
        out.append(data[i + 4:i + 8].decode("latin-1"))
        i += 12 + length
    return out


# The one use of 'this repository' the projection page may make: its README's file table names the skills
# repository's own check script. Any other use, and every other neutrality term, is reported.
ALLOWED_PHRASES = [re.compile(r"this repository's check script", re.I)]


def neutrality(text, allowed=()):
    for phrase in allowed:
        text = phrase.sub("", text)
    return guide.problems(text)


class Secrets(unittest.TestCase):
    """Kimi round 2, findings 4, 5 and 12: credential shapes in every page (markup and visible text), every
    Markdown source and every diagram input, with canaries for each shape."""

    def test_no_page_source_or_diagram_input_holds_a_credential(self):
        texts = {}
        for spec in b.PAGES:
            page = re.sub(r"data:image/png;base64,[A-Za-z0-9+/=]+", "", read(spec["out"]))
            texts[spec["out"]] = page
            texts[spec["out"] + " (visible)"] = visible_text(page)
            for src in spec["sources"]:
                texts[src] = read(src)
        for paths in diagram_inputs().values():
            for path in paths:
                with open(path, encoding="utf-8") as f:
                    texts[path] = f.read()
        for name, text in texts.items():
            with self.subTest(text=name):
                self.assertEqual(credentials(text), [])

    def test_each_credential_shape_is_caught(self):
        for canary in ("dapi" + "0123456789abcdef0123456789abcdef", "sk-" + "A1b2C3d4E5f6G7h8I9j0K1l2",
                       "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2", "github_pat_" + "11ABCDEFG0123456789_abcdefghijklmnop",
                       "xoxb-" + "1234567890-abcdefghij", "AKIA" + "ABCDEFGHIJKLMNOP",
                       "aws_secret_access_key = " + "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                       "-----BEGIN RSA " + "PRIVATE KEY-----", "AIza" + "SyA1234567890abcdefghijklmnopqrstuv",
                       "password=" + "Hunter2!Hunter2!9", "api_key: " + "'x9.y8-z7_w6@v5u4'"):
            with self.subTest(canary=canary):
                self.assertNotEqual(credentials(canary), [])

    def test_prose_and_placeholders_are_not_credentials(self):
        for text in ("the password is in ~/epm-lpg/run.env", "--password <password>", "NEO4J_PASSWORD=%s",
                     "token: see the env file", "a skill-version"):
            with self.subTest(text=text):
                self.assertEqual(credentials(text), [])

    def test_a_credential_split_by_markup_is_found_in_the_visible_text(self):
        page = "<p>dapi0123456789<strong>abcdef0123456789abcdef</strong></p>"
        self.assertEqual(credentials(page), [])
        self.assertNotEqual(credentials(visible_text(page)), [])

    def test_the_diagrams_carry_no_text_chunks(self):
        # The PNGs are rendered from the .excalidraw scenes the tests read; a text chunk (tEXt, iTXt, zTXt)
        # would carry words those scans never see. Raster text itself is not read: its source is the scene.
        for path in sorted(glob.glob(os.path.join(DIAGRAMS, "*.png"))):
            with self.subTest(png=path):
                with open(path, "rb") as f:
                    data = f.read()
                self.assertEqual(sorted(set(png_chunks(data)) - {"IHDR", "IDAT", "IEND", "sRGB", "pHYs", "gAMA"}), [])
                self.assertEqual(credentials(data.decode("latin-1")), [])


class Neutral(unittest.TestCase):
    """The pages and every diagram input name no project's records, companies, paths or industry; markup cannot
    hide a name (the visible text is scanned too). The only phrase allowed on the projection page is
    ALLOWED_PHRASES; the diagram inputs get no exemption. Kimi round 2, findings 5, 6 and 7."""

    def test_each_page_is_neutral_in_markup_and_visible_text(self):
        for spec, allowed in ((ONTOLOGY, ()), (PROJECTION, ALLOWED_PHRASES)):
            text = read(spec["out"])
            for name, body in (("markup", text), ("visible", visible_text(text))):
                with self.subTest(page=spec["out"], view=name):
                    self.assertEqual(neutrality(body, allowed), [])

    def test_every_diagram_input_is_neutral(self):
        inputs = diagram_inputs()
        self.assertEqual({k: len(v) for k, v in inputs.items()}, {"eraser": 2, "excalidraw": 2, "generator": 2})
        for paths in inputs.values():
            for path in paths:
                with self.subTest(source=path):
                    with open(path, encoding="utf-8") as f:
                        self.assertEqual(neutrality(f.read()), [])

    def test_the_exemption_is_one_phrase(self):
        self.assertEqual(neutrality("Tests: this repository's check script runs them.", ALLOWED_PHRASES), [])
        self.assertNotEqual(neutrality("This repository holds one project's private build.", ALLOWED_PHRASES), [])
        self.assertNotEqual(neutrality("the worked example's build", ALLOWED_PHRASES), [])

    def test_a_name_split_by_markup_is_found(self):
        page = "<p>Mar<strong>athon</strong> plans</p>"
        self.assertEqual(neutrality(page), [])
        self.assertNotEqual(neutrality(visible_text(page)), [])


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



class QuickCheckRegressions(unittest.TestCase):
    """Pi's quick check after round 2: an email autolink, a construct on a list marker line, a labelled README link."""

    def test_an_email_autolink_stops_the_build(self):
        self.assertEqual(b.unsupported(["contact <user@example.com> please"]), [(1, "inline HTML or an autolink")])

    def test_a_blockquote_or_definition_on_a_list_marker_line_stops_the_build(self):
        self.assertEqual(b.unsupported(["- > quoted"]), [(1, "a blockquote")])
        self.assertEqual(b.unsupported(["- [ref]: https://example.org"]), [(1, "a reference-style link definition")])
        self.assertEqual(b.unsupported(["- a plain item", "- [a link](https://example.org) item"]), [])
        self.assertEqual(b.unsupported(["- - > quoted"]), [(1, "a blockquote")])
        self.assertEqual(b.unsupported(["* - 3. [ref]: https://example.org"]), [(1, "a reference-style link definition")])
        self.assertEqual(b.unsupported(["- ~~~"]), [(1, "a tilde code fence")])

    def test_a_readme_link_whose_label_is_not_the_path_is_read_by_its_target(self):
        row = "| [New doc](references/new.md) | agent | y |\n"
        self.assertEqual(readme_problems(row, []), ["references/new.md is in the README but not on the page"])


if __name__ == "__main__":
    unittest.main()
