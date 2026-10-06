# Definition quality and soundness checks

Read this when writing or reviewing definitions (Step 3 onward), and before handing any change to the owner.

## Definition quality bar

Every authored definition meets all ten:

1. **Define, don't label.** State the recurring activity and its intended outcome.
2. **Primary purpose.** The decision, outcome or responsibility served, not the asset, department or data source.
3. **Bounded.** A scope note on every approved concept. Name an owner in an exclusion only if that owner exists in the taxonomy.
4. **Parent test.** "This is a way of carrying out [parent]" holds.
5. **Sibling-disjoint.** No two siblings claim the same primary activity.
6. **Stable terms.** One meaning per material term across the scheme.
7. **Park, don't smuggle.** No data fields, systems, KPIs, controls or thresholds as concepts.
8. **Evidence-based.** References inform; nothing is copied verbatim.
9. **Baseline preserved.** Comparisons use the approved plan and its assumptions at the time.
10. **Clean provenance.** Author, approver, date.

Candidate text collected from references goes through a human gate, exactly like text a person wrote.

## Soundness checks

**Identity.** Identity before direction before meaning. A label suggests a candidate and never confirms one. Renames are overlay fields on the identity map; restore them after any regeneration before rebuilding the Turtle.

**Taxonomy.** Exactly one parent per concept, except the scheme's top concepts (`skos:topConceptOf`), which have none; no cycles; every concept at a level, with its parent shown unless it is a top concept; one `prefLabel` per language; a language tag on every literal; local IDs as `skos:notation`; external IDs via `dcterms:references`.

**Predicates.** Judge each row against its written definition. Never translate a verb silently. A failing row is held, and its fact removed if it was emitting.

**Evidence.** Every verdict records what was checked, what passed, who decided, when. Match types come from the evidence file. Held rows carry their reason and reopen condition in the source record. Supersessions keep the earlier reason; history is appended, never rewritten. No evidence, no fact.

**Counts.** Conservation is an equation. Every count change names row ID, old bucket, new bucket, reason. When one figure is wrong, search every governed document for it. If figures do not reconcile, report and stop.

**Changes.** Name the one safety fact a change depends on and prove it by running code against the real artifacts. Migrations prove replacement with a per-predicate ledger and a dry-run count. Reruns on unchanged input produce identical output.

**Sampling.** Samples come only from promotions, with a recorded seed, and stay pending until the owner reviews them. One wrong sample stops the pass.
