# Organize an existing project

## Establish the baseline

Read the project instructions, charter or equivalent authority, handoff, index,
decision records, relevant code/configuration, and checks. Record the revision
being inspected and preserve unrelated working changes. Existing approvals stay
attached to their recorded content; a reorganization does not approve new design.

Inventory relevant files before drafting replacements. Identify each document’s
purpose, authority, approval state, overlap, consumers, and stale or missing
content. Check executable references such as build paths, imports, scripts, CI,
notebook paths, and generated outputs before proposing repository moves.

Separate an organizational problem from a design gap. Several documents covering
one subject may need one owner and links. An absent filename is not a missing
requirement if another document already covers it. Resolve conflicting statements
against recorded authority; leave unresolved policy choices visible.

## Plan the smallest useful change

For each affected file or subject, choose keep, move, combine, rewrite, archive,
or add, and state the reason. Name the authoritative destination and affected
consumers. Use existing IDs and conventions where they serve the project.
Do not create empty directories or split coherent documents to match an example.

Assess a supplied reference using `discovery.md`. Consider its applicable stack
before recommending substitutes, while preserving the current project’s contracts.
Record reuse, adaptation, deferral, or exclusion separately from adoption.

Distinguish path/link changes from substantive rewrites. Preserve approved
contracts and approval evidence. Label proposed amendments and list their affected
documents. Research new external claims before including them; moving existing
text does not require inventing a new architecture or repeating all discovery.

In interactive mode, present the plan at the agreed review boundary. In authorized
batch mode, record the bounded plan and proceed with reversible in-scope changes.
Ask only about choices that would change scope, authority, or delivery permission.

## Apply and verify

Keep one authoritative home per definition, decision, and current status. Update
indexes and references instead of copying contracts into summaries. Preserve
historical wording and source attribution; distinguish historical paths from
current navigation. Mark archives as superseded without deleting decision evidence.

When paths change, maintain a migration map where readers or downstream tools need
it. Update affected links, assets, commands, imports, configuration, and generated
twins together. Run project checks appropriate to the move; link validation alone
does not prove code or build paths still work.

Keep a running record of consequential changes, reasons, evidence, checks, and
remaining work in the project’s existing log or handoff. Separate current status
from dated history. Check that quotations and historical claims match the named
source revision and time; do not rewrite an earlier observation as a later result.

Use `review-and-handoff.md` for review and delivery. For this path, also verify
coverage survived consolidation, approved contracts were preserved or visibly
amended, old paths have no unintended live consumers, and rewrites did not invent
approvals. Report the reading order, migration map if needed, completed checks,
and unresolved gaps. Organization can be complete while implementation work
remains gated; identify that work without claiming it is implemented.
