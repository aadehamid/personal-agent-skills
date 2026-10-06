# Versioning and releases

Read this before a release (Step 4's first module release, Step 10) or when a change might break consumers.

## Rule

Term URIs are permanent and carry no version. Versions live on the module's `owl:Ontology` header (`owl:versionInfo`, `owl:versionIRI`) and on versioned distributions (`.../releases/1.2.0/ontology.ttl`).

## Classify every change

- **Major:** a URI changes or a concept is removed (both should never happen); a definition's meaning changes; a hierarchy change alters meaning.
- **Minor:** new concepts, modules, aliases, references; additive hierarchy.
- **Patch:** typos; clearer wording with the same meaning; an added scope note.

Meaning-change test: would every query, report and assistant answer produced under the old definition still be correct? Yes means patch, no means major. When unsure, major.

## Deprecate, never delete

`owl:deprecated true` plus `dcterms:isReplacedBy`, keep every existing triple, log the reason, and only in a major release.

## Release gate

Every held item has a verdict and the ledger reconciles; build, evidence and consumer-impact scan cite one commit; the consumer attestation is fresh; the SHACL slice passes; the owner has approved in writing.

Every release ships version info on each module and the release, issued and modified dates, a changelog entry per change (what, why, who approved, classification), and a new DCAT dataset version with its distributions. Module owners approve minor and patch releases; the ontology owner approves majors.

## Header example

```turtle
<https://w3id.org/example/ontology/modules/core>
    a owl:Ontology ;
    dcterms:title "Example Core Process Ontology"@en ;
    owl:versionIRI <https://w3id.org/example/ontology/modules/core/1.0.0> ;
    owl:versionInfo "1.0.0" ;
    dcterms:issued "2026-10-05"^^xsd:date ;
    dcterms:license <https://w3id.org/example/ontology/license> .
```
