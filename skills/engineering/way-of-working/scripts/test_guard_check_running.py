#!/usr/bin/env python3
"""Tests for guard-check-running.py against real running check scripts.

Each test makes temporary repository folders whose scripts/check.sh changes to / (so the check's working
directory says nothing about its repository) and sleeps. A test starts it the way people and hooks do, in its own
process group with no inherited output, and feeds the guard the JSON a Claude Code PreToolUse hook receives.
Each refusal is asserted to name the test's own repository, so a check.sh running around the tests (the
repository's own) cannot make a test pass.
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
GUARD = os.path.join(HERE, "guard-check-running.py")
# A direct shebang: a script run from it is named after the script, not the shell, on Linux.
CHECK_SH = "#!/bin/bash\ncd /\nsleep 60\n"


def guard(event):
    data = event if isinstance(event, str) else json.dumps(event)
    return subprocess.run([sys.executable, GUARD], input=data, capture_output=True, text=True, timeout=60)


class GuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = os.path.realpath(self.tmp.name)
        # Long, with spaces: a process table cuts such a command line short, and a split on spaces breaks it.
        self.repo = self.make_repo("a repository whose path is long enough to pass eighty columns on its own")
        self.other = self.repo + "-other"
        self.make_repo(os.path.basename(self.other))

    def make_repo(self, name):
        folder = os.path.join(self.base, name)
        os.makedirs(os.path.join(folder, "scripts"))
        path = os.path.join(folder, "scripts", "check.sh")
        with open(path, "w") as f:
            f.write(CHECK_SH)
        os.chmod(path, 0o755)
        return folder

    def start(self, command, cwd=None):
        proc = subprocess.Popen(command, cwd=cwd or self.base, stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        self.addCleanup(self.stop, proc)
        time.sleep(0.5)
        self.assertIsNone(proc.poll(), "the stand-in process must still be running")
        return proc

    def stop(self, proc):
        if proc.returncode is not None:  # stopped already: its process group id may belong to someone else now
            return
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()

    def start_check(self, *command, cwd=None):
        return self.start(list(command) or ["bash", os.path.join(self.repo, "scripts", "check.sh")], cwd)

    def edit(self, path, tool="Edit", key="file_path", cwd=None):
        event = {"tool_name": tool, "tool_input": {key: path}}
        if cwd is not None:
            event["cwd"] = cwd
        return guard(event)

    def assert_refused(self, result, proc=None):
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn(f"scripts/check.sh is running in {self.repo}", result.stderr)
        if proc:
            self.assertIn(f"process {proc.pid}", result.stderr)

    def assert_allowed(self, result):
        self.assertEqual((result.returncode, result.stderr), (0, ""))

    def test_an_edit_inside_a_running_check_is_refused(self):
        proc = self.start_check()
        self.assert_refused(self.edit(os.path.join(self.repo, "src", "a.py")), proc)

    def test_write_multiedit_and_notebook_edits_are_refused_too(self):
        self.start_check()
        self.assert_refused(self.edit(os.path.join(self.repo, "new.md"), tool="Write"))
        self.assert_refused(self.edit(os.path.join(self.repo, "a.py"), tool="MultiEdit"))
        self.assert_refused(self.edit(os.path.join(self.repo, "n.ipynb"), tool="NotebookEdit", key="notebook_path"))

    def test_a_read_or_an_event_with_no_tool_name_is_allowed(self):
        self.start_check()
        self.assert_allowed(self.edit(os.path.join(self.repo, "a.py"), tool="Read"))
        self.assert_allowed(guard({"tool_input": {"file_path": os.path.join(self.repo, "a.py")}}))

    def test_every_way_of_starting_the_check_is_seen(self):
        script = os.path.join(self.repo, "scripts", "check.sh")
        ways = [["bash", "-e", "-x", script], ["bash", "--noprofile", "--norc", script], ["sh", script],
                ["./scripts/check.sh"], ["bash", "-c", f'exec "{script}"']]
        ways += [["zsh", script], ["dash", script]]
        for way in ways:
            with self.subTest(way=way):
                if not shutil.which(way[0]) and not way[0].startswith("."):
                    self.skipTest(f"{way[0]} is not installed here")
                proc = self.start_check(*way, cwd=self.repo)
                self.assert_refused(self.edit(os.path.join(self.repo, "a.py")))
                self.stop(proc)

    def test_a_relative_path_is_read_against_the_event_cwd(self):
        self.start_check()
        self.assert_refused(self.edit("src/a.py", cwd=self.repo))
        self.assert_allowed(self.edit("src/a.py", cwd=self.other))
        self.assert_allowed(self.edit("src/a.py"))         # no cwd: nothing to read it against

    def test_a_symlink_in_either_direction_is_followed(self):
        self.start_check()
        outside = os.path.join(self.base, "outside")
        os.makedirs(outside)
        os.symlink(os.path.join(outside, "file.txt"), os.path.join(self.repo, "link-out"))
        os.symlink(self.repo, os.path.join(outside, "link-in"))
        self.assert_refused(self.edit(os.path.join(self.repo, "link-out")))
        self.assert_refused(self.edit(os.path.join(outside, "link-in", "a.py")))
        self.assert_allowed(self.edit(os.path.join(outside, "file.txt")))
        os.makedirs(os.path.join(self.repo, "sub"))
        os.symlink(os.path.join(self.repo, "sub"), os.path.join(outside, "link-sub"))
        self.assert_refused(self.edit(os.path.join(outside, "link-sub", "..", "a.py")))
        self.assert_refused(self.edit(os.path.join("..", "a.py"), cwd=os.path.join(outside, "link-sub")))

    def test_the_path_is_matched_by_identity_not_by_letter_case(self):
        upper = self.repo.upper()
        if not os.path.exists(upper):
            self.skipTest("this disk tells letter case apart")
        self.start_check()
        self.assert_refused(self.edit(os.path.join(upper, "a.py")))

    def test_a_folder_whose_name_starts_with_the_running_one_is_allowed(self):
        self.start_check()
        self.assert_allowed(self.edit(os.path.join(self.other, "a.py")))

    def test_an_edit_elsewhere_is_allowed(self):
        self.start_check()
        self.assert_allowed(self.edit(os.path.join(self.base, "notes.md")))

    def test_an_edit_is_allowed_once_the_check_has_ended(self):
        proc = self.start_check()
        self.assert_refused(self.edit(os.path.join(self.repo, "a.py")))
        self.stop(proc)
        self.assert_allowed(self.edit(os.path.join(self.repo, "a.py")))

    def test_a_shell_that_only_names_check_sh_is_not_a_check(self):
        self.start(["bash", "-c", "sleep 60", os.path.join(self.repo, "scripts", "check.sh")])
        self.start([sys.executable, "-c", "import time; time.sleep(60)", "scripts/check.sh"], cwd=self.repo)
        self.assert_allowed(self.edit(os.path.join(self.repo, "a.py")))

    def test_list_prints_each_running_check_and_only_those(self):
        proc = self.start_check()
        self.start(["bash", "-c", "sleep 60", os.path.join(self.other, "scripts", "check.sh")])
        out = subprocess.run([sys.executable, GUARD, "--list"], capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0)
        self.assertIn(f"{proc.pid} {self.repo}\n", out.stdout)
        self.assertNotIn(self.other, out.stdout)

    def test_a_program_named_like_a_shell_is_not_a_check(self):
        # lsof -c sh matches every name that starts with sh. A copied system binary is killed on macOS and a
        # symlink takes its target's name, so the stand-in is a small C program built here.
        compiler = shutil.which("cc")
        if not compiler:
            self.skipTest("no C compiler here")
        source, fake = os.path.join(self.base, "holder.c"), os.path.join(self.base, "shfake")
        with open(source, "w") as f:
            f.write('#include <stdio.h>\n#include <unistd.h>\n'
                    'int main(int c, char **v) { FILE *f = fopen(v[1], "r"); if (!f) return 1; sleep(60); }\n')
        subprocess.run([compiler, "-o", fake, source], check=True, capture_output=True)
        self.start([fake, os.path.join(self.repo, "scripts", "check.sh")])
        self.assert_allowed(self.edit(os.path.join(self.repo, "a.py")))

    def test_input_it_cannot_read_never_blocks(self):
        self.start_check()
        inside = os.path.join(self.repo, "a.py")
        for event in ("not json", json.dumps([1]), json.dumps({"tool_name": "Edit", "tool_input": 3}),
                      json.dumps({"tool_name": "Edit", "tool_input": {}}),
                      json.dumps({"tool_name": "Edit", "tool_input": {"file_path": "a.py"}, "cwd": 123}),
                      json.dumps({"tool_name": "Edit", "tool_input": {"file_path": inside + "\x00b"}})):
            with self.subTest(event=event):
                self.assert_allowed(guard(event))


if __name__ == "__main__":
    unittest.main()
