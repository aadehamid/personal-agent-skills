#!/usr/bin/env python3
"""Tests for graph_tool.py. Installed from the consistency-graph skill.

Keep the generic tests as they are. Replace the example fixture and the
example-specific tests with ones that cover every source form your parsers
read and every kind of finding your check can raise: each check needs a test
that fails when the check is removed. The relate tests skip where relate is
not installed, as on CI.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "graph_tool.py")
sys.path.insert(0, HERE)
import graph_tool  # noqa: E402

DECISIONS = """| Decision | Title |
|---|---|
| D1 | Use a queue |
| D2 | Use a cache |
"""

COMPONENTS = """Built from **3 components**.

| Component | Depends on | Decision | Owner |
|---|---|---|---|
| api | queue, cache | D1 | web |
| queue | - | D1 | platform |
| cache | - | D2 | platform |
"""


def write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        write(self.root, graph_tool.DECISIONS, DECISIONS)
        write(self.root, graph_tool.COMPONENTS, COMPONENTS)

    def tearDown(self):
        self.tmp.cleanup()

    def findings(self):
        return graph_tool.check(graph_tool.build(self.root))

    def cli(self, *args):
        env = dict(os.environ, GRAPH_ROOT=self.root)
        return subprocess.run([sys.executable, SCRIPT, *args], env=env, capture_output=True, text=True, timeout=60)


class Generic(Fixture):
    def test_markdown_tables_read_rows_by_header(self):
        tables = graph_tool.markdown_tables(DECISIONS + "\ntext\n\n| A | B |\n|:-|-:|\n| 1 | 2 |\n")
        self.assertEqual([h for h, _ in tables], [["Decision", "Title"], ["A", "B"]])
        self.assertEqual(tables[1][1][0]["B"], "2")

    def test_an_empty_last_cell_with_no_space_is_kept(self):
        # "| 1 ||" ends with two pipes: removing every outer pipe would lose the empty cell.
        tables = graph_tool.markdown_tables("| A | B | C |\n|---|---|---|\n| 1 | 2 ||\n")
        row = tables[0][1][0]
        self.assertEqual((row["_cells"], row["C"]), (3, ""))

    def test_a_separator_needs_dashes(self):
        # "| : | : |" holds only colons; it is a row, not the line under a header.
        self.assertEqual(graph_tool.markdown_tables("| P | Q |\n| : | : |\n| r | s |\n"), [])

    def test_tables_in_fenced_code_are_skipped(self):
        text = "```\n| X | Y |\n|---|---|\n| in | code |\n```\n| A |\n|---|\n| 1 |\n"
        self.assertEqual([h for h, _ in graph_tool.markdown_tables(text)], [["A"]])

    def test_clashes_compare_type_as_well_as_value(self):
        g = graph_tool.Graph(self.root)
        g.node("Valve", "V-1", "a.md", size="3", open=True)
        g.node("Valve", "V-1", "b.json", size=3, open=1)
        clashes = g.clashes()
        self.assertEqual(len(clashes), 2, clashes)
        self.assertTrue(any("size" in c and "'3'" in c and "says 3" in c for c in clashes), clashes)

    def test_one_source_stating_a_value_twice_compares_type(self):
        g = graph_tool.Graph(self.root)
        g.node("Valve", "V-1", "a.json", open=True, n=1)
        g.node("Valve", "V-1", "a.json", open=1, n=1.0)
        self.assertEqual(len([p for p in g.problems if "states" in p and "twice" in p]), 2, g.problems)

    def test_list_properties_reach_the_cypher_and_other_shapes_are_refused(self):
        g = graph_tool.Graph(self.root)
        g.node("Pump", "P-1", "a.md", tags=["a", "b"], size=3, spec={"x": 1})
        self.assertIn('`tags`: ["a", "b"]', graph_tool.cypher_seed(g))
        self.assertEqual([p for p in g.problems if "gives spec a dict" in p], [
            "P-1: a.md gives spec a dict; use text, a number, true/false or a list of those"])

    def test_labels_and_link_types_must_be_plain_names(self):
        g = graph_tool.Graph(self.root)
        g.node("Work Request", "WR-1", "a.md")
        g.node("Pump", "P-1", "a.md")
        g.node("Pump", "P-2", "a.md")
        g.link("P-1", "clarified by", "P-2", "a.md")
        self.assertIn("WR-1: a.md gives the label 'Work Request'; use letters, digits and _", g.problems)
        self.assertIn("P-1: a.md gives the link type 'clarified by'; use letters, digits and _", g.problems)
        seed = graph_tool.cypher_seed(g)
        self.assertNotIn("Work Request", seed)
        self.assertNotIn("clarified by", seed)

    def test_missing_sources_are_reported_once_each(self):
        empty = tempfile.TemporaryDirectory()
        try:
            findings = graph_tool.check(graph_tool.build(empty.name))
        finally:
            empty.cleanup()
        self.assertEqual(sorted(f for f in findings if "missing" in f),
                         ["docs/components.md: source is missing", "docs/decisions.md: source is missing"])

    def test_reserved_property_names_are_refused(self):
        g = graph_tool.Graph(self.root)
        g.node("Pump", "P-1", "a.md", id="other", sources="x")
        self.assertEqual(len([p for p in g.problems if "reserved property" in p]), 2, g.problems)
        self.assertNotIn('"other"', graph_tool.cypher_seed(g))

    def test_a_bad_required_link_direction_is_reported(self):
        saved = graph_tool.REQUIRED_LINKS
        graph_tool.REQUIRED_LINKS = [("Component", "DEFINED_BY", "outbound", "x")]
        try:
            self.assertIn("REQUIRED_LINKS: Component DEFINED_BY has direction 'outbound'; use 'out' or 'in'",
                          self.findings())
        finally:
            graph_tool.REQUIRED_LINKS = saved

    def test_argument_errors_come_before_reading_sources(self):
        empty = tempfile.TemporaryDirectory()
        try:
            env = dict(os.environ, GRAPH_ROOT=empty.name)
            for args in (("nonsense",), ("summary", "x"), ("impact",)):
                with self.subTest(args):
                    p = subprocess.run([sys.executable, SCRIPT, *args], env=env, capture_output=True, text=True, timeout=60)
                    self.assertEqual(p.returncode, 2, p.stderr)
                    self.assertNotIn("Traceback", p.stderr)
        finally:
            empty.cleanup()

    def test_two_sources_that_disagree_make_a_clash_not_a_choice(self):
        g = graph_tool.Graph(self.root)
        g.node("Pump", "P-1", "spec.md", name="Feed pump")
        g.node("Pump", "P-1", "sheet.py", name="FEED PUMP A")
        g.node("Pump", "P-1", "other.md")
        clashes = g.clashes()
        self.assertEqual(len(clashes), 1)
        self.assertIn("sheet.py says 'FEED PUMP A'", clashes[0])
        self.assertIn("spec.md says 'Feed pump'", clashes[0])

    def test_one_id_with_two_labels_names_every_source_on_each_side(self):
        g = graph_tool.Graph(self.root)
        g.node("Pump", "X-1", "a.md")
        g.node("Valve", "X-1", "b.md")
        g.node("Pump", "X-1", "c.md")
        g.node("Tank", "X-1", "d.md")
        self.assertEqual(g.clashes(), ["X-1: sources disagree on its label: a.md, c.md call it a Pump; "
                                       "d.md calls it a Tank; b.md calls it a Valve"])

    def test_cli_arguments(self):
        self.assertEqual(self.cli("summary").returncode, 0)
        for args in (("summary", "x"), ("check", "--strict"), ("export", "x"), ("impact",),
                     ("impact", "nope"), ("query",), ("nonsense",), ("help", "x")):
            with self.subTest(args):
                self.assertEqual(self.cli(*args).returncode, 2, args)


class Example(Fixture):
    def test_consistent_sources_pass(self):
        self.assertEqual(self.findings(), [])
        p = self.cli("check")
        self.assertEqual((p.returncode, p.stdout.strip()), (0, "graph_tool: the sources agree"))

    def test_summary_counts(self):
        self.assertEqual(json.loads(self.cli("summary").stdout),
                         {"nodes": {"Component": 3, "Decision": 2}, "links": {"DEFINED_BY": 3, "DEPENDS_ON": 2}})

    def test_each_kind_of_finding_is_reported(self):
        cases = {
            "api -DEPENDS_ON-> store: store is not defined by any source":
                COMPONENTS.replace("queue, cache | D1", "queue, store | D1"),
            "cache: a Component with no DEFINED_BY link": COMPONENTS.replace("| - | D2 |", "| - | - |"),
            "Component: the sources define 3, but docs/components.md says 4":
                COMPONENTS.replace("**3 components**", "**4 components**"),
            "row has 3 cells, the header 4": COMPONENTS.replace("| cache | - | D2 | platform |", "| cache | - | D2 |"),
            "is not the component table": COMPONENTS + "\n| Name | Uses |\n|---|---|\n| x | y |\n",
            "docs/components.md: promises no component count": COMPONENTS.replace("Built from **3 components**.", ""),
            "row has no component name": COMPONENTS.replace("| cache | - | D2 | platform |", "|  | - | D2 | platform |"),
            "cache: docs/components.md states owner twice: 'platform' and 'data'": COMPONENTS + "\n| Component | Depends on | Decision | Owner |\n"
                                                             "|---|---|---|---|\n| cache | - | D2 | data |\n",
        }
        for message, text in cases.items():
            with self.subTest(message):
                self.tearDown()
                self.setUp()
                write(self.root, graph_tool.COMPONENTS, text)
                findings = self.findings()
                self.assertTrue(any(message in f for f in findings), findings)
                p = self.cli("check")
                self.assertEqual(p.returncode, 1)
                self.assertIn("finding(s)", p.stderr)

    def test_a_count_inside_fenced_code_is_not_the_promise(self):
        write(self.root, graph_tool.COMPONENTS,
              "```\n**9 components**\n```\n" + COMPONENTS)
        self.assertEqual([f for f in self.findings() if "the sources define" in f], [])

    def test_a_decision_row_with_an_extra_cell_is_reported(self):
        write(self.root, graph_tool.DECISIONS, DECISIONS + "| D9 | Nine | extra |\n")
        findings = self.findings()
        self.assertTrue(any("docs/decisions.md:" in f and "row has 3 cells, the header 2" in f for f in findings), findings)
        self.assertNotIn("D9", graph_tool.build(self.root).nodes)


@unittest.skipUnless(shutil.which("relate"), "relate is not installed")
class Queries(Fixture):
    def test_impact_reaches_linked_nodes(self):
        p = self.cli("impact", "cache")
        self.assertEqual(p.returncode, 0, p.stderr)
        rows = {r["id"]: r["hops"] for r in map(json.loads, p.stdout.splitlines())}
        self.assertEqual(rows["api"], 1)
        self.assertEqual(rows["D2"], 1)
        self.assertEqual(rows["queue"], 2)

    def test_query_is_read_only(self):
        p = self.cli("query", "MATCH (c:Component) RETURN count(c) AS n")
        self.assertEqual(json.loads(p.stdout.splitlines()[0]), {"n": 3})
        self.assertNotEqual(self.cli("query", "MATCH (c:Component) DETACH DELETE c").returncode, 0)
        p = self.cli("query", "--version")
        self.assertNotEqual(p.returncode, 0)
        # relate read it as a statement and rejected its syntax; read as a flag it would print its version.
        self.assertIn("syntax error", p.stderr)
        self.assertNotIn("Relate v", p.stderr + p.stdout)

    def test_export_loads_and_keeps_sources(self):
        rows = graph_tool.run_relate(graph_tool.build(self.root),
                                     "MATCH (:Component {id: 'api'})-[r:DEPENDS_ON]->(d) RETURN d.id AS d, r.sources AS s ORDER BY d", {})
        self.assertEqual([json.loads(r) for r in rows],
                         [{"d": "cache", "s": ["docs/components.md"]}, {"d": "queue", "s": ["docs/components.md"]}])


if __name__ == "__main__":
    unittest.main()
