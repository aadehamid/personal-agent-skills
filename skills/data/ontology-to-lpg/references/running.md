# Running the projection: where each step runs, pins, reports and scale

Serves the load step (rule 5, the container) and the running step. Read it before the first load, when setting up the projection in a repository or its CI, and before each rerun. The scripts named here are in this skill's `scripts/`.

## Rules

1. **Split the steps by what they need.** CI runs only what needs no Java and no Docker (each line is `uv run --no-project --with rdflib python3 <script> ...`, with `--with pyshacl` for `validate_data.py`):

   ```bash
   check_projection_rules.py --config <config> --shapes <shapes>... --releases <folder> <data>...
   validate_data.py --config <config> --shapes <shapes>... <data>...
   build.py loadable --output <temporary>/loadable.nt <data>...
   validate_data.py --config <config> --shapes <shapes>... <temporary>/loadable.nt inferred.nt
   build.py manifest --config <config> --shapes <shapes>... --loadable <temporary>/loadable.nt \
     --inferred inferred.nt --output projection-manifest.json --verify <data>...
   build.py check-report --manifest projection-manifest.json --report projection-report.json
   ```

   A workstation runs reason (ROBOT needs Java 11 or later), then load and verify with `load_verify.py` against a Neo4j container (rule 5). *Why:* CI images rarely run Java and Docker together, and the committed report (rule 3) carries the workstation's result into CI.

2. **Pin every tool by version, and every downloaded jar by its SHA-256, and check the checksums before each run.** Record the versions in the configuration's `versions`, which the manifest copies. For the tested versions:

   | Jar | Download URL | SHA-256 |
   |---|---|---|
   | n10s 2025.06.1 | https://github.com/neo4j-labs/neosemantics/releases/download/2025.06.1/neosemantics-2025.06.1.jar | `4c461087e08405c7cb472ecfefc043e9e8ed93628ed74988e4fda1f1bac54b3e` |
   | ROBOT 1.9.10 | https://github.com/ontodev/robot/releases/download/v1.9.10/robot.jar | `16a73c074f3df359a7338a84b4e0788785fe06117f931bb9796e9619ea776105` |

   Check with `shasum -a 256 <jar>`. If a checksum differs, stop: the file is not the one these rules were tested with. Take the n10s jar that matches the Neo4j version (n10s 2025.06.1 is built for Neo4j 2025.06). APOC is not downloaded: with `NEO4J_PLUGINS='["apoc"]'` the image copies the APOC jar it bundles into `/plugins` as `apoc.jar` (for `neo4j:2025.06.2`, SHA-256 `4df40cea7444ea193d08f8a679aa998c498196fe149c8c02badb998f1c9580fb`, from `apoc-2025.06.2-core.jar`). So pin the image instead: record its digest (`docker inspect --format '{{index .RepoDigests 0}}' neo4j:2025.06.2`; on 2026-10-23 it was `sha256:0347fe5b1126dd328cc68a54449c2cf83636e348e2da1547abf62b2dbfad67f2`), and let `load_verify.py --plugins-dir` record every jar's SHA-256 in the report. *Why:* a different jar changes which constraints run in the graph and how values round-trip.

3. **Commit a manifest and a report that go stale on their own.** `build.py manifest` writes the manifest: the SHA-256 of each data and shape file, the triple counts, the input fingerprint (`pipeline.md`, rule 5), the shapes fingerprint (the SHA-256 of every shape file's bytes, concatenated in the order given), the Rule 4 option and its reason, the release exceptions and the versions; with `--verify` it fails when the committed manifest differs. `load_verify.py` writes the report, in the shape of `templates/projection-report.json`. Its fields:

   | Field | Meaning |
   |---|---|
   | `input_fingerprint`, `shapes_fingerprint` | As in the manifest. |
   | `dropped_constraints` | One object per constraint `in_graph_shapes.py` dropped: `{"shape": <IRI or blank-node id>, "constraint": <predicate IRI>, "reason": <text>}`. |
   | `shapes_import_rows`, `in_graph_shape_constraints` | The rows the shapes import returned, and the `listShapes()` count (`pipeline.md`, rule 11). |
   | `shacl_violations_in_graph` | Violations after the load; must be 0. |
   | `fail_cases` | One object per generated case: kind, shape, focus, the Cypher, the expected and the reported components, and whether it passed (`pipeline.md`, rule 14). |
   | `kinds_without_case`, `manual_cases` | Constraint kinds left in the graph, on a property the data uses, with no generated case; and the cases written by hand for them (`pipeline.md`, rule 14). Every listed kind needs a passing manual case. |
   | `mutant`, `in_graph_mutant_violations` | The mutant's focus and property, its violations (must be above 0) and the violations after the restore (must be 0). |
   | `export_rows`, `schema_rows_skipped`, `roundtrip_lost`, `roundtrip_added` | The raw export rows, the schema rows left out, and the triples lost and added; the last two must be 0. |
   | `determinism_hash_sorted`, `determinism_hash_shuffled` | Must be equal (`pipeline.md`, rule 17). |
   | `nodes`, `relationships`, `schema_relationships` | Counts after the sorted load: every `:Resource` node (schema nodes included), every relationship between two `:Resource` nodes, and how many of those are `n4sch__` schema relationships from `onto.import`. To compare data between runs, use `nodes` and `relationships` minus `schema_relationships` (the data relationships); the schema part changes whenever a class or property is added. |
   | `versions`, `plugin_jars_sha256` | The configuration's versions, and each jar's SHA-256 in the plugins folder. |
   | `samples` | Up to ten lost or added triples, five violations and five failed cases. |

   `build.py check-report` fails when the report's fingerprints differ from the manifest's, or when any check in it did not pass; it also fails when a fail case did not fire, when the mutant object is missing, caught nothing or was not restored, or when a kind in `kinds_without_case` has no complete passing manual case (`pipeline.md`, rule 14). The template, with its empty values, fails on purpose. *Why:* a projection result that outlives its inputs is a false pass, and a shape can change while the loaded triples do not.

4. **Commit `inferred.nt`, the manifest and the report together, after one full workstation run.** Keep `loadable.nt`, `merged.ttl` and the downloads out of the repository; they are rebuilt from the Turtle files. *Why:* the three describe one run, and CI compares them with each other.

5. **Run Neo4j in a container bound to localhost, with the pinned plugins, and remove it once `check-report` has passed, or when you stop.** Use the `neo4j:2025.06.2` image (Community edition), mount a plugins folder holding the checked n10s jar at `/plugins` and the import folder at `/import`, let the image install APOC, allow both procedure namespaces, and bind Bolt to `127.0.0.1` on a non-default port, with a password made for this run.

   The plugins folder must be writable: the image changes its owner and writes `apoc.jar` into it, so a read-only mount (`:ro`) stops the container. Make new folders for each run, and copy the checked n10s jar into the plugins folder, so the image never writes into the folder that holds your downloads. Open both folders to other users (`chmod 755`): `mktemp -d` makes a folder only its owner can open, and with it the container exits at once ("Folder /plugins is not accessible for user: neo4j").

   ```bash
   PLUGINS=$(mktemp -d); chmod 755 "$PLUGINS"; cp <downloads>/neosemantics-2025.06.1.jar "$PLUGINS"/
   IMPORT=$(mktemp -d); chmod 755 "$IMPORT"
   PASSWORD=$(openssl rand -hex 12)
   docker run -d --name lpg-projection -p 127.0.0.1:17687:7687 \
     -e NEO4J_AUTH=neo4j/$PASSWORD -e NEO4J_PLUGINS='["apoc"]' \
     -e NEO4J_dbms_security_procedures_unrestricted='apoc.*,n10s.*' \
     -v "$IMPORT":/import -v "$PLUGINS":/plugins neo4j:2025.06.2
   ```

   Then wait for the start, and stop on a failure:

   ```bash
   for i in $(seq 1 60); do
     docker logs lpg-projection 2>&1 | grep -q 'Started.' && break
     [ "$(docker inspect -f '{{.State.Running}}' lpg-projection)" = true ] || { docker logs lpg-projection | tail -20; exit 1; }
     docker logs lpg-projection 2>&1 | grep -q ' ERROR ' && { docker logs lpg-projection | tail -20; exit 1; }
     sleep 3
   done
   docker logs lpg-projection 2>&1 | grep -q 'Started.' || { echo 'Neo4j did not start in 180 seconds'; exit 1; }
   ```

   Then, in this order:
   1. run `load_verify.py` as its docstring shows, with `NEO4J_PASSWORD="$PASSWORD"`, `--bolt bolt://127.0.0.1:17687`, `--import-dir "$IMPORT"`, `--plugins-dir "$PLUGINS"` and the configuration, shape, data, `merged.ttl`, `loadable.nt`, `inferred.nt` and `--report` arguments;
   2. if it lists kinds that still need a case, run a case for each by hand against the same container and add it to the report's `manual_cases` (`pipeline.md`, rule 14). The script writes the key as an empty list, and keeps cases already in the report when a rerun describes the same inputs and shapes;
   3. run `build.py check-report --manifest projection-manifest.json --report projection-report.json`, as in rule 1;
   4. only then `docker rm -f -v lpg-projection` and `unset PASSWORD`. If you stop before `check-report` passes, run the same removal anyway; `docker ps -a` then lists no projection container. The `-v` removes the container's anonymous `/data` and `/logs` volumes; without it each run leaves them behind, and after a few runs Docker's disk fills and Neo4j fails to start ("Database name 'system' is invalid"). *Why:* the load script reads `file:///import/...`; Community edition has one user database, so the determinism check empties it between loads (`pipeline.md`, rule 17); and a forgotten container with a known password is an open database on the workstation.

6. **Change only the loader as the graph grows:**

   | Size | Loader | What changes |
   |---|---|---|
   | Up to about 10M triples | n10s `rdf.import.fetch` | Nothing |
   | About 10M to 1B+ triples | Generate node and relationship CSVs from `loadable.nt` and `inferred.nt` with the same mapping, then `neo4j-admin database import` | Only the load step |
   | Incremental updates | Load each delta with n10s (MERGE by `uri`); delete with `n10s.rdf.delete` | Add a periodic full rebuild and compare hashes |

   *Why:* the mapping rules do not depend on size, so the checks and the verify step stay valid.
