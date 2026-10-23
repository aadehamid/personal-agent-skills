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
10. **Scripts for the check, reason and serialise steps** (load and verify followed in item 15): `validate_data.py` (pySHACL and the refusals) and `build.py` (the reasoner's merged input, the N-Triples files, the inferred filter, the generated load script, the manifest and the report check), with the jar checksums and a `docker run` line bound to localhost.
11. **Exact definitions where 2.2 left room:** the byte sort order and the input fingerprint (`pipeline.md`, rule 5); the decimal and language-tag refusals (rule 3); which predicates load as arrays (rule 10); which file `onto.import` reads and what success is for the shapes import (rule 11); the export query and the schema rows it must leave out (rule 16); emptying the database between loads on Community edition (rule 17).
12. **Fixes found by running 2.3 end to end:** ROBOT needs `--include-indirect true` to infer anything an individual's direct type does not already say (rule 4); array sorting is restricted to `:Resource` nodes, because sorting n10s's own configuration nodes corrupts them (rule 10); the export returns a tagged literal's text with `literalLang` set (rule 16).
13. **The in-graph subset follows the n10s source:** it also drops `sh:datatype` values n10s throws on, `sh:and`, `sh:or`, `sh:xone` and a literal `sh:hasValue`, and keeps a property shape a targeted shape still uses (rule 13). Rule 14 gives a fail case for each constraint kind left in the graph.
14. **The checker is stricter:** a datatype range must be a row of the XSD to Cypher table; a cardinality counts only on an applied shape; every namespace a class uses needs a prefix; each qualified-relation end needs an exact shape; release exceptions waive only Rule 1, 2 and 5 gaps; the Rule 4 option and its reason are read from the configuration.
15. **A load-and-verify script, `load_verify.py`** (later also generating `sh:closed`, `sh:disjoint` and inverse `sh:maxCount` cases, and listing any kind left without one), from two more test runs (one on the library example, one on a private multi-module ontology): it loads with status checks, compares the shapes import with `listShapes()`, runs one generated fail case per constraint kind in a rolled-back transaction, commits and restores the mutant, diffs the export with schema rows left out, and compares two hashed loads, with the hash fully specified.
16. **A round-trip fix:** n10s exports a tagged string that holds a newline as `xsd:string` `"text@en"` with no `literalLang`; the diff now splits the tag with a DOTALL pattern (`pipeline.md`, rule 16).
17. **Rule 2 counts every target kind SHACL applies**, and shapes reached through `sh:node`, `sh:and`, `sh:or` and `sh:xone`; it checks only the properties the data uses. Release-exception keys may use full IRIs.
18. **The in-graph subset keeps only the SHACL terms n10s reads,** so `sh:lessThan`, `sh:lessThanOrEquals`, `sh:equals` and the like are dropped, as are IRI-named SHACL-SPARQL nodes and deactivated shapes.
19. **Running details:** the plugins mount must be writable and open to the container's user (the image writes `apoc.jar` into it); the image is pinned by digest; the start wait fails on an exited container or an error; the manifest records paths relative to its own folder.

## Where 2.3 differs from the method as practised

- **Annotation properties need no range here.** The build behind 2.3 required a single range for every owned predicate, annotation properties included; this skill follows the `ontology` skill, where an annotation property takes neither a domain nor a range.
- **Rule 2 checks only properties the data uses.** The build did the same; the first draft of 2.3 also checked declared but unused ones.

20. **From review round 2:** `sh:node` on an applied node shape and n10s's `sh:targetQuery` stay in the in-graph subset; an `owl:Class` shape without `sh:targetClass` leaves it; dropping an `sh:or`, `sh:and` or `sh:xone` list keeps a property shape another shape still uses; every script stops under Rule 4b; predicates inside property paths and superproperties need a prefix; a pin must be `X.Y.Z`; `check-report` needs a complete manual case and a mutant object; `docker rm -f -v` removes the run's volumes.

## Migrating a project from 2.2

Expect the checker to report two things a 2.2 project did not see:

- **A missing `xsd:` prefix.** Rule 3 now counts datatype ranges, so the namespace of every `rdfs:range` datatype needs a prefix in the configuration.
- **A stale release exception on an annotation property.** 2.2 builds required a range on annotation properties too; 2.3 does not, so an exception listed for an annotation property with no range no longer occurs and fails as stale. Remove it.
