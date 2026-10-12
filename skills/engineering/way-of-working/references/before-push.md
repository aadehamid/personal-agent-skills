# Before every push

Run these before you open a PR and again before every review-fix push. Fixes cause as many misses as first pushes.

1. **The check script passes.** Run the project's check script (for example `scripts/check.sh`). If the project has none, see `guardrails.md`.
2. **Figures come from the shared tool.** Every count, total and ID list is recomputed by the project's tool from the source files, never copied from memory, a summary or an earlier message. Count the population the sentence claims: rows, not mentions; listed rows, not IDs cited in rationale text.
3. **External facts cite a primary source.** Release notes, a changelog, a specification or a filing, with version and date. An open issue, a roadmap or a search snippet is a lead, not a source. A version claim names the first release with full support, not a preview. For anything hosted on GitHub, read it with `gh api` (releases, tags, file contents).
4. **A change reaches every place it applies.** Search the whole repo for every status, rule, term or figure you change, including text split across lines. When you change a rule, walk every section that depends on it: later pipeline steps, checklists, examples, companion documents, other repos that copy it.
5. **An independent review runs on the diff, and every finding is fixed or answered.** Use a different model from the one that wrote the change. Prefer Herdr when the working agent is inside a Herdr-managed pane (`test "${HERDR_ENV:-}" = 1`); fall back to the Codex plugin otherwise.

   **Commit the change first, and leave the working tree clean.** A branch review reads committed commits only, so an uncommitted fix is not reviewed at all — an agent that reviews, then edits, then pushes has reviewed the wrong thing. Note the commit you reviewed; if HEAD moves before the push, review again.

   **With Herdr** (the working agent is inside a Herdr pane), spawn a reviewer agent in its own pane — a different kind/model from the writer — and have it run the `ce-code-review` skill, which does a structured multi-agent review (risk-based reviewer selection, parallel reviewers, a cross-model adversarial pass, a validator, and a rendered report). **Reuse the review tab for this repo rather than opening a new one for every review.** Name it `review-<repo>` (the repo's directory name) so it is findable:

      ```sh
      set -euo pipefail   # a failed lookup must stop the recipe, not create a stray tab
      # Work in this agent's own workspace. An unfiltered `tab list` spans every
      # workspace, and a tab created without --workspace can open in whichever
      # one the owner is looking at.
      repo=$(basename "$PWD")
      review_tab=$(herdr tab list --workspace "$HERDR_WORKSPACE_ID" | jq -r --arg l "review-$repo" \
        '.result.tabs[] | select(.label == $l) | .tab_id' | head -1)
      if [ -z "$review_tab" ]; then
        created=$(herdr tab create --workspace "$HERDR_WORKSPACE_ID" --cwd "$PWD" --label "review-$repo" --no-focus)
        review_tab=$(printf '%s\n' "$created" | jq -r '.result.tab.tab_id')
      fi
      # `herdr tab get` does not return the pane; find it in the pane list.
      review_pane=$(herdr pane list | jq -r --arg t "$review_tab" '.result.panes[] | select(.tab_id == $t) | .pane_id' | head -1)

      # Start a reviewer only if the pane has none; a reused tab keeps its reviewer.
      # Different model from the writer, no approval prompts, sandboxed with network.
      # (Claude writing: Codex on gpt-6.1-sol at medium reasoning, Hamid's choice 2026-10-11.)
      # Standalone assignment, so set -e stops the recipe if the lookup fails.
      pane_agent=$(herdr pane get "$review_pane" | jq -r 'if .result.pane then (.result.pane.agent // "") else error("pane lookup failed") end')
      if [ -z "$pane_agent" ]; then
        if ! herdr agent start "rev-$(printf '%s' "$repo" | tr 'A-Z' 'a-z' | tr -cs 'a-z0-9' '-' | cut -c1-28)" \
            --kind codex --pane "$review_pane" -- \
            -m gpt-6.1-sol -c model_reasoning_effort=medium \
            -a never -s workspace-write -c sandbox_workspace_write.network_access=true; then
          # agent_not_ready: usually Codex's trust dialog on a new directory.
          herdr agent read "$review_pane" --source recent-unwrapped --lines 30 || true
          echo "Reviewer blocked at startup. Answer it (herdr agent send-keys $review_pane <key>), then run this again."
          exit 1
        fi
      fi

      # A review takes longer than a foreground tool call allows (10 minutes in Claude Code).
      # Run the whole block as a background job the harness reports back on, with its exit
      # status (Claude Code: run_in_background), never with `&`. Address the reviewer by its pane. --wait fails fast (agent_prompt_stalled) if the prompt never
      # starts work, and otherwise returns when the reviewer is idle, done or blocked.
      report=$(mktemp "${TMPDIR:-/tmp}/review-XXXXXX")   # unique; a failure stops here
      rm -f "$report"                                     # absent until the reviewer writes it
      if ! herdr agent prompt "$review_pane" \
          "Run the ce-code-review skill on branch <branch>, diff vs main. Verify: <what to verify>. Report findings only; do not apply them. Write them as Markdown to $report and reply with the path." \
          --wait --timeout 3600000; then
        herdr agent read "$review_pane" --source recent-unwrapped --lines 60 || true
        echo "Prompt not completed. agent_blocked: the reviewer was already waiting on a question and"
        echo "got nothing; answer it (herdr agent send-keys $review_pane <key>), then run this again."
        echo "timeout: the review may still be running; wait for the same report:"
        echo "  herdr agent wait $review_pane --until idle --until done --timeout 3600000 && cat '$report'"
        exit 1
      fi
      if [ ! -f "$report" ]; then   # no report means no review, whatever the pane shows
        state=$(herdr agent get "$review_pane" | jq -r '.result.agent.agent_status' || true)
        herdr agent read "$review_pane" --source recent-unwrapped --lines 60 || true
        echo "No report (state: $state). A blocked reviewer refuses new prompts: answer it"
        echo "(herdr agent send-keys $review_pane <key>), then wait for the same report:"
        echo "  herdr agent wait $review_pane --until idle --until done --timeout 3600000 && cat '$report'"
        exit 1
      fi
      cat "$report"
      ```

      The review tab shares the working tree, so the reviewer sees the branch you have checked out. A `blocked` state means the reviewer is waiting on a question; read the pane and answer it. `ce-code-review` is report-only by default, so it will not mutate the tree; apply its findings yourself. For later rounds, prompt the same pane with the new commit and say which findings you fixed or answered (see "Re-review after fixing" below).

      Setup notes and one known gap:
      - **The writer can drive the reviewer only with an allow rule.** Claude Code's auto mode blocks starting or prompting an agent that never asks for approval. Hamid adds `Bash(herdr agent:*)` once per machine through `/permissions`.
      - **`-a never` stops command-approval prompts.** Execution failures go back to the reviewer instead, so the owner is never asked to approve its commands.
      - **Known gap: the cross-model pass does not run.** Under `workspace-write`, `ce-code-review`'s Claude cross-check fails with `npm error code EPERM`. Adding `writable_roots` for `~/.npm`, `~/.claude`, `~/.cache` and `~/.config` clears that, but the transport then fails with `ETARGET`: `acpx@0.19.4` requires `@agentclientprotocol/sdk@^1.5.0`, which npm cannot find (2026-10-12). Either way the review falls back to an adversarial pass from the same model family. Say so in the PR body.

      **Close the review tab when the PR merges.** The originating agent sends the reviewer a "PR merged" message, then closes the tab it created: `herdr tab close "$review_tab"` (or `herdr workspace close` if the review lives in its own workspace). Do not close a tab you did not create.

   **Without Herdr** (the working agent is not inside a Herdr pane), use the Codex plugin:

   ```sh
   node "$(ls -d "$HOME"/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs | tail -1)" \
     adversarial-review --wait --base main --scope branch "<what to verify>"
   ```

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
