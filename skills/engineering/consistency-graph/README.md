# consistency-graph

Turns a project's sources into a graph that is rebuilt from them on every run, then checks where they disagree. It's for projects where several documents, specs or data files describe the same things: decisions that amend each other, equipment on drawings and in specs, components and the decisions behind them. Each source can be right on its own terms while two of them disagree, and the graph shows where.

The tool is a Python script in each project, started from this skill's tested template and backed by Relate for the graph queries. It has five commands: `check` reports disagreements, `impact ID` shows what a change touches, `query` runs read-only Cypher, and `summary` and `export` describe the graph.

This README is for people. Agents read `SKILL.md` and the files it points to.

## Files

| Path | Read by | What it does |
|---|---|---|
| `SKILL.md` | agent | The steps, from inventorying sources to making `check` a gate, and the hazards. |
| `references/check-catalog.md` | agent, when choosing checks | The kinds of finding, each with a real case from PPC or tar-twin. |
| `scripts/start.py` | agent runs it | Copies the template into a project under the tool's own name, and refuses to overwrite. |
| `scripts/test_start.py` | `scripts/check.sh` | Tests that `start.py` renames the copy and that the copy passes its own tests. |
| `templates/graph_tool.py` | copied into projects | The generic core (sources, clashes, checks, relate queries, command line) and an example PROJECT section to replace. |
| `templates/test_graph_tool.py` | copied into projects | Tests for the core and the example, with a fixture to replace. |
| `SOURCES.md` | you | Where the design came from. |
| `README.md` | you | This file. |

## Set up on a machine

`relate` (`curl -sSfL https://relatedb.ai/install.sh | bash`) for `impact` and `query`. `summary`, `check` and `export` need only Python, so CI runs them.

## Status

- Drawn from two uses: PPC's `scripts/adr_graph.py` (PR #18, merged 2026-11-27), which found 18 disagreements in its decision records, and tar-twin's `twin_graph.py` design pass (2026-11-28, tool not yet built), which found five gaps before any code.
- Open: the template reads markdown tables; a project with other source forms writes its own parsers in the PROJECT section.
