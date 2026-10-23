<!-- Copy this file at Step 1 and keep it with the queries. It is the regression table: rules in references/regression.md (trace, queries, statuses). The questions' priority, rationale and scope live in requirements.yaml (references/governance.md, rule 2); keep the IDs the same in both. Delete every comment. -->

# Competency questions

<!-- Until the owner locks them: "Drafted <YYYY-MM-DD>; not yet locked (Q<n> to the owner)." -->
Approved and locked by the owner on <YYYY-MM-DD> (<decision record>). A locked question changes only by the owner's recorded decision.

| ID | Question | Tested parts (one query each) | Status | Waits for | Elements it needs |
|---|---|---|---|---|---|
| CQ1 | Which loan period applies to a copy of a given item type, and which policy sets it? | `cq1a-loan-period.rq`; `cq1b-period-has-source.rq` (must be none) | answerable | | `lib:ItemType`, `lib:loanPeriod`, `dcterms:source` |
| CQ2 | Who is accountable for each lending process? | `cq2a-accountable-role.rq` (must be none) | partial | the role register for the branch libraries (Step 5); the circulation manager confirms it | `skos:Concept`, `org:Role`, `lib:ResponsibilityAssignment` |
| CQ3 | Which supplier delivered the parts in a finished batch? | | waiting | the supplier module, release 1.0.0 | `mfg:Batch`, `mfg:Part`, `mfg:Supplier` |
| CQ4 | What makes a loan overdue, and when does it stop being overdue? | | drafted | the owner's lock (Q2) | `lib:Loan`, `lib:dueDate`, `lib:overdue` (expected names) |

<!-- Status is one of: drafted (written, not locked or not yet run; element names are expected and may change until Step 3), answerable (every query runs on the released packages), partial (the graph part runs; name the rest), waiting (name the step, module or decision). "Waits for" names whom or what: the owner, a process owner, the business, a release (governance.md, rule 14). Ask only what definitions and reference facts answer: never "which loans are overdue today" (foundations.md, policy 2). -->

## Left out on purpose

| Element or area | Reason | Revival trigger |
|---|---|---|
| <term, or a reused vocabulary's term> | <no question needs it / no source supports it / parked by <record>> | <what would bring it back> |
