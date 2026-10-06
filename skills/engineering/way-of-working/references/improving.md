# Improving the standard

Read this after a session with repeated review rounds, or when the owner asks for a retrospective.

## The loop

1. Run a retro on the session (the `retro` skill in mattpocock-skills): list where the agent lost time or the reviewer held a PR, in order of cost.
2. For each lesson, choose exactly one home:
   - a **check** (a script, test or CI job) when a machine can catch it;
   - the project's **review standards** when it is a judgement only a reviewer can make in that project;
   - **this skill** when it holds for any project;
   - the agent's **memory** when it is about one owner's preferences or one machine.
3. Make the change through a PR, like any other change.
4. Remove what no longer earns its place: a rule whose decision changed, an instruction a check now enforces, a memory note that only replays history.

## Signals worth a retro

- More than two review rounds on one PR.
- The same kind of finding on two different PRs.
- A figure, status or rule found stated two ways.
- A tool call that returned far more than the answer needed.

## Done when

Every lesson from the retro is in one home, merged, and nothing it replaces is left behind.
