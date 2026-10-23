# Governance: decisions, delegation, checks, review and publication

Read it before you start a new ontology, record a decision, work under a delegation, set up checks, review a change, release or publish.

The `way-of-working` skill (`skills/engineering/way-of-working/`) is the general engineering standard: decision records, the pull-request loop, the check script and the shared tool. This file adds what an ontology build needs on top of it, and points to the rule's home where another file already holds it. "As practised" below means the rule was proven in a completed multi-module ontology build that used this method.

## Before modelling: name the gaps

1. **Sort the inputs into six kinds before any modelling: purpose (users, use cases, scope), competency questions, representative data, reusable vocabularies, semantic evidence (glossaries, filings, definitions) and constraints. Name each one that is missing or thin, say how the gap limits the design, and stop for the owner's answer.** Invent no requirement to fill a gap. *Why:* a model built over a silent gap encodes the builder's guess as the business's requirement. Source: adapted from the five input buckets of the `ontology-builder-assistant` skill (competency questions split out of purpose here), Jesús Barrasa, Going Meta S03E07, "Agent Skills For Creating and Using Ontologies" (7 April 2026), `session45/.agent/skills/ontology-builder-assistant/SKILL.md` lines 17 to 28, https://github.com/jbarrasa/goingmeta.
2. **Keep the requirements machine-readable (one file: purpose, users, use cases, in and out of scope, competency questions with id, priority and rationale, assumptions, constraints), and check them for conflicts in the check script.** A conflict is, for example, an area listed out of scope that a question's rationale needs. *Why:* the example file in the same session puts provenance out of scope while its first question's rationale requires it (`session45/requirements/requirements_scope.yaml` lines 18 and 23), and no gate in that skill catches it.

## Decisions

General record rules (one record per decision, quote the question, nothing added under the owner's decision, amend rather than rewrite) live in `way-of-working`, `references/deciding.md`. Copy `templates/decision-record.md`.

3. **Number every record and give each decision its own.** *Why:* a later record, a test or a release manifest can then cite exactly one decision, and an amendment names the record it changes.
4. **Save the owner's words verbatim in an answers file before you quote them** (`templates/answers-file.md`). The file holds only the owner's words; your questions and options sit inside an HTML comment. Nobody edits it after saving. *Why:* a quote taken from chat or memory cannot be checked, and an edited answers file proves nothing.
5. **Make the Status say whose decision it is:** `Proposed`, `Decided (the owner, <date>)`, or `Decided (delegated under <record>)`. Split the Decision section into the owner's decision (their words, or the option text they chose) and "What follows", written as the agent's. *Why:* a reviewer reads the owner's part line by line against the saved words, and an added phrase there reads as the owner's.
6. **Call a decision Decided only with the owner's recorded words or a recorded delegation that covers it. A merge decides nothing.** *Why:* a reviewer's MERGE checks the change, not the owner's intent.
7. **Check quotes mechanically.** The check script compares every quoted span in a record's recorded-words section with the answers file it cites, and fails on a mismatch. Check the rest by hand: paraphrases, PR bodies, and that the text claims no more than the words say. *Why:* as practised, a reason stating more than the answer, and a quote taken only from a chat session, each reached a pull request before a reviewer caught it.
8. **Keep the method and the record apart:** this skill (or the project's playbook) holds company-neutral method; project decisions go in records. When a decision also improves the method, change the method in the same pull request. Home: `way-of-working`, `references/documents.md`. *Why:* a method full of project rulings cannot be reused.
9. **When a gate read literally blocks far more than the plan intended, put the scope to the owner with figures from the shared tool and options; never narrow it yourself.** *Why:* as practised, a release gate read literally covered every held row, while the plan meant only the source-correction backlog (`promotion.md`); choosing between them was the owner's call.

## Delegation

10. **Record a delegation as its own decision record, with the owner's words, its scope (which questions or steps), the evidence order each decision must rest on, and how each decision is recorded.** *Why:* the record is the owner's decision to delegate, so it is what makes each delegated decision count as Decided.
11. **Mark every delegated decision "delegated under <record>", with its evidence, and keep it reversible:** the owner can reverse any one, and the reversal is recorded the same way. *Why:* the owner can then audit each decision and find what to undo.
12. **Keep with the owner what `SKILL.md` reserves** (statements only the owner can make; the approvals in `release.md`, "Who approves"), **plus any change to the delegation itself and any question outside its named scope.** Ask to extend the scope; do not stretch it. *Why:* a delegation covers what its words cover, and as practised its extension to later steps was a separate question with its own answer.
13. **Amend a delegation in the same record, as a dated amendment with the owner's words, and add a dated note to each sentence it replaces.** *Why:* a reader of an old sentence then finds what replaced it.
14. **Attribute every open item to whoever its record names: the owner, a named process owner, the business, a later release, "no confirmer named", or "unresolved by decision".** Never list them all as the owner's. *Why:* a list headed "waits on the owner" that holds a process owner's confirmation asks the owner for something they cannot give, and hides whom to ask.

## Checks

Mechanics of the one check script (CI and the pre-push hook both run it; the no-writes guard's four snapshots; wiring the hook) live in `way-of-working`, `references/guardrails.md`. Copy `templates/check.sh`.

15. **Make the check script rebuild and verify every generated file and run every test:** each package builder's and the catalog's `--verify` (`release.md`, rules 9 and 19), every module's shapes and the whole-graph gate (`shacl.md`), the competency-question regression (`regression.md`, rule 13), every test file, and the shared tool's consistency checks (decision index, quotes, names). *Why:* a generated file that no check rebuilds can drift from its sources without a failure.
16. **A check never writes to the repository.** Builders write to a temporary directory and `--verify` compares; the script fails if the tree changed. *Why:* a check that edits what it checks can pass by changing it, and a local run and CI then disagree.
17. **Keep every check blocking: the work is not done while the check script exits non-zero.** *Why:* an advisory failure is read as a pass. Source: `neo4j-ontology-skill` 1.0.1, `SKILL.md` lines 50 to 52 ("never present an ontology as done with a non-zero exit"), commit 39247b9 (21 October 2026), https://github.com/neo4j-contrib/neo4j-skills/tree/39247b9c4ab20062aefd1cfe83c040167ef9ee83/neo4j-ontology-skill.
18. **Pin the schema or shape version each validator checks against, and fail when that exact version cannot be loaded.** Never fall back to a moving "current" or a branch head. *Why:* the same skill's validator falls back to a moving alias and then a branch when the named version cannot be fetched, and reports it only on stderr (`scripts/validate.py` lines 106 to 121), so a pass may be against a schema the document never named.

## Figures and repository-wide searches

The rule (one tested tool in the repository answers figures and searches; never a one-off script or memory) lives in `way-of-working`, `references/guardrails.md`. Counting rules live in `quality.md`, "Counts".

19. **Give the shared tool, at least: `counts` (ledger buckets, held rows, question statuses), `row <id>`, `find <text>` (also matching text split across lines), `sweep <base>`, and the checks `decisions`, `quotes` and `names`.** Quote its commit line in the pull-request body. *Why:* every figure a document states then traces to one computation at one commit.
20. **Make a change reach every place it applies:** run `sweep` against the base branch (it lists where the words the branch replaced still stand), then `find` every status, rule, term or figure you changed in each wording it can take: the bare old figure, the other members of a set you added to, and every record number a changed statement cites in its full, short and range forms. *Why:* a sweep sees only the exact words changed, and as practised a second copy of a sentence citing the same record was missed by a search on its wording.

## Generated content

21. **Generate structure (triples, shapes, packages, projections) with deterministic code from the sources.** A model never writes structure. *Why:* a model given the ontology still produced triples that break it, and asking a model to reason in place of a reasoner "is Dangerous" (Going Meta, "Ontologies, LLMs, Property Graphs - Do we really have a Jaguar Problem?", 9 December 2025, `session41` PDF pages 5 and 11); "an LLM never touches it" (Going Meta, "Unwrapping OKF", 4 August 2026, `session49/okf-neo4j.pdf` page 13), both at https://github.com/jbarrasa/goingmeta.
22. **Let a model write text (a draft definition, a description) only from sources you supply, citing them; re-check each claim against its source with a script before the text enters, then send it through the human gate (`quality.md`).** *Why:* "A constrained LLM endpoint may write only from supplied source_refs; the worker re-checks every claim … and drops anything ungrounded" (William Lyon, Going Meta, "Actionable Knowledge For Agents With Context Graphs", 7 July 2026, `session48` PDF page 54).

## Review

23. **Run the `way-of-working` review loop** (`references/before-push.md` and `references/changing.md`): an independent review of committed work by a different model before each push, then a PR verdict from another tool, so the merged commit's two reviews come from different tools. At most two full independent rounds per pull request; after that, a quick check of each later fix commit only. Never merge past a HOLD or a failed check. The project's `AGENTS.md` names the tools. *Why:* one tool reviewing twice repeats its own blind spots, and a third round on the same kind of finding means the design needs changing, not another patch (`way-of-working`, `references/before-push.md`, "Re-review after fixing").
24. **Have the reviewer block on these ontology judgements,** kept in the project's review-standards file: a quote matches the saved words and claims no more; a figure outside CI traces to the shared tool over the population the sentence claims (rows, not mentions); a hierarchy claim (parent, ancestor, sibling) matches `skos:broader` in the built taxonomy; a check of decided values tests the decision (`shacl.md`, rule 10); approved text moves word for word; the method stays company-neutral (rule 8); held rows reach the source author only through the backlog (`promotion.md`). *Why:* each caught a real defect in practice that the checks passed.

## Releases

25. **Release approval, semantic versioning, candidates, the cut and the tag live in `release.md`** ("Who approves" and rules 14 to 17). Use `templates/release-checklist.md` before each release.

## Privacy and publication

26. **Name the owner by role ("the ontology owner") in every tracked file, and make the check script fail when a tracked file or path contains the owner's personal name or account name.** Build the names from fragments inside the check, so it does not match itself. *Why:* as practised, a name in approvals and creator fields made a governed release read as one person's approval; the owner asked for role wording and a guard.
27. **Keep customer inputs (files, images, transcripts) out of the repository.** Store them outside it and refer to them neutrally. *Why:* a committed file stays in git history after deletion, and removing it needs a history rewrite.
28. **Publish no proprietary content in a public artifact.** Before a repository or package becomes public, list what relies on it being private (internal system names; material in `foundations.md`, source policies) and put the visibility change to the owner. Re-read the visibility after the answer (`way-of-working`, `references/deciding.md`, "When an option depends on external state"). Licence: `foundations.md`, policy 7; rights statement: `release.md`, rule 22. *Why:* as practised, internal names were allowed because a repository was private, and making it public needed the owner's separate decision to accept that exposure.

## Sources, claims and scope

29. **Rank sources by the evidence order (`foundations.md`, policy 3) and give each cited source a tier (`integration.md`, rule 26).** A delegated decision rests on that order, and uses an external search only to settle an ambiguity the evidence leaves open, citing what it finds. *Why:* a decision the owner did not make must still show which evidence won.
30. **Claim only what has landed** (`way-of-working`, rule 5): a record calls a module released only once its package has merged and passes `--verify`, and says a tag comes at merge (`release.md`, rule 16). *Why:* a pending pull request can still change or close.
31. **State what each skill, tool or validator the build ships does not do, and name what does.** *Why:* an agent otherwise stretches a tool past its scope. Source: `neo4j-ontology-skill` 1.0.1, `SKILL.md` lines 3 to 9 and 20 to 23 (no Cypher, no loading, no general modelling advice, each routed to a named skill).
