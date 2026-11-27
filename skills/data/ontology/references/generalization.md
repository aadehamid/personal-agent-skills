# Generalizing an existing release

Serves Steps 2 and 3, and Step 11 for the migration tests. Read it before you turn an organization's released ontology into an organization-neutral one, such as an industry reference (`industry-reference.md`), so that nothing in the old release is lost or carried over by accident.

The released ontology you start from is the **baseline**. Each rule below makes the move from the baseline to the new ontology checkable, term by term.

## Before the first change

1. **Freeze the baseline.** Record the commit or tag it came from and a hash manifest, one hash per file, and make a check fail when any baseline file changes. *Why:* every later comparison is against the baseline, so a baseline that moves makes every comparison meaningless.
2. **Keep a migration map: one row for every term in the baseline, each with exactly one status** (retained, renamed, moved, merged, deprecated, excluded), the new IRI where there is one, and the decision behind the row. A check fails when a baseline term has no row or two. *Why:* a term with no row was either lost or carried over without anyone deciding.
3. **Mint neutral IDs for the new ontology, and keep the old codes only in the migration map.** A neutral ID says nothing about place or about the old organization. *Why:* an old code carried into the new ontology ties it to the baseline's structure, and a code that encodes a parent breaks when the node moves.

## Removing what belongs to one organization

4. **Keep an organization-term register:** each term that names the organization, one of its internal systems or its internal practice, with the kind of each. Make a check scan every literal of every subject, `skos:hiddenLabel` and examples included, and every IRI, and fail on any register term. *Why:* a hidden label or an example is still published, and an IRI under the old organization's namespace still names it.
5. **Exclude a term that only one organization uses, with its migration-map row; never carry it into the new ontology as deprecated.** *Why:* a deprecated term is still part of the published ontology, and it keeps one organization's practice in the shared one.
6. **Record one decision per top-level node** of the new hierarchy, citing its evidence. *Why:* the top levels decide where every lower term goes.

## Testing the migration and finding subtrees

7. **Make the identity migration test cover both ends of every relationship fact the new ontology keeps.** A fact that is not carried over gets a disposition in the migration map instead. *Why:* a test that checks only the concepts passes while a relationship still points at an old IRI.
8. **Let no script or test find a subtree by a code prefix; follow the parent links.** This holds for build, query and check scripts as well as tests. *Why:* once a node moves, its old code no longer matches its place, so a prefix search misses the moved node or catches one that left.
