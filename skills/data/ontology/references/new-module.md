# Adding a module to an existing ontology

Serves any new module added after an ontology's first release. Read it before you start the module, then follow `SKILL.md`'s steps as this file narrows them.

For a logical data model exported from a modelling tool, read `logical-model.md` too.

The steps stay the same and their gates still apply. What changes is their scope: the ontology's policies, namespace and earlier modules already exist, so most steps cover only the new module's domain.

## Decide whether it is a new module

1. **Name the competency question the existing modules cannot answer.** With no such question, do not add the module. *Why:* a module with no question to answer adds terms nobody asked for, and the regression cannot test it.
2. **Check that no module already owns the domain (`foundations.md`, policy 8).** If one does, extend that module in its next release. *Why:* two owners give two definitions.
3. **Record the decision, and name the module's owner.** Until the ontology owner names one, they own it (`release.md`, rule 6). *Why:* every later approval needs a named approver.

## What each step covers

| Step | For a new module |
|---|---|
| Intake | Add the module's purpose, questions, inputs and scope to the requirements file, and sort its inputs into the six kinds (`governance.md`, rule 1) |
| 0, reference framework | Survey the module's domain only: frameworks, public ontologies and code lists |
| 8, scope review | Review the candidate areas of this domain, with a boundary note on each out call |
| 1, foundations | The ten policies already hold, so do not decide them again; a change to one is its own decision and applies to every module. Lock the new competency questions with the owner. If policy 10 says the ontology will be projected, or this module is why projection starts, record that and the Rule 4 option, and read `ontology-to-lpg`'s design rules |
| 2, identity | IRIs under the module's namespace, in the URI policy's form. Point to another module's terms by IRI; never redefine them |
| 3, terms | Classes, properties, concepts and definitions, each with its kind, to the quality bar |
| 4, relationships | Promote provisional data through the evidence gate |
| 5, organizations | RACI, the role register, party roles and reference instances |
| 6, plans and runs | The definition-to-run pattern. A module that defines the terms of records kept outside the ontology, such as a technical graph of what was built, ships an example graph of such records as test data (rule 9) |
| 7, integration | Link it to the other modules by IRI, in one direction, with no cycle. Record each gap as linked or parked |
| 9, SHACL | The module's own shapes and negative tests. Add the module to the project's lists first (rule 6), then run the whole-graph gate with its data and shapes included |
| 10, release | The first release, then the combined catalog (below) |
| 11, regression | The new questions, plus the full suite (`regression.md`, rule 13) |
| 12, projection | Design rules are already met from Step 1. Add the module to the projection's inputs, and rerun it |

This table says what each step covers, and `SKILL.md` holds its gate. A step can have little to do for a module, but no required step is skipped, and Step 12 applies when policy 10 says the ontology will be projected: meet each gate as `SKILL.md` and the reference it names state it, and record why a step holds little.

## Releasing it beside the others

4. **Release the module at `1.0.0`, with the ontology owner's approval, not only the module owner's (`release.md`, rule 6).** Build it as a candidate until then. Adding a module is a minor change to the release as a whole (`release.md`, rule 3). *Why:* a first release is the promise every consumer will rely on, and it adds to the whole without breaking it.
5. **Pin the versions the module requires with `dcterms:requires` and a manifest entry, importing no module (`release.md`, rule 11), and leave every released package as it is (`release.md`, rule 10).** A module that should link back to the new one does so in its own next release. *Why:* a released package never changes, and a change to one module must not force a release of the others.
6. **Find every place the project lists its modules, and add the new one, before you run Step 9's gate.** Search for an existing module's name across the build, check, projection and regression scripts and the documents. Common places are the release builder, the check script, the projection's inputs and prefixes, the store configuration, the regression's data files and any stated count of modules. *Why:* a list that misses the new module often fails silently: the gate passes without its data, its checks do not run, or the projection leaves it out.
7. **Run the whole check suite, not only the module's tests (`regression.md`, rule 14).** An earlier question that now fails is a regression or a recorded, deliberate change (`regression.md`, rule 13); one may move from waiting to answerable. *Why:* a new module can break a query or a shape elsewhere.
8. **If the release lives in several stores, reload them and prove nothing was lost (`ontology-to-lpg`, `references/multi-store.md`).** *Why:* a store that holds the old release set answers without the new module, and nothing in the answer shows it.
9. **When the module's questions are asked of records the ontology must not hold, test them on the package plus a conforming example graph.** A vocabulary for records kept elsewhere (a technical graph, a run log, a register of what was built) cannot answer its questions alone, and its records stay out of the ontology ("define, don't record"). Ship a small example graph beside the module as test data, never in the package: built from real records where they exist, regenerated by a script with a check that fails when it is stale, and conforming to the module's shapes with the releases it links to loaded. The regression runs the questions on the package plus the example; write the queries so they run unchanged on the live records. The example is an illustration in the sense of `provenance.md`, rule 6: it never joins a package or a store. Policy 1's exception for such questions is in `foundations.md`. Give each shape a negative test on the example. *Why:* without records the questions return nothing, so the regression proves nothing; records inside the package would make the ontology a store of operational data.

Done when the module's question passes on its released package (or, under rule 9, on the package plus its conforming example graph), its entries exist everywhere the project lists modules, each step's gate in `SKILL.md` is met, the whole-graph gate and the full regression pass with the module included, the catalog lists the release, Step 12's gates are met if the ontology will be projected, and every store in a multi-store plan holds the new release with nothing lost.
