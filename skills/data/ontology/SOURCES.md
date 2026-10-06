# Sources

What the ontology skill was built from. Agents do not read this file. All text in the skill is our own wording.

Last full review: 2026-10-05. Suggested cadence: when either source below changes, and every three months for the W3C and tool status in `references/lpg-projection.md`.

## 1. The EPM ontology playbook

- **Link:** `business_architecture/ontology/ontology-playbook.md` in https://github.com/aadehamid/enterprise-performance-model
- **Version used:** the company-neutral rewrite in PR #199 (2026-10-05).
- **What we took:** the step sequence and gates, the policies, the eleven promotion rules, the predicate review method, the quality bar, the soundness checks and the versioning rules. Shortened for an agent.
- **What we left out:** the worked example and every project-specific decision (EPM IRIs, MPC choices, counts).
- **License:** Hamid's own work.
- **How to check for updates:** `gh api "repos/aadehamid/enterprise-performance-model/commits?path=business_architecture/ontology/ontology-playbook.md&since=2026-10-05T00:00:00Z" --jq '.[] | "\(.sha[0:12]) \(.commit.message|split("\n")[0])"'`

## 2. Ontology_to_LPG_Conversion_Playbook v2.1

- **Link:** https://github.com/aadehamid/enterprise-people-graph/tree/main/guideline_to_map_ontology_to_LPG
- **Version used:** commit `e7b09e8` (v2.1, October 2026; first used at `cd63e12`, v2).
- **What we took:** the mental model, design Rules 1, 2, 3, 4 and 5 with Rule 4 set to option 4a (qualified-relation nodes, the v2.1 default) rather than 4b (RDF 1.2 reifiers), the pipeline (without the 4b flatten queries) and the anti-patterns. The reasons for 4a are in `references/lpg-projection.md`.
- **License:** Hamid's own work.
- **How to check for updates:** `gh api "repos/aadehamid/enterprise-people-graph/commits?path=guideline_to_map_ontology_to_LPG" --jq '.[] | "\(.sha[0:12]) \(.commit.message|split("\n")[0])"'`

## 3. Juha Korpela, "Building Semantics with Conceptual Models" (Common Sense Data, 2026)

- **What we took:** the foundations behind the playbook: model the business, not the storage; entities as singular nouns; relationships as verbs; a definition for every entity. The skill relies on them through the playbook and does not restate them.
- **License:** a published book. Nothing is quoted.

## 4. External status checks (2026-10-05)

These facts in `references/lpg-projection.md` change over time:

- RDF 1.2 Concepts is a W3C Candidate Recommendation Snapshot, 7 April 2026: https://www.w3.org/TR/rdf12-concepts/
- rdflib RDF 1.2 support: https://github.com/RDFLib/rdflib/issues/3524 (all stages open)
- Jena RDF 1.2 support: full syntax input and output and SPARQL 1.2 from 6.1.0 (5.4.0 to 6.0.x was an experimental preview), per https://github.com/apache/jena/blob/main/CHANGES.txt. The tracking issue #2805 is still open, which is not the status. Corrected 2026-10-06.
- RDF4J RDF 1.2 support: from 6.0.0, https://rdf4j.org/release-notes/6.0.0/
- n10s: https://github.com/neo4j-labs/neosemantics (last commit 29 May 2026, Neo4j 2025.06.2, no RDF 1.2)
