<!-- Copy this file at Step 1 and keep it with the queries. It is the regression table: rules in references/regression.md (trace, queries, statuses). Each question's priority, rationale, scope needs and lock state (drafted or locked) live in requirements.yaml (references/governance.md, rule 2); keep the IDs and the question text the same in both. Delete every comment. -->

# Competency questions

Drafted <YYYY-MM-DD>; not yet locked (Q<n> to the owner).

<!-- Once the owner locks them, replace the line above with: "Approved and locked by the owner on <YYYY-MM-DD> (<decision record>). A locked question changes only by the owner's recorded decision." -->

| ID | Question | Tested parts (one query each) | Status | Waits for | Elements it needs |
|---|---|---|---|---|---|
| CQ1 | What is a loan, and which events start and end one? | `cq1a-loan-defined.rq`; `cq1b-renewal-is-not-a-loan.rq` (must be none) | drafted | the owner's lock (Q<n>) | `lib:Loan`, `lib:lending-activity`, `lib:renewal`, `skos:definition` |
| CQ2 | Which lending-system status values map to which loan state? | `cq2a-status-mapped.rq`; `cq2b-unmapped-status.rq` (must be none) | drafted | the owner's lock (Q<n>); then the status mapping (Step 7), which the systems librarian confirms | `lib:loanState`, `lib:loan-state`, `skos:notation` |

<!-- Status here is the regression status, separate from the lock state in requirements.yaml. One of: drafted (written, not locked or not yet run; element names are expected and may change until Step 3), answerable (every query runs on the released packages), partial (the graph part runs; name the rest), waiting (name the step, module or decision). "Waits for" names whom or what: the owner, a process owner, the business, a release (governance.md, rule 14). Ask only what definitions and reference facts answer: never "which loans are overdue today" (foundations.md, policy 2). -->

## Left out on purpose

| Element or area | Reason | Revival trigger |
|---|---|---|
| Holds | No holds export yet; out of scope in requirements.yaml and on the parked list | A holds export and a competency question about holds |
| <term, or a reused vocabulary's term> | <no question needs it / no source supports it / parked by <record>> | <what would bring it back> |
