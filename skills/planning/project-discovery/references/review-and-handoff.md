# Review, verification, and delivery

## Review the final package

Check the package against its agreed purpose and authoritative requirements.
Use a fresh reviewer when available; provide the actual documents, source evidence,
approved decisions, and scope. The reviewer must not edit shared files or grant
approval. If independent review is unavailable, label self-review honestly.
An explicitly required independent review remains a delivery blocker until fulfilled.

Resolve findings against evidence. Correct material contradictions and missing
contracts; do not expand scope solely because a reviewer suggests more features.
Keep unresolved findings with consequences and an owner. Recheck the affected
artifacts after fixes, including links and any downloadable package.

Review particularly:

- Terminology and ownership of policy, model, and metric definitions.
- Source authority, identity, versions, corrections, and historical behavior.
- Approval state versus publication state and actual user permissions.
- Data rights, hidden evaluation truth, credentials, access, and retention.
- Requirement-to-scenario coverage and exact evaluation units/matching rules.
- Component necessity, reference-project departures, and unverified claims.
- Dependency order, failure/retry/replay/rollback behavior, and unfinished gates.

These checks adapt to the project; irrelevant areas need a short scope reason,
not an invented subsystem.

## Verification evidence

Validate local paths/links, IDs, references, status/version consistency, diagrams,
and archive contents using available tools. Report checks not performed, including
visual rendering or external-source verification. A filename or command mentioned
in a document is not evidence that the artifact exists or the command succeeded.

When an archive is requested, include individual Markdown files and a manifest of
their checksums. Exclude secrets, unauthorized third-party material, large datasets,
and the archive itself. Verify an extracted copy and rebuild after final edits.
Use the host's actual download/link mechanism; do not invent a downloadable URL.

## Publishing

Publishing is opt-in and independent of batch mode. Preserve unrelated changes.
Before a requested commit/push/PR, inspect current branch, remote, diff, and existing
PR state using the available repository workflow. Do not invent a remote or base
branch or create a duplicate PR. Carry the user's action scope into delegated
shipping; a helper's defaults cannot broaden it.

If review or verification is incomplete, do not call it passed. If required review,
publication access, or another delivery gate is blocked, save the local result and
report the exact blocker rather than promising that publication happened.

## Completion and resumption

Deliver the files, reading order, approval status, evidence summary, unresolved
implementation gates, and first concrete implementation milestone. If published,
verify the remote commit/PR and state whether it is open or merged.

A draft package is complete for review when its agreed contents, checks, and review
record exist. Implementation readiness is a separate claim tied to closed gates
for a named milestone. Do not imply production readiness from a planning exercise.

For a partial run, save the completed artifacts, remaining work, unresolved blockers,
and next executable action. On resume, inspect those files and current repository
state before continuing; do not restart discovery or replay superseded decisions.

When persistence is unavailable, supply feasible artifacts and the resume record
inline and label them unpersisted. Report which delivery or continuity guarantees
cannot be met. Do not invent paths or claim that a later session will recover
unsaved conversation state.
