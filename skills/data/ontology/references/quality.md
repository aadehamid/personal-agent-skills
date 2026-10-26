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
4. **Bounded.** An approved concept has a scope note; an exclusion names an owner only if that owner exists in the ontology. A scope note that names another concept gets a reciprocal sentence in that concept's scope note. A comparison (actual against plan) names the approved plan and its assumptions at the time, not a later forecast.
5. **Stable terms.** One meaning per material term across the ontology, and every material term the definition uses is defined in the ontology, in a module or source it cites, or on the parked list.
6. **Park, don't smuggle,** as `foundations.md` sets it out.
7. **Evidence-based.** Every claim is in the cited source, at the item that holds it. Nothing is copied verbatim, because copied text carries another organization's scope and licence.
8. **Clean provenance, by role.** `dcterms:creator` names a role IRI (the modeller, the ontology owner), never a person; `dcterms:dateAccepted` gives the approval date; `skos:changeNote` names the decision record that approved it. A term without `dcterms:dateAccepted` is a candidate.

*Why:* each point is a way a definition fails a reader, and together they make a definition something a reviewer can reject. The genus-and-difference form is the intensional definition of ISO 704:2022, *Terminology work: Principles and methods*; the other forms carry the same idea to activities, states and links, which have no genus a reader would name. Point 8 uses roles because a personal name in an approval field makes a governed release read as one person's opinion and puts personal data into every copy (`governance.md`, rule 23).

**The human gate.** Candidate text collected from references, or proposed from a document by a model (`governance.md`, "Candidates from documents"), goes through it, exactly like text a person wrote: first `scripts/check_taxonomy.py`, then a person reviews the meaning against the bar. An open question is a question recorded against a term (in the decision log, or as a `skos:editorialNote` starting "OPEN:") that has no answer yet; no approved term has one. Nothing merges on assumption.

## The qSKOS issues

qSKOS (Mader, Haslhofer and Isaac; its wiki page "Quality Issues" and the v2.0.4 code, `SOURCES.md` section 4) lists 29 quality issues for SKOS vocabularies. `scripts/check_taxonomy.py` checks each one that holds for a closed, offline build, following the v2.0.4 query for it; its docstring names the check for each. Where the skill differs from qSKOS on purpose, the table says how. *Why:* each issue is one a reviewer would otherwise have to spot by eye.

| qSKOS issue | In this skill |
|---|---|
| Omitted or Invalid Language Tags | `untagged`; `lang-tag` checks that a tag is well-formed (RFC 5646, section 2.1, grandfathered tags included). qSKOS also requires a primary language in Java's ISO 639 list, which rejects valid three-letter codes such as `haw` and private-use tags; the skill does not copy that. |
| Incomplete Language Coverage; No Common Language | `language`, over every language-tagged literal a concept has, as qSKOS reads it |
| Undocumented Concepts | `definition`, which is stricter: every concept needs a `skos:definition` |
| Overlapping Labels | `collision`: two concepts sharing a preferred, alternative or hidden label, ignoring the case of the label and of its language tag, in any scheme. One exception, decided by the skill's owner on 2026-10-25: concepts in different schemes may share a preferred label; inside one scheme a shared preferred label still fails. *Why:* each scheme is its own vocabulary, and the label is the right business term in each (a status "Approved" in two code lists); qSKOS targets ambiguity inside one vocabulary, and identity is the IRI (`identity-taxonomy.md`, Step 2, rule 1). An alternative or hidden label shared with any other concept still fails, because a search on it would find two concepts. qSKOS v2.0.4 reports every shared label. |
| Missing Labels; Empty Labels | `label`. A scheme or collection needs a `skos:prefLabel`, `rdfs:label` or `dcterms:title`. qSKOS also accepts DC Elements `dc:title` and does not accept `skos:prefLabel`; the skill writes DCMI Terms only (`SOURCES.md`, section 4), so a `dc:` predicate fails `property-kind`. |
| Unprintable Characters in Labels | `label-chars` |
| Ambiguous Notation References | `notation` |
| Orphan Concepts; Disconnected Concept Clusters | Left out. A code list is a flat scheme of top concepts by design (`identity-taxonomy.md`, Step 3, rule 11), and `parent` already ties every other concept to a top concept. |
| Cyclic Hierarchical Relations; Top Concepts Having Broader Concepts; Hierarchical Redundancy | `parent`: one `skos:broader`, none on a top concept, no cycles. One parent leaves no room for a redundant path. |
| Reflexive Relations | `related`: a concept linked to itself by any SKOS semantic relation, or by a property the files declare beneath one. A `skos:broader` to itself is reported as a `parent` cycle. |
| Valueless Associative Relations; Relation Clashes (SKOS S27) | `related`, for `skos:related` and `skos:relatedMatch`; siblings share a parent directly or through the transitive properties |
| Solely Transitively Related Concepts | `transitive`: a stated transitive relation needs a `skos:broader` path (or `skos:narrower` the other way) behind it |
| Unidirectionally Related Concepts | `reciprocal`, for every inverse pair qSKOS checks, between concepts declared in the files, since an outside target cannot state its side. The skill states `skos:broader` only, so a `skos:broader` without its `skos:narrower` passes; a stated `skos:narrower` needs its `skos:broader`. |
| Omitted Top Concepts | `scheme` |
| Inconsistent Preferred Labels | `label` (one `skos:prefLabel` per language, SKOS S14) |
| Disjoint Labels Violation (SKOS S13) | `disjoint-labels` |
| Mapping Clashes (SKOS S46) | `mapping`: a chain of `skos:exactMatch`, either way, joining two concepts that are also linked by `skos:broadMatch`, `skos:narrowMatch` or `skos:relatedMatch` |
| Mapping Relations Misuse | `mapping`: a mapping between two concepts declared in the files that share a scheme or are both in no scheme. An outside target's scheme is unknown in the files. |
| Undefined SKOS Resources | `skos-term` |
| HTTP URI Scheme Violation | `uri-scheme`, for SKOS concepts, schemes and collections, ignoring case. qSKOS checks every subject; the skill leaves other subjects, such as a `urn:` source record, alone. |
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

## The vocabulary standards behind these rules

The definition, label and scope-note rules were checked against ANSI/NISO Z39.19-2005 (R2010), *Guidelines for the Construction, Format, and Management of Monolingual Controlled Vocabularies*, read in full. ISO 25964-1:2011 (*Thesauri for information retrieval*) and ISO 25964-2:2013 (*Interoperability with other vocabularies*) are its international counterparts; their text is paywalled and was not read, so no rule here claims to follow their clauses. Each row below says whether the skill's rule is the same as Z39.19's or differs from it, and every difference is deliberate, with its reason. Section numbers and quotations are Z39.19's.

| Z39.19 says | This skill | Same, or why it differs |
|---|---|---|
| "A scope note should state the chosen meaning of a term. It may also indicate other meanings that are recognized in natural language, but which have been deliberately excluded from the controlled vocabulary." (§6.2.2) | Point 4: every approved concept has a scope note; an exclusion it states names an owner only if that owner exists in the ontology | Stricter on purpose: a scope note is required on every approved concept, where Z39.19 supplies one when a term needs it. What a scope note must say is the skill's own: the chosen meaning is stated by the definition (point 1), and an exclusion names an owner only if that owner exists; §6.2.2's "may" on excluded meanings is unchanged. |
| "When reference is made to other terms in a scope note, a reciprocal scope note should generally be provided for each term mentioned." "Even where the scope of only one of the terms requires clarification, it is useful to note in the term record for the second term that it has been cited in a scope note of a different term." Its Example 12 writes that note as "X SN" (§6.2.2.1) | Point 4: a scope note that names another concept always gets a reciprocal sentence in that concept's scope note | Stricter on purpose: SKOS has no cross-reference field like "X SN", so a sentence in the other concept's scope note is the only place its record can show the link. |
| "Each term should have a history note recording its date of entry"; it "should also track the history of modifications ..., recording previous forms with reasons for the change" (§11.3.2.2); when relationships change, "a record of the old ones should be maintained in the history note as well" (§11.3.1.2) | The entry date is `dcterms:dateAccepted`, and `skos:changeNote` names the decision record with the reason (point 8); each release's changelog says what changed, why and who approved (`release.md`, rule 18); a released package never changes (`release.md`, rule 10), so a term's previous form and old relationships stay in the earlier release; former names that are not live aliases go in a history annotation (`identity-taxonomy.md`, Step 3, rule 8) | Differs on purpose: the history lives in the decision records and the immutable releases rather than in one note per term, because a hand-kept note would repeat them and could drift from them. |
| "A compound term should be used instead of a single-word term with a parenthetical qualifier, if usage permits, i.e., if the compound occurs in natural language." (§6.2.1 a); "A qualifier should be added to each homograph, even when one is used in the primary sense of the domain and the second in a different sense." (§6.2.1 b); "A homograph's parenthetical qualifier may be left out when a term is used in only one of its meanings within a given controlled vocabulary domain and the meaning is obvious to users within that domain. However, if the vocabulary will be used across domains, e.g. in a multidisciplinary retrieval system, the qualifier should be included as it facilitates cross-database searching and mapping of terms in disparate domains." (§6.2.1 c) | `collision` ("The qSKOS issues" above): no two concepts share a preferred, alternative or hidden label, ignoring the case of the label and of its language tag, in any scheme, except a preferred label of concepts in different schemes; labels are presentation and identity is the IRI (`identity-taxonomy.md`, Step 2, rule 1) | Differs on purpose: the skill has no rule on compounds or qualifiers. It keeps labels apart with the `collision` check and identifies each concept by its IRI, so how a label is made distinct is the modeller's choice. |
| Count nouns "should normally be expressed as plurals" (§6.5.1); "If in the domain of the controlled vocabulary there is literary or user warrant for the expression of count nouns in the singular, establishment of terms in that form is acceptable" (§6.5.1.1) | Entity and class names are singular nouns (`foundations.md`, conceptual modelling, rule 3); activities and states are named as the domain names them | Same, through §6.5.1.1: a class names what one instance is, and OWL and conceptual-modelling usage is the warrant. |
| "Abbreviations and acronyms should be selected as terms only when they have become so well established that the full form of the term or proper name is rarely used. Cross-references should be made from the full forms." (§6.6.3.1); "The full form of terms should be selected as terms when the abbreviated form is not widely used and generally understood. Cross references should be made from the abbreviated forms." (§6.6.3.2.1); "the full form of the term should therefore be selected as the term in preference to the abbreviated form, even when the abbreviation has only one value in the domain of the controlled vocabulary" (§6.6.3.2.2) | `identity-taxonomy.md`, Step 3, rule 8: the full form is the preferred label and the abbreviation an alternative label; an established abbreviation may be the preferred label; an abbreviation with more than one expansion takes the full form | Same for §6.6.3.2.1 and §6.6.3.2.2, with `skos:altLabel` as the cross-reference. Differs from §6.6.3.1 on purpose: where Z39.19 says an established abbreviation should be the term, the skill says it may, and the default stays the full form, because an ontology's labels are read by consumers outside the domain who may not know the abbreviation. |
| The generic relationship "is often called “IsA.”"; test it with "[narrower term] is a [broader term]" and the "all-and-some" test (§8.3.1); "Hierarchical relationships cover three logically different and mutually exclusive situations": generic, instance and whole-part (§8.3) | The parent test for each kind (point 3) | Same for things and classes: "Every [term] is a [parent]" is the IsA sentence. Differs on purpose for the other kinds, whose tests are the skill's own: an activity is "a way of carrying out" its parent, a subproperty's every use is a use of its parent (the meaning of `rdfs:subPropertyOf`), and a code value is a member of its list's scheme, which is not a hierarchical relationship. Z39.19 builds hierarchies of terms for indexing; these kinds need a test their own semantics can pass. |
| "Some concepts belong, on logical grounds, to more than one category. They are then said to possess polyhierarchical relationships." (§8.3.4) | Exactly one parent (`identity-taxonomy.md`, Step 3, rule 2) | Differs on purpose: the parent test and every roll-up query assume a tree. Model a second view as its own scheme. |
| "All terms in a controlled vocabulary must have an unambiguous, non-redundant definition", with the note "This is a design goal that may not be true in practice" (§4.1, under "controlled vocabulary"); "a scope note (SN) can be supplied for any term" (§6.2.2) | A definition on every concept, class and property, to the eight points, is a gate (Step 3); a scope note on every approved concept (point 4) | Stricter on purpose: Z39.19 itself calls the definition requirement a design goal; here it is a check, because an ontology's consumers read the definition. |

*Why:* a reviewer can then trace each rule to a published standard, and a rule that departs from the standard is visible as a choice rather than an accident.
