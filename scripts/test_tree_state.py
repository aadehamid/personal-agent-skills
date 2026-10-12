#!/usr/bin/env python3
"""Each change check.sh's guard claims to catch must change the hash."""
import importlib.util
import os
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("tree_state", os.path.join(os.path.dirname(__file__), "tree-state.py"))
ts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ts)


def git(repo, *args):
    subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True)


class TreeState(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "t@example.com")
        git(self.repo, "config", "user.name", "t")
        self.write("tracked.txt", "one\n")
        git(self.repo, "add", "tracked.txt")
        git(self.repo, "commit", "-qm", "init")
        self.write("untracked.sh", "echo hi\n")
        os.chmod(self.p("untracked.sh"), 0o755)
        self.write("-", "dash\n")
        self.write("a.txt", "same\n")
        self.write("b.txt", "same\n")
        os.symlink("a.txt", self.p("link"))
        self.before = ts.tree_state(self.repo)

    def p(self, name):
        return os.path.join(self.repo, name)

    def write(self, name, text):
        with open(self.p(name), "w") as f:
            f.write(text)

    def changed(self):
        return ts.tree_state(self.repo) != self.before

    def test_unchanged_tree_hashes_the_same(self):
        self.assertFalse(self.changed())

    def test_untracked_file_rewritten(self):
        self.write("untracked.sh", "echo bye\n")
        self.assertTrue(self.changed())

    def test_file_named_dash_rewritten(self):
        self.write("-", "other\n")
        self.assertTrue(self.changed())

    def test_execute_bit_dropped(self):
        os.chmod(self.p("untracked.sh"), 0o644)
        self.assertTrue(self.changed())

    def test_symlink_retargeted_to_identical_contents(self):
        os.remove(self.p("link"))
        os.symlink("b.txt", self.p("link"))
        self.assertTrue(self.changed())

    def test_symlink_target_with_trailing_newline(self):
        os.remove(self.p("link"))
        os.symlink("a.txt\n", self.p("link"))
        self.assertTrue(self.changed())

    def test_index_blob_replaced(self):
        self.write("tracked.txt", "two\n")
        git(self.repo, "add", "tracked.txt")
        before = ts.tree_state(self.repo)
        self.write("tracked.txt", "three\n")
        git(self.repo, "add", "tracked.txt")
        self.write("tracked.txt", "two\n")
        self.assertNotEqual(ts.tree_state(self.repo), before)

    def test_unreadable_file_raises(self):
        os.chmod(self.p("a.txt"), 0)
        try:
            with self.assertRaises(PermissionError):
                ts.tree_state(self.repo)
        finally:
            os.chmod(self.p("a.txt"), 0o644)


if __name__ == "__main__":
    unittest.main()
