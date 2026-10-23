# Versions of the method

Read it when a project pins an earlier version of the guideline, or asks what changed. Each version keeps the earlier rules unless a line below says otherwise.

| Version | Where | What it changed |
|---|---|---|
| 2 (October 2026) | the guideline folder in the enterprise-people-graph repository, commit `cd63e12` | Five design rules and a five-step core path, with optional add-ons; RDF 1.2 reifiers for link properties. |
| 2.1 (October 2026) | same folder, commit `e7b09e8` | Rule 4 got two options: 4a, qualified-relation nodes, the default, and 4b, RDF 1.2 reifiers. The flatten step became 4b only. RDF 1.2 status corrected to Candidate Recommendation. |
| 2.2 (October 2026) | same folder, commit `8ce9ada` | From the first full run: SHORTEN instead of MAP; the full shapes before the load and a subset in the graph; `inferred.nt` without the reasoner's declarations; the round trip compares values, not spellings; CI checks a committed report; plugin jars pinned by checksum. |
| 2.3 (this skill, 23 October 2026) | `ontology-to-lpg` | See below. |

## What 2.3 adds over 2.2

From the projection of a multi-module enterprise ontology, every released package at once, in October 2026:

1. **The guideline becomes this skill.** Repositories that kept a copy of 2.2 point here instead. The examples move to the library domain.
2. **Inputs are released packages** (`inputs.md`, rules 1 and 2): each at its newest version, pinned by hand and checked against the release folder, each with its own shapes, plus the whole-graph shapes.
3. **The rules cover every namespace you own**, each with a fixed prefix, and the standard namespaces are registered too (`inputs.md`, rules 3 and 4).
4. **Release exceptions are a mechanism, not a checklist line** (`inputs.md`, rules 5 and 6): keyed by the checker's exact message, each with its fix, failing on a stale entry. `scripts/check_projection_rules.py` implements it.
5. **Rule 4a counts an inverse link as an end** and requires exactly one such link per node (`design-rules.md`, rule 4). Every qualified-relation class is registered with its ends.
6. **`sh:pattern` and literal `sh:in` lists leave the graph**, found by testing n10s 2025.06.1 against the source (`pipeline.md`, rule 13); `sh:in` lists of IRIs stay. Each constraint kind is tested in the engine with a pass and a fail case (rule 14). `scripts/in_graph_shapes.py` generates the subset.
7. **Rule 1 and Rule 2 say how annotation properties and lists are stated:** an annotation property needs a kind and a cardinality but no range; an optional list says `sh:minCount 0`.
8. **Rule 3 says why prefixes matter in SHORTEN mode:** n10s names a term by its namespace's prefix and invents a numbered prefix for an unknown namespace.
9. **Running the projection** (`running.md`): CI runs check and serialise only; the report's fingerprints cover every shape file; `inferred.nt`, the manifest and the report are committed together; the container and its password are removed after each run.
