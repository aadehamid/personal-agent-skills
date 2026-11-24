#!/usr/bin/env python3
"""Tests for guard-check-running.py against a real running scripts/check.sh.

Each test makes a temporary repository folder whose scripts/check.sh changes to the folder's top level and
sleeps, starts it as bash would, and feeds the guard the JSON a Claude Code PreToolUse hook receives.
"""
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
GUARD = os.path.join(HERE, "guard-check-running.py")

CHECK_SH = textwrap.dedent('''\
    #!/usr/bin/env bash
    cd "$(dirname "$0")/.."
    sleep 60
''')


def guard(event):
    data = event if isinstance(event, str) else json.dumps(event)
    return subprocess.run([sys.executable, GUARD], input=data, capture_output=True, text=True, timeout=60)


class GuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = os.path.realpath(self.tmp.name)
        self.repo = os.path.join(base, "repo")
        self.other = os.path.join(base, "repo-other")
        for folder in (self.repo, self.other):
            os.makedirs(os.path.join(folder, "scripts"))
            path = os.path.join(folder, "scripts", "check.sh")
            with open(path, "w") as f:
                f.write(CHECK_SH)
            os.chmod(path, 0o755)

    def start_check(self, folder, *command):
        proc = subprocess.Popen(list(command) or ["bash", "scripts/check.sh"], cwd=folder)
        self.addCleanup(proc.wait)
        self.addCleanup(proc.kill)
        time.sleep(0.5)                  # let the script reach its cd
        return proc

    def edit(self, path, tool="Edit", key="file_path", cwd=None):
        event = {"tool_name": tool, "tool_input": {key: path}}
        if cwd:
            event["cwd"] = cwd
        return guard(event)

    def test_an_edit_inside_a_running_check_is_refused(self):
        proc = self.start_check(self.repo)
        result = self.edit(os.path.join(self.repo, "src", "a.py"))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn(f"scripts/check.sh is running in {self.repo}", result.stderr)
        self.assertIn(f"process {proc.pid}", result.stderr)

    def test_write_and_notebook_edits_are_refused_too(self):
        self.start_check(self.repo)
        self.assertEqual(self.edit(os.path.join(self.repo, "new.md"), tool="Write").returncode, 2)
        self.assertEqual(self.edit(os.path.join(self.repo, "n.ipynb"), tool="NotebookEdit",
                                   key="notebook_path").returncode, 2)

    def test_a_relative_path_is_read_against_the_event_cwd(self):
        self.start_check(self.repo)
        self.assertEqual(self.edit("src/a.py", cwd=self.repo).returncode, 2)
        self.assertEqual(self.edit("src/a.py", cwd=self.other).returncode, 0)

    def test_the_check_started_by_path_or_by_another_shell_is_seen(self):
        self.start_check(self.repo, "./scripts/check.sh")
        self.assertEqual(self.edit(os.path.join(self.repo, "a")).returncode, 2)

    def test_a_folder_whose_name_starts_with_the_running_one_is_allowed(self):
        self.start_check(self.repo)
        self.assertEqual(self.edit(os.path.join(self.other, "a.py")).returncode, 0)

    def test_an_edit_elsewhere_is_allowed(self):
        self.start_check(self.repo)
        self.assertEqual(self.edit(os.path.join(os.path.dirname(self.repo), "notes.md")).returncode, 0)

    def test_an_edit_is_allowed_once_the_check_has_ended(self):
        proc = self.start_check(self.repo)
        proc.kill()
        proc.wait()
        self.assertEqual(self.edit(os.path.join(self.repo, "a.py")).returncode, 0)

    def test_a_process_that_only_names_check_sh_is_not_a_check(self):
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)", "scripts/check.sh"],
                                cwd=self.repo)
        self.addCleanup(proc.wait)
        self.addCleanup(proc.kill)
        time.sleep(0.3)
        self.assertIsNone(proc.poll(), "the stand-in process must still be running")
        self.assertEqual(self.edit(os.path.join(self.repo, "a.py")).returncode, 0)

    def test_input_it_cannot_read_never_blocks(self):
        self.start_check(self.repo)
        for event in ("not json", json.dumps({"tool_input": {}}), json.dumps([1]), json.dumps({"tool_input": 3})):
            self.assertEqual(guard(event).returncode, 0, event)


if __name__ == "__main__":
    unittest.main()
