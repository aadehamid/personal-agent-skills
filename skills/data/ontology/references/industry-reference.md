# Industry-reference mode

Serves Steps 0, 1, 3 to 5, 7 and 8 when the ontology describes a whole industry rather than one organization. Read it at intake, before Step 0, when the requirements file says the ontology is a reference for an industry or a sector. The other references still apply; where this file sets a different rule for this mode, this file wins.

A single-organization ontology models one business from its own documents. An industry reference models what every organization in the sector shares, so that each organization can specialize it. The rules below keep the reference free of any one organization's practice.

## The backbone

1. **Build the backbone (the hierarchy of processes or concepts that Steps 2 and 3 rest on) from a published standard plus the public evidence of 3 or more independent organizations.** Three is the default; the requirements file may set a different number, with the owner's reason, and that number then applies wherever this file says 3 or more. A seed hierarchy, such as one organization's own release, is a starting point only, never the backbone. *Why:* a hierarchy copied from one organization encodes its structure as the industry's.
2. **Have the owner sign off the top levels of the backbone, node by node** (for example the first three levels), and record one decision per node. Lower levels follow the evidence rules below without a decision each. *Why:* the top levels shape every later choice, and a decision per node lets a reviewer trace each one; signing every leaf costs more than it adds.

## Evidence order

3. **Rank sources in this order instead of `foundations.md`, policy 3:**
   1. standards and sector bodies;
   2. the public disclosures of 3 or more independent organizations (filings, annual reports, published policies);
   3. sector-specific sources;
   4. generic frameworks, as a crosswalk only. A generic framework may fill a naming gap only where the item is tied to work that practitioners are shown to do.

   An organization's private material may show what exists, but it is never cited. *Why:* in a reference, standards drive the design and organizations' disclosures only confirm it; the organization's own documents, which rank first for a single-organization build, would make the reference that organization's copy.

## Two layers and the clean-room rule

4. **Keep two layers apart.** The reference holds: definitions; public formulas that are the same everywhere (never one organization's own formula); each measure's nature and roles, including its role as a typical KPI; links between drivers and the measures they move; and typical RACI by generic role. An organization's specialization holds: KPI designations with their targets, thresholds and owners; its own formulas and their versions; its role titles mapped to the generic roles; named assignments; its internal systems; and its instances. *Why:* each organization can then adopt the reference and add its own layer without editing the shared one.
5. **Put nothing internal to an organization anywhere in the reference: not in a label, a hidden label (`skos:hiddenLabel`), a definition, a note or an example.** Check it mechanically with an organization-term register (`generalization.md`, rule 4). *Why:* a hidden label is still published, and an example is still read as the reference's content.

## Roles and RACI

6. **Take the generic roles from a public occupational, governance or regulatory standard, or from 3 or more independent organizations.** Examples: O*NET-SOC, ISCO-08, ESCO, the ISO management-system standards, sector regulations. *Why:* an organization's job titles are its own; a standard's roles are shared.
7. **Cite the evidence of every typical RACI assignment, and mark a role that comes from one jurisdiction's rule with that jurisdiction.** `organization.md`, rule 8 still holds: infer nothing from the hierarchy. *Why:* a role one regulator requires is not an industry-wide role, and a reader must be able to tell the two apart.

## Systems

8. **Model a system as a generic capability** (for example "production planning"), never as a product. Give an organization's homegrown system a neutral capability name. An off-the-shelf product may appear only as a labelled example, cited to its vendor's public page. A single-organization ontology still models its own systems, in its organization layer. *Why:* an internal system name is the organization's private fact, and a product name ties the reference to one vendor.

## Order between steps

9. **Keep a `precedes` link only where a published standard, a physical or logical necessity, or the public material of 3 or more independent organizations establishes the order.** Drop one organization's step orders; never keep them as examples. In this mode it replaces the rules for every `precedes` link in `promotion.md`, rule 5 and the `precedes` definition, for siblings and non-siblings alike. Taxonomy numbering implies no order. For example, APQC says so of its own Process Classification Framework: "Although process elements are numbered ascendingly, it is important to understand this does not imply that process elements occur in a certain order" (APQC, *Understanding the Elements of APQC's Process Classification Framework*, 2018, https://www.apqc.org/sites/default/files/files/PCF%20Collateral/Understanding%20the%20PCF%20Elements%20%20-%20FINAL.pdf, read 2026-11-27). *Why:* the order of steps in one organization's hierarchy or documents is that organization's practice, not the industry's.

## Completeness

10. **Treat a seed release as a starting point, not the boundary of scope.** At Step 8, keep a coverage table per area: each item, its evidence class (from rule 3) and its source. Mark an area complete only with the owner's recorded approval. *Why:* a reference built only from what one organization happened to model leaves out what the rest of the industry does.
