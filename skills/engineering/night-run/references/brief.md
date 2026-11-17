# The brief and the log

The brief is the owner's instructions for the run, written down before they leave. The log is the record the owner reads when they come back. Keep both in one folder outside the repository, such as the agent's scratchpad, and tell the owner the path.

## Brief template

Fill every field. A field the owner leaves open gets the default shown, and the brief says so.

```markdown
# Night run brief, <project>, <date>

Permission (owner's words): "<quote>"
Goal (owner's words): "<quote>"
Done means: <numbered done lines; see "Done lines" below>
Target: <the machine, operating system and accounts the result must run on, and the record that holds those facts; "this repository only" when there is none>
Order: <item 1>, <item 2>, ... (the queue, in the owner's order)

Decisions (owner's words): "<quote of the delegation>"
  Decide unless the evidence leaves the choice unclear. Evidence order:
  1. Recorded, approved decisions.
  2. Project documents, ranked by the project's index or instruction file if it ranks them.
  3. Sources the project has already recorded, such as a reference register.
  4. Light external search, registered as a source when used.

Reviewers: default: way-of-working's "Who reviews" table (changing.md), with its wait.
  Otherwise, name each one and how it starts:
  PR reviewer: <who gives the merge verdict>; stand-in: <who gives it when the PR reviewer is not available>
  Independent reviewer while the PR reviewer is available: <...>; while the stand-in reviews: <...>
  The stand-in takes over when the PR reviewer has not started within <minutes> of a push, or not given a verdict within <minutes>
Merge rule: default: check green, CI green, every independent-review finding fixed or answered, a MERGE verdict on the latest push from the PR's current reviewer, and the latest push's two reviews from different tools.
Check command: <the project's check script>
Remote and default branch: <for example origin and main>

Log: <path>
Stop conditions: a question the evidence cannot settle; anything irreversible outside the repository; <any the owner adds>
Owner's other instructions: <quotes>
```

## Done lines

"Done means" is a numbered list of **done lines**. The run closes when every done line has its evidence, so the owner agrees them before leaving.

- **Each done line names a state that a command's output or a file shows.** "The test runs every code block in the runbook, or the block is in the table of blocks the test does not run" can be checked. "The documents are tested" cannot.
- **Exceptions and the owner's own steps sit in the done lines.** An exception recorded anywhere else is a failed line at the close. Name what the owner does themselves, such as the first run on their own machine, as outside the run.
- **Read each done line back to the owner against what they said.** Where a line is stricter or looser than their talk, ask which they mean before they leave. At the close, the line as written decides.
- **Before each long proof run, count what would fail a done line.** Fix a known gap first: a run that cannot pass still costs its full length.

On one run, a goal of "every snippet is tested" with its exceptions kept only in a table was refused at the close twice, and a goal sentence stricter than the owner's talk about it cost one more pull request and build. Each refusal cost a build and a proof run of several hours.

## Log entries

Write one entry each time an item ships, stalls, changes plan, or needs a decision. Give each entry a UTC time and one fact per sentence:

- **Shipped:** `MERGED PR #<n> (<item>) as <merge commit>`, with the review rounds it took.
- **Decided:** `Decided (under the delegation): <choice>`, with the evidence, and where the decision is recorded.
- **Deferred:** the item, why it waits, and what it waits for.
- **Stalled or blocked:** what blocks it, what you tried, and what you moved on to.
- **Incident:** what went wrong, what it touched, and how you fixed it. If an earlier entry blamed the wrong cause, add a `CORRECTION` entry. Leave the earlier entry in place.

## Morning summary

End the log with this section:

```markdown
## Summary (<time> UTC)

<One sentence: is the goal met? If not, what is left?>

| Done line | Evidence: the command and what it printed, or the file |
|---|---|
| <n> | <evidence> |

| PR | What | Merge |
|---|---|---|
| #<n> | <item> | <commit> |

Deferred: <each item and what it waits for>.

Decisions made for the owner: <list, each with where it is recorded>. The owner can reverse any of them.

For the owner:
1. <each question waiting on them, with your recommendation>
2. <the proof kit kept for a fix: each store, data set and service, and how to remove it>
3. <anything else left running or stopped that they should know about>
```
