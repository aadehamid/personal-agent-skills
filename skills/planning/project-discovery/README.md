# project-discovery

Turn an idea into a researched documentation package, or organize and update
an existing project's documents and repository layout.

The skill supports interactive discovery and batch drafting. It preserves approved
decisions, labels new proposals, and records implementation gates. It can assess a
reference repository without copying its architecture or assuming that planned
components are implemented.

## Use

Invoke `project-discovery` through your agent's skill interface or ask it to use
the skill. Supply the project idea, repository or existing documents, optional
reference projects, constraints, and preferred review mode. Missing information
remains unknown until discovered or resolved.

Example:

> Use project-discovery for a volunteer scheduling application. Inspect this
> repository first. Ask the important questions, propose the needed documents,
> and keep changes local. Do not select a hosting provider yet.

For an existing project:

> Use project-discovery to organize this repository's existing documentation.
> Inventory it first, preserve approved decisions, and add only missing content.
> Assess the reference layout and stack where they meet this project's needs.
> Work in batch, keep a log, and open a PR. Do not merge it.

To work unattended, explicitly request batch drafting and state the delivery
permission separately. For example, ask for all agreed drafts without pauses
but no commits, or separately authorize a commit and PR.

## What is configurable

Project names, reference repositories, domain, stack, models, providers, hosting,
licensing, data sources, document count, paths, and publishing are not preset.
Interactive drafting and local output are conservative defaults.
Evidence, approval integrity, and permission boundaries are fixed safeguards.

The skill uses `grilling`, `domain-modeling`, and `clear-writing` when available.
Missing helpers have an explicit fallback and do not trigger automatic installation.
It does not build the application, deploy infrastructure, or approve its own designs.

## Files

| File | Reader | Purpose |
| --- | --- | --- |
| `SKILL.md` | Agent | Activation, outcome, permissions, operating modes, and completion |
| `references/discovery.md` | Agent during discovery/research | Context, reference inspection, source research, and questions |
| `references/existing-projects.md` | Agent organizing an existing project | Inventory, consolidation, moves, history, and gap assessment |
| `references/documentation.md` | Agent before package drafting | Tailored documents, authority, state, evaluation, and batch behavior |
| `references/review-and-handoff.md` | Agent before delivery | Review, verification, optional publication, and resumption |
| `assets/record-templates.md` | Agent creating records | Adaptable field shapes, not fixed project documents |
| `README.md` | People | Usage, file map, and status |
| `SOURCES.md` | Maintainers | Provenance and update checks |
| `evals/cases.json` | Evaluator | Activation, main-path, restraint, and resumption cases |
| `evals/README.md` | Evaluator | Fresh-context execution and grading procedure |
| `scripts/validate.py` | Maintainer/CI | Standard-library mechanical checks |
| `scripts/subject_case.py` | Evaluator | Export a prompt without grading criteria |
| `scripts/test_subject_case.py` | Maintainer/CI | Verify prompt isolation and command failures |
| `scripts/test_validate.py` | Maintainer/CI | Regression tests for the validator |
| `scripts/make_fixture.py` | Evaluator | Original disposable project for file-tool behavior checks |
| `evals/RESULTS.md` | People | Observed validation and independent review results, including limits |

## Validate

From this skill directory:

```sh
python3 scripts/validate.py
python3 scripts/test_validate.py
```

Behavioral evaluation is separate from these checks. See `evals/README.md`.

## Status

Initial implementation. Generic record shapes and conditional references are
present. No project-specific technology or reference repository is built in.
Read `evals/RESULTS.md` for tested behavior and host limitations.

Install using the repository's existing `scripts/link-skills.sh`. The installer
discovers existing agent directories; rerun it after installing a new agent.
New agent sessions may be needed to refresh a cached skill catalog.
