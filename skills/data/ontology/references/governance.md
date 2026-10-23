# Governance: intake, decisions, delegation, checks, review and publication

Read it before you start a new ontology, record a decision, work under a delegation, set up checks, review a change, release or publish.

This file holds what an ontology build adds to general engineering practice. Where the `way-of-working` skill is installed, it is the home for decision records, the pull-request loop, the check script's design and the shared figures tool: follow it, and use this file for the additions. Where it is not installed, each section below says what to do instead, and the templates carry the rules you need.

## Before modelling

1. **Sort the inputs into six kinds before any modelling: purpose (users, use cases, scope), competency questions, representative data, reusable vocabularies, semantic evidence (glossaries, policies, filings, definitions) and constraints.** Record each in the `inputs` section of `templates/requirements.yaml`, name each one that is missing or thin, say how the gap limits the design, and stop for the owner's answer. Invent no requirement to fill a gap. *Why:* a model built over a silent gap encodes the builder's guess as the business's requirement. Adapted from the input buckets of the ontology-builder skill shown in Going Meta S03E07 (7 April 2026; `SOURCES.md`).
2. **Keep the requirements in that one machine-readable file, and run `scripts/check_requirements.py` on it in the check script.** It enforces the schema written at the top of the template and fails on a conflict: a competency question that needs, or whose rationale names, an area listed out of scope. *Why:* the example requirements file in the same session puts provenance out of scope while its first question's rationale requires it, and nothing in that skill catches it.
3. **When the owner says "not yet", or cannot answer, mark the gap and keep going only where it is cheap to undo.** Save their words verbatim in the answers file. Mark the item "ASSUMED, not yet answered" with the question's ID in `requirements.yaml` (`assumptions`), in the decision record (Status `Proposed`), and in each template row it touches. Continue only with work a later answer can reverse without remodelling, and leave open every gate that depends on the answer. List it as an open item that waits on the owner (rule 14). *Why:* a visible assumption can be found and reversed; a silent one becomes the business's requirement.

## Decisions

Record rules (one record per decision; status Proposed, Decided or Superseded; quote the question in full with its recommendation; amend, never rewrite) live in `way-of-working`, `references/deciding.md`. Without that skill, `templates/decision-record.md` carries them. Copy the template either way.

4. **Number every record and give each decision its own.** *Why:* a later record, a test or a release manifest can then cite exactly one decision, and an amendment names the record it changes.
5. **Save the owner's words verbatim in an answers file before you quote them** (`templates/answers-file.md`). The file holds only the owner's words; your questions and options sit inside an HTML comment. Nobody edits it after saving. *Why:* a quote taken from chat or memory cannot be checked, and an edited answers file proves nothing.
6. **Call a decision Decided only with the owner's recorded words, or under a recorded delegation that covers it, and make the Status say which:** `Proposed`, `Decided (the owner, <date>)`, `Decided (delegated under <record>)` or `Superseded by <record>`. A statement only the owner can make (who consumes the ontology, policy 9) and the approvals in `release.md`, "Who approves", stay with the owner even under a delegation. A merge decides nothing. *Why:* a reviewer's merge checks the change, not the owner's intent, and a reviewer reads the owner's part of a record line by line against the saved words.
7. **Check quotes mechanically.** The check script compares every quoted span in a record's recorded-words section with the answers file it cites, and fails on a mismatch; without a shared tool, a short committed script does it. Check by hand the rest: paraphrases, pull-request text, and that the text claims no more than the words say. *Why:* a reason that states more than the answer, or a quote taken from a chat session, otherwise reaches review unnoticed.
8. **When a decision also improves the method, change the method (this skill, or the project's playbook) in the same pull request.** Keep project rulings in records, never in the method (`way-of-working`, `references/documents.md`). *Why:* a method full of project rulings cannot be reused, and a fix left only in a record is lost to the next build.
9. **When a gate read literally blocks far more than the plan intended, put the scope to the owner with computed figures and options; never narrow it yourself.** *Why:* a literal reading and the planned reading can differ by hundreds of rows, and choosing between them changes what ships.

## Delegation

10. **Record a delegation as its own decision record, with the owner's words, its scope (which questions or steps), the evidence order each decision must rest on, and how each decision is recorded.** *Why:* the record is the owner's decision to delegate, so it is what makes each delegated decision count as Decided.
11. **Mark every delegated decision "delegated under <record>", with its evidence, and keep it reversible:** the owner can reverse any one, and the reversal is recorded the same way. *Why:* the owner can then audit each decision and find what to undo.
12. **Keep with the owner what rule 6 reserves, plus any change to the delegation itself and any question outside its named scope.** Ask to extend the scope; do not stretch it. *Why:* a delegation covers what its words cover, and extending it to later steps is a new question with its own answer.
13. **Amend a delegation in the same record, as a dated amendment with the owner's words, and add a dated note to each sentence it replaces.** *Why:* a reader of an old sentence then finds what replaced it.
14. **Attribute every open item to whoever its record names: the owner, a named process owner, the business, a later release, "no confirmer named", or "unresolved by decision".** Never list them all as the owner's. *Why:* a list headed "waits on the owner" that holds a process owner's confirmation asks the owner for something they cannot give, and hides whom to ask.

## Checks

The check script's design (one script that CI and the pre-push hook both run; the no-writes guard's four snapshots; wiring the hook) lives in `way-of-working`, `references/guardrails.md`. Without that skill, `templates/check.sh` carries the guard. Copy the template either way and fill every TODO; until you do, it fails.

15. **Make the check script run every check the build has:** `scripts/check_requirements.py` and `scripts/check_taxonomy.py` from Step 1 and Step 3; each package builder's and the catalog's `--verify` (`release.md`, rules 9 and 19); every module's shapes and the whole-graph gate (`shacl.md`); the competency-question regression (`regression.md`, rule 13); every test file; and the quote and name checks (rules 7 and 23). Compute every figure a document states with committed code: the shared tool where `way-of-working` provides one, otherwise a script in the repository, never memory or a one-off command. *Why:* a generated file or figure that no check recomputes can drift from its sources without a failure.
16. **Keep every check blocking: the work is not done while the check script exits non-zero.** *Why:* an advisory failure is read as a pass. Source: `neo4j-ontology-skill` 1.0.1 (`SOURCES.md`): "never present an ontology as done with a non-zero exit".
17. **Pin the schema or shape version each validator checks against, and fail when that exact version cannot be loaded.** Never fall back to a moving "current" or a branch head. *Why:* the same skill's validator falls back to a moving alias and then a branch head when the named version cannot be fetched, and reports it only on standard error, so a pass may be against a schema the document never named.

## Generated content

18. **Generate structure (triples, shapes, packages, projections) with deterministic code from the sources.** A model never writes structure. *Why:* a model given the ontology in its prompt still produced triples that break it, and asking a model to reason in place of a reasoner "is Dangerous" (Going Meta, 9 December 2025; `SOURCES.md`).
19. **Let a model write text (a draft definition, a description) only from sources you supply, citing them; re-check each claim against its source with a script before the text enters, then send it through the human gate (`quality.md`).** *Why:* the same series shows a constrained model that "may write only from supplied source_refs", with a worker that re-checks every claim and drops anything ungrounded (Going Meta, 7 July 2026; `SOURCES.md`).

## Review

20. **Have a reviewer other than the author read every change before it merges, and merge nothing past an unresolved finding or a failed check.** Where `way-of-working` is installed, its review loop is the rule: who reviews and the round limits are in its `references/before-push.md` ("Re-review after fixing") and `references/changing.md` ("Who reviews"); the project's `AGENTS.md` names the tools. Without it, the reviewer is a person or a different model from the author. *Why:* an author reviewing their own work repeats their own blind spots.
21. **Have the reviewer block on these ontology judgements,** kept in the project's review-standards file: a quote matches the saved words and claims no more; a figure traces to committed code over the population the sentence claims (rows, not mentions); a hierarchy claim (parent, ancestor, sibling) matches `skos:broader` in the built taxonomy; a check of decided values tests the decision (`shacl.md`, rule 10); approved text moves word for word; the method stays organization-neutral (rule 8); held rows reach the source author only through the backlog (`promotion.md`). *Why:* each is a defect the mechanical checks pass.

## Releases

22. **Release approval, semantic versioning, candidates, the cut and the tag live in `release.md`** ("Who approves" and rules 14 to 17). Use `templates/release-checklist.md` before each release. A record calls a module released only once its package has merged and passes `--verify`.

## Privacy and publication

23. **Name the owner by role ("the ontology owner") in every tracked file, and make the check script fail when a tracked file or path contains the owner's personal name or account name.** Build the names from fragments inside the check, so it does not match itself. *Why:* a personal name in approval and creator fields makes a governed release read as one person's opinion, and it is personal data in every copy.
24. **Keep customer inputs (files, images, transcripts) out of the repository.** Store them outside it and refer to them neutrally. *Why:* a committed file stays in git history after deletion, and removing it needs a history rewrite.
25. **Publish no proprietary content in a public artifact.** Before a repository or package becomes public, list what relies on it being private (internal system names; material derived under `foundations.md`, source policies) and put the visibility change to the owner. Read the visibility again after the answer. Licence: `foundations.md`, policy 7; rights statement: `release.md`, rule 22. *Why:* content allowed because a repository was private becomes public the moment it is, and accepting that exposure is the owner's decision.

## Sources, claims and scope

26. **Rank sources by the evidence order and give each cited source its tier** (`foundations.md`, policy 3). A delegated decision rests on that order, and uses an external search only to settle an ambiguity the evidence leaves open, citing what it finds. *Why:* a decision the owner did not make must still show which evidence won.
27. **State what each skill, tool or validator the build ships does not do, and name what does.** *Why:* an agent otherwise stretches a tool past its scope. Source: `neo4j-ontology-skill` 1.0.1 (`SOURCES.md`), which routes Cypher, loading and general modelling advice to named sibling skills.
