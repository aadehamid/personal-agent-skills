# Sources

| Source | What was taken | Version or date | How to check for updates |
|---|---|---|---|
| PPC `scripts/adr_graph.py`, <https://github.com/aadehamid/pearland-petroleum-corporation/pull/18> | The pattern: rebuild the graph from the sources every run, report unreadable forms instead of dropping them, run queries on a read-only copy with `--command`, keep links to undefined ids out of the graph and report them. | Merged 2026-11-27 | Compare `templates/graph_tool.py` with PPC's tool after its next change. |
| tar-twin `twin_graph.py` design pass | The finding kinds in `references/check-catalog.md` marked tar-twin, and the hazard about planned material. | 2026-11-28 | Read the merged tar-twin tool when it lands. |
| Relate cookbook, "Answer codebase questions text search can't", <https://relatedb.ai/cookbook/codebase-context-graph/index.md> | The idea of answering "was this replaced?" and "what builds on this?" from links between documents rather than matching text. | Read 2026-11-27 | Read the recipe again. |
