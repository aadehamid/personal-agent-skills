#!/usr/bin/env python3
"""Tests for scripts/link-skills.sh --global, run against a throwaway HOME: --dry-run changes nothing,
the snippet reaches GEMINI.md and .goosehints once, a real file where the split's link goes is kept, and an
install made before the markers existed is not appended again."""
import os
import subprocess
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, "scripts", "link-skills.sh")
SNIPPET = os.path.join(REPO, "config", "global-snippet.md")
MARKERS = [line.strip() for line in open(SNIPPET) if line.startswith("<!-- way-of-working-snippet:")]


def run(home, *args, glob=True):
    env = dict(os.environ, HOME=home)
    return subprocess.run(["bash", SCRIPT, *(["--global"] if glob else []), *args], env=env, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, check=True).stdout


def tree(home):
    out = []
    for root, dirs, files in os.walk(home):
        for name in dirs + files:
            path = os.path.join(root, name)
            if os.path.islink(path):
                state = ("link", os.readlink(path))
            elif os.path.isfile(path):
                state = ("file", open(path, "rb").read(), os.stat(path).st_mode)
            else:
                state = ("dir", os.stat(path).st_mode)
            out.append((os.path.relpath(path, home), state))
    return sorted(out)


def agent_root(home, root, filename, text=""):
    """An agent folder as npx skills leaves it: a skills folder holding a link into ~/.agents/skills."""
    skills = os.path.join(home, root, "skills")
    os.makedirs(skills)
    os.symlink(os.path.relpath(os.path.join(home, ".agents", "skills", "x"), skills), os.path.join(skills, "x"))
    path = os.path.join(home, root, filename)
    with open(path, "w") as f:
        f.write(text)
    return path


class LinkSkillsGlobal(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        # Resolved, because macOS temp folders sit under /var, a link to /private/var, and relative links
        # built from the /var spelling climb out of /private. A real HOME has no such link in its path.
        self.home = os.path.realpath(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_dry_run_on_an_empty_home_changes_nothing(self):
        for glob in (True, False):
            run(self.home, "--dry-run", glob=glob)
            self.assertEqual(tree(self.home), [], f"--global={glob}")

    def test_dry_run_on_a_configured_home_changes_nothing(self):
        agent_root(self.home, ".gemini", "GEMINI.md", "# Mine\n")
        before = tree(self.home)
        for glob in (True, False):
            run(self.home, "--dry-run", glob=glob)
            self.assertEqual(tree(self.home), before, f"--global={glob}")

    def test_gemini_and_goose_get_each_section_once(self):
        gemini = agent_root(self.home, ".gemini", "GEMINI.md")
        goose = agent_root(self.home, os.path.join(".config", "goose"), ".goosehints")
        run(self.home)
        run(self.home)
        for path in (gemini, goose):
            text = open(path).read()
            for marker in MARKERS:
                self.assertEqual(text.count(marker), 1, f"{marker} in {path}")

    def test_an_agents_md_reachable_by_two_spellings_gets_each_section_once(self):
        path = agent_root(self.home, os.path.join(".pi", "agent"), "AGENTS.md")
        run(self.home)
        text = open(path).read()
        for marker in MARKERS:
            self.assertEqual(text.count(marker), 1, marker)

    def test_the_split_is_linked_and_a_real_file_there_is_kept(self):
        run(self.home)
        link = os.path.join(self.home, ".agents", "poteto-mode-split.md")
        self.assertEqual(os.path.realpath(link), os.path.realpath(os.path.join(REPO, "config", "poteto-mode-split.md")))

        os.remove(link)
        with open(link, "w") as f:
            f.write("mine\n")
        run(self.home)
        self.assertFalse(os.path.islink(link))
        self.assertEqual(open(link).read(), "mine\n")

    def test_an_install_without_markers_is_not_appended_again(self):
        sections = open(SNIPPET).read()
        unmarked = "\n".join(line for line in sections.splitlines() if not line.startswith("<!-- way-of-working-snippet:"))
        path = agent_root(self.home, ".gemini", "GEMINI.md", unmarked + "\n")
        run(self.home)
        self.assertEqual(open(path).read(), unmarked + "\n")


if __name__ == "__main__":
    unittest.main()
