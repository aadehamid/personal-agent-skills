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
   - **Redesign when tightening a rule starts flagging a *correct* case.** That is the stop signal: a rule tightened to catch one variant of a defect now fails on a case which is right, and no further tightening converges from there — each attempt buys another review round. Change the design instead: what the rule reads, or where in the flow it sits. Say in the PR what design changed and why, then re-check the old variants under the new shape. Until that redesign lands, variants of one wrong design are not separate bugs to be filed away — three copies of a stale figure are three real defects, and they stay defects. The re-review above still has to come back with no new finding.

## Prove a new check fails

When you add a check, break the thing it checks on purpose (change one figure, one status, one row) and confirm the check fails; then restore it. A check that has never failed may pass vacuously.

Test the check against the cases it claims, not just the happy path: a guard that hashes names rather than contents, or that follows a symlink, or that reads a file named `-` as standard input, passes every ordinary run and fails none. Enumerate the cases the check claims to catch and make each one fail on purpose.

A test that **reproduces a defect** is held to the same standard: run it against the unfixed code and confirm it fails, for the reason you expect. That is not a rule for every new test. A compatibility or invariant test — a valid input still works, the same answer survives reformatting — passes both versions, and forcing it to fail would delete exactly the coverage `guardrails.md` asks for. But that holds only while the invariant already holds on the unfixed code. When the defect *is* that it does not — reformatting changes the answer — the test must fail there, and it is a defect test like any other.

Watch too for a test that passes for the wrong reason: the input that looks like the bug is not always the one that exercises it.

Take a check that reads backticked spans in documents and treats a digest-shaped one as a pin to verify. It must leave `docker compose up …` alone, where `…` means "and so on", so a test asserts exactly that — and it passed, on a span written the way the docs show it, `! docker compose up …`. The check removes the whitespace inside a span before asking whether the span is a pin at all, and the shell's `!` is no digit or letter, so that span failed on its first character and was never judged. The `!` was doing the work; the ellipsis was never tested. Drop the `!` and the same words join into `dockercomposeup…`, which passes for a digest, and the build fails on a documentation line — the case the test existed to cover. Same words, one character apart, and the assertion held in both runs for reasons that had nothing to do with each other.

So state the input and the assertion, then say why the assertion held. If the reason is not the one you meant to test, the input is wrong.

## Done when

All five hold, and the PR body says that they ran and what the review found.
