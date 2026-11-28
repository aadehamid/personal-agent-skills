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

    def test_two_sources_that_disagree_make_a_clash_not_a_choice(self):
        g = graph_tool.Graph(self.root)
        g.node("Pump", "P-1", "spec.md", name="Feed pump")
        g.node("Pump", "P-1", "sheet.py", name="FEED PUMP A")
        g.node("Pump", "P-1", "other.md")
        clashes = g.clashes()
        self.assertEqual(len(clashes), 1)
        self.assertIn("sheet.py says 'FEED PUMP A'", clashes[0])
        self.assertIn("spec.md says 'Feed pump'", clashes[0])

    def test_one_id_with_two_labels_is_a_problem(self):
        g = graph_tool.Graph(self.root)
        g.node("Pump", "X-1", "a.md")
        g.node("Valve", "X-1", "b.md")
        self.assertTrue(any("b.md calls it a Valve" in p for p in g.problems), g.problems)

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
        self.assertNotEqual(self.cli("query", "--version").returncode, 0)

    def test_export_loads_and_keeps_sources(self):
        rows = graph_tool.run_relate(graph_tool.build(self.root),
                                     "MATCH (:Component {id: 'api'})-[r:DEPENDS_ON]->(d) RETURN d.id AS d, r.sources AS s ORDER BY d", {})
        self.assertEqual([json.loads(r) for r in rows],
                         [{"d": "cache", "s": ["docs/components.md"]}, {"d": "queue", "s": ["docs/components.md"]}])


if __name__ == "__main__":
    unittest.main()
