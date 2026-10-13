# Before every push

Run these before you open a PR and again before every review-fix push. Fixes cause as many misses as first pushes.

1. **The check script passes.** Run the project's check script (for example `scripts/check.sh`). If the project has none, see `guardrails.md`.
2. **Figures come from the shared tool.** Every count, total and ID list is recomputed by the project's tool from the source files, never copied from memory, a summary or an earlier message. Count the population the sentence claims, not a neighbouring one: the listed items, not IDs cited in another item's rationale or explanation.
3. **External facts cite a primary source.** Release notes, a changelog, a specification or a filing, with version and date. An open issue, a roadmap or a search snippet is a lead, not a source. A version claim names the first release with full support, not a preview. For anything hosted on GitHub, read it with `gh api` (releases, tags, file contents).
4. **A change reaches every place it applies.** Search the whole repo for every status, rule, term or figure you change, including text split across lines. When you change a rule, walk every section that depends on it: later pipeline steps, checklists, examples, companion documents, other repos that copy it. When a change adds a member to a set of values (an enum value, a status, a category) or replaces an instruction, also search for the bare old number, the set's other members, and the old instruction's own words, such as the ticket a step used to wait for. A search for the phrases you expect finds only those phrases.
5. **An independent review runs on the diff, and every finding is fixed or answered.** Use a different model from the one that wrote the change. Prefer Herdr when the working agent is inside a Herdr-managed pane (`test "${HERDR_ENV:-}" = 1`); fall back to the Codex plugin otherwise.

   **Commit the change first, and leave the working tree clean.** A branch review reads committed commits only, so an uncommitted fix is not reviewed at all — an agent that reviews, then edits, then pushes has reviewed the wrong thing. Note the commit you reviewed; if HEAD moves before the push, review again, within the round limit under "Re-review after fixing" below.

   **With Herdr** (the working agent is inside a Herdr pane), spawn a reviewer agent in its own pane — a different kind/model from the writer — and have it run the `ce-code-review` skill, which does a structured multi-agent review (risk-based reviewer selection, parallel reviewers, a cross-model adversarial pass, a validator, and a rendered report). **Reuse the review tab for this repo rather than opening a new one for every review.** Name it `review-<repo>` (the repo's directory name) so it is findable:

      ```sh
      # From the repository under review, as a background job the harness reports back on
      # (Claude Code: run_in_background), never with `&`: a review outlasts a foreground call.
      ~/.agents/skills/way-of-working/scripts/herdr-review.sh --branch <branch> --verify "<claims to verify>"
      ```

      `scripts/herdr-review.sh` opens or reuses the `review-<repo>` tab in this agent's own workspace, starts a reviewer only in an empty pane (Codex on gpt-6.1-sol at medium reasoning, `-a never`, sandboxed with network; the owner's choice, set in the script; `--kind kimi` (Kimi Code, default model kimi-code/k3, run with `-y`) or `--model <model>` uses another reviewer when the owner asks, in its own `review-<repo>-<kind>-<model>` tab), tells it to apply the repository's review standards, waits, and prints the report. It exits 1 with recovery steps when there is no report: a blocked or busy start, a rejected or timed-out prompt, or a reviewer that stopped on a question. Before it prompts, it prints `Report file: <path>` on standard error, so the report stays findable when the output is cut short. `scripts/test_herdr_review.py` covers each of those cases.

      **Wait for the job's exit status and output before you push or open a pull request.** Launching it returns neither. A non-zero status stops the push: follow the recovery lines it printed. The review tab shares the working tree, so the reviewer sees the branch you have checked out. For later rounds, run it again with the new commit and say which findings you fixed or answered (see "Re-review after fixing" below). `ce-code-review` is report-only, so apply its findings yourself.

      Setup notes and one known gap:
      - **The writer can drive the reviewer only with an allow rule.** Claude Code's auto mode blocks starting or prompting an agent that never asks for approval. The owner adds `Bash(herdr agent:*)` once per machine through `/permissions`.
      - **`-a never` stops command-approval prompts.** Execution failures go back to the reviewer instead, so the owner is never asked to approve its commands.
      - **Known gap: the cross-model pass does not run.** Under `workspace-write`, `ce-code-review`'s Claude cross-check fails with `npm error code EPERM`. Adding `writable_roots` for `~/.npm`, `~/.claude`, `~/.cache` and `~/.config` clears that, but the transport then fails with `ETARGET`: `acpx@0.19.4` requires `@agentclientprotocol/sdk@^1.5.0`, which npm cannot find (2026-10-12). Either way the review falls back to an adversarial pass from the same model family. Say so in the PR body.

      **Close the review tab when the PR merges.** The script prints `Review tab: <tab id> (created|reused)` on standard error. If this agent's run created it, send the reviewer a "PR merged" message, then `herdr tab close <tab id>`. Do not close a tab you did not create.

   **Without Herdr** (the working agent is not inside a Herdr pane), use the Codex plugin:

   ```sh
   node "$(ls -d "$HOME"/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs | tail -1)" \
     adversarial-review --wait --base main --scope branch "<what to verify>"
   ```

   Tell it which claims to verify and which documents must stay consistent. Ask it to be adversarial, and to say how the thing under review could still pass while being wrong.

   - **State claims as the change's effects, not as your search.** Name what the change does to the project, in this PR's own terms. For example, a PR that adds an order status and drops a manual approval step should claim "orders gain a status; refunds no longer wait for manual approval", not "every document stating the counts was updated". The reviewer checks what the claim names, so a claim that describes your search confines the review to the places you already looked.
   - **Reproduce every finding before you accept it.** A finding is a claim; run it. A finding accepted on assertion becomes a wrong change.
   - **Fix clear defects; answer judgement calls in the PR body.** Say which is which, so the reviewer can weigh the judgement.
   - **Re-review after fixing, at most two rounds.** A fix can introduce its own defects — a guard tightened in one place is often loosened in another — so run the review again on the fixed diff. A round is one independent review of the branch's head. The limit applies per batch of work:
     - Before the pull request opens, at most two rounds.
     - Each HOLD on the open pull request starts a fresh count of two for the fixes it asks for.

     After the second round of a batch, fix only a finding that would let a wrong result through on input the project will realistically see. List every other finding in the PR body as a follow-up. Push the last fix without another review, and name that unreviewed commit in the PR body. If round two finds the same kind of defect as round one, redesign (next point) instead of patching a third time.
   - **Redesign when tightening a rule starts flagging a *correct* case.** That is the stop signal: a rule tightened to catch one variant of a defect now fails on a case which is right, and no further tightening converges from there — each attempt buys another review round. Change the design instead: what the rule reads, or where in the flow it sits. Say in the PR what design changed and why, then re-check the old variants under the new shape. Until that redesign lands, variants of one wrong design are not separate bugs to be filed away — three copies of a stale figure are three real defects, and they stay defects. A redesign forced by round two gets one review of its own. That is the only review past the limit.

## Prove a new check fails

When you add a check, break the thing it checks on purpose (change one figure, one status, one record) and confirm the check fails; then restore it. A check that has never failed may pass vacuously.

Test the check against the cases it claims, not just the happy path: a guard that hashes names rather than contents, or that follows a symlink, or that reads a file named `-` as standard input, passes every ordinary run and fails none. Enumerate the cases the check claims to catch and make each one fail on purpose.

A test that **reproduces a defect** is held to the same standard: run it against the unfixed code and confirm it fails, for the reason you expect. That is not a rule for every new test. A compatibility or invariant test — a valid input still works, the same answer survives reformatting — passes both versions, and forcing it to fail would delete exactly the coverage `guardrails.md` asks for. But that holds only while the invariant already holds on the unfixed code. When the defect *is* that it does not — reformatting changes the answer — the test must fail there, and it is a defect test like any other.

Watch too for a test that passes for the wrong reason: the input that looks like the bug is not always the one that exercises it.

Take a check that reads backticked spans in documents and treats a digest-shaped one as a pin to verify. It must leave `docker compose up …` alone, where `…` means "and so on", so a test asserts exactly that — and it passed, on a span written the way the docs show it, `! docker compose up …`. The check removes the whitespace inside a span before asking whether the span is a pin at all, and the shell's `!` is no digit or letter, so that span failed on its first character and was never judged. The `!` was doing the work; the ellipsis was never tested. Drop the `!` and the same words join into `dockercomposeup…`, which passes for a digest, and the build fails on a documentation line — the case the test existed to cover. Same words, one character apart, and the assertion held in both runs for reasons that had nothing to do with each other.

So state the input and the assertion, then say why the assertion held. If the reason is not the one you meant to test, the input is wrong.

A test that checks data against a document (a fixture against its specification, a generated file against the table it encodes) compares every fact the document states, not just the identifiers. Comparing names and connections lets a wrong type, value or reference through. Two more steps close the gap:

- **Forbid facts the document does not state.** Compare whole records for exact equality, so an invented value fails.
- **Pin the document text the data was last checked against,** by hash, so any edit to that text fails the test until someone checks the data again. A parser reads only the facts it was written for and cannot notice an edit to the rest; the pin can.

## Done when

All five hold, and the PR body says that they ran and what the review found.
