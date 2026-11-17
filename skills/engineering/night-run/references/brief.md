# The brief and the log

The brief is the owner's instructions for the run, written down before they leave. The log is the record the owner reads when they come back. Keep both in one folder outside the repository, such as the agent's scratchpad, and tell the owner the path.

## Brief template

Fill every field. A field the owner leaves open gets the default shown, and the brief says so.

```markdown
# Night run brief, <project>, <date>

Permission (owner's words): "<quote>"
Goal (owner's words): "<quote>"
Done means: <numbered done lines; see "Done lines" below>
Owner's steps after the run: <what the owner does themselves, such as the first run on their own machine; "none" when there are none>
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

"Done means" is a numbered list of **done lines**. Each done line ends the run **Met**, with its evidence, or **Blocked**, with the log entry of the stop condition that blocks it. The owner agrees the done lines before leaving.

- **Each done line names a state that a command's output or a file shows.** "The test runs every code block in the runbook except blocks 4, 9 and 12, and the test's table of blocks it does not run lists exactly those three" can be checked. "The documents are tested" cannot.
- **Each exception is named in its done line.** An exception that the line does not name fails the line, wherever else it is recorded.
- **The owner's own steps go in "Owner's steps after the run".** They are outside the run and are not done lines. The summary's "For the owner" list repeats them.
- **Read each done line back to the owner against what they said.** Where a line is stricter or looser than their talk, ask which they mean before they leave. At the close, the line as written decides.
- **Before each long proof run, count what would fail a done line.** Fix a known gap first: a run that cannot pass still costs its full length.
- **Evidence comes from the final result.** For each Met line, give the command, its exit status and what it printed, or the file, with the commit or the artifact checksum it ran against. Rerun on the final commit or build any proof taken on an earlier one.
- **A done line about the Target takes its evidence from the Target.** Evidence from a stand-in counts only when the line names that stand-in.

On one run, a goal of "every snippet is tested" with its exceptions kept only in a table was refused at the close twice, and a goal sentence stricter than the owner's talk about it cost one more pull request and build. Each refusal cost a build and a proof run of several hours.

## Target

When Target names a machine or platform outside this repository, put a **tracer bullet** first in the Order, with the owner's agreement: the thinnest end-to-end path of the result, run on the Target or on the closest stand-in the run can reach, such as a CI runner on that operating system. Log the environment it ran on and each known difference from the Target. On one run, the first end-to-end run on the target operating system came after four builds and found three faults, and the owner's first run on the real machine found four more.

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

| Done line | Met or Blocked | Evidence, as "Done lines" defines it, and where it ran; or the log entry that blocks the line |
|---|---|---|
| <n> | <Met or Blocked> | <evidence or log entry> |

| PR | What | Merge |
|---|---|---|
| #<n> | <item> | <commit> |

Deferred: <each item and what it waits for>.

Decisions made for the owner: <list, each with where it is recorded>. The owner can reverse any of them.

For the owner:
1. <each question waiting on them, with your recommendation>
2. <the proof kit kept for a fix: each store, data set and service, and how to remove it>
3. <the owner's steps after the run, from the brief>
4. <anything else left running or stopped that they should know about, and any clean-up that was refused>
```
