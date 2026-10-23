# Cross-model integration

Serves Step 7. Read it before you bring back a parked overlay (measures, data products, value streams, capabilities, systems, lanes, market series), rank sources, write consumer rules, or apply an external mapping assigned to this step.

## How overlays come back

1. **Revive one parked overlay at a time, each in its own module** with its own namespace, vocabulary, shapes, build and tests, referring to core processes by IRI. *Why:* each overlay then releases and versions on its own, and one bad overlay blocks nothing else.
2. **Reference process nodes; never duplicate them.** An overlay node is its own thing that points at processes. *Why:* a value stream cuts across the hierarchy, and every concept has exactly one parent, so a value stream can never be a parent.
3. **Define only what a source describes.** An item an overlay names without describing (a data product, a system) gets an editorial note that its definition waits for its owners, never a definition written from its name. A shape requires the definition or the note, and rejects both together. *Why:* a definition guessed from a name is read as the owners' meaning.
4. **Resolve each gap an earlier step exposed (an empty output set, a missing owner) as its own recorded decision**: linked, or parked with a trigger, never filled by an invented owner (`foundations.md`). *Why:* the Step 7 gate counts decisions.
5. **Apply the external mappings assigned to this step at Step 0** (`external-ontologies.md`), each with its trigger if it must wait.

## Measures: definitions, never values

6. **Model a measure as a definition:** name, definition, kind, population, grain, basis, and what it is not. It carries no value, target or actual, and a closed shape lists every property a measure may carry so any other property fails. *Why:* the data-scope policy (`foundations.md`, policy 2); the closed shape makes it checkable.
7. **Cite the public filing or source that uses each measure.** *Why:* a measure's meaning is what its source computes, not what its name suggests.
8. **Classify each measure's kind with tests in a fixed order, and stop at the first that assigns one.** Record the test and the reason.
   1. No formula, unit or time grain: a tracker or report (or not a measure at all, for a capability request).
   2. Emitted only when a condition is met: an alert.
   3. Set by a market the business cannot influence: a market indicator. Computed from market prices and a planning model to start or rank a decision, with no performance target: a decision-support indicator.
   4. Actual or plan against a plan, forecast, prior version or history for one period: a plan-variance diagnostic.
   5. Otherwise an operational metric, unless designated a KPI (rule 9).
   *Why:* a fixed order gives every reviewer the same answer for the same row.
9. **Treat a KPI as a designation, not a kind.** A measure is a KPI only when the business names it as one of the few measures of a stated objective, with a recorded target and an accountable owner. Mark an operational metric a KPI candidate only where evidence makes it strong (a headline measure the company reports, or one a peer targets); never invent a target or an owner. *Why:* the same ratio can be a KPI for a region and an operational metric for a unit.
10. **Make a comparison part of a variance measure, and only a view of any other.** "Loans against forecast" is defined by its comparison; "shelf utilization" against plan or against five years of history is one measure asked two ways, recorded as a `comparedAgainst` list. *Why:* a new measure per reference multiplies definitions of one thing.
11. **Name the basis in words:** numerator, denominator and unit (calendar-day or stream-day capacity; net or gross throughput). Give a definition that changes between filings a version, not a silent edit. *Why:* two ratios with different denominators are different measures.
12. **State a measure's population (what it includes and excludes) only where its source states it**, with the evidence; park the rest by decision until the owner states it. *Why:* a population written from the definition is a guess.
13. **Link "what it is not" explicitly:** a `notToBeConfusedWith` link to a nearby measure, with a scope note saying how they differ. *Why:* the commonest consumer error is answering with the neighbouring measure.
14. **Turn the people on a measure list into the roles they hold**, defined by plan type and horizon; no person's name enters the ontology. *Why:* `organization.md`, rule 22.
15. **Link measures to processes as context:** a link says which process a measure informs; it does not certify the process (rule 25). *Why:* informing is not owning.

## Market series

16. **Separate a measure from its published series.** A series is one form of a measure, built from parts its source names. Two series are the same only when every attribute their sources use to tell them apart is the same; otherwise they are two series of one measure, not two measures. Record which attributes decide it in a decision record. *Why:* treating series as measures splits one definition; treating them as one hides a real difference.
    Example: Marathon Petroleum's Form 10-K for fiscal 2025 says "The benchmark crack spreads below do not reflect the market cost of RINs". A Gulf Coast 3-2-1 crack spread that deducts that cost is a different series of the same crack-spread measure, even with the same crude and product markets.
17. **Store the recipe, never the prices.** A leg names a benchmark and its quantity; weights that change by period go in a cited note. *Why:* prices are observed values (`foundations.md`, policy 2).
18. **Keep price markets apart from the company's own reporting regions** as two schemes. *Why:* they answer different questions and change on different schedules.

## Data products, value streams, capabilities

19. **Model a data product as a definition in its own scheme** (its line as `skos:broader`), mapped to DCAT with `skos:closeMatch dcat:Dataset` (DCAT Version 3, W3C Recommendation 22 August 2024, https://www.w3.org/TR/vocab-dcat-3/), not typed as one. *Why:* a definition of a product is not a published dataset, and mapping keeps DCAT's authority without its commitments.
20. **Make a value-stream process its own node that `realizes` each process it names**, with its produce and consume links to data products. A producing process is the data product's owning process. *Why:* the overlay keeps its own identity and the backbone stays untouched.
21. **Qualify a measure link on a value-stream process** (measure, relationship, cited basis), and let no measure kind sit on the link. *Why:* a link is not a KPI designation.
22. **Keep the source's own domain label as written** when it does not map cleanly to your domain list. *Why:* a forced mapping claims a scope match the source never made.

## Systems and other code lists

23. **Build systems from the source's strings through a register**, as roles are built (`organization.md`, rules 2 to 5): merge on spelling only, split a string joined by "/" into its systems, create nothing for a string that names no system. Give each system a kind (application, office tool, working document) and no definition until its owners give one. *Why:* systems are shared by many processes, so they are things, not process attributes.
24. **Link a code-list value to a process by key** (the value's `skos:notation`), checked by the build, and inherit nothing down the hierarchy. *Why:* the key is how the source names it; inheritance is a guess (`organization.md`, rule 8).

## Placement, authority and consumers

25. **Say what each placing link claims, in a form a query reads.** Annotate every property that places a measure, data product or system on a process with a placement kind: **certification** (the link names one end's owning process) or **context** (it says only where one thing is used or placed). Only an owning link certifies. *Why:* consumers otherwise read every placement as ownership.
26. **Give every cited source an evidence tier from the project's evidence order, each tier with a rank,** and test that no cited source lacks one. *Why:* when two sources of one concept disagree, the best tier wins, and a query can say which.
27. **Write down the rules for the graph's consumers:**
    - **The catalog binding:** a row binds a measure to the data product that publishes its values only when both ends are defined first, checked by a shape.
    - **What an agent may answer from the graph alone:** what a thing is; what it is not; where it sits and what the placement claims; what a series is built from; who is responsible; which source says so and which wins; what a measure includes and excludes, where its source says.
    - **What an agent must refuse:** computing or quoting a value; building a series from its legs; treating a candidate or a report column as a KPI; naming a party without its role; presenting a context placement as ownership.
    *Why:* a consumer that improvises these rules gives answers the ontology does not support.
28. **Make each consumer rule name the graph terms it relies on**, and test that they exist. *Why:* a renamed term otherwise silently breaks a rule nobody runs.
