<!-- Copy at Step 8, right after Step 0. Rules: references/foundations.md, "Step 8". Take candidate areas from the framework's top-level areas, the requirements file's scope lists, and the columns of the representative data. Delete every comment. -->

# Step 8: scope review

Reviewed <YYYY-MM-DD> against the purpose in `<path to requirements.yaml>`.

| Candidate area | Call (in / out) | Hook or reason | Boundary note (out only) | Revival trigger (out only) |
|---|---|---|---|---|
| Lending | in | CQ1 needs it | | |
| Fines | out | Amounts are records the lending system holds (policy 2). | Fine amounts and payments stay in the lending system; nothing in the ontology depends on them. | A competency question about kinds of fine, not amounts. |
| <area> | <call> | <the competency question, consumer or in-scope area that needs it; or why nothing does> | <where the area is handled and what depends on it> | <the event that would bring it back for review> |

<!-- A revival trigger is the event that reopens an out call: a new competency question, a named consumer, a framework release. An in call needs none. -->
