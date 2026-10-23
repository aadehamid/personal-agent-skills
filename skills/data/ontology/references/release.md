# Versioning, release packages and publication

Serves Step 10, and every module release from Step 4 on. Read it before you classify a change, build or approve a release, deprecate a term, or publish a catalog.

## The rule

1. **Put versions on each module's `owl:Ontology` header (`owl:versionInfo`, `owl:versionIRI`) and on versioned distributions (`.../releases/1.2.0/core.ttl`).** Term IRIs: `identity-taxonomy.md`, Step 2, rule 3. *Why:* the header and the distribution are what a consumer pins.
2. **Version each module, and each release as a whole, with `MAJOR.MINOR.PATCH`.** A release records exactly which module versions it bundles. *Why:* a consumer pins what it tested against.

## Classify every change

3. **Major:** an IRI changes or a concept is removed (both should never happen); a definition's meaning changes, not only its wording; a hierarchy change alters what a concept means; any deprecation.
   **Minor:** new concepts, modules, aliases, references, instances or constraint shapes; additive hierarchy; an added range or cardinality shape that the released content already meets.
   **Patch:** typos; clearer wording with the same meaning; an added example or scope note.
4. **Apply the meaning-change test:** would every query, report and assistant answer produced under the old definition still be correct under the new one? Yes means patch or minor; no means major. When unsure, major. *Why:* a false major costs a version number; a false patch corrupts consumers silently.

## Deprecate, never delete

5. **Mark the term `owl:deprecated true`, add `dcterms:isReplacedBy` to its successor, keep every existing triple, log the reason in the changelog, and do it only in a major release.** *Why:* deleting an IRI orphans every catalog row, assignment and measure binding that pointed at it, and kept triples still answer "what did this use to mean?".

## Who approves

6. **The module owner (the role the ontology owner names for a module in its decision record; the ontology owner until one is named) approves minor and patch releases. The ontology owner approves every major release, including a module's first release (1.0.0) and any deprecation.** *Why:* a major can make existing consumers wrong, and a first release sets the meaning every consumer starts from.
7. **Quote the sentence that approved the release in the manifest, and pin it in a test that reads it from the saved answer.** *Why:* the release cannot then be issued without the approval it claims.

## The release package

8. **Give every module the same package, built by one script:** the module's Turtle and JSON-LD, its shapes, a DCAT record, a changelog, and a manifest with the SHA-256 of each file and the module versions it requires. *Why:* consumers validate against a package, not a working tree, and one builder keeps every package the same shape.
9. **Make the builder deterministic, and give it `--verify`, which fails unless the written package equals a fresh build.** The check script runs `--verify` for every package. *Why:* a hand edit to a package, or a drift in its sources, then fails the check.
10. **Never change a released package; cut a new release instead.** *Why:* consumers pinned it by version and checksum.
11. **Name each dependency's version with `dcterms:requires` on the header and an entry in the manifest; import no module.** The build fails if a named version does not exist. *Why:* an import pulls a moving target into a pinned release.
12. **Resolve a package's dependency closure from the released manifests:** what a dependency itself requires is read from that release's own manifest, and where two paths reach different releases of one module, only the highest is loaded. *Why:* a later release of a dependency then changes neither the package nor what its checks load.
13. **Build the next release of a module from its released graph, not from the evidence again.** The builder reads the released package, applies the decided changes, and records a hash of the released manifest so the check fails if that package changes. Test that every earlier triple is kept, except the version header and what a decision changed. *Why:* the earlier release stays reproducible from its own pinned evidence, and the new one shows exactly what changed.

## Candidates and the cut

14. **Until the owner approves, build a release candidate (`1.0.0-rc.1`):** the candidate label in `owl:versionInfo`, the version IRI, the catalog and the manifest, and no `dcterms:issued`. *Why:* a candidate cannot be mistaken for a release.
15. **Cut in one commit after the approval:** drop the stage, set `dcterms:issued` and `dcterms:modified` from the cut date (never copied from an earlier release), update the test that pins the version, rebuild, and remove the candidate package. *Why:* only the release is left to consume.
16. **Tag the merge commit after the merge.** Records written before the merge say the tag comes at merge, never that it exists. *Why:* the tag records the immutable commit the release was built from.

## Before every release

17. **Check the gate:** the source-correction backlog is settled (`promotion.md`); the build, the evidence and the consumer-impact scan cite one commit; the consumer attestation is fresh; the package conforms to its shapes over its closure (`shacl.md`, rule 9); the competency questions run on it (`regression.md`); the approval in rule 6 is recorded in writing.
18. **Ship with every release:** `owl:versionInfo` on each module and on the release; `dcterms:issued` and `dcterms:modified`; a changelog entry per change (what, why, who approved, classification); a new DCAT dataset version with its distributions.

## The catalog

19. **Build one combined catalog of every release from the packages on disk**, as the union of their DCAT records plus the catalog's own title and description, and verify it in the check script: `--verify` fails unless the written catalog equals a fresh build. Test one dataset per package folder, that every distribution a dataset links to is described and names a file in its package, and that the catalog adds only its own title and description. *Why:* a release missing from the catalog then fails the check, and the catalog never says more about a release than the release's own record.
20. **Treat namespace hosting as an explicit decision.** Until the owner decides to host the base IRI, the IRIs identify and do not resolve, releases are retrievable from the repository at their tags, and the gate's "catalog resolves" is parked by that decision with its trigger. If the base IRI later changes, every term's identity changes: that needs its own decision and a major release of every module. *Why:* choosing the domain before anyone consumes the ontology keeps that cost low.

## The ontology header

```turtle
<https://w3id.org/example/ontology/modules/lending>
    a owl:Ontology, skos:ConceptScheme ;
    dcterms:title "Example Library Lending Ontology"@en ;
    owl:versionIRI <https://w3id.org/example/ontology/modules/lending/1.0.0> ;
    owl:versionInfo "1.0.0" ;
    dcterms:issued "2026-10-05"^^xsd:date ;
    dcterms:modified "2026-10-05"^^xsd:date ;
    dcterms:requires <https://w3id.org/example/ontology/modules/core/2.1.0> ;
    dcterms:rights "All rights reserved."@en .
```

21. **Type a module `skos:ConceptScheme` as well as `owl:Ontology` when its concepts are `skos:inScheme` the module IRI.** *Why:* otherwise the concepts sit in a scheme the release never declares.
22. **State rights with a licence that names real licence text, or with `dcterms:rights`;** never a `dcterms:license` IRI that resolves to nothing. *Why:* a dangling licence IRI claims terms nobody can read.

Consumers who need the current meaning use the ontology IRI; consumers who need reproducibility pin the version IRI or a versioned distribution.

## When the reference framework changes

23. **Leave your IRIs where they are, review each `dcterms:references` link against the new version, send newly relevant elements through the scope review (`foundations.md`, Step 8), and record the framework version on the release.** This is a minor release at most, usually a patch. *Why:* the framework is the check, not the source of truth.
