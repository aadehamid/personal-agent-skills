---
name: consistency-graph
description: >-
  Builds a consistency graph: a Relate graph rebuilt from a project's own sources on every run, with a check that reports where those sources disagree, an impact query for a planned change, and read-only Cypher. Use when several documents, specs or data files describe the same things (decisions that amend each other, equipment on drawings and in specs, components and their dependencies) and must agree; before changing something those sources describe; or to find out how things fit together.
---

# Consistency graph

A project's sources often describe the same things from different sides: an ADR index and each ADR's own header, a scenario spec and a drawing script, a component list and its decision log. Each source can be right on its own terms while two of them disagree. Reading files one at a time misses that; a graph of everything they state, built from all of them at once, shows it as a missing link, a link with no end, a name stated two ways, or a count that does not add up.

The tool is a Python script in the project that rebuilds the graph from the sources every run, so it never drifts from them. Start it from this skill's tested template with `scripts/start.py`, then replace its example parsers with the project's.

Two projects shaped it. PPC's `scripts/adr_graph.py`, merged, found 18 places where its decision records disagree. tar-twin's design pass for a `twin_graph.py`, not yet built, found five gaps between its scenario spec, drawings and verification rules before any code. `references/check-catalog.md` lists the kinds of finding with those examples; read it before you choose your checks.

## Steps

1. **Read the project's rules first**: its `AGENTS.md`, decision process, check script and review rules. Its rules win, and the tool ships through its normal pull-request process.
2. **Inventory the sources.** List every file that states a node or a link, and what each states. A fact the tool needs must come from a source; never type it into the tool.
3. **Design the graph and propose it to the owner before code.** Name the node labels, the link types and their direction, and the checks, each tied to a kind from the catalog. Show the findings a first pass over the sources would raise. Anything that needs a ruling (which name is right, which count is right, whether an exception is allowed) is the owner's call: ask, with your recommendation first, and record the answer the way the project records decisions.
4. **Start the tool**: `python3 <this skill>/scripts/start.py <repo> <name>`, such as `twin_graph`. It writes `scripts/<name>.py` and `scripts/test_<name>.py`, renamed, and refuses to overwrite. Keep the generic core; replace the PROJECT section.
5. **Write the tests first** if the project asks for that: a small fixture with every source form your parsers read, and one case per finding kind. Each check needs a test that fails when the check is removed; remove it once to prove it.
6. **Write the parsers.** Every node and link records the source that stated it. When two sources state one property differently, keep both and let `check` report the clash; do not choose. When a source cannot be read (a row of the wrong shape, an unknown verb, a missing file), report it; never skip it silently.
7. **Run it on the real sources** and bring every finding the owner must settle to a decision round. Fix what the evidence settles.
8. **Make `check` a gate** in the project's check script once it reports nothing. Until then, run it and print the summary there, so nobody mistakes findings for failures.
9. **Point agents at it** with one line in `AGENTS.md`: run `<tool> impact ID` before changing what ID names, and `<tool> check` after.

Done when the tool, its tests and the AGENTS.md line have merged, every finding is fixed or settled with the owner's words, and `check` is a gate or the reason it is not yet is recorded.

## Using a graph you already have

- Before changing something, run `impact ID` and read what the change touches.
- After changing a source, run `check`.
- For any other question about how things connect, use `query 'CYPHER'`. It runs on a read-only copy, so relate itself refuses writes.
- When later sources join (generated data, a live database), add them as sources of the same graph and let `check` compare them with the documents. Do not keep a second copy.

## Hazards

- **Counts come from a source.** `EXPECTED_COUNTS` reads the number a document promises; a number typed into the tool goes stale the day the document changes.
- **A parser that guesses hides the finding.** Normalising two spellings of one tag to one node without recording both is the commonest way a real disagreement disappears.
- **Pass statements with `--command`.** The template does; a statement starting with `-` is then never read as a relate flag.
- **Planned material is not a failure yet.** When sources promise elements that do not exist yet (a phase not built), report them as pending rather than failing the gate, and say in the check output which mode ran.
