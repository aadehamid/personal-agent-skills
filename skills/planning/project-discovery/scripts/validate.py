"""Mechanical skill checks. Behavioral quality requires separate fresh-context evals."""

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    required = [
        "SKILL.md", "README.md", "SOURCES.md",
        "references/discovery.md", "references/documentation.md",
        "references/review-and-handoff.md", "assets/record-templates.md",
        "evals/cases.json", "evals/README.md", "evals/RESULTS.md",
        "scripts/validate.py", "scripts/test_validate.py", "scripts/make_fixture.py",
    ]
    for name in required:
        if not (root / name).is_file():
            errors.append(f"Missing {name}")
    skill_path = root / "SKILL.md"
    skill = skill_path.read_text(encoding="utf-8") if skill_path.is_file() else ""
    front = re.match(r"\A---\n(.*?)\n---\n", skill, re.DOTALL)
    if not front:
        errors.append("Missing YAML frontmatter")
    else:
        if not re.search(r"^name: project-discovery$", front[1], re.MULTILINE):
            errors.append("Incorrect skill name")
        if not re.search(r"^description: \S.+$", front[1], re.MULTILINE):
            errors.append("Missing single-line activation description")
    for target in re.findall(r"`((?:references|assets)/[^`]+)`", skill):
        path = (root / target).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            errors.append(f"Invalid bundled reference: {target}")
    for path in root.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        name = path.relative_to(root).as_posix()
        if not text.endswith("\n"):
            errors.append(f"{name}: missing final newline")
        if any(line.rstrip() != line for line in text.splitlines()):
            errors.append(f"{name}: trailing whitespace")
        if len(re.findall(r"^```", text, re.MULTILINE)) % 2:
            errors.append(f"{name}: unclosed fence")
    runtime = [root / "SKILL.md", *(root / "references").glob("*.md"),
               *(root / "assets").glob("*.md")]
    # Portable runtime instructions must not depend on the author's machine/project.
    for path in runtime:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r"/Users/|[A-Z]:\\\\Users\\\\|worktree://|DELTA_SCRATCH_DIR|\bLIONG\b|\bPPC\b", text):
            errors.append(f"{path.name}: project or machine-specific runtime value")
    cases_path = root / "evals/cases.json"
    if cases_path.is_file():
        try:
            data = json.loads(cases_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] != 1:
                raise ValueError("expected a version-1 object")
            if set(data) != {"version", "cases"}:
                errors.append("Evaluation root has missing or unknown fields")
            cases = data.get("cases")
            if not isinstance(cases, list):
                raise ValueError("cases must be a list")
            ids = []
            kinds = {}
            for index, case in enumerate(cases):
                if not isinstance(case, dict):
                    errors.append(f"Case {index}: expected an object")
                    continue
                if set(case) != {"id", "kind", "prompt", "expected"}:
                    errors.append(f"Case {index}: missing or unknown fields")
                case_id = case.get("id")
                if not isinstance(case_id, str) or not case_id.strip():
                    errors.append(f"Case {index}: id must be a nonempty string")
                    continue
                ids.append(case_id)
                kind = case.get("kind")
                if not isinstance(kind, str) or kind not in {"activation", "behavior"}:
                    errors.append(f"{case_id}: invalid kind")
                kinds[case_id] = kind
                if not isinstance(case.get("prompt"), str) or not case["prompt"].strip():
                    errors.append(f"{case_id}: prompt must be a nonempty string")
                expected = case.get("expected")
                if (not isinstance(expected, list) or not expected
                        or any(not isinstance(item, str) or not item.strip() for item in expected)):
                    errors.append(f"{case_id}: expected must be a nonempty list of strings")
            if len(ids) != len(set(ids)):
                errors.append("Duplicate evaluation case IDs")
            for name in ("activation-positive", "activation-negative", "explicit-interactive",
                         "batch-main", "blocked-reference", "approval-resume",
                         "publishing-restraint", "repository-resume", "real-failure-regression"):
                if name not in ids:
                    errors.append(f"Missing evaluation case: {name}")
                elif kinds[name] != ("activation" if name.startswith("activation-") else "behavior"):
                    errors.append(f"{name}: kind does not match its execution contract")
        except (ValueError, KeyError, TypeError) as exc:
            errors.append(f"Invalid evaluation data: {exc}")
    return errors


if __name__ == "__main__":
    findings = validate(ROOT)
    if findings:
        print("\n".join(findings))
        raise SystemExit(1)
    print("Mechanical skill checks passed; no behavioral result implied.")
