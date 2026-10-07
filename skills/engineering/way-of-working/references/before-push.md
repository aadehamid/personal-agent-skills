# Before every push

Run these before you open a PR and again before every review-fix push. Fixes cause as many misses as first pushes.

1. **The check script passes.** Run the project's check script (for example `scripts/check.sh`). If the project has none, see `guardrails.md`.
2. **Figures come from the shared tool.** Every count, total and ID list is recomputed by the project's tool from the source files, never copied from memory, a summary or an earlier message. Count the population the sentence claims: rows, not mentions; listed rows, not IDs cited in rationale text.
3. **External facts cite a primary source.** Release notes, a changelog, a specification or a filing, with version and date. An open issue, a roadmap or a search snippet is a lead, not a source. A version claim names the first release with full support, not a preview. For anything hosted on GitHub, read it with `gh api` (releases, tags, file contents).
4. **A change reaches every place it applies.** Search the whole repo for every status, rule, term or figure you change, including text split across lines. When you change a rule, walk every section that depends on it: later pipeline steps, checklists, examples, companion documents, other repos that copy it.
5. **An independent review runs on the diff, and every finding is fixed or answered.** Use a different model from the one that wrote the change. With the Codex plugin installed:

   ```sh
   node "$(ls -d "$HOME"/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs | tail -1)" \
     adversarial-review --wait --base main --scope branch "<what to verify>"
   ```

   **Commit the change first, and leave the working tree clean.** A branch review reads committed commits only, so an uncommitted fix is not reviewed at all — an agent that reviews, then edits, then pushes has reviewed the wrong thing. Note the commit you reviewed; if HEAD moves before the push, review again.

   Tell it which claims to verify and which documents must stay consistent. Ask it to be adversarial, and to say how the thing under review could still pass while being wrong.

   - **Reproduce every finding before you accept it.** A finding is a claim; run it. A finding accepted on assertion becomes a wrong change.
   - **Fix clear defects; answer judgement calls in the PR body.** Say which is which, so the reviewer can weigh the judgement.
   - **Re-review after fixing.** A fix can introduce its own defects — a guard tightened in one place is often loosened in another. Run the review again on the fixed diff, and keep going until a pass returns no new finding.
   - **Findings of the same shape are one wrong design, not many bugs.** When a review keeps finding new variants of the same defect, the pattern is not the problem. Stop patching and redesign, then say in the PR that you did, so the reviewer weighs the new shape instead of re-checking the old one. The tell is a rule that catches one variant and flags a correct case in another — at that point no amount of tightening converges.

## Prove a new check fails

When you add a check, break the thing it checks on purpose (change one figure, one status, one row) and confirm the check fails; then restore it. A check that has never failed may pass vacuously.

Test the check against the cases it claims, not just the happy path: a guard that hashes names rather than contents, or that follows a symlink, or that reads a file named `-` as standard input, passes every ordinary run and fails none. Enumerate the cases the check claims to catch and make each one fail on purpose.

The same goes for a test that **reproduces a defect**: run it against the unfixed code and confirm it fails, for the reason you expect. That is not a rule for every new test. A compatibility or invariant test — a valid input still works, the same answer survives reformatting — should pass both versions, and forcing it to fail would delete exactly the coverage `guardrails.md` asks for.

Watch too for a test that passes for the wrong reason. One written as `docker compose up …` proved nothing, because the `!` in front of the real case is what stopped it being read as a digest. The example that looks like the bug is not always the one that exercises it.

## Done when

All five hold, and the PR body says that they ran and what the review found.
