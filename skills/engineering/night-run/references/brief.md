# The brief and the log

The brief is the owner's instructions for the run, written down before they leave. The log is the record the owner reads when they come back. Keep both in one folder outside the repository, such as the agent's scratchpad, and tell the owner the path.

## Brief template

Fill every field. A field the owner leaves open gets the default shown, and the brief says so.

```markdown
# Night run brief, <project>, <date>

Permission (owner's words): "<quote>"
Goal (owner's words): "<quote>"
Done means: <the checkable state that ends the run>
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
Merge rule: default: check green, CI green, every independent-review finding fixed or answered, and a MERGE verdict on the latest push from the PR's current reviewer.
Check command: <the project's check script>
Remote and default branch: <for example origin and main>

Log: <path>
Stop conditions: a question the evidence cannot settle; anything irreversible outside the repository; <any the owner adds>
Owner's other instructions: <quotes>
```

## Log entries

Write one entry each time an item ships, stalls, changes plan, or needs a decision. Give each entry a UTC time and one fact per sentence:

- **Shipped:** `MERGED PR #<n> (<item>) as <merge commit>`, with the review rounds it took.
- **Decided:** `Decided (under the delegation): <choice>`, with the evidence, and where the decision is recorded.
- **Stalled or blocked:** what blocks it, what you tried, and what you moved on to.
- **Incident:** what went wrong, what it touched, and how you fixed it. If an earlier entry blamed the wrong cause, add a `CORRECTION` entry. Leave the earlier entry in place.

## Morning summary

End the log with this section:

```markdown
## Summary (<time> UTC)

<One sentence: is the goal met? If not, what is left?>

| PR | What | Merge |
|---|---|---|
| #<n> | <item> | <commit> |

Decisions made for the owner: <list, each with where it is recorded>. The owner can reverse any of them.

For the owner:
1. <each question waiting on them, with your recommendation>
2. <anything left running or stopped that they should know about>
```
