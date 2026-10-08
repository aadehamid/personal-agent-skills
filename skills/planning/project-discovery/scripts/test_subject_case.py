"""Test the prompt-only handoff, including deliberately sensitive grading text."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from subject_case import subject_prompt


class SubjectCaseTests(unittest.TestCase):
    def test_subject_receives_prompt_without_grader_material(self):
        with tempfile.TemporaryDirectory() as directory:
            cases = Path(directory) / 'cases.json'
            cases.write_text(json.dumps({'cases': [{
                'id': 'sample', 'kind': 'behavior', 'prompt': 'Organize this project.',
                'expected': ['SECRET_GRADING_TEXT'], 'grader_notes': 'SECRET_NOTES',
            }]}))
            self.assertEqual(subject_prompt('sample', cases), 'Organize this project.')

    def test_missing_and_duplicate_cases_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            cases = Path(directory) / 'cases.json'
            for entries in [[], [{'id': 'sample', 'prompt': 'one'}] * 2]:
                cases.write_text(json.dumps({'cases': entries}))
                with self.assertRaises(ValueError):
                    subject_prompt('sample', cases)

    def test_command_emits_actual_prompt_and_rejects_unknown_case(self):
        script = Path(__file__).with_name('subject_case.py')
        result = subprocess.run([sys.executable, str(script), 'existing-project-organization'],
                                capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout, subject_prompt('existing-project-organization') + '\n')
        missing = subprocess.run([sys.executable, str(script), 'missing'],
                                 capture_output=True, text=True)
        self.assertEqual(missing.returncode, 2)
        self.assertEqual(missing.stdout, '')


if __name__ == '__main__':
    unittest.main()
