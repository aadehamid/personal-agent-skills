# Sources and maintenance

This skill's wording and templates are original. They generalize owner-requested
project discovery and documentation work, including failures observed during
review: conflicting permission definitions, undocumented scoring rules, premature
evaluation before isolation controls, and confusion between visible fixtures and
hidden evaluation truth.

No reference company, architecture, product stack, local path, or document count
from that work is a runtime default.

## Authoring guidance

- [Portable agent skill authoring](https://github.com/EveryInc/compound-engineering-plugin/blob/075bac8169b17e4afebcc3ef94d300f1d12ecb53/docs/solutions/skill-design/portable-agent-skill-authoring.md), inspected 2026-10-05 at the last commit changing that file, document `last_updated: 2026-09-11`: outcome-first instructions, capability-based portability, bounded authority, and proportionate evaluation. Guidance was applied, not copied.
- Local companion skills `grilling`, `domain-modeling`, and `clear-writing`:
  optional capabilities, not pinned runtime dependencies or permission grants.
- This repository's root README: category layout, per-skill README/SOURCES,
  reference files, evaluation fixtures, and discovered-agent installation.

The personal repository's layout is authoritative here. Its README requires a
per-skill README and supports an `evals/` directory; the upstream author's different
repository layout, inventory tests, and package tooling are not imported.

## Updating

Compare any changed upstream guidance against the smallest behavior the skill needs.
Do not copy an upstream workflow wholesale or introduce its platform-specific paths.
Re-run activation, restraint, batch/interactive, and resumption cases after changes
to permissions or stopping rules. Record host and model/runtime differences.

References inspected online can change. If retaining upstream snapshots for a future
comparison, keep them under the repository's ignored `upstream/` convention; do not
commit third-party documents without permission.
