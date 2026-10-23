<!-- Copy at Step 2 and keep it as the identity map. Rules: references/identity-taxonomy.md, "Step 2", and references/domain-model.md, rule 1 (the kind). A slug, once minted, never changes when the label does; renames go in the overlay columns. Delete every comment. -->

# Identity table

Base IRI: `<https://id.example.org/library/>` (policy 4; <record, or "ASSUMED, not yet answered (Q<n>)">).

| IRI | Kind (concept, class, property, code value, reference individual) | `skos:notation` | Slug source (local ID, or "minted <YYYY-MM-DD> from the label then") | Current label | Prior label (overlay) | Rename record |
|---|---|---|---|---|---|---|
| `lib:circulation` | concept | C | minted 2026-10-22 from "Circulation" | Circulation | | |
| `lib:Loan` | class | | minted 2026-10-22 from "Loan" | Loan | | |
| `lib:loanState` | property | | minted 2026-10-22 | loan state | | |
| `lib:overdue` | code value (`lib:loan-state`) | LS-2 | lending system status code `OD` | Overdue | | |
| <IRI> | <kind> | <notation> | <source> | <label> | <prior label, if renamed> | <record> |

## Source strings mapped to code values

<!-- One row per string as the source spells it (identity-taxonomy.md, Step 3, rule 14). -->

| Source string | Code value | Merge reason (case, plural, punctuation, "&"/"and") or open question |
|---|---|---|
| `overdue` | `lib:overdue` | |
| `Overdue` | `lib:overdue` | case only |
| `overdue/hold pending` | <open> | Two dimensions in one string; asked the owner (Q<n>). |
