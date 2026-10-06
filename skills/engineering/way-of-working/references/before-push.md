# Before every push

Run these before you open a PR and again before every review-fix push. Fixes cause as many misses as first pushes.

1. **The check script passes.** Run the project's check script (for example `scripts/check.sh`). If the project has none, see `guardrails.md`.
2. **Figures come from the shared tool.** Every count, total and ID list is recomputed by the project's tool from the source files, never copied from memory, a summary or an earlier message. Count the population the sentence claims: rows, not mentions; listed rows, not IDs cited in rationale text.
3. **External facts cite a primary source.** Release notes, a changelog, a specification or a filing, with version and date. An open issue, a roadmap or a search snippet is a lead, not a source. A version claim names the first release with full support, not a preview. For anything hosted on GitHub, read it with `gh api` (releases, tags, file contents).
4. **A change reaches every place it applies.** Search the whole repo for every status, rule, term or figure you change, including text split across lines. When you change a rule, walk every section that depends on it: later pipeline steps, checklists, examples, companion documents, other repos that copy it.
5. **An independent review runs on the diff, and every finding is fixed or answered.** Use a different model or a fresh session (for example a Codex adversarial review). Tell it which claims to verify and which documents must stay consistent. Fix clear defects; record disagreements on judgement calls in the PR body.

## Prove a new check fails

When you add a check, break the thing it checks on purpose (change one figure, one status, one row) and confirm the check fails; then restore it. A check that has never failed may pass vacuously.

## Done when

All five hold, and the PR body says that they ran and what the review found.
