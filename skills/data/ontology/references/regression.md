# Competency questions as regression tests

Serves Step 11, and Step 1 where the competency questions are written. Read it before you write a competency-question query, add a class or property, land a module, or cut a release.

The competency questions are the exam the owner approved and locked at Step 1 (`foundations.md`). This step turns them into SPARQL and keeps running them.

## Trace every element to a question

1. **Trace every class and property to at least one competency question or explicit requirement, in a table kept with the questions:** per question, the classes and properties it needs. *Why:* an element no question or requirement needs is scope nobody asked for. The rule follows the requirement gate of the ontology-builder skill in Going Meta S03E07 (7 April 2026; `SOURCES.md`): "An ontology element is eligible only if it is required to answer at least one competency question or explicit requirement."
2. **List what was left out on purpose, each with its reason** (no question needs it, no source supports it, parked with a trigger), including terms of a reused vocabulary you chose not to use. *Why:* the next reviewer can then tell a deliberate omission from a gap, and nobody re-adds it unasked.
3. **Treat a question the model cannot answer as a modelling gap, not a bad question.** Change a locked question only by the owner's recorded decision. *Why:* editing the exam to fit the model hides the gap.

## Write the queries

4. **Write one SPARQL query per tested part of a question.** A question with three parts gets three queries, named after the question and part (`q21a-roles-are-dated.rq`). *Why:* a part that fails is then named by its own query, not hidden in a combined one.
5. **Make each query either return rows or, marked "(must be none)", return none.** A must-be-none query states a rule the graph keeps ("no process with RACI lacks an accountable role"). *Why:* both directions are testable with one runner.
6. **Test only the part the graph supplies** where a question depends on a system outside the ontology (a catalog page, an assistant). *Why:* the regression tests the ontology, and the rest is the consumer's test.
7. **Test the harness with mutated graphs:** remove the fact a query needs and require it to fail; add the fact a must-be-none query forbids and require it to fire. *Why:* a query that passes on an empty graph proves nothing.
8. **Check a query's population against the whole before you trust its count:** count what the query selects, the rows it returns and the rows it leaves out, and confirm they add up. *Why:* a filter on one concept kind silently drops concepts that carry no kind.
9. **Make every identity link reach every identity query.** When a module adds a link saying two IRIs are one thing (`skos:exactMatch`, `owl:sameAs`), every query that tells same-named things apart follows it and compares alternative as well as preferred labels. Its test pins each linked pair's two IRIs, not only the word they share. *Why:* a query that pairs each node with itself returns the same words.

## Give every question a status

10. **Start the harness early, before most questions can pass, and give each question one status:**
    - **drafted:** written at Step 1, not yet locked or not yet run; the elements it names are expected, and their names may change until Step 3;
    - **answerable:** all its queries run on the released packages;
    - **partial:** the graph part runs and the rest is named, with what it waits for; it closes Step 11 only by a recorded decision (rule 11);
    - **waiting:** it names the step, module or decision it waits for.
    A module's pull request moves its questions to answerable. *Why:* the status list is the build's progress, and a question with no named wait has been forgotten.
11. **Park a question, or leave it partial or waiting, only by a recorded decision that names its reason and what it waits for;** the Step 11 gate in `SKILL.md` is the rule. *Why:* a question set aside without a record has quietly left the exam the owner locked.
12. **Pin the counts a harness test checks by hand, and expect each new query to change them.** A test that pins how many queries fail on an empty graph, or which question is the example of a waiting one, moves with every module that adds a query or answers that question. *Why:* a stale pin fails for the wrong reason, and the fix that silences it can hide a real regression.

## Run it every time

13. **Run the full suite against the released packages after every module lands and on every release, from the check script,** with `scripts/run_regression.py`, which also checks each question's status against rules 10 and 11. A failing query is a regression or a recorded, deliberate change, never a surprise. *Why:* a change in one module can break a question another module answers.
14. **Run the whole check suite, not only the module's tests, before a review.** *Why:* a new source, value or node can break a check in another module, such as the rule that every cited source has an evidence tier.
