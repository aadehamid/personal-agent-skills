# Adding a module to an existing ontology

Serves any new module added after an ontology's first release. Read it before you start the module, then follow `SKILL.md`'s steps as this file narrows them.

The steps stay the same and their gates still apply. What changes is their scope: the ontology's policies, namespace and earlier modules already exist, so most steps cover only the new module's domain.

## Decide whether it is a new module

1. **Name the competency question the existing modules cannot answer.** With no such question, do not add the module. *Why:* a module with no question to answer adds terms nobody asked for, and the regression cannot test it.
2. **Check that no module already owns the domain (`foundations.md`, policy 8).** If one does, extend that module in its next release. *Why:* two owners give two definitions.
3. **Record the decision, and name the module's owner.** Until the ontology owner names one, they own it (`release.md`, rule 6). *Why:* every later approval needs a named approver.

## What each step covers

| Step | For a new module | Skip when |
|---|---|---|
| Intake | Add the module's purpose, questions, inputs and scope to the requirements file, and sort its inputs into the six kinds (`governance.md`, rule 1) | Never |
| 0, reference framework | Survey the module's domain only: frameworks, public ontologies and code lists | Never |
| 8, scope review | Review the candidate areas of this domain, with a boundary note on each out call | Never |
| 1, foundations | The ten policies already hold, so do not decide them again. Lock the new competency questions with the owner | A change to a policy is its own decision, and it applies to every module |
| 2, identity | IRIs under the module's namespace, in the URI policy's form. Point to another module's terms by IRI; never redefine them | Never |
| 3, terms | Classes, properties, concepts and definitions, each with its kind, to the quality bar | Never |
| 4, relationships | Promote provisional data through the evidence gate | The module promotes no provisional data |
| 5, organizations | RACI and role links, using the existing role register | The module has no roles |
| 6, plans and runs | The definition-to-run pattern | The module has no processes or runs |
| 7, integration | Link it to the other modules by IRI, in one direction, with no cycle. Record each gap as linked or parked | The module stands alone |
| 9, SHACL | The module's own shapes and negative tests, then the whole-graph gate over every module | Never |
| 10, release | The first release, then the combined catalog (below) | Never |
| 11, regression | The new questions, plus the full suite (`regression.md`, rule 13) | Never |
| 12, projection | Meet `ontology-to-lpg`'s design rules from Step 2 on, add the module to the projection's inputs, and rerun it | The ontology is not projected |

## Releasing it beside the others

4. **Treat the first release as a major, and get the owner's approval (`release.md`, rule 6).** Build it as a candidate until then. *Why:* a first release is the promise every consumer will rely on.
5. **Pin the versions the module requires, and leave every released package as it is (`release.md`, rule 10).** A module that should link back to the new one does so in its own next release. *Why:* a released package never changes, and a change to one module must not force a release of the others.
6. **Find every place the project lists its modules, and add the new one.** Search for an existing module's name across the build, check, projection and regression scripts and the documents. Common places are the release builder, the check script, the projection's inputs and prefixes, the store configuration, the regression's data files and any stated count of modules. *Why:* a list that misses the new module often fails silently: its checks do not run, or the projection leaves it out.
7. **Run the whole check suite, not only the module's tests (`regression.md`, rule 14).** Earlier questions must keep their status. *Why:* a new module can break a query or a shape elsewhere.
8. **Reload the stores, and prove nothing was lost, after the release (`ontology-to-lpg`, `references/multi-store.md`).** *Why:* a store that holds the old release set answers without the new module, and nothing in the answer shows it.

Done when the module's question passes on its released package, its entries exist everywhere the project lists modules, the whole-graph gate and the full regression pass, and the catalog lists the release.
