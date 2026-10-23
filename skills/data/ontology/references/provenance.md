# Definitions, plans and runs

Serves Step 6. Read it before you model planned inputs and outputs, link a run of a process to its definition, or record who asserted a mapping.

The rule behind this step: the ontology holds definitions; consuming systems hold what happened. The recipe is not the meal.

Standards: PROV-O (W3C Recommendation, 30 April 2013, https://www.w3.org/TR/prov-o/); P-Plan, the ontology at http://purl.org/net/p-plan# (`owl:versionInfo` "1.2", `dcterms:modified` 2013-05-17; its documentation at https://www.opmw.org/model/p-plan/ is "Release 17 September 2013", revision 1.1). The documentation says the relation of a plan with agents and activities is not specified in P-Plan, "since it can be modeled with PROV (with the prov:hadPlan property)".

## Rules

1. **Never type a process definition as `prov:Activity`.** Reserve `prov:Activity` for runs, and ship a shape that fails any definition typed as one. *Why:* a definition typed as an occurrence makes every count of "what happened" include the catalogue.
2. **Let the consuming systems hold the runs.** The ontology defines the pattern and publishes the shapes; it stores no run (`foundations.md`, policy 2). *Why:* runs are event records that change daily in the systems that produce them.
3. **Link a run to its definition with PROV-O as published:** the run is a `prov:Activity` with exactly one `prov:qualifiedAssociation`, whose `prov:hadPlan` names exactly one process definition and whose `prov:agent` names the actor, where one is recorded (PROV-O, W3C Recommendation 30 April 2013: `prov:agent` has domain `prov:AgentInfluence`, and the Association example carries both). The run itself states `prov:startedAtTime` and may state `prov:endedAtTime`; a direct link from the run to its actor, if wanted too, is `prov:wasAssociatedWith`. Mint no `runOf` property of your own. *Why:* consumers that speak PROV-O read the link with no mapping.
4. **Require the plan to be live work:** in the scheme, not retired, not a structural anchor, and not a capability (an ability realized by processes). *Why:* a run follows one of the processes that realize a capability, never the capability or a grouping node.
5. **Leave P-Plan's steps and variables unused while the taxonomy is a naming hierarchy.** *Why:* typing each concept as a plan and its children as steps reads a naming hierarchy as an execution structure, and changes released definitions.
6. **Ship the pattern as shapes plus one example run that passes**, marked as an illustration and never loaded as data. *Why:* a consumer can then validate its own records against the shapes together with the released definitions.
7. **Take planned inputs and outputs only from a source field whose meaning the owner has confirmed.** A field with an unclear name gets a question to the owner before any term is named after it (`foundations.md`, source policies). *Why:* a guessed field meaning becomes a wrong property on every process.
8. **Carry each planned input and output as a governed literal, one value per item** (`plannedInput`, `plannedOutput`), until a use case needs to trace one flow as a node of its own. *Why:* flow nodes multiply identity questions that no competency question asks yet.
9. **Draft no inputs or outputs for processes the source leaves empty.** List them with a query as the source author's backlog. *Why:* a drafted flow is a fact with no source.
10. **Use PROV-O's second job, trust, for assertions about the ontology itself:** which source asserted a mapping, when, and under what authority. *Why:* a reviewer can then audit a mapping without reading the build history.

Step 9 tests these shapes like any other (`shacl.md`); they check a consumer's data, so the release-package test (`shacl.md`, rule 9) does not run them over the ontology's own packages.
