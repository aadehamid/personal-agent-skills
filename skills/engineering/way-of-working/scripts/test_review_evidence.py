#!/usr/bin/env python3
"""review-evidence.sh, and the read rule that every review script carries."""
import os
import re
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
HELPER = os.path.join(HERE, "review-evidence.sh")
REVIEWERS = ("agy", "pi", "herdr", "rex", "hc")


def source(name):
    with open(os.path.join(HERE, name)) as f:
        return f.read()


class OneRule(unittest.TestCase):
    def test_every_review_script_is_covered(self):
        found = {f[:-len("-review.sh")] for f in os.listdir(HERE) if f.endswith("-review.sh")}
        self.assertEqual(found - {"stop-cursor"}, set(REVIEWERS), "a new review script needs the read rule")

    def test_the_rule_and_the_evidence_sentence_are_the_same_in_every_script(self):
        for pattern in (r'^scope="([^"\n]+)"$', r'^  scope="\$scope ([^"\n]+)"$'):
            copies = {}
            for name in REVIEWERS:
                found = re.findall(pattern, source(name + "-review.sh"), re.M)
                self.assertEqual(len(found), 1, (name, pattern))
                copies[name] = found[0]
            self.assertEqual(len(set(copies.values())), 1, copies)

    def test_the_hosts_keep_and_remove_evidence_alike(self):
        blocks = set()
        for name in ("herdr", "rex", "hc"):
            found = re.search(r"^# Cursor's sandbox reads /tmp.*?^clean_evidence\(\) \{.*?^\}$",
                              source(name + "-review.sh"), re.M | re.S)
            self.assertTrue(found, name)
            blocks.add(found.group(0))
        self.assertEqual(len(blocks), 1, "the hosts' evidence blocks differ")

    def test_the_rule_sends_a_missing_file_to_the_report(self):
        rule = re.search(r'^scope="([^"\n]+)"$', source("pi-review.sh"), re.M).group(1)
        self.assertIn("Read and search only the repository under review", rule)
        self.assertIn("do not look for it", rule)
        self.assertIn("'Missing evidence'", rule)


class Evidence(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.parent = os.path.join(self.root, "evidence parent")

    def write(self, path, body="body\n"):
        full = os.path.join(self.root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(body)
        return full

    def attach(self, *paths):
        return subprocess.run(["bash", HELPER, self.parent, *paths], cwd=self.root, capture_output=True, text=True)

    def refused(self, *paths):
        r = self.attach(*paths)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertEqual(r.stdout, "")
        left = os.listdir(self.parent) if os.path.isdir(self.parent) else []
        self.assertEqual(left, [], "a refused attach left a copy")
        return r.stderr

    def read(self, *parts):
        with open(os.path.join(*parts)) as f:
            return f.read()

    def test_files_and_folders_are_copied_and_listed(self):
        a, b = self.write("a/out log.txt", "first"), self.write("b/out log.txt", "second")
        self.write("folder/sub/.hidden", "third")
        r = self.attach(a, b, "folder")
        self.assertEqual(r.returncode, 0, r.stderr)
        out = r.stdout.strip()
        self.assertEqual(self.read(out, "1-out log.txt"), "first")
        self.assertEqual(self.read(out, "2-out log.txt"), "second")
        self.assertEqual(self.read(out, "3-folder", "sub", ".hidden"), "third")
        self.assertEqual(self.read(out, "MANIFEST.txt").splitlines(),
                         ["1-out log.txt <- " + a, "2-out log.txt <- " + b, "3-folder <- folder"])

    def test_the_copy_is_fixed_when_the_original_changes(self):
        a = self.write("a.txt", "before")
        out = self.attach(a).stdout.strip()
        self.write("a.txt", "after")
        self.assertEqual(self.read(out, "1-a.txt"), "before")

    def test_a_link_named_directly_is_copied_as_what_it_points_at(self):
        link = os.path.join(self.root, "link")
        os.symlink(self.write("target.txt", "content"), link)
        out = self.attach(link).stdout.strip()
        self.assertFalse(os.path.islink(os.path.join(out, "1-link")))
        self.assertEqual(self.read(out, "1-link"), "content")

    def test_a_name_starting_with_a_dash_is_a_path(self):
        self.write("-n", "dash")
        out = self.attach("-n").stdout.strip()
        self.assertEqual(self.read(out, "1--n"), "dash")

    def test_a_missing_or_empty_path_is_refused_before_anything_is_copied(self):
        good = self.write("good.txt")
        for bad in ("gone.txt", ""):
            self.assertIn("no such file or folder", self.refused(good, bad))

    def test_a_folder_holding_a_link_is_refused(self):
        # The copy would lead the reviewer back out to a file nobody attached.
        self.write("folder/real.txt")
        os.symlink(self.write("elsewhere.txt"), os.path.join(self.root, "folder", "link"))
        self.assertIn("attach its target by name", self.refused("folder"))

    def test_a_pipe_is_refused_alone_or_in_a_folder(self):
        self.write("folder/real.txt")
        os.mkfifo(os.path.join(self.root, "pipe"))
        os.mkfifo(os.path.join(self.root, "folder", "pipe"))
        self.refused("pipe")
        self.refused("folder")

    @unittest.skipIf(os.geteuid() == 0, "root reads every file")
    def test_an_unreadable_file_leaves_no_copy(self):
        good, bad = self.write("good.txt"), self.write("bad.txt")
        os.chmod(bad, 0)
        self.refused(good, bad)


if __name__ == "__main__":
    unittest.main()
