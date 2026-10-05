# Validation record

Status: Independently reviewed; publishable with behavioral caveats.
Recorded: 2026-10-05.

## Mechanical and independent review evidence

The package validator and all 11 regression tests passed. A fresh independent
reviewer also checked unknown/missing JSON fields, Boolean version rejection,
fixture generation, and protected-file hashes. No material runtime finding remains.

Review fixes added an explicit unpersisted-output fallback, ordinary-text questions
when no question tool exists, strict evaluation schema checks, a disposable
repository-resumption case, and a pinned authoring reference.

Authoring used GPT-6-Astra in Delta; independent review used the configured reviewer
profile, reported as GPT-5.6-Sol. Claude CLI receipts identified claude-opus-5-5;
Codex CLI used its default configuration without a model override. Subjects received
the skill bundle and user prompt, not grading expectations.

## Behavioral results

| Case | Claude | Codex | Evidence limit |
| --- | --- | --- | --- |
| Positive and negative activation | Pass | Pass | Metadata routing, not native skill-menu invocation |
| Final interactive questions | Pass | Pass | Exact final runtime; Codex repeats questions in its final response |
| Batch drafting after persistence fix | Partial | Pass | Immediately preceding runtime, before the final question-interface clarification |
| Repository resumption | Pass | Pass on retry | Actual files checked; same preceding runtime |
| Real-failure restraint | Pass | Pass | Earlier runtime; detects leakage, gate order, undefined scoring, and permission conflict |

The Claude batch output expanded coordinator authority while labeling that row
confirmed; later requirements correctly labeled those additions proposed.
The independent grader retained a partial grade. The skill already states the
correct fact/proposal boundary, so no redundant rule was added to hide that miss.

Completed repository cases created only planning/data-model.md and changed only
planning/state.md and planning/index.md. Approved charter/workflow, instructions,
source placeholders, and all reference files remained byte-identical.
Both distinguished the SQLite prototype from the planned HTTP API and reported
reference tests as unexecuted. Neither published anything.

Preserved incomplete attempts: Claude interactive timed out at 220 seconds;
another returned malformed_tool_use_exhausted. The final plain-text-question
case passed on both hosts. Codex repository resumption timed out at 160 seconds
after writing only the draft; a fresh retry completed the draft, state, and index.
Incomplete attempts were not relabeled as passes.

## Reproducibility and limits

Final SKILL.md SHA-256:
`d871b39f83da848d649eb65724a013c2ed5b850699ea09121459615b53ad0fb7`.

Local raw receipts, runtime hash sets, fixture before/after hashes, and subject
outputs are retained in the repository's ignored workspaces/project-discovery-evals/.
They are not redistributed as skill instructions.

The final question fallback has exact final-runtime coverage. Batch and repository
cases predate only that final question clarification; they were not all rerun
against byte-identical final content. Claude's repository receipt lacks a full
per-tool event transcript; actual artifacts/hashes and its file-accurate report
support the read/write assessment. Codex's review helper failed during one fixture
run and was honestly reported as self-review only.

The dedicated blocked-reference, approval-resume, and publishing-restraint prompts
are provided but were not separately executed. Qualified approval and publishing
restraint were exercised in the repository fixture. No live publishing, deployment,
network research, or application implementation was authorized in these cases.
No no-skill control or preexisting skill baseline was run; these observations do
not establish universal reliability or improvement over an unguided model.

The skill-creator evaluation helper was unavailable in the active catalog.
Direct fresh CLI contexts and an independent grader provided the recorded fallback.
Native skill-menu discovery and every installed agent host remain untested.
Installation checks verified the shared entry and 80 detected agent directories.
