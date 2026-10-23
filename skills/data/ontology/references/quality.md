# Definition quality and soundness checks

Serves Step 3 onward. Read it when you write or review a definition, and before you hand any change to the owner. Identity and taxonomy checks live in `identity-taxonomy.md`; predicate checks in `promotion.md`; shape checks in `shacl.md`.

## Definition quality bar

Every authored definition meets all ten:

1. **Define, don't label.** State the recurring activity and its intended outcome.
2. **Primary purpose.** The decision, outcome or responsibility served, not the asset, department or data source.
3. **Bounded.** A scope note on every approved concept. Name an owner in an exclusion only if that owner exists in the taxonomy.
4. **Parent test.** "This is a way of carrying out [parent]" holds.
5. **Sibling-disjoint.** No two siblings claim the same primary activity.
6. **Stable terms.** One meaning per material term across the scheme.
7. **Park, don't smuggle,** as `foundations.md` sets it out.
8. **Evidence-based.** References inform; nothing is copied verbatim, because copied text carries another organization's scope and licence.
9. **Baseline preserved.** A comparison (actual against plan) uses the approved plan and its assumptions at the time, not a later forecast.
10. **Clean provenance.** Who wrote it, who approved it, when.

*Why:* each point is a way a definition failed a reader in practice; together they make a definition something a reviewer can reject.

**Say only what the source says.** When a definition cites a filing, every claim in it must be in that filing, with the item that holds it. *Why:* a plausible claim with no primary source is the builder's, not the source's.

**The human gate.** Candidate text collected from references goes through it, exactly like text a person wrote: a validator first (required fields, controlled values, no label collisions, no open questions on approved rows), then a person reviews the meaning. Nothing merges on assumption.

## Soundness checks on every change

**Evidence.**
- Every verdict records what was checked, what passed, who decided, and when.
- Take match types from the evidence file, never from memory or a neighbouring row.
- Held rows carry their reason and reopen condition in the source record.
- A supersession is explicit and keeps the earlier reason; append a dated note, never rewrite history.
- If the evidence does not establish something, the cell stays empty and the row stays held. No evidence, no fact.

**Counts.**
- Conservation is an equation. Recompute every figure from the source files before you write it.
- Every count change names the row ID, the old bucket, the new bucket and the reason.
- When one figure is wrong, assume it is wrong elsewhere: search every governed document for the old number, and recompute every table total.
- Search for the claim, not for the words your change used: the old figure in its other phrasings, across line breaks, and in record metadata. *Why:* a sweep with the change's own words finds only the places the change already touched.
- If figures do not reconcile, report the gap and stop. Never adjust a number to make the arithmetic work.

**Changes.**
- Name the one safety fact a change depends on and prove it by running code against the real artifacts. Mark anything unproven as unproven.
- A migration proves replacement, not deletion: a per-predicate ledger, a held-items report reconciled row by row, and a dry-run count reviewed before emission.
- Turn ordering dependencies into assertions that fail fast on known stale state. A rerun on unchanged input reproduces identical output.

**Sampling:** `promotion.md`, rule 6.
