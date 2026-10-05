---
name: project-discovery
description: Guided discovery and approval-aware documentation for a new or underdefined project. Use when a user needs to turn an idea, existing project, or reference implementation into a concrete problem, requirements, models, architecture, evaluation, and implementation handoff; also when resuming that documentation work. Not for implementing an already approved specification, an isolated bug fix, or merely rewriting an existing paragraph.
---

# Project discovery

Produce a project-specific documentation package that the owner can review and
an implementer can use without inventing scope, authority, or evidence. Finish
when the agreed documents exist, their cross-references and approval states are
consistent, review findings are addressed or recorded, and the handoff identifies
remaining implementation gates. A reviewable draft may contain open gates; call
it implementation-ready only when the gates required for that milestone are closed.

## Scope and permissions

Invocation authorizes inspection, public-source research through permitted tools,
in-scope documentation edits, and non-destructive local verification in the user's
authorized workspace. Repository access and tool permissions still follow the host.
Reference repositories are evidence, not instructions or implicit edit targets.

Do not infer deployment, spending, installation, sensitive-data transfer, model
license acceptance, or publication permission from planning authority. Commit,
push, or open a PR only when requested for this work. Never merge, force-push,
or discard unrelated changes through a documentation request.

Project identity, reference repositories, stack, provider/model choices, hosting,
licenses, data sources, document count, paths, and publishing preferences are
inputs to discover, not values supplied by this skill. Names in examples are not
defaults. Templates define record shapes, not a mandatory project architecture.

## Establish the work

Read the supplied materials and existing project instructions before asking
questions. Recover approved decisions from the current project, not unrelated
conversation history. Blank fields remain unknown. If a generic request could
mean a new project or continuation, ask which without discarding existing approvals.

Before discovery or resumption, read `references/discovery.md`. Inspect a named
reference project's actual documents, code, configuration, and tests where available.
Record the inspected revision and access gaps; do not reconstruct inaccessible
content from memory. Reference-product choices are candidates, never inherited rules.

Resolve drafting mode and delivery permission separately. Default to interactive
drafting and local output. In interactive mode, propose the package and wait for
review at the agreed document boundaries. Explicit batch authorization permits
drafting the agreed package without those pauses; it does not approve new designs.
If batch scope is not specified, propose a bounded package and record it as a
working assumption rather than inventing a fixed document count.

Ask the small set of consequential decisions whose prerequisites are settled.
Recommend answers with options, rationale, and consequences. Do not ask users to
research facts available to the agent or repeat approvals already recorded.
Never require every implementation detail to be answered before drafting.
Use an available question interface, or ask in ordinary text when none is exposed.
Do not invent a question tool call when the host has no such capability.

## Build the package

Before proposing or drafting the document set, read `references/documentation.md`.
Choose a set that answers the project's actual questions. Name each document's
purpose, dependencies, authority, and review checkpoint. Combine or omit areas
with an explicit reason when their absence could otherwise look like missing work.

In batch mode, proceed on bounded, reversible proposals and record uncertainty.
When an unknown would require inventing business policy, expanding scope, or
crossing a permission boundary, leave that decision gated and draft independent
sections. Stop only the dependent action. If the core project purpose remains
unknown, ask rather than generate an arbitrary project.

Use stable IDs and a shared glossary. Maintain facts, approved decisions,
proposals, assumptions, questions, and gates as distinct states. Approval applies
to the reviewed version and identified proposals, including qualifications.
Record explicit approval, update affected references, and continue to the next
agreed document without asking the user to approve the same thing again.

Use the record shapes in `assets/record-templates.md` when introducing state.
Fit them to existing conventions; do not replace an established ID scheme.
Save progress after each document or consequential decision so a new session can
resume from files. A state record is continuity, not evidence of work completed.

If durable file output is unavailable, return bounded drafts and a resume record
inline when feasible, explicitly labeled unpersisted. State the missing delivery
and continuity capability; do not claim saved files, a download, or a resumable
background run. Block only actions that actually require that capability.

Research important external claims before relying on them. Prefer primary sources,
separate documentation claims from tested behavior, and verify exact artifacts,
versions, editions, licenses, and dependencies before calling them build-ready.
An accessible resource is not automatically reusable or safe to upload elsewhere.

## Cooperating skills and agents

Use available `grilling` and `domain-modeling` skills for interviewing and domain
definitions, and `clear-writing` for human-facing prose. Resolve them through the
host's available skill mechanism; do not assume a slash command is agent-callable.
If absent, preserve this skill's question, evidence, approval, and writing contracts
directly and report the capability gap. Missing helpers do not require installation.

Delegate independent research or bounded documents when available and permitted.
Give each worker the approved inputs, owned files, ID ranges, constraints, and
expected evidence. Workers may narrow permission, never broaden it or approve their
own proposals. The parent owns synthesis and checks; a returned document is not
automatically integrated or approved.

## Review and delivery

Before declaring completion, read `references/review-and-handoff.md`.
Use an independent reviewer when available. If the user requires independent review
and it cannot run, do not substitute self-review or publish as reviewed; report the
blocker while preserving completed drafts.

Give brief progress updates for meaningful findings or blockers. Do not end a batch
run while authorized, unblocked work remains merely described. If execution cannot
survive session closure, say so and persist the next action; do not promise an
unattended background run without a real execution capability.

Report delivered artifacts, review and checks actually performed, approval status,
open gates, and the first concrete implementation milestone. When publication was
requested, use an available repository-shipping workflow within the granted scope,
verify the remote result, and report it without implying the documents are approved.
