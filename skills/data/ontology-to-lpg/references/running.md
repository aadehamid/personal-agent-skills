# Running the projection: where each step runs, pins, reports and scale

Serves the load step (rule 5, the container) and the running step. Read it before the first load, when setting up the projection in a repository or its CI, and before each rerun. The scripts named here are in this skill's `scripts/`.

## Rules

1. **Split the steps by what they need.** CI runs only what needs no Java and no Docker (each line is `uv run --no-project --with rdflib python3 <script> ...`, with `--with pyshacl` for `validate_data.py`):

   ```bash
   check_projection_rules.py --config <config> --shapes <shapes>... --releases <folder> <data>...
   validate_data.py --config <config> --shapes <shapes>... <data>...
   build.py loadable --output <temporary>/loadable.nt <data>...
   build.py check-serialised --loadable <temporary>/loadable.nt --inferred inferred.nt
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
   | `kinds_without_case`, `manual_cases` | Constraint kinds left in the graph (on a property the data uses, a closed shape, or a node-level `sh:class`, listed as `nodeClass`; a kind on a `sh:targetQuery` shape carries the suffix ` (sh:targetQuery)`) with no generated case; and the cases written by hand for them (`pipeline.md`, rule 14). Every listed kind needs a passing manual case that reports one of the kind's components (`EXPECTED` in `build.py`). |
   | `mutant`, `in_graph_mutant_violations` | The mutant's focus and property, its violations (must be above 0) and the violations after the restore (must be 0). |
   | `export_rows`, `schema_rows_skipped`, `roundtrip_lost`, `roundtrip_added` | The raw export rows, the schema rows left out, and the triples lost and added; the last two must be 0. |
   | `determinism_hash_sorted`, `determinism_hash_shuffled` | Must be equal (`pipeline.md`, rule 17). |
   | `nodes`, `relationships`, `schema_relationships` | Counts after the sorted load: every `:Resource` node (schema nodes included), every relationship between two `:Resource` nodes, and how many of those are `n4sch__` schema relationships from `onto.import`. To compare data between runs, use `nodes` and `relationships` minus `schema_relationships` (the data relationships); the schema part changes whenever a class or property is added. |
   | `versions`, `plugin_jars_sha256` | The configuration's versions, and each jar's SHA-256 in the plugins folder. |
   | `samples` | Up to ten lost or added triples, five violations and five failed cases. |

   `build.py check-report` fails when the report's fingerprints differ from the manifest's, or when any check in it did not pass; it also fails when a fail case did not fire, when the mutant object is missing, caught nothing or was not restored, when the report has no `kinds_without_case` list, when a listed kind has no complete passing manual case that reports one of its components (`pipeline.md`, rule 14), or when the report carries an `invalidated` field (a report `load_verify.py` set aside). The template, with its empty values, fails on purpose. *Why:* a projection result that outlives its inputs is a false pass, and a shape can change while the loaded triples do not.

4. **Commit `inferred.nt`, the manifest and the report together, after one full workstation run.** Keep `loadable.nt`, `merged.ttl` and the downloads out of the repository; they are rebuilt from the Turtle files. *Why:* the three describe one run, and CI compares them with each other.

5. **Run Neo4j in a container bound to localhost, with the pinned plugins, and remove it once `check-report` has passed, or when you stop.** Use the `neo4j:2025.06.2` image (Community edition), mount a plugins folder holding the checked n10s jar at `/plugins` and the import folder at `/import`, let the image install APOC, allow both procedure namespaces, and bind Bolt to `127.0.0.1` on a non-default port, with a password made for this run.

   The plugins folder must be writable: the image changes its owner and writes `apoc.jar` into it, so a read-only mount (`:ro`) stops the container. Make new folders for each run, and copy the checked n10s jar into the plugins folder, so the image never writes into the folder that holds your downloads.

   Agent tools often start a fresh shell for every command, so keep the run's settings in a file, not in shell variables: a mode-600 `run.env` in a new run folder, read at the start of each later command and deleted with the folder after removal. Pick a container name and a free host port for this run; the examples use `lpg-projection` and 17687.

   ```bash
   RUN=$(mktemp -d); chmod 711 "$RUN"; echo "$RUN"          # note this path; every later command starts from it
   mkdir -m 755 "$RUN/plugins" "$RUN/import"
   cp <downloads>/neosemantics-2025.06.1.jar "$RUN/plugins/"
   ( umask 077; printf 'CONTAINER=%q\nPORT=%q\nPASSWORD=%q\nRUN=%q\n' lpg-projection 17687 "$(openssl rand -hex 12)" "$RUN" > "$RUN/run.env" )
   . "$RUN/run.env"
   docker run -d --name "$CONTAINER" -p "127.0.0.1:$PORT:7687" \
     -e NEO4J_AUTH="neo4j/$PASSWORD" -e NEO4J_PLUGINS='["apoc"]' \
     -e NEO4J_dbms_security_procedures_unrestricted='apoc.*,n10s.*' \
     -v "$RUN/import":/import -v "$RUN/plugins":/plugins neo4j:2025.06.2
   ```

   The `chmod 711` on the run folder and `755` on the two mounted folders matter: a folder only its owner can open (what `mktemp -d` makes) stops the container at once ("Folder /plugins is not accessible for user: neo4j"), while `run.env` itself stays readable by you alone.

   Then wait for the start, and stop on a failure. The check is a function that returns, so a failure ends the command and not your shell:

   ```bash
   . "<run folder>/run.env"
   wait_for_neo4j() {
     for i in $(seq 1 60); do
       docker logs "$CONTAINER" 2>&1 | grep -q 'Started.' && return 0
       [ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER")" = true ] || { docker logs "$CONTAINER" 2>&1 | tail -20; return 1; }
       docker logs "$CONTAINER" 2>&1 | grep -q ' ERROR ' && { docker logs "$CONTAINER" 2>&1 | tail -20; return 1; }
       sleep 3
     done
     echo 'Neo4j did not start in 180 seconds'; return 1
   }
   wait_for_neo4j
   ```

   Then, in this order, each command starting with `. "<run folder>/run.env"`:
   1. run `load_verify.py` as its docstring shows, with `NEO4J_PASSWORD="$PASSWORD"`, `--bolt "bolt://127.0.0.1:$PORT"`, `--import-dir "$RUN/import"`, `--plugins-dir "$RUN/plugins"`, `--container "$CONTAINER"` and the configuration, shape, data, `merged.ttl`, `loadable.nt`, `inferred.nt` and `--report` arguments. It prints its next step with that container name;
   2. if it lists kinds that still need a case, run a case for each by hand against the same container and add it to the report's `manual_cases` (`pipeline.md`, rule 14). Each case must report one of its kind's components (`EXPECTED` in `build.py`). The script writes the key as an empty list, and keeps cases already in the report only when a rerun has the same input and shapes fingerprints and the same, non-empty, tool versions and plugin jar checksums (a run without `--plugins-dir` carries nothing). If `load_verify.py` exits 1 or 2, stop here, do not run `check-report`, and go to step 4. What it leaves: on exit 2 because the existing report is not valid JSON, that file stays as it is; on any other exit 2, and on a run that fails, a previous report is moved to `<report>.previous` with an `invalidated` field, which `check-report` rejects; on exit 1 because a verify check failed, the report at `--report` holds the failing values, which `check-report` also rejects;
   3. run `build.py check-report --manifest projection-manifest.json --report projection-report.json`, as in rule 1;
   4. only then `docker rm -f -v "$CONTAINER"`, then delete the run folder with its `run.env`. If you stop before `check-report` passes, do the same anyway; `docker ps -a` then lists no projection container. The `-v` removes the container's anonymous `/data` and `/logs` volumes; without it each run leaves them behind, and after a few runs Docker's disk fills and Neo4j fails to start ("Database name 'system' is invalid"). *Why:* the load script reads `file:///import/...`; Community edition has one user database, so the determinism check empties it between loads (`pipeline.md`, rule 17); and a forgotten container with a known password is an open database on the workstation.

6. **Change only the loader as the graph grows:**

   | Size | Loader | What changes |
   |---|---|---|
   | Up to about 10M triples | n10s `rdf.import.fetch` | Nothing |
   | About 10M to 1B+ triples | Generate node and relationship CSVs from `loadable.nt` and `inferred.nt` with the same mapping, then `neo4j-admin database import` | Only the load step |
   | Incremental updates | Load each delta with n10s (MERGE by `uri`); delete with `n10s.rdf.delete` | Add a periodic full rebuild and compare hashes |

   *Why:* the mapping rules do not depend on size, so the checks and the verify step stay valid.
