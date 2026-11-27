#!/usr/bin/env python3
"""Tests for install.py, the relate-project-memory installer.

Each test installs into a fresh git repository in a temporary folder. The last
test also runs the installed test_memory.py there, so the templates are tested
as a project would run them. Its Relate tests skip where relate is missing.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
INSTALL = os.path.join(HERE, "install.py")
TEMPLATES = os.path.join(os.path.dirname(HERE), "templates")


def git_env():
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_") and k != "PROJECT_MEMORY_DB"}


class Installer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = os.path.join(self.tmp.name, "repo")
        subprocess.run(["git", "init", "-q", self.repo], env=git_env(), check=True)
        os.makedirs(os.path.join(self.repo, "tests"))

    def tearDown(self):
        self.tmp.cleanup()

    def run_install(self, *args):
        return subprocess.run([sys.executable, INSTALL, self.repo, *args], env=git_env(),
                              capture_output=True, text=True, timeout=60)

    def install(self, *extra):
        p = self.run_install("--decision-ref", "D1", "--decision-records", "`docs/decisions.md`", *extra)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p

    def path(self, rel):
        return os.path.join(self.repo, rel)

    def read(self, rel):
        with open(self.path(rel), encoding="utf-8") as fh:
            return fh.read()

    def snapshot(self):
        state = {}
        for root, dirs, files in os.walk(self.repo):
            dirs[:] = [d for d in dirs if d != ".git"]
            for name in files + [d for d in dirs if os.path.islink(os.path.join(root, d))]:
                full = os.path.join(root, name)
                rel = os.path.relpath(full, self.repo)
                if os.path.islink(full):
                    state[rel] = ("link", os.readlink(full))
                else:
                    with open(full, "rb") as fh:
                        state[rel] = (oct(os.stat(full).st_mode & 0o777), fh.read())
        return state

    def test_fresh_install_creates_every_file(self):
        self.install()
        for rel in ("scripts/memory.sh", "scripts/memory/schema.cypher", "scripts/memory/remember.cypher",
                    "tests/test_memory.py", ".agents/skills/project-memory/SKILL.md"):
            self.assertTrue(os.path.isfile(self.path(rel)), rel)
        self.assertTrue(os.access(self.path("scripts/memory.sh"), os.X_OK))
        link = self.path(".claude/skills/project-memory/SKILL.md")
        self.assertTrue(os.path.islink(link))
        self.assertEqual(os.path.realpath(link), os.path.realpath(self.path(".agents/skills/project-memory/SKILL.md")))
        skill = self.read(".agents/skills/project-memory/SKILL.md")
        self.assertIn("(D1)", skill)
        self.assertIn("only in `docs/decisions.md`", skill)
        self.assertNotRegex(skill, r"\{\{[A-Z_]+\}\}")
        hooks = json.loads(self.read(".claude/settings.json"))["hooks"]["SessionStart"]
        self.assertIn("scripts/memory.sh brief", hooks[0]["hooks"][0]["command"])
        self.assertEqual(json.loads(self.read(".gemini/settings.json"))["context"]["fileName"], ["AGENTS.md"])
        ignore = self.read(".gitignore").splitlines()
        self.assertIn(".relate-memory/", ignore)
        self.assertIn(".relate-memory.*", ignore)

    def test_tests_go_to_scripts_when_there_is_no_tests_folder(self):
        os.rmdir(self.path("tests"))
        self.install()
        self.assertTrue(os.path.isfile(self.path("scripts/test_memory.py")))

    def test_second_install_changes_nothing(self):
        self.install()
        before = self.snapshot()
        p = self.install()
        self.assertIn("nothing to change", p.stdout)
        self.assertEqual(self.snapshot(), before)

    def test_dry_run_changes_nothing(self):
        before = self.snapshot()
        p = self.run_install("--decision-ref", "D1", "--decision-records", "x", "--dry-run")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("would write scripts/memory.sh", p.stdout)
        self.assertEqual(self.snapshot(), before)

    def test_existing_settings_are_merged_not_replaced(self):
        os.makedirs(self.path(".claude"))
        with open(self.path(".claude/settings.json"), "w") as fh:
            json.dump({"permissions": {"allow": ["Bash(ls)"]},
                       "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "echo hi"}]}]}}, fh)
        os.makedirs(self.path(".gemini"))
        with open(self.path(".gemini/settings.json"), "w") as fh:
            json.dump({"theme": "dark", "context": {"fileName": "GEMINI.md"}}, fh)
        with open(self.path(".gitignore"), "w") as fh:
            fh.write("node_modules/\n.relate-memory/")
        self.install()
        claude = json.loads(self.read(".claude/settings.json"))
        self.assertEqual(claude["permissions"], {"allow": ["Bash(ls)"]})
        commands = [h["command"] for g in claude["hooks"]["SessionStart"] for h in g["hooks"]]
        self.assertEqual(commands[0], "echo hi")
        self.assertEqual(len(commands), 2)
        gemini = json.loads(self.read(".gemini/settings.json"))
        self.assertEqual(gemini["theme"], "dark")
        self.assertEqual(gemini["context"]["fileName"], ["GEMINI.md", "AGENTS.md"])
        ignore = self.read(".gitignore").splitlines()
        self.assertEqual(ignore.count(".relate-memory/"), 1)
        self.assertIn(".relate-memory.*", ignore)
        self.assertIn("node_modules/", ignore)

    def test_gemini_keeps_an_existing_gemini_md(self):
        with open(self.path("GEMINI.md"), "w") as fh:
            fh.write("# Gemini\n")
        self.install()
        self.assertEqual(json.loads(self.read(".gemini/settings.json"))["context"]["fileName"],
                         ["GEMINI.md", "AGENTS.md"])

    def test_changed_tool_file_needs_update_and_project_files_are_kept(self):
        self.install()
        with open(self.path("scripts/memory.sh"), "a") as fh:
            fh.write("# local edit\n")
        with open(self.path(".agents/skills/project-memory/SKILL.md"), "a") as fh:
            fh.write("\nProject rule.\n")
        p = self.run_install()
        self.assertEqual(p.returncode, 1)
        self.assertIn("scripts/memory.sh", p.stderr)
        self.assertIn("--update", p.stderr)
        p = self.run_install("--update")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("replace scripts/memory.sh", p.stdout)
        with open(os.path.join(TEMPLATES, "memory.sh")) as fh:
            self.assertEqual(self.read("scripts/memory.sh"), fh.read())
        self.assertTrue(self.read(".agents/skills/project-memory/SKILL.md").endswith("Project rule.\n"))

    def test_update_on_a_repo_without_a_project_skill_needs_the_decision(self):
        p = self.run_install("--update")
        self.assertEqual(p.returncode, 2)
        self.assertIn("--decision-ref", p.stderr)

    def test_check_reports_each_gap_until_adapted(self):
        self.install()
        p = self.run_install("--check")
        self.assertEqual(p.returncode, 1)
        self.assertIn("ADAPT marker", p.stderr)
        self.assertIn("AGENTS.md: does not mention scripts/memory.sh", p.stderr)
        skill = self.read(".agents/skills/project-memory/SKILL.md")
        start = skill.index("<!-- ADAPT")
        end = skill.index("-->", start) + 3
        with open(self.path(".agents/skills/project-memory/SKILL.md"), "w") as fh:
            fh.write(skill[:start] + "Customer names stay out." + skill[end:])
        with open(self.path("AGENTS.md"), "w") as fh:
            fh.write("Read memory with `scripts/memory.sh brief`.\n")
        p = self.run_install("--check")
        self.assertEqual(p.returncode, 0, p.stderr)
        with open(self.path("tests/test_memory.py"), "a") as fh:
            fh.write("# drift\n")
        p = self.run_install("--check")
        self.assertEqual(p.returncode, 1)
        self.assertIn("tests/test_memory.py: differs", p.stderr)

    def test_refuses_a_folder_that_is_not_a_repo_root(self):
        p = subprocess.run([sys.executable, INSTALL, os.path.join(self.repo, "tests")],
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 2)
        self.assertIn("not the root of a git repository", p.stderr)

    def test_installed_memory_tests_pass_in_the_project(self):
        self.install()
        env = git_env()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        p = subprocess.run([sys.executable, "-m", "unittest", "-q", "tests.test_memory"], cwd=self.repo,
                           env=env, capture_output=True, text=True, timeout=600)
        self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-4000:])
        self.assertIn("OK", p.stderr)


if __name__ == "__main__":
    unittest.main()
