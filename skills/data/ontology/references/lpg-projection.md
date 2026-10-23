# Projecting an ontology into a labelled property graph

Serves Step 12, and Step 1's target-format policy. The method lives in the `ontology-to-lpg` skill; load it whenever the ontology will be loaded into Neo4j or another labelled property graph (LPG). The Turtle release stays the master copy.

1. **Decide at Step 1 whether the ontology will be projected, and record it in policy 10** (`foundations.md`). If it will, adopt `ontology-to-lpg`'s design rules (its `references/design-rules.md`) before the first release, and record the Rule 4 choice: qualified-relation nodes (4a, the default) or RDF 1.2 reifiers (4b). *Why:* a rule adopted after a release forces a new release of every module that breaks it.
2. **Run the projection at Step 12, over the released packages, once Steps 9 to 11 pass.** Follow `ontology-to-lpg` from its inputs step. *Why:* the projection tests what consumers receive, so it reads releases, not the working files.
3. **When a release closes a gap the projection lists, move the projection's pin and remove the exception in the same change** (`ontology-to-lpg`, `references/inputs.md`, rules 5 and 6). *Why:* the projection fails until both are done.
