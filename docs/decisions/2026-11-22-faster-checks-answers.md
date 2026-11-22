# Recorded answers, 2026-11-22: faster checks

The owner's messages in the project thread, verbatim, with their times (2026-11-22, UTC). Trailing spaces are
removed. The numbered list in the 04:38:28 message is text the owner pasted from the agent's suggestions.

## 04:33:07

```text
when you do finish . I want you to analyze the time taken and where the bottle neck is and report back. I notice my Ci maybe taking too long. We can discuss optimization when you finish.
```

## 04:38:28

```text
let us work the suggestion s below. The reason I ask if we should wai tis that the current job is using this script. but you did say it okay to do them in paralell
Fixes to discuss, biggest first

1. Make the review-script tests skip real sleeps, for example with a poll-interval setting the tests set to 0. Likely saves about 3 minutes a run.
2. Run the independent test files in parallel inside `check.sh`.
3. Run `check.sh` and the Pi review side by side on your Mac. That saves about 6 minutes a round.
4. Require the `check` job before merging on `main`, so the Cursor bot can't merge without CI, as it did on PR #101.
```

## 04:42:28

```text
work the plan. Done is when  PR flow is optimized and we have substantinal reduction on code review without a single drop in quality. Quality is the most important thing.

Again it is okay to switch repo to public to avoid billing issues and flip back at the end of the session. This is now a standing project instruction here
```
