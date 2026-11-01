<!-- Copy at Step 0. Rules: references/foundations.md, "Step 0", and references/external-ontologies.md. In the framework, boundary and survey tables, a row is done only when every cell holds a fact you read in the publisher's own copy; write "not checked" rather than a guess, and the gate stays open. The registry-search table records your own searches instead (its note says how). Delete every comment. -->

# Step 0: reference framework and survey

Checked <YYYY-MM-DD>.

## Reference framework

<!-- The sector's reference standard, classification or code list. If the sector has none, write "None found" with what you searched, and record it as a finding. -->

- **Framework:** <name, version, publication date, publisher's URL>
- **Licence and attribution notice:** <the notice as the publisher states it, and where it must travel>
- **Copy stored at:** <path in the repository, with the notice intact>

### Cited elements

| Framework element ID | Name in the publisher's copy | Verified against (document, page or section) | Local concept |
|---|---|---|---|
| <ID> | <name> | <where you read it> | <local IRI, attached by `dcterms:references`> |

### Boundary notes

<!-- A boundary note records one place where the local model differs from the framework, and why. One row per divergence. -->

| Local concept | Framework element | How they differ | Reason | Mapping (`exactMatch`, `closeMatch` or none) |
|---|---|---|---|---|
| <local term> | <ID and name> | <what the local term includes or excludes that the framework does not> | <the evidence, by tier> | <match> |

## Registry searches

<!-- One row per registry in references/external-ontologies.md, "The registries to search", and one per further search you ran. These cells record what you did, not a publisher's fact: the date, the exact query terms, and the hits by name as the registry listed them. "no hits" is a complete answer for a search that found nothing; never leave the row out. A search you could not run is "not run (offline)", or "not run" with another reason, dated the day you recorded it, with the terms you would use; Step 0 then stays open and Step 1 may start (external-ontologies.md, "Offline"). -->

| Registry | Date | Query terms | Hits (names), or "no hits" |
|---|---|---|---|
| Linked Open Vocabularies (vocabulary and term search) | <YYYY-MM-DD> | <terms> | <hits> |
| BARTOC | <YYYY-MM-DD> | <terms> | <hits> |
| Open Knowledge Graphs | <YYYY-MM-DD> | <terms> | <hits> |
| DBpedia Archivo | <YYYY-MM-DD> | <terms> | <hits> |

## Survey of public ontologies and code lists

| Source | What it covers | Licence (read in full) | Version or version IRI, date checked | Treatment (map, import, ignore) and why | Target step |
|---|---|---|---|---|---|
| <name and URL> | <the questions or concepts it covers> | <licence> | <version, date> | <treatment> | <step> |

## Findings

- <Each area no source covers, as a finding (external-ontologies.md, rule 8).>
