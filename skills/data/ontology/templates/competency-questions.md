<!-- Copy this file at Step 1 and keep it with the queries. Rules: references/regression.md (trace, queries, statuses) and references/governance.md, rule 2 (machine-readable requirements). Delete every comment. -->

# Competency questions

Approved and locked by the owner on <YYYY-MM-DD> (<decision record>). A locked question changes only by the owner's recorded decision.

| ID | Question | Tested parts (one query each) | Status | Waits for | Elements it needs |
|---|---|---|---|---|---|
| CQ1 | Which copies of a title can a member borrow today? | `cq1a-available-copies.rq`; `cq1b-member-not-blocked.rq` (must be none) | answerable | | `lib:Copy`, `lib:Title`, `lib:copyOf`, `lib:Loan`, `lib:Member` |
| CQ2 | Who is accountable for each lending process? | `cq2a-accountable-role.rq` (must be none) | partial | the role register for the branch libraries (Step 5) | `lib:Process`, `org:Role`, `lib:RaciAssignment` |
| CQ3 | Which supplier delivered the parts in a finished batch? | | waiting | the supplier module, release 1.0.0 | `mfg:Batch`, `mfg:Part`, `mfg:Supplier` |

<!-- Status is one of: answerable (every query runs on the released packages), partial (the graph part runs; name the rest), waiting (name the step, module or decision). "Waits for" names whom or what: the owner, a process owner, the business, a release. -->

## Left out on purpose

| Element or area | Reason | Revival trigger |
|---|---|---|
| <term, or a reused vocabulary's term> | <no question needs it / no source supports it / parked by <record>> | <what would bring it back> |
