# Organizations, roles and responsibilities

Serves Step 5. Read it before you model roles, RACI assignments, party roles, real companies or ownership between legal entities.

Roles are positions people hold, not people. The same person can be Accountable for one process and only Informed on another. RACI is design-time responsibility, not a record of who did the work.

## Roles and the role register

1. **Model each role as an `org:Role`** (W3C Organization Ontology, Recommendation 16 January 2014, https://www.w3.org/TR/vocab-org/), used by IRI and not imported. *Why:* consumers that read ORG need no mapping, and importing would bring structure no question needs (`external-ontologies.md`).
2. **Normalize the source's role strings through a role register:** one row per string as the source spells it, mapped to one or more roles. A build script checks the register against the source, so a new or changed string stops the build. *Why:* the register is the only place a spelling becomes a role, so every role traces to its strings.
3. **Merge two strings only when they differ in case, plural, punctuation or "&" against "and".** Never merge on a guess at what an acronym or a title means. *Why:* a wrong merge gives one role another's responsibilities, and splitting later costs more than merging later.
4. **Split a compound string ("Planner / Scheduler") into its roles; keep a qualifier ("for rare books") on the assignment, not in the role; model a team named in a RACI list as a role with a scope note** saying it stands for the team acting as one party. *Why:* each assignment then names exactly one role, and the qualifier survives.
5. **Put a possible misspelling or an unexplained acronym to the owner; correct nothing yourself.** Record the question in the register until it is answered. *Why:* only the owner knows whether "Circ Lead" and "Circulation Lead" are one role.

## RACI assignments

6. **Bind role, process and RACI level with an explicit n-ary assignment node** (`ResponsibilityAssignment`): exactly one process, one role, one level from a four-member code list, the role text as the source wrote it, and at least one source. *Why:* a single property cannot carry a three-way binding, and the node can carry its source text and citation.
7. **Emit one assignment per source entry and per role the entry names.** Two entries naming the same role on the same process and level stay two assignments, each with its own text; queries use `DISTINCT` over process, level and role. *Why:* collapsing them drops all but one qualifier.
8. **Infer nothing from the hierarchy.** A process with no RACI in the source gets no assignment, even when its parent or child has one. *Why:* "the parent's owner owns the child" is a guess the source never made.
9. **Mint assignment IRIs from content** (process, level, role, and a hash of the source string), as `identity-taxonomy.md`, Step 2, rule 6 says.
10. **Reconcile in a conservation table:** source entries plus the extra roles that compound strings add equal the assignments, in total and at every level. The build fails otherwise. *Why:* the same arithmetic as `promotion.md`, rule 7.
11. **Get a recorded scope before you test the gate.** "Every in-scope process has RACI" needs a decision on which processes are in scope. Processes outside it go on the source author's backlog, and a must-be-none query lists them; do not invent RACI for them. *Why:* without a recorded scope the gate is either untestable or met by invention.

## Party roles: dated nodes, never subclasses

12. **Model a party role (borrower, supplier, carrier, customer) as a node, not a subclass of party.** The role node names exactly one party that holds it, one role type from a code list, a start date and an optional end date; a shape rejects an end before the start. *Why:* one organization can be a supplier in one deal and a customer in the next, and each role can end without touching the others.
   Example: a library member holds a Borrower role from the day the card is issued and a Volunteer role from a later date. Both are nodes pointing at one `Person`; neither is a class.
13. **Allow only the subclasses the business guarantees under party** (typically Person and Organization), and check that no other class is a subclass of party at any depth (`shacl.md`, rule 12). *Why:* "Customer" as a subclass freezes a role into an identity.
14. **Keep a place apart from the role played there.** A delivery location is a site; the party that receives goods there holds a receiving role. *Why:* systems often keep a site as its own customer number, and a model that copies that loses who the party is.
15. **Date an assignment of a class to an account** (for example a customer class) as its own node with a start date, when the source gives such assignments their own effective dates. *Why:* the same reasoning as rule 12.

## Real organizations: the reference module

16. **Put public reference instances of real companies, sites and assets in their own module** (`ref-<company>`), as `org:FormalOrganization`, `org:OrganizationalUnit` and `org:Site`, using the organization module's terms and minting none of its own. *Why:* the module policy in `foundations.md`.
17. **Cite a source and state an as-of date on every instance and fact, not only on the source node.** Give the source node its title, filing date, accession or edition, and URL. *Why:* a later filing may restate some facts and not others, and each fact must say which filing it rests on.
18. **Keep a legal entity apart from a reporting segment.** A segment (`org:OrganizationalUnit`, `org:unitOf` the company) is how a company reports; a subsidiary is a separate legal entity that may publish its own filings. *Why:* treating a subsidiary as a segment loses its own filings and owners.
   Example: Marathon Petroleum Corporation's Form 10-K for fiscal 2025 (filed 2026-02-26, accession 0001510295-26-000009) says "Our operations consist of three reportable operating segments: Refining & Marketing, Midstream and Renewable Diesel." MPLX is a separate legal entity.
19. **Model control and ownership between legal entities as a qualified relation of its own**, never as `org:subOrganizationOf` alone. In the W3C ORG Recommendation (16 January 2014), `org:subOrganizationOf` "represents hierarchical containment of Organizations or OrganizationalUnits": it says one organization contains another, and it cannot carry a share, an as-of date or a source. The control node names exactly one controlling and one controlled entity, at most one share (0 to 1), exactly one as-of date and at least one source. Quote the filing's own hedge where the share is rounded. *Why:* the link carries a share, a date and a source, so it needs a node (`foundations.md`, conceptual modelling, rule 8).
   Example: the same 10-K says "As of December 31, 2025, we owned the general partner of MPLX and approximately 64 percent of the outstanding MPLX common units." That is one control node: MPC controls MPLX, share 0.64, as of 2025-12-31, with a note quoting "approximately".
20. **Map legal entities to a public registry by identifier**, for example the GLEIF LEI as `org:identifier` with `rdfs:seeAlso` to its registry record, and record in a note where the registry lacks the relation you model. *Why:* the registry gives external authority without importing its model, and the note stops a reader expecting a mapping that does not exist.
21. **Describe real multi-role organizations from filings only, as reference facts:** the roles each holds, the agreement it holds them under, a start date the filing gives, and the filing. Record no transaction, price or volume. Test them both ways, party to roles and role to party. *Why:* real examples prove the role model works, and the data-scope policy keeps records out (`foundations.md`, policy 2).
22. **Keep an organization's people out of the ontology; model the roles they hold.** *Why:* names change and are personal data; roles are what consumers query.
