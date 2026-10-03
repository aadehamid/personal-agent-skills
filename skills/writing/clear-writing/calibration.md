# Personal calibration

Last run: 2026-10-03. Sessions read: 3 (last 60 days, the sampler found only 3). This is a small sample. Rules marked "tentative" rest on one or two passages. Rerun calibrate when more sessions exist.

## Emphasize
- Rule 1 (one idea per sentence), applied to colons and semicolons: Claude joins clauses with colons and semicolons, sometimes two colons in one line. Example: "**Checks:** all five passed: Cursor Bugbot, the Cursor Approval Agent, ..." and "I didn't merge it; that happened from your account." Rewrite: "All five checks passed. I didn't merge the PR. You merged it from your account." Tentative.
- Rule 12 (specific words), for undefined labels: "Watching PR #198 in `target` mode" uses a skill's internal term that the user never saw. Rewrite: "I'm watching PR #198. I'll fix feedback and CI failures, but I won't merge it." Tentative.
- AI tells, decorative emoji: "🎉 PR #198 is merged." Rewrite: "PR #198 is merged." Tentative (the user did not react to it).

## Relax
- Rules 10 and 11 (numbered steps, warnings first): rarely apply. The sampled replies are status reports and answers, with at most one command to run.
- Rule 7 (keep small words): neutral. Claude already writes full sentences, even in interim progress lines.
- Rule 4 (topic sentence first): neutral. Claude already opens with the answer, for example "Yes, the updates are in the repo." and "I couldn't find that session."

## Added rules
- Give a yes/no question one answer, and do not hedge it in the next sentence. Evidence: Claude wrote "**Do the Downloads files need deleting?** No. Git ignores them, ... You can remove them to keep the folder tidy." The user then asked again: "Should I delete the 4 files in my local Download folder then?" Rewrite: "Yes, you can delete them. The repo has identical copies." This is the only direct follow-up in the sample, so it is tentative, but it is the strongest evidence found.
- Use prose, not bold "Label:" lead-ins and bullets. Every long reply in the sample used them: "**Two things for you to decide:**", "**What happens next:**", "**How I installed it:**", "**Two things to know:**". Rewrite the "What happens next" block as: "A background watcher checks the PR about every 2.5 minutes for up to 8 hours. I'll handle new feedback and tell you if the PR is merged or closed." Supported by the 2026-10-03 blind review (see Register notes).
- Do not recap what an earlier message already reported. Evidence: the "PR is merged" reply has a section "What happened while I watched (about 7 minutes):" that repeats the HOLD review fixes reported two messages before. Rewrite: "PR #198 is merged (commit `c13dd2e`). To catch up, run `git checkout main && git pull`." Tentative.

## Register notes
- The user mostly reads status reports on repo work: PR state, file checks, installs, and searches. The user replies in short, direct requests and acts on the answer right away.
- From a blind review on 2026-10-03: the user reads bold "Label:" lead-ins, restating "Bottom line" or summary sections, and bullet-heavy structure as AI-written. The user prefers plain prose with the answer in the first sentence. Use a table or a list only when the content is a real comparison or a real sequence.
