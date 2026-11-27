#!/usr/bin/env python3
"""Tests for install.py, the relate-project-memory installer.

Each test installs into a fresh git repository in a temporary folder. The last
test also runs the installed test_memory.py there, so the templates are tested
as a project would run them. Its Relate tests skip where relate is missing.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
INSTALL = os.path.join(HERE, "install.py")
TEMPLATES = os.path.join(os.path.dirname(HERE), "templates")
LINK = "../../../.agents/skills/project-memory/SKILL.md"
TOOL_FILES = ("scripts/memory.sh", "scripts/memory/schema.cypher", "scripts/memory/remember.cypher",
              "tests/test_memory.py")


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

    def write(self, rel, text):
        os.makedirs(os.path.dirname(self.path(rel)) or self.repo, exist_ok=True)
        with open(self.path(rel), "w", encoding="utf-8") as fh:
            fh.write(text)

    def snapshot(self):
        # Folders count too, so a run that only creates an empty folder is caught.
        state = {}
        for root, dirs, files in os.walk(self.repo):
            if ".git" in dirs:
                dirs.remove(".git")
            for name in dirs + files:
                full = os.path.join(root, name)
                rel = os.path.relpath(full, self.repo)
                if os.path.islink(full):
                    state[rel] = ("link", os.readlink(full))
                elif os.path.isdir(full):
                    state[rel] = ("dir",)
                else:
                    with open(full, "rb") as fh:
                        state[rel] = (oct(os.stat(full).st_mode & 0o777), fh.read())
        return state

    def adapt(self):
        skill = self.read(".agents/skills/project-memory/SKILL.md")
        start = skill.index("<!-- ADAPT")
        end = skill.index("-->", start) + 3
        self.write(".agents/skills/project-memory/SKILL.md", skill[:start] + "Customer names stay out." + skill[end:])
        self.write("AGENTS.md", "Read memory with `scripts/memory.sh brief`.\n")

    def test_fresh_install_creates_every_file(self):
        self.install()
        for rel in TOOL_FILES + (".agents/skills/project-memory/SKILL.md",):
            self.assertTrue(os.path.isfile(self.path(rel)), rel)
        self.assertTrue(os.access(self.path("scripts/memory.sh"), os.X_OK))
        link = self.path(".claude/skills/project-memory/SKILL.md")
        self.assertEqual(os.readlink(link), "../../../.agents/skills/project-memory/SKILL.md")
        self.assertEqual(os.path.realpath(link), os.path.realpath(self.path(".agents/skills/project-memory/SKILL.md")))
        skill = self.read(".agents/skills/project-memory/SKILL.md")
        self.assertIn("(D1)", skill)
        self.assertIn("only in `docs/decisions.md`", skill)
        self.assertNotRegex(skill, r"\{\{[^{}]+\}\}")
        hooks = json.loads(self.read(".claude/settings.json"))["hooks"]["SessionStart"]
        self.assertIn("scripts/memory.sh brief", hooks[0]["hooks"][0]["command"])
        self.assertEqual(json.loads(self.read(".gemini/settings.json"))["context"]["fileName"], ["AGENTS.md"])
        ignore = self.read(".gitignore").splitlines()
        self.assertIn(".relate-memory/", ignore)
        self.assertIn(".relate-memory.*", ignore)

    def test_decision_ref_is_escaped_inside_the_example_json(self):
        p = self.run_install("--decision-ref", 'D1 "quoted" \\ path', "--decision-records", "`docs/x.md`")
        self.assertEqual(p.returncode, 0, p.stderr)
        skill = self.read(".agents/skills/project-memory/SKILL.md")
        example = skill.split("<<'JSON'\n", 1)[1].split("\nJSON\n", 1)[0]
        episode = json.loads(example)
        self.assertIn('D1 "quoted" \\ path', episode["episode"]["text"])

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

    def test_refusals_change_nothing(self):
        cases = {
            "a clash on one file while others are missing": (
                lambda: self.write("scripts/memory/remember.cypher", "local\n"), ["--decision-ref", "D1", "--decision-records", "x"], 1),
            "missing decision arguments": (lambda: None, [], 2),
            "unreadable Claude settings": (
                lambda: self.write(".claude/settings.json", "{not json"), ["--decision-ref", "D1", "--decision-records", "x"], 2),
            "Claude hooks of the wrong shape": (
                lambda: self.write(".claude/settings.json", '{"hooks": {"SessionStart": [{"hooks": [{"command": null}]}]}}'),
                ["--decision-ref", "D1", "--decision-records", "x"], 2),
            "Claude hooks that are not an object": (
                lambda: self.write(".claude/settings.json", '{"hooks": null}'), ["--decision-ref", "D1", "--decision-records", "x"], 2),
            "Gemini context of the wrong shape": (
                lambda: self.write(".gemini/settings.json", '{"context": {"fileName": [1]}}'),
                ["--decision-ref", "D1", "--decision-records", "x"], 2),
            "a symlinked .claude/skills folder": (
                lambda: (os.makedirs(self.path(".agents/skills")), os.makedirs(self.path(".claude")),
                         os.symlink("../.agents/skills", self.path(".claude/skills"))),
                ["--decision-ref", "D1", "--decision-records", "x"], 2),
            "a symlinked scripts folder": (
                lambda: (os.makedirs(os.path.join(self.tmp.name, "elsewhere"), exist_ok=True),
                         os.symlink(os.path.join(self.tmp.name, "elsewhere"), self.path("scripts"))),
                ["--decision-ref", "D1", "--decision-records", "x"], 2),
            "a symlinked .gitignore": (
                lambda: (open(os.path.join(self.tmp.name, "ignore"), "w").close(),
                         os.symlink(os.path.join(self.tmp.name, "ignore"), self.path(".gitignore"))),
                ["--decision-ref", "D1", "--decision-records", "x"], 2),
            "unreadable Gemini settings": (
                lambda: self.write(".gemini/settings.json", "[1, 2]"), ["--decision-ref", "D1", "--decision-records", "x"], 2),
        }
        for name, (prepare, args, code) in cases.items():
            with self.subTest(name):
                shutil.rmtree(self.repo)
                subprocess.run(["git", "init", "-q", self.repo], env=git_env(), check=True)
                os.makedirs(self.path("tests"))
                prepare()
                before = self.snapshot()
                p = self.run_install(*args)
                self.assertEqual(p.returncode, code, p.stdout + p.stderr)
                self.assertEqual(self.snapshot(), before)

    def test_file_modes_follow_the_execute_bit_not_the_umask(self):
        self.install()
        for rel in TOOL_FILES:
            os.chmod(self.path(rel), 0o775 if rel.endswith(".sh") else 0o664)
        self.adapt()
        p = self.install()
        self.assertIn("nothing to change", p.stdout)
        self.assertEqual(self.run_install("--check").returncode, 0)
        os.chmod(self.path("scripts/memory.sh"), 0o644)
        p = self.run_install("--check")
        self.assertEqual(p.returncode, 1)
        self.assertIn("execute bit should be set", p.stderr)

    def test_existing_settings_are_merged_and_keep_their_mode(self):
        self.write(".claude/settings.json", json.dumps({
            "permissions": {"allow": ["Bash(ls)"]},
            "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "echo hi"}]}]}}))
        os.chmod(self.path(".claude/settings.json"), 0o600)
        self.write(".gemini/settings.json", json.dumps({"theme": "dark", "context": {"fileName": "GEMINI.md"}}))
        self.write(".gitignore", "node_modules/\n/.relate-memory/")
        self.install()
        claude = json.loads(self.read(".claude/settings.json"))
        self.assertEqual(claude["permissions"], {"allow": ["Bash(ls)"]})
        commands = [h["command"] for g in claude["hooks"]["SessionStart"] for h in g["hooks"]]
        self.assertEqual((commands[0], len(commands)), ("echo hi", 2))
        self.assertEqual(os.stat(self.path(".claude/settings.json")).st_mode & 0o777, 0o600)
        gemini = json.loads(self.read(".gemini/settings.json"))
        self.assertEqual((gemini["theme"], gemini["context"]["fileName"]), ("dark", ["GEMINI.md", "AGENTS.md"]))
        self.assertEqual(self.read(".gitignore"), "node_modules/\n/.relate-memory/\n.relate-memory.*\n")

    def test_one_combined_gitignore_pattern_is_enough(self):
        self.write(".gitignore", ".relate-memory*\n")
        self.install()
        self.assertEqual(self.read(".gitignore"), ".relate-memory*\n")

    def test_empty_gemini_file_name_becomes_agents_md(self):
        self.write(".gemini/settings.json", '{"context": {"fileName": ""}}')
        self.install()
        self.assertEqual(json.loads(self.read(".gemini/settings.json"))["context"]["fileName"], ["AGENTS.md"])

    def test_a_cp_copy_of_the_test_template_is_accepted(self):
        shutil.copy(os.path.join(TEMPLATES, "test_memory.py"), self.path("tests/test_memory.py"))
        p = self.install()
        self.assertNotIn("tests/test_memory.py", p.stdout)

    def test_gemini_keeps_an_existing_gemini_md(self):
        self.write("GEMINI.md", "# Gemini\n")
        self.install()
        self.assertEqual(json.loads(self.read(".gemini/settings.json"))["context"]["fileName"],
                         ["GEMINI.md", "AGENTS.md"])

    def test_changed_tool_file_needs_update(self):
        self.install()
        with open(self.path("scripts/memory.sh"), "a") as fh:
            fh.write("# local edit\n")
        p = self.run_install()
        self.assertEqual(p.returncode, 1)
        self.assertIn("scripts/memory.sh", p.stderr)
        self.assertIn("--update", p.stderr)
        p = self.run_install("--update")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("replace scripts/memory.sh", p.stdout)
        with open(os.path.join(TEMPLATES, "memory.sh")) as fh:
            self.assertEqual(self.read("scripts/memory.sh"), fh.read())

    def test_update_touches_only_tool_files(self):
        self.install()
        self.write(".claude/settings.json", json.dumps({"hooks": {"SessionStart": [
            {"hooks": [{"type": "command", "command": "tools/wrapper.sh"}]}]}}))
        self.write(".gemini/settings.json", "{}")
        self.write(".gitignore", "/memory-store/\n")
        os.remove(self.path(".claude/skills/project-memory/SKILL.md"))
        with open(self.path(".agents/skills/project-memory/SKILL.md"), "a") as fh:
            fh.write("\nProject rule.\n")
        with open(self.path("scripts/memory.sh"), "a") as fh:
            fh.write("# drift\n")
        project = {k: v for k, v in self.snapshot().items() if not k.startswith(("scripts", "tests"))}
        p = self.run_install("--update")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout.strip(), "replace scripts/memory.sh")
        after = {k: v for k, v in self.snapshot().items() if not k.startswith(("scripts", "tests"))}
        self.assertEqual(after, project)

    def test_symlinked_tool_file_is_refused_and_its_target_untouched(self):
        outside = os.path.join(self.tmp.name, "outside.sh")
        with open(outside, "w") as fh:
            fh.write("keep me\n")
        os.makedirs(self.path("scripts"))
        os.symlink(outside, self.path("scripts/memory.sh"))
        p = self.run_install("--update")
        self.assertEqual(p.returncode, 2)
        self.assertIn("is a symlink", p.stderr)
        with open(outside) as fh:
            self.assertEqual(fh.read(), "keep me\n")

    def test_check_passes_only_when_installed_current_and_adapted(self):
        self.install()
        self.adapt()
        self.assertEqual(self.run_install("--check").returncode, 0)
        skill = ".agents/skills/project-memory/SKILL.md"
        link = ".claude/skills/project-memory/SKILL.md"
        breaks = {
            "missing or not a plain file": lambda: os.remove(self.path("scripts/memory/schema.cypher")),
            "differs from the skill's template": lambda: open(self.path("tests/test_memory.py"), "a").write("# drift\n"),
            "execute bit should be set": lambda: os.chmod(self.path("scripts/memory.sh"), 0o644),
            f"{skill}: missing": lambda: os.remove(self.path(skill)),
            "still holds an ADAPT marker": lambda: open(self.path(skill), "a").write("<!-- ADAPT: x -->\n"),
            "still holds a {{placeholder}}": lambda: open(self.path(skill), "a").write("See {{lower_case1}}.\n"),
            "not the relative link": lambda: (os.remove(self.path(link)), os.symlink(self.path(skill), self.path(link))),
            "a symlink, not a folder ": lambda: (shutil.rmtree(self.path(".claude/skills")),
                                                 os.makedirs(self.path("other/project-memory")),
                                                 os.symlink(LINK, self.path("other/project-memory/SKILL.md")),
                                                 os.symlink("../other", self.path(".claude/skills"))),
            "a symlink, not a folder": lambda: (shutil.rmtree(self.path(".claude/skills/project-memory")),
                                                os.symlink(self.path(".agents/skills/project-memory"),
                                                           self.path(".claude/skills/project-memory"))),
            "AGENTS.md: missing or does not mention": lambda: self.write("AGENTS.md", "No pointer here.\n"),
        }
        for message, damage in breaks.items():
            with self.subTest(message):
                shutil.rmtree(self.repo)
                subprocess.run(["git", "init", "-q", self.repo], env=git_env(), check=True)
                os.makedirs(self.path("tests"))
                self.install()
                self.adapt()
                damage()
                p = self.run_install("--check")
                self.assertEqual(p.returncode, 1, message)
                self.assertIn(message.strip(), p.stderr)

    def test_refuses_a_folder_that_is_not_a_repo_root(self):
        p = subprocess.run([sys.executable, INSTALL, os.path.join(self.repo, "tests")],
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 2)
        self.assertIn("not the root of a git repository", p.stderr)

    def test_installed_memory_tests_pass_in_the_project(self):
        self.install()
        env = git_env()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        p = subprocess.run([sys.executable, "-m", "unittest", "-v", "tests.test_memory"], cwd=self.repo,
                           env=env, capture_output=True, text=True, timeout=600)
        self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-4000:])
        ran = re.search(r"^Ran (\d+) tests?", p.stderr, re.MULTILINE)
        self.assertIsNotNone(ran, p.stderr[-500:])
        self.assertEqual(int(ran.group(1)), 38)
        skipped = re.search(r"skipped=(\d+)", p.stderr)
        if shutil.which("relate"):
            self.assertIsNone(skipped, "relate is installed, so no memory test may skip")
        else:
            self.assertEqual(int(skipped.group(1)), 30)


if __name__ == "__main__":
    unittest.main()
