"""The playbooks' HTML pages match a fresh build of their Markdown, and the renderer handles what they use.

Run from the repository root: python3 scripts/test_playbook_html.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_playbook_html as b  # noqa: E402


class Fresh(unittest.TestCase):
    def test_every_committed_page_matches_a_fresh_build(self):
        for spec in b.PAGES:
            with self.subTest(page=spec["out"]):
                with open(os.path.join(b.ROOT, spec["out"]), encoding="utf-8") as f:
                    self.assertEqual(f.read(), b.build(spec),
                                     f"{spec['out']} is stale: run python3 scripts/build_playbook_html.py")

    def test_every_source_exists(self):
        for spec in b.PAGES:
            for src in spec["sources"]:
                self.assertTrue(os.path.isfile(os.path.join(b.ROOT, src)), src)


class Renderer(unittest.TestCase):
    def page(self):
        return b.Page(b.PAGES[1])

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

    def test_a_table_right_aligns_a_column_of_figures(self):
        out = self.page().table(self.src("pipeline.md"), ["| Item | Count |", "|---|---|", "| a | 12 |"])
        self.assertIn('<th class="num">Count</th>', out)
        self.assertIn('<td class="num">12</td>', out)

    def test_a_thematic_break_is_dropped(self):
        self.assertEqual(self.page().blocks(self.src("pipeline.md"), ["---"]), "")


if __name__ == "__main__":
    unittest.main()
