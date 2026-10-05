# Evaluating project-discovery

Run mechanical checks separately from behavior. A passing file/path check is not
evidence that an agent interviews well or respects approvals.

## Fresh-context procedure

1. Freeze the skill and referenced files; record their hashes.
2. For activation cases, give a fresh agent the name/description and the user prompt.
   Ask which workflow it would use. Do not give it the expected result.
3. For behavior cases, load the actual SKILL.md and applicable bundled references
   into a fresh context, then submit only the case's user prompt. Exclude this file
   and the `expected` fields from the subject's context.
4. Use read-only/no-tools boundaries for inline-output cases. They intentionally
   cannot demonstrate real file delivery or shipping. For `repository-resume`,
   create a new directory with `scripts/make_fixture.py`, enable scoped file tools,
   and give the subject only its user prompt and the skill bundle. Grade actual
   reads and resulting files. The approved charter and all files outside planning/
   must remain unchanged; the next draft and state/index must exist. Do not expose
   expected outcomes or the original hashes to the subject.
5. An independent grader reads the prompt, output, and action transcript against
   the expected outcomes. Report concrete evidence, not keyword counts.
6. Run at least `batch-main`, an interactive case, and a restraint or real-failure
   case on available Claude and Codex hosts. Record exact capability/auth failures,
   not a passing result for an unexecuted host.

Use the configured host model; do not silently substitute a named model or increase
paid usage. Inspect live CLI help before adapting commands. Never bypass permission
controls or allow the subject to publish as part of an inline case.

For a new skill there is no pre-change behavior baseline. A no-skill control can
compare added value, but passing the skill cases alone establishes only the observed
behavior, not improvement over that control. Avoid claiming broad cross-host
reliability from a small sample.

## Files and records

`cases.json` contains prompts and grading expectations. Keep generated subject
outputs in the repository's ignored `workspaces/` area, not inside the skill.
`RESULTS.md` records scenario/host outcomes, hashes, reviewer findings, and limits.

The real-failure case comes from observed documentation defects: leaked development
answers described as hidden truth, controls scheduled after dependent evaluation,
undefined scoring, and conflicting permissions. It contains no project-specific stack.
