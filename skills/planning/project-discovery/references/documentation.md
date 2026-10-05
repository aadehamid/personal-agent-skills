# Tailored documents and durable state

## Select a package

Use project conventions and user preferences for output paths and IDs. If absent,
propose a repository-relative documentation location and stable naming scheme.
Check applicable instructions before editing. A reference repository's paths are
not automatic targets. Never overwrite unrelated artifacts or move approved
documents merely to imitate a reference layout.

Cover the following needs where they affect the project. Combine them into the
fewest useful documents; this is a coverage check, not a mandatory document list:

- Problem, users, objectives, scope, success, and operating workflows.
- Business questions, requirements, data needs, and source authority.
- Sources, reuse rights, vocabulary assessment, domain and logical models.
- Synthetic data or evidence-corpus generation when needed.
- Component selection, data flows, interfaces, failure handling, and recovery.
- Access, approval, quality, retention, observability, and decision provenance.
- Scenarios, metrics, acceptance evidence, and implementation dependencies.
- Approvals, decisions, unresolved gates, references, and a navigable index.

Business-facing requirements should not prescribe technology unless the choice
affects a meaningful requirement or is an explicit constraint. Detailed contracts
belong in their owning documents.

## Document contract

Each document states its ID/version, status, purpose, dependencies, owned definitions,
scope, and pending decisions. Include examples, failure cases, and verification
methods where needed to make its contracts implementable. Cite source claims and
label proposed behavior. Do not fill sections with generic “best practices.”

Keep one authoritative definition for each policy, metric, model, or interface.
The glossary defines concepts without implementation details. Use references rather
than inconsistent copies. Trace outcome → use case → requirement → data/model →
implementation responsibility → acceptance scenario, adapting names to the domain.

Keep human prose plain, with one meaning per term, direct verbs, and short sentences.
Use tables for real comparisons and compact Mermaid diagrams for useful relationships.
Do not claim formal writing-standard compliance. Do not include private discovery
conversation history in deliverables unless the user requests it.

## State and approvals

Maintain an index and a decision record in existing files where possible.
Use `assets/record-templates.md` from the skill directory for the field shapes.
The minimum durable state identifies:

- Current project and scope, source locations, output paths, and relevant constraints.
- Drafting mode and separately authorized delivery actions.
- Documents/versions, approval evidence, material qualifications, and next action.
- Confirmed facts, approved and proposed decisions, assumptions, questions, and gates.

An approval records the reviewed version or commit/checksum, approver, accepted
proposals, qualifications, and known implementation gates. Do not invent dates,
signatures, or an approval the owner did not give. A merged PR does not imply every
draft is approved unless that intent is explicit.

Material changes to approved definitions are visible amendments with affected
documents listed. Routine link/status corrections may proceed in scope. Preserve
previous approval history rather than extending it silently to a new design.

## Evaluation and implementation honesty

Define truth representation, matching rules, scoring units, denominators, missing-data
rules, workload, and measurement boundary before comparative evaluation. Proposed
thresholds need rationale and review; label them separately from measured results.
Never let an aggregate score hide a critical control failure.

Where synthetic data is used, distinguish visible development examples from fresh
held-out truth. Keep scoring keys and reconstructible hidden inputs outside evaluated
processes. Verify isolation before admitting protected evaluation data.

Separate design recommendation, approved design, configured implementation, executed
test, measured result, and deployed system. A valid diagram or passing documentation
check is not a working implementation. Build prerequisites must precede dependent
work; a gate cannot be satisfied by a test scheduled before its controls exist.

## Batch drafting

Batch authorization removes document-by-document waiting, not review or truthfulness.
Choose reversible draft recommendations and name consequential unresolved choices.
Continue independent work when a source or gate is blocked. Save intermediate
documents and a resume point rather than keeping the only record in conversation.

Parallel authors receive shared definitions and disjoint ownership. Integrate returned
work before final checks. A worker's source inspection date or incomplete-package
note may be stale by integration time; reconcile it against the actual final package.
