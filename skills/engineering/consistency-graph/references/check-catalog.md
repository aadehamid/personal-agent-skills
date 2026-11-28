# Kinds of finding

Each kind below is a check a consistency graph can run, with the real case that showed it. Pick the kinds your sources can raise; each needs a test that fails when the check is removed.

| Kind | What it catches | Real example |
|---|---|---|
| Two-sided link disagreement | Two sources state one link from each end, with different meanings | PPC: ADR-0055's index row says it *amends* ADR-0045; ADR-0045's status says *clarified by* ADR-0055 |
| Link stated on one side only | One source states a link the other end never mentions | PPC: ADR-0056 amends ADR-0043, but ADR-0043's status does not say so |
| Field that means something else | One field used for a wider meaning than its name | PPC: several ADRs list *clarifies* and *stages* targets under frontmatter `amends:` |
| Link to nothing | A link whose end no source defines | PPC check: an index link to an ADR number no record holds |
| Element with a required link missing | An element every rule says must connect, and does not | tar-twin: KT-201 is on a drawing and in the equipment list but in no isolation envelope |
| One element, two places that conflict | An element a rule says belongs to one group, stated in two | tar-twin: P-201A/B appear in two envelopes (suction and discharge); settled as a property of the link, not a clash |
| Name stated two ways | Two sources name or describe one element differently | tar-twin: `FL-201A, FL-201B` in one section and `FL-201A/B` in another; R-202 "Main reactor" in the spec and "HYDROTREATING REACTOR" in the drawing script |
| Two taxonomies that never meet | Two classifications of the same population with no mapping | tar-twin: 12 discipline categories and 9 matching classes, each summing to 200 work requests |
| Rule with no decision behind it | A rule or requirement that cites no decision | tar-twin: most rules in `docs/verification.md` cite no decision ID |
| Count that does not add up | A document's promised count differs from what the sources define | tar-twin: 112 boundary valves and 200 work requests promised, not yet named; reported as pending until the data exists |
| Unreadable source form | A row, verb or file the parser cannot read | PPC: a link clause like "Amends ADR-0042a" or a row with an extra column, reported instead of dropped |

Findings that need a ruling go to the owner with a recommendation; the check does not settle them by choosing a source.
