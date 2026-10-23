<!-- Copy at Step 3 for each batch of definitions. Rules: references/quality.md, "Definition quality bar". Mark each cell P (passes), F (fails, with the fix in Notes) or n/a only where quality.md says the point does not apply to that kind. Run scripts/check_taxonomy.py first; this sheet covers what a script cannot judge. Delete every comment. -->

# Definition review: <batch name>, <YYYY-MM-DD>

Reviewer: <role, never a personal name>. Check script result: <"all checks pass" line and commit>.

| Term | Kind | 1 Form for its kind | 2 Distinguishing | 3 Parent test | 4 Bounded | 5 Stable terms | 6 Park | 7 Evidence | 8 Provenance | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| `lib:renewal` | activity | P | P | P | P | P | P | P | F | No `dcterms:dateAccepted` yet; awaits the owner's approval. |
| `lib:overdue` | code value | P | P | P | n/a (candidate) | F | P | P | F | "due date" used but not defined: define `lib:dueDate` first. |
| `lib:Loan` | thing | P | P | n/a (no parent) | P | P | P | P | F | |
| <term> | <activity / thing / code value / property> | | | | | | | | | |

Open questions raised: <IDs, each attributed to whom it waits on (governance.md, rule 14)>.
