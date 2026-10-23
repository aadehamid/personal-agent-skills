<!-- Copy at Step 1 to record the ten policies. Rules: references/foundations.md, "Step 1". One row per policy: the choice, its reason, and the record that decided it. A choice the owner has not answered is "ASSUMED, not yet answered" with the question's ID; Step 1 closes only when no row says ASSUMED. Delete every comment. -->

# Policies

Recorded <YYYY-MM-DD>. Requirements file: `<path to requirements.yaml>`.

| # | Policy | Choice | Reason | Decided by |
|---|---|---|---|---|
| 1 | Competency questions | Locked list in `<path>` | The acceptance test (Step 11). | <record, e.g. LIB-0001> |
| 2 | Data scope | Concepts, definitions, relationships and reference facts only; no event records or observed values | Records change daily in the lending system. | <record> |
| 3 | Evidence order | 1. the library's own policies and system configuration; 2. peer libraries' published policies; 3. library standards bodies; 4. generic vocabularies | The closest source knows the business best. | <record> |
| 4 | URI policy | Base `<https://id.example.org/library/>`; local IDs as `skos:notation` | A rename changes one redirect. | <record, or "ASSUMED, not yet answered (Q3)"> |
| 5 | Language | Primary `en`; every language-text literal tagged | Tagged and untagged literals are different RDF terms. | <record> |
| 6 | Version | Semantic versioning per module and release; deprecate, never delete | Consumers pin versions. | <record> |
| 7 | Licence | <closed / open, naming the licence> | <why, e.g. "a public body publishes openly"> | <record> |
| 8 | Modules | <module list and their one-way dependencies> | A cycle blocks releasing a module alone. | <record> |
| 9 | Consumers | <the owner's statement: who consumes, whether any is active> | Release rules depend on it; only the owner can state it. | <record> |
| 10 | Target formats | <RDF only / RDF plus a property-graph projection; if projected, the Rule 4 option: 4a qualified-relation nodes or 4b RDF 1.2 reifiers> | Projection rules adopted late force a remodel; <why this Rule 4 option, for example: the validator is pySHACL, which does not read RDF 1.2>. | <record> |
