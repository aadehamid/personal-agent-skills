#!/usr/bin/env python3
"""Tests for start.py: it copies the template under a new name, and the copy's own tests pass."""
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
START = os.path.join(HERE, "start.py")


def git_env():
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


class Start(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = os.path.join(self.tmp.name, "repo")
        subprocess.run(["git", "init", "-q", self.repo], env=git_env(), check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def start(self, *args):
        return subprocess.run([sys.executable, START, self.repo, *args], capture_output=True, text=True, timeout=60)

    def test_copies_renames_and_the_copy_passes_its_own_tests(self):
        p = self.start("twin_graph")
        self.assertEqual(p.returncode, 0, p.stderr)
        tool = os.path.join(self.repo, "scripts", "twin_graph.py")
        with open(tool) as fh:
            text = fh.read()
        self.assertNotIn("graph_tool", text)
        self.assertIn("TWIN_GRAPH_ROOT", text)
        self.assertTrue(os.access(tool, os.X_OK))
        env = dict(git_env(), PYTHONDONTWRITEBYTECODE="1")
        t = subprocess.run([sys.executable, "-m", "unittest", "-q", "test_twin_graph"], cwd=os.path.join(self.repo, "scripts"),
                           env=env, capture_output=True, text=True, timeout=300)
        self.assertEqual(t.returncode, 0, t.stderr[-3000:])
        self.assertRegex(t.stderr, r"Ran 1\d tests")

    def test_refuses_to_overwrite_and_bad_names(self):
        self.assertEqual(self.start("plant_graph").returncode, 0)
        p = self.start("plant_graph")
        self.assertEqual(p.returncode, 1)
        self.assertIn("the project owns it now", p.stderr)
        for name in ("Plant", "graph_tool", "1x", "bad-name"):
            with self.subTest(name):
                self.assertEqual(self.start(name).returncode, 2)

    def test_custom_folder(self):
        self.assertEqual(self.start("adr_graph", "--dir", "tools").returncode, 0)
        self.assertTrue(os.path.isfile(os.path.join(self.repo, "tools", "test_adr_graph.py")))


if __name__ == "__main__":
    unittest.main()
