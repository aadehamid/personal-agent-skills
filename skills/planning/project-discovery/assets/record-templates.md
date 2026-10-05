# Adaptable record shapes

Use these fields within the project's own paths, names, and ID scheme. Angle-bracket
values are placeholders to resolve, not text to leave in a finished document.
Combine records in existing files when that reduces competing sources of truth.

## Project state

```markdown
# <Project> discovery state

Scope: <confirmed purpose and exclusions>
Workspace and output paths: <authorized locations>
Drafting mode: <interactive or batch; authorization source>
Delivery: <local, commit, push, PR; only the actions actually authorized>
Reference projects: <optional URLs/paths and inspected revisions>
Constraints: <hosting, budget, licensing, data, and user-specific exceptions>
Current document: <ID and version>
Last completed check: <actual result and evidence location>
Next action: <one executable next step>
Blocked work: <gate and dependent action, or none>
```

## Document index

| ID | Path | Version | Status | Owns | Depends on | Approval record |
| --- | --- | --- | --- | --- | --- | --- |

## Decision record

| ID | State | Decision or unknown | Options and recommendation | Evidence | Consequence | Owner and closure condition |
| --- | --- | --- | --- | --- | --- | --- |

Allowed distinctions: confirmed fact, user-approved decision, proposed decision,
working assumption, open question, implementation gate. Adapt spelling to existing
conventions without collapsing the meanings.

## Approval record

| Document/version or checksum | Approver | Evidence of approval | Accepted proposals | Qualifications | Remaining implementation gates |
| --- | --- | --- | --- | --- | --- |

## Reference record

| ID | Official source | Inspected revision/date | Supported claim | Reuse/license status | Limitations and required verification |
| --- | --- | --- | --- | --- | --- |

## Traceability

| Outcome | Use case | Requirement | Data/model contract | Implementation responsibility | Acceptance scenario and evidence |
| --- | --- | --- | --- | --- | --- |

## Reference-component assessment

| Reference component | Reference responsibility/evidence | Project need | Reuse/adapt/defer/exclude | Rationale and integration changes | Version/license/compatibility gates |
| --- | --- | --- | --- | --- | --- |
