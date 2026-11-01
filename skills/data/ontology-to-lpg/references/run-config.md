# One run, every store, every check: `run_projection.py`

Read it when a project projects its release more than once, or into more than one store, and wants one command instead of its own scripts around this skill's. `run_projection.py` runs steps 2 to 6, add-ons F, H, I, J, K and M, the `rdf-store` skill's round trips and a rebuild from any store, all from one run configuration, and runs every check each of them has. It runs the skill's own scripts; it adds no check of its own except the rebuild's two comparisons.

```
uv run --no-project --with rdflib python3 scripts/run_projection.py --config run.json --plan
uv run --no-project --with rdflib python3 scripts/run_projection.py --config run.json [--only a,b] [--skip a,b]
```

`--plan` lists the steps that would run, and why any is skipped, and runs nothing. It needs uv, Docker, and Java 11 or later for ROBOT. It never prints a password: the local Neo4j's password is generated and kept in `<out>/neo4j-run/run.env` (mode 600). The target and Databricks env files are passed to the scripts by path, never read by the driver.

## First, choose releases or files

The run configuration's `mode` says what is projected. Without one, the driver prints this choice and stops, so ask the user before writing the configuration:

| Mode | What it takes | For | Against |
|---|---|---|---|
| `releases` (recommended) | Versioned packages: each data file has one `owl:versionIRI` and pins what it requires | The pins and the closure of requirements are checked, every node is tagged with its release, the module graph shows what requires what, and a store copy traces back to a release | You need packages first |
| `files` | Any Turtle or N-Triples files, or folders of them | Works on what you have now, with the same loads, hashes, round trips and rebuild | No version pins or closure check; without SHACL shapes the projection uses defaults derived from the data |

When the user picks releases and has none, the driver stops and points to the `ontology` skill's guided packaging walk-through (`skills/data/ontology/scripts/build_package.py`), which builds them. The walk-through is being built separately; until it lands, package with the `ontology` skill's Step 10 (release and publication), or choose files.

## The run configuration

A JSON object. Paths are relative to the configuration's own folder, so it can sit in the project repository, beside the projection configuration. Copy `templates/run-config.json`.

| Key | Needed by | What it holds |
|---|---|---|
| `projection_config` | every step | The projection configuration (`templates/projection-config.json`). |
| `mode` | every step | `releases` or `files` (above). |
| `data`, `shapes` | every step | Releases: the released package files, and the shape files (each release's and any whole-graph ones). Or give `inputs_script` instead. Files: `shapes` is optional. |
| `files` | files mode | RDF files (`.ttl`, `.nt`) or folders; a folder gives every such file under it, in path order. |
| `graphs` | files mode, optional | `{file: graph IRI}` for a file with no `owl:versionIRI`. |
| `inputs_script` | instead of `data` and `shapes` | A Python script printing one absolute path per line for `<script> data` and `<script> shapes`, when the project keeps its list elsewhere. It runs with rdflib, pySHACL and the neo4j driver. |
| `releases` | releases mode | The folder of released packages, `<module>/<X.Y.Z>/`, for the pin check. |
| `out` | every step | The output folder. It must be outside the repository that holds the configuration. |
| `robot_jar` | `project` | ROBOT 1.9.10. Its SHA-256 is checked before any command runs (`running.md`, rule 2). |
| `manual_cases` | `load`, optional | Passed to `load_verify.py --manual-cases`. |
| `release_graphs` | `jena`, `databricks`, `rebuild` | The other files of each release that the store copy holds, by name without `.ttl` (for example `["shapes", "catalog"]`): `<name>.ttl` beside each data file, loaded as the graph `<version IRI>/<name>`. |
| `target_env` | `copy` | An env file naming another Neo4j, such as Aura: `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, optional `NEO4J_DATABASE`. |
| `replace_target` | `copy`, optional | `true` passes `--replace` to `copy_graph.py`, which deletes everything on the target first. A rebuild that copies needs it, because the target then holds the first copy. |
| `databricks` | `databricks`, a rebuild from Databricks | `{"env": <file>, "table": <catalog.schema.table>}`; the env file is the one the `rdf-store` skill reads. |
| `queries` | `explore` | The project's saved walks for `explore.py compare`. |
| `rebuild` | `rebuild` | `{"source": "repo" or "jena" or "databricks", "out": <folder>}`. |
| `rdf_store` | `jena`, `databricks`, `explore`, `rebuild` | The `rdf-store` skill folder; by default `../rdf-store` beside this skill. |
| `neo4j`, `jena`, `explore_fuseki`, `triplestore_fuseki` | optional | `{"compose_project", "bolt_port"}` or `{"compose_project", "port"}` for each container. The defaults are `lpg-local` on Bolt 17711, `lpg-jena` on 13031, `lpg-explore` on 13032 and `lpg-triplestore` on 13030. |
| `keep_neo4j` | optional | `true` leaves the local Neo4j running at the end; otherwise it is removed. |
| `keep_jena` | optional | `true` leaves the `jena` step's Fuseki running, loaded, once its round trip has passed; otherwise it is removed. A failed round trip removes it either way. Its dataset is in memory, so a restart empties it: reload it with `--only jena`. A later run starts it afresh. |
| `separator` | `load`, `review`, `tags`, `graph-type`, `copy`, `explore`, `rebuild`, optional | What sits between a prefix and a local name in the kept graph: underscores only, `"_"` for one. n10s writes two; with another value every check runs on n10s's names first, then every label, relationship type and property key is renamed, the rename is proven lossless on a dump of the whole graph or the load fails with no report (`pipeline.md`, rule 11; `rename_lossless` in the report), and the hashes are of the renamed graph. The value is passed as `--separator` to every script that reads or describes the graph (`load_verify.py`, `model_review.py` locally and on the copy, `module_tags.py`, `build.py graph-type`, `explore.py`, and the rebuild's run of each), so the review, the tags, the `GRAPH TYPE` and the walks read the renamed names. A value that is not a string of underscores is refused when the configuration is read, before `--plan` prints anything; under a separator other than n10s's, a prefix that holds the separator, or n10s's own two underscores, is refused by each of those scripts before it loads, queries or writes. `copy_graph.py` takes no separator: it copies the names as they are. |

A step whose key is missing is skipped and says so: no `target_env`, no `copy`; no `databricks`, no Databricks round trip. A step that needs an earlier one's output or the local Neo4j stops with a message when it isn't there. Run `load` in the same run as the steps that read the local graph.

## Files mode

Each file is one named graph. Its name is its `owl:versionIRI` when it has one; else its entry in `graphs`; else `urn:ontology-to-lpg:file:` and its path relative to the run configuration. A `graphs` entry for a file that has an `owl:versionIRI` is refused, so the store and Neo4j always name a file alike. Every store gets each file under that name (`rdfstore.py --graph FILE=IRI`), `module_tags.py --graph` tags each node and relationship with it, and `explore.py --files` reads every graph in the store as a package.

Without `shapes`, the driver writes `default-shapes.ttl` into `out`: one `sh:NodeShape` per class the data types a node with (outside the RDF, RDFS, OWL, SHACL and XSD namespaces), and for each predicate the class's instances use (subclasses' instances included), a property shape with the counts the data shows: `sh:maxCount` the most values one instance has, and `sh:minCount 1` when every instance has one. The inverse ends of the qualified-relation classes the projection configuration registers get a shape on `sh:inversePath`, counted the same way, as Rule 4a requires. The data conforms by construction, and the load's gates (compiled rows, a fail case each, the mutant) have something to check. n10s's defaults decide the rest: a literal becomes a property, an IRI a relationship.

The rule check runs without `--releases`, so version pins and the closure of requirements are not checked. The run says so, and so does `run-manifest.json`.

## The run manifest

The `project` step writes `<out>/run-manifest.json`: the mode, each data and shape file with its SHA-256 (and, in files mode, its graph name and where the name came from), each release's `catalog.ttl` with its SHA-256, whether the shapes were derived, and the notes above. The rebuild refuses to compare with `out` when any of those files has changed, or a catalog has been added or removed, since. `release_record.py` refuses a file whose path and SHA-256 are not in it.

## The steps and their checks

| Step | What runs | It passes when |
|---|---|---|
| `project` | `check_projection_rules.py`, `validate_data.py`, `build.py merge`, ROBOT ELK, `build.py inferred`, `loadable`, `check-serialised`, `validate_data.py` again on both files, `build.py manifest`, then the advisory `in_graph_shapes.py` | every script exits 0: checks V1 to V5 (`multi-store.md`) |
| `load` | Neo4j with n10s from `docker/compose.yaml`, `load_verify.py --compose-project`, `build.py check-report` | the report is written and `check-report` passes: V6 to V12. A failure removes the container. |
| `review` | `model_review.py` on the local graph, written to `model-review.json` | no ERROR finding |
| `tags` | `module_tags.py tag`, `check`, `modules` on the local graph (add-on F) | every node and relationship carries exactly one tag, equal to its package |
| `release-record` | `release_record.py records`, `write` and `check` on the local graph, into `release-records.json` (add-on M). Files mode skips it | one record per module, every field read back, and the graph hash unchanged and equal to the report's |
| `graph-type` | `build.py graph-type` to `graph-type.cypher` (add-on H) | the statement is written; apply it by hand |
| `triplestore` | Fuseki from `docker/compose.yaml`, `triplestore.py` (add-on J) | the per-graph, per-predicate and three-way counts match the report |
| `copy` | `copy_graph.py` to `target_env` (add-on I), then `module_tags.py check` and `modules`, `release_record.py write` and `check` when this load has records, and `model_review.py` there | the target's graph hash equals the source's and the report's, the tags check passes there, the records read back, and no ERROR finding |
| `jena` | the `rdf-store` skill's Fuseki and `rdfstore.py roundtrip` of the data files and their release graphs (files mode: each file under its graph name) | the store's export has the files' RDFC-1.0 hash |
| `databricks` | `rdfstore.py roundtrip --store databricks` of the same dataset (add-on K) | the same, for the Delta table; the table is replaced only by a staging copy with that hash |
| `explore` | a second Fuseki holding the data and `inferred.nt`, then `explore.py compare` against the local graph and, when this run copied, against the target | every saved walk and the module map give the same edges, nodes and tags in Neo4j and in Jena |
| `rebuild` | see below | the store's export hashes equal to the release, the rebuild's triples and graph hashes equal this run's, and its own load, tags, release records, copy and walks pass |

## The rebuild

`rebuild` proves the graph can be rebuilt from a store's copy alone. It needs `project` and `load` to have run into `out` (in this run or an earlier one), with the inputs `run-manifest.json` records, and removes this run's local Neo4j first, because the rebuild loads its own on the same port.

1. With `source` `jena` or `databricks`, it exports everything the store holds (`rdfstore.py export --ttl-dir`), packs the release files the same way the round trip did, and requires equal RDFC-1.0 hashes (`rdfstore.py compare`). A rebuild from Jena loads Jena first when this run hasn't. With `repo`, it takes the repository files.
2. It maps the exported graphs to the inputs. A data file maps to the graph named by its `owl:versionIRI` (in files mode, by its graph name), and a release graph's shapes file to `<version IRI>/<name>`. A shape file that is no release graph, such as a whole-graph shapes file, was never in the store, so it comes from the repository, and the run says which.
3. It runs `project` and `load` into `rebuild.out`, then requires `loadable.nt` and `inferred.nt` to hold the first run's triples, compared as RDF 1.1 terms, and both reports to hold exactly `determinism_hash_sorted` and `determinism_hash_shuffled`, non-empty and equal to the first run's. A store export may write a literal typed `xsd:string` as a plain literal, which RDF 1.1 defines as the same term, so the files need not be byte-equal. The equal graph hashes prove Neo4j holds the same graph.
4. It tags, writes the release records (releases mode), copies when `target_env` is set (with `replace_target`), and explores when `queries` is set.

`run_projection.py compare-triples <rebuild out> <baseline out>` and `compare-reports <rebuild report> <baseline report>` run step 3's two checks on their own.

## What it leaves behind

Every Fuseki is removed when the run ends, pass or fail, except a `jena` Fuseki that `keep_jena` keeps, and the local Neo4j too unless `keep_neo4j` is set. Each removal runs even when another fails. A removal that fails fails the run, even when every step passed, and the run says which; a step's own failure is still the one reported. A copy stays on the target, and a Databricks round trip leaves the table holding the release. To empty them, delete only what the run loaded.
