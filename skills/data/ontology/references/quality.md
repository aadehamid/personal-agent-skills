# Definition quality and soundness checks

Serves Step 3 onward. Read it when you write or review a definition, and before you hand any change to the owner. Identity and taxonomy checks live in `identity-taxonomy.md`; class and property rules in `domain-model.md`; predicate checks in `promotion.md`; shape checks in `shacl.md`.

## Definition quality bar

Every authored definition meets all eight points. Points 1 and 3 take the form for the term's kind (`domain-model.md`, rule 1). Record the review in `templates/definition-review.md`.

1. **Define, don't label, in the form for its kind.** Say what the term is in words other than its label:

   | Kind | Definition form | Parent test (point 3) |
   |---|---|---|
   | Activity or process | The recurring activity and its intended outcome. Classify by primary purpose: the decision, outcome or responsibility it serves, never the asset, department or system. | "This is a way of carrying out [parent]." |
   | Thing (a class, or a concept naming a kind of thing) | Genus and difference: "a [parent or broader kind] that [what sets it apart]", plus what makes two of them the same one ("identified by its barcode"). | "Every [term] is a [parent]." |
   | State or code value | The condition it names, of what, from when it starts until when it ends. | It is in its list's scheme; its siblings exclude each other unless the list says a thing can hold two at once. |
   | Property | Object or datatype: what it relates (domain to range) and what the link means in the business, in the stored direction. Annotation: what it records about a term and who reads it. | For a subproperty: every use of it is also a use of the parent. |

2. **Distinguishing.** The definition tells the term apart from its siblings and nearest neighbours; no two siblings share the part that sets them apart.
3. **Parent test.** The test for its kind (table above) holds. Top concepts and classes with no parent skip it.
4. **Bounded.** An approved concept has a scope note; an exclusion names an owner only if that owner exists in the ontology. A comparison (actual against plan) names the approved plan and its assumptions at the time, not a later forecast.
5. **Stable terms.** One meaning per material term across the ontology, and every material term the definition uses is defined in the ontology, in a module or source it cites, or on the parked list.
6. **Park, don't smuggle,** as `foundations.md` sets it out.
7. **Evidence-based.** Every claim is in the cited source, at the item that holds it. Nothing is copied verbatim, because copied text carries another organization's scope and licence.
8. **Clean provenance, by role.** `dcterms:creator` names a role IRI (the modeller, the ontology owner), never a person; `dcterms:dateAccepted` gives the approval date; `skos:changeNote` names the decision record that approved it. A term without `dcterms:dateAccepted` is a candidate.

*Why:* each point is a way a definition fails a reader, and together they make a definition something a reviewer can reject. The genus-and-difference form is the intensional definition of ISO 704:2022, *Terminology work: Principles and methods*; the other forms carry the same idea to activities, states and links, which have no genus a reader would name. Point 8 uses roles because a personal name in an approval field makes a governed release read as one person's opinion and puts personal data into every copy (`governance.md`, rule 23).

**The human gate.** Candidate text collected from references goes through it, exactly like text a person wrote: first `scripts/check_taxonomy.py`, then a person reviews the meaning against the bar. An open question is a question recorded against a term (in the decision log, or as a `skos:editorialNote` starting "OPEN:") that has no answer yet; no approved term has one. Nothing merges on assumption.

## The qSKOS issues

qSKOS (Mader, Haslhofer and Isaac; its wiki page "Quality Issues", `SOURCES.md` section 4) lists 29 quality issues for SKOS vocabularies. `scripts/check_taxonomy.py` checks every one that holds for a closed, offline build under this skill's rules; its docstring names the check for each. *Why:* each issue is one a reviewer would otherwise have to spot by eye.

| qSKOS issue | In this skill |
|---|---|
| Omitted or Invalid Language Tags | `untagged`; `lang-tag` (BCP 47) |
| Incomplete Language Coverage; No Common Language | `language` |
| Undocumented Concepts | `definition`, which is stricter: every concept needs a `skos:definition` |
| Overlapping Labels | `collision` (preferred labels, then alternative and hidden labels against other concepts' labels) |
| Missing Labels; Empty Labels | `label` |
| Unprintable Characters in Labels | `label-chars` |
| Ambiguous Notation References | `notation` |
| Orphan Concepts; Disconnected Concept Clusters | Left out. A code list is a flat scheme of top concepts by design (`identity-taxonomy.md`, Step 3, rule 11), and `parent` already ties every other concept to a top concept. |
| Cyclic Hierarchical Relations; Top Concepts Having Broader Concepts; Hierarchical Redundancy | `parent`: one `skos:broader`, none on a top concept, no cycles. One parent leaves no room for a redundant path. |
| Valueless Associative Relations; Relation Clashes (SKOS S27); Reflexive Relations | `related`; `mapping` for a concept mapped to itself; a `skos:broader` to itself is a cycle |
| Solely Transitively Related Concepts | `transitive` |
| Unidirectionally Related Concepts | `reciprocal` for `skos:related`, `skos:topConceptOf` and a stated `skos:narrower`. The skill states `skos:broader` only, so a `skos:broader` without its `skos:narrower` passes. |
| Omitted Top Concepts | `scheme` |
| Inconsistent Preferred Labels | `label` (one `skos:prefLabel` per language, SKOS S14) |
| Disjoint Labels Violation (SKOS S13) | `disjoint-labels` |
| Mapping Clashes (SKOS S46); Mapping Relations Misuse | `mapping`. Misuse counts only when both concepts are declared in the files, since an external target's scheme is unknown there. |
| Undefined SKOS Resources | `skos-term` |
| HTTP URI Scheme Violation | `uri-scheme` |
| Missing In-Links; Missing Out-Links; Broken Links | Left out. They need the web or a remote index, and the script runs offline, so it gives the same answer on every run. Mapping to outside vocabularies is a Step 7 choice (`integration.md`), not a rule for every concept. |

## Soundness checks on every change

Before you hand a change to the owner, run these checks on what changed, then the project's full check script. *Why:* the checks below catch what a script cannot judge, and the script catches the rest.

**Evidence.**
- Every verdict records what was checked, what passed, who decided (by role), and when.
- Take match types from the evidence file, never from memory or a neighbouring row.
- Held rows carry their reason and reopen condition in the source record.
- A supersession is explicit and keeps the earlier reason; append a dated note, never rewrite history.
- If the evidence does not establish something, the cell stays empty and the row stays held. No evidence, no fact.

**Counts.**
- Conservation is an equation. Recompute every figure from the source files with committed code before you write it (`governance.md`, rule 15).
- Every count change names the row ID, the old bucket, the new bucket and the reason.
- When one figure is wrong, assume it is wrong elsewhere: search every governed document for the old number, and recompute every table total.
- Search for the claim, not for the words your change used: the old figure in its other phrasings, across line breaks, in record metadata, and every decision-record number the changed statement cites in its full, short and range forms. *Why:* a sweep with the change's own words finds only the places the change already touched.
- If figures do not reconcile, report the gap and stop. Never adjust a number to make the arithmetic work.

**Changes.**
- Name the one safety fact a change depends on and prove it by running code against the real artifacts. Mark anything unproven as unproven.
- A migration proves replacement, not deletion: a per-predicate ledger, a held-items report reconciled row by row, and a dry-run count reviewed before emission.
- Turn ordering dependencies into assertions that fail fast on known stale state. A rerun on unchanged input reproduces identical output.

**Sampling:** `promotion.md`, rule 6.
