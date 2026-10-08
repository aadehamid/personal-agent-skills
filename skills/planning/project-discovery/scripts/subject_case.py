"""Emit only a subject's case prompt. Keep grading criteria outside its context."""

import argparse
import json
from pathlib import Path


CASES = Path(__file__).resolve().parents[1] / 'evals' / 'cases.json'


def subject_prompt(case_id: str, cases_path: Path = CASES) -> str:
    cases = json.loads(cases_path.read_text(encoding='utf-8'))['cases']
    matches = [case for case in cases if case['id'] == case_id]
    if len(matches) != 1:
        raise ValueError(f'Expected one case named {case_id!r}, found {len(matches)}')
    return matches[0]['prompt']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case_id')
    args = parser.parse_args()
    try:
        print(subject_prompt(args.case_id))
    except ValueError as error:
        parser.exit(2, f'{error}\n')
