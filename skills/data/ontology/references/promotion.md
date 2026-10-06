# Promoting provisional data into governed relationships

Read this before Step 4, or whenever rough source data (a workbook, a spreadsheet, an export) becomes governed triples. The usual pattern: capture the source first as provisional annotations in a staging namespace (for example `intake:`), then promote them. The staging layer may be the only copy of facts like "which process uses which input", so a careless promotion corrupts them without any visible error.

## The eleven rules

1. **Pin evidence to one commit.** Every evidence file records its commit and input hashes. Re-pin to the current approved commit before release. Build and evidence cite the same commit.
2. **Regenerate review packages after the taxonomy changes**, and diff them field by field against the old package.
3. **Carry an approval forward only for an unchanged row.** The one exception: a change that only adds a stable identifier or a citation, with source, verb, target and disposition unchanged. Record each use.
4. **Labels propose candidates. They never prove identity.**
5. **Structural nearness alone supports only a sequence between siblings.** Every other relation (enables, governed by, requires, assured by, depends on) also needs independent evidence: the target named in the source's definition or scope note, a strict two-way mention, or a recorded architecture decision.
6. **Sample automatic promotions; stop at the first wrong one.** `max(10, ceil(5%))` per domain, fixed recorded seed, a person reads each row's definitions. One wrong row stops the line: fix the rule, re-run, never patch the row.
7. **Conserve every source predicate and mention.** Emitted + held + merged + redirected = total, proved by arithmetic. Zero staging triples proves deletion, not migration.
8. **One stored direction per fact.** Derive inverses. Mirrors inflate counts and hide contradictions.
9. **Row-level evidence starts outside the graph** (versioned CSVs). Bring provenance in later, as qualified-relation nodes, if a consumer needs it.
10. **Release on one commit with a fresh consumer attestation.**
11. **Promotion never changes source meaning.** Emit, hold, defer or reclassify a disposition. Never replace a verb, invent a target or reinterpret meaning. Corrections go back to the source as a reviewed change.

## Standing triggers

- **Attack the premise.** Two failed fixes on one gate, or a check twice found not to test what you assumed: stop fixing, list what the check misses, fix the premise.
- **Failing check first.** Every regression fix starts with a check watched failing on the broken state.
- **Adversarial review first.** Review every evidence package independently (Act On / Consider / Noted / Dismissed) before the owner sees it.

## Reviewing one predicate family

1. **Fix the definition** before reading rows. It must be falsifiable.
2. **Build the batch:** every row asserting the verb, with source and target by slug, both definitions, the raw verb, the evidence tier, the proposed disposition.
3. **Verdict each row:** identity, then direction, then the definition test.
   - APPROVE: meets the definition; the fact is stored.
   - HOLD: fails, or evidence too weak; no fact; back to the source author. Never remap to another predicate.
   - STAND: already emitting correctly. Counts move only when a row changes bucket.
4. **Sample and reconcile** per rule 6.

Boundary wording ("excludes X", "owned by", "may be handled by") is never a route for any verb. A row verdict is not an architecture decision.

## Example predicate definitions

Write your own to your evidence. "Source" is the subject of the stored triple.

- `enabledBy`: the target supplies an operating base, control, mechanism, capability, resource or prerequisite that makes the source able to operate. "A enables B" is stored as `B enabledBy A`. Test: could the source operate without it?
- `informedBy`: the target provides context or planning input that shapes the source. Not every data flow.
- `dependsOnOutputOf`: the source consumes a specific output of the target.
- `requires`: the source cannot validly start, complete or proceed without the target or its condition, stated as a precondition in the source.
- `assuredBy`: the target performs governance, compliance, review or control-testing oversight over the source.
- `constrainedBy`: the target binds the source; the source cannot exceed, ignore or waive it.
- `governedBy`: the target holds policy, approval or enforcement authority over the source. Hierarchy position alone never qualifies.
- `triggeredBy`: the target generates or detects the event or handoff that starts the source.
- `precedes`: the source completes before the target begins, as the business states it.
