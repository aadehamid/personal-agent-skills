# Promoting provisional data into governed relationships

Serves Step 4. Read it before Step 4, and whenever rough source data (a workbook, a spreadsheet, an export) becomes governed triples.

The usual pattern: capture the source first as provisional annotations in a staging namespace (for example `intake:`), then promote them. The staging layer may be the only copy of facts like "which process uses which input", so a careless promotion corrupts them without any visible error: the triples look fine but no longer say what the business said.

## The eleven rules

1. **Pin all evidence to one commit.** Every evidence file records its commit and the hashes of its inputs; re-pin to the current approved commit before release. *Why:* a stale baseline approves different data: target labels can be renamed under approved rows between two package versions, and only the pin and a field diff show it.
2. **Regenerate review packages after any rename, move or reclassification**, from the pinned baseline, and diff them field by field against the old package. *Why:* same failure as rule 1.
3. **Carry an approval forward only for a row identical on every evidence field.** The one exception: a change that only adds a stable identifier or a citation, with source, verb, target and disposition unchanged. Record each use of the exception. *Why:* an approval covers the row the reviewer read, not its successor.
4. **Labels propose candidates; they never prove identity.** *Why:* see `identity-taxonomy.md`, Step 2, rule 8.
5. **Structural nearness is evidence only for a sequence between siblings** ("A precedes B"). Every other relation (enables, governed by, requires, assured by, depends on) also needs independent evidence: the target named in the source's definition or scope note, a strict two-way mention, or a recorded architecture decision. *Why:* an evidence pass that counts terminology notes as citations and any back-link as confirmation is wrong and confident.
6. **Sample automatic promotions, and stop at the first wrong one.** Sample `max(10, ceil(5%))` per domain with a fixed, recorded seed; a person reads each sampled row's definitions. A sample is pending until the owner reviews it. One wrong resolution stops the line and is never averaged away: fix the rule and re-run, never patch the row. *Why:* a wrong row means a wrong rule, which made other wrong rows.
7. **Conserve every source predicate and every mention.** A conservation ledger (a table, one row per staging predicate, with its source count and where each triple went) accounts for each staging triple and mention: emitted, held, merged or redirected, and the arithmetic balances. *Why:* zero staging triples proves deletion, not migration.
8. **Store one direction per fact; derive inverses.** *Why:* mirrored rows inflate the fact count and hide contradictions.
9. **Keep row-level evidence outside the graph at first** (versioned CSVs). Bring it in later as one qualified-relation node per fact if a consumer or a shape needs it (`shacl.md`). *Why:* the graph stays small until someone needs the provenance.
10. **Release on one commit, with a fresh consumer attestation.** Build, evidence and consumer-impact scan cite one commit; confirm again who consumes the ontology right before release. *Why:* a scan on one commit says nothing about a build cut from another.
11. **Promotion never changes source meaning.** The pipeline may emit, hold, defer or reclassify a disposition. It never replaces a verb, invents a target or reinterprets meaning; corrections go back to the source as a reviewed change. *Why:* a script that picks a nicer predicate for a mistyped verb hides an authoring error inside the ontology.

**Give every source mention a disposition.** Only mentions that resolve to a concept become relationship triples. Each other mention becomes a parked future concept, a structured value, an external reference, a dropped mention or a deferred ambiguity, and is recorded. *Why:* an unrecorded mention breaks rule 7.

## Standing triggers

- **Attack the premise.** Two failed fixes on one gate, or a check twice found not to test what you assumed: stop fixing, list what the check misses, fix the premise.
- **Failing check first.** Every regression fix starts with a check you watched fail on the broken state.
- **Adversarial review first.** Every evidence package gets an independent review (Act On / Consider / Noted / Dismissed) before the owner sees it.

## Reviewing one predicate family

Review one verb per pass. *Why:* a reviewer holding one definition applies it consistently; mixing verbs lets definitions drift into each other.

1. **Fix the definition before reading rows.** It must be falsifiable: you can read a row and say "this fails". *Why:* a definition every row passes is no definition.
2. **Build the batch:** every row asserting the verb, with source and target by slug, both definitions, the raw verb, the evidence tier and the proposed disposition. The reviewer reads the definitions, not the pipeline's recommendation.
3. **Verdict each row:** identity, then direction, then the definition test.
   - **APPROVE:** meets the definition; the fact is stored.
   - **HOLD:** fails, or the evidence is too weak. No fact; the reason is recorded in the source record with what would reopen it. If the row was emitting, its fact is removed and no substitute is emitted. A hold is never a remap to another predicate. *Why:* the source author chose the verb, so a wrong verb is fixed in the source.
   - **STAND:** already emitting correctly. Counts move only when a row changes bucket.
4. **Sample and reconcile** per rule 6: every row has a verdict and the ledger balances.

Two citation rules hold for every verb. **Boundary wording is never a route:** "excludes X", "owned by" and "may be handled by" say where a boundary lies, not that a relationship holds. **A row verdict is not an architecture decision:** only a recorded architecture decision counts as decision evidence.

## The release gate and the source-correction backlog

Before the first module release:

1. **Decide which held rows go back to the source author, and record that list: the source-correction backlog.** A held row reaches the source author only through this list. *Why:* a hold sent around the list bypasses the owner's decision.
2. **Release only when every backlog row has a fresh verdict after its correction.** The fresh verdict may be HOLD again, with its reason. *Why:* a row released before it settles loses its provisional form and needs a second release.
3. **Held rows not on the list stay held with their reason**, emit nothing, and wait for a later release.
4. **Retire the provisional layer in one release** while no consumer is active (`foundations.md`, policy 9), and check the release with the SHACL slice (`shacl.md`).

Working a backlog of a few hundred rows goes fastest as one answer register, built and checked in batches:

1. **Draft one answer per row:** the corrected verb or target, or "no relationship"; the stored fact; one sentence for the source's scope note. Flag rows that need the owner's judgement; the owner approves the register as a whole and answers the flagged rows.
2. **Correct the source in place.** Change a row's verb or target where it stands; never add, remove or move a relationship, because row IDs usually follow position. *Why:* moving one assertion renumbers every later row.
3. **When an approved fact runs opposite to its row**, first add a mirror raw verb ("provides input to" for "uses input") to the direction table and the correction tool's known verbs, with a decision record. *Why:* item 2 forbids moving the assertion.
4. **Make the correction tool refuse, before it writes,** a missing, duplicated or converging segment, an unknown verb, or a target containing the cell's delimiter. A "no relationship" answer is a fresh HOLD with the answer as its reason. *Why:* a half-applied correction is worse than none.
5. **Add each answer's sentence to the source's scope note.** *Why:* it becomes the affirmative citation rule 5 asks for.
6. **Rebuild, re-pin and re-run the whole pipeline in a copy.** Adopt the output only if every changed row belongs to the batch; keep review notes the pipeline does not reproduce. *Why:* an unexpected changed row is a defect somewhere else.
7. **Check each batch against the approved register:** exactly the batch's rows, each decided field, the stored fact, the published sentence, and the published taxonomy equal to the pinned copy. *Why:* one register check replaces many per-row hold checks.
8. **Use a row-level verdict when a grouping heuristic would turn a corrected verb into another predicate.** *Why:* rule 11.

## Building the first release from evidence

1. **Build with a script that reads only the pinned evidence**, stops on any staging triple, blank node or staging predicate without a target, and writes the after half of the ledger (one row per staging predicate, with source and migrated counts). *Why:* the release must be reproducible from evidence alone.
2. **Give the builder one source of targets: a decision record.** Where a draft ledger and an approved decision disagree, record the approved target, update the ledger, and mark where it disagreed. *Why:* a builder that chooses between sources at write time is authoring meaning.
3. **Test the builder from outside.** Tests read each staging value from the source and check it sits on its recorded target in the built graph, with every value a rule produces; pin measured splits so that routing every value one way fails. Prove the tests by sending one field to the wrong target and watching them fail. *Why:* conservation counts balance even when a field lands on the wrong property.

Packaging, versioning and later releases: `release.md`.

## Example predicate definitions

Write your own to your evidence. "Source" is the subject of the stored triple.

- `enabledBy`: the target supplies an operating base, control, mechanism, capability, resource or prerequisite that makes the source able to operate. "A enables B" is stored as `B enabledBy A`. Test: could the source operate without it?
- `informedBy`: the target provides context or planning input that shapes the source. Not every data flow; hold a row whose citation shows information flowing the other way.
- `dependsOnOutputOf`: the source consumes a specific output of the target. A broken output is a data problem; a missing capability is `enabledBy`.
- `requires`: the source cannot validly start, complete or proceed without the target or its condition, stated as a precondition in the source.
- `assuredBy`: the target performs governance, compliance, review or control-testing oversight over the source. Supplying evidence is not assurance.
- `constrainedBy`: the target binds the source; the source cannot exceed, ignore or waive it.
- `governedBy`: the target holds policy, approval or enforcement authority over the source. Hierarchy position alone never qualifies.
- `triggeredBy`: the target generates or detects the event or handoff that starts the source. "Feeds" and "precedes" are not triggers.
- `precedes`: the source completes before the target begins, as the business states it. Siblings need no more; non-siblings need the sequence stated in the source or a strict two-way pair.
