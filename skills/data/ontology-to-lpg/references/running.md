# Running the projection: where each step runs, pins, reports and scale

Serves the load step (rule 5, the container) and the running step. Read it before the first load, when setting up the projection in a repository or its CI, and before each rerun. The scripts named here are in this skill's `scripts/`.

## Rules

1. **Split the steps by what they need.** CI runs only what needs no Java and no Docker:

   ```bash
   check_projection_rules.py --config <config> --shapes <shapes>... --releases <folder> <data>...
   validate_data.py --config <config> --shapes <shapes>... <data>...
   build.py loadable --output <temporary>/loadable.nt <data>...
   validate_data.py --config <config> --shapes <shapes>... <temporary>/loadable.nt inferred.nt
   build.py manifest --config <config> --shapes <shapes>... --loadable <temporary>/loadable.nt \
     --inferred inferred.nt --output projection-manifest.json --verify <data>...
   build.py check-report --manifest projection-manifest.json --report projection-report.json
   ```

   A workstation runs reason (ROBOT needs Java 11 or later), load and verify (a Neo4j container, so Docker). *Why:* CI images rarely run Java and Docker together, and the committed report (rule 3) carries the workstation's result into CI.

2. **Pin every tool by version, and every downloaded jar by its SHA-256, and check the checksums before each run.** Record the versions in the configuration's `versions`, which the manifest copies. For the tested versions:

   | Jar | Download URL | SHA-256 |
   |---|---|---|
   | n10s 2025.06.1 | https://github.com/neo4j-labs/neosemantics/releases/download/2025.06.1/neosemantics-2025.06.1.jar | `4c461087e08405c7cb472ecfefc043e9e8ed93628ed74988e4fda1f1bac54b3e` |
   | ROBOT 1.9.10 | https://github.com/ontodev/robot/releases/download/v1.9.10/robot.jar | `16a73c074f3df359a7338a84b4e0788785fe06117f931bb9796e9619ea776105` |

   Check with `shasum -a 256 <jar>`. If a checksum differs, stop: the file is not the one these rules were tested with. Take the n10s jar that matches the Neo4j version (n10s 2025.06.1 is built for Neo4j 2025.06). The Neo4j image installs APOC itself (rule 5). *Why:* a different jar changes which constraints run in the graph and how values round-trip.

3. **Commit a manifest and a report that go stale on their own.** `build.py manifest` writes the manifest: the SHA-256 of each data and shape file, the triple counts, the input fingerprint (`pipeline.md`, rule 5), the shapes fingerprint (the SHA-256 of every shape file's bytes, concatenated in the order given), the Rule 4 option and its reason, the release exceptions and the versions; with `--verify` it fails when the committed manifest differs. The verify step writes the report, in the shape of `templates/projection-report.json`: both fingerprints, `shapes_import_rows` and `in_graph_shape_constraints` (`pipeline.md`, rule 11), the dropped constraints, the in-graph violation count, the mutant's violation count, the round-trip lost and added counts, both determinism hashes, the node and relationship counts, the versions, and samples of any failure. `build.py check-report` fails when the report's fingerprints differ from the manifest's, or when any check in it did not pass; the template, with its empty values, fails on purpose. *Why:* a projection result that outlives its inputs is a false pass, and a shape can change while the loaded triples do not.

4. **Commit `inferred.nt`, the manifest and the report together, after one full workstation run.** Keep `loadable.nt`, `merged.ttl` and the downloads out of the repository; they are rebuilt from the Turtle files. *Why:* the three describe one run, and CI compares them with each other.

5. **Run Neo4j in a container bound to localhost, with the pinned plugins, and remove it after each run.** Use the `neo4j:2025.06.2` image (Community edition), mount the folder that holds the checked n10s jar at `/plugins` and the import folder at `/import`, let the image install APOC, allow both procedure namespaces, and bind Bolt to `127.0.0.1` on a non-default port, with a password made for this run:

   ```bash
   PASSWORD=$(openssl rand -hex 12)
   docker run -d --name lpg-projection -p 127.0.0.1:17687:7687 \
     -e NEO4J_AUTH=neo4j/$PASSWORD -e NEO4J_PLUGINS='["apoc"]' \
     -e NEO4J_dbms_security_procedures_unrestricted='apoc.*,n10s.*' \
     -v "$IMPORT":/import -v "$PLUGINS":/plugins neo4j:2025.06.2
   ```

   Wait until `docker logs lpg-projection` prints `Started.` After the run, `docker rm -f lpg-projection` and `unset PASSWORD`; `docker ps -a` then lists no projection container. *Why:* the load script reads `file:///import/...`; Community edition has one user database, so the determinism check empties it between loads (`pipeline.md`, rule 17); and a forgotten container with a known password is an open database on the workstation.

6. **Change only the loader as the graph grows:**

   | Size | Loader | What changes |
   |---|---|---|
   | Up to about 10M triples | n10s `rdf.import.fetch` | Nothing |
   | About 10M to 1B+ triples | Generate node and relationship CSVs from `loadable.nt` and `inferred.nt` with the same mapping, then `neo4j-admin database import` | Only the load step |
   | Incremental updates | Load each delta with n10s (MERGE by `uri`); delete with `n10s.rdf.delete` | Add a periodic full rebuild and compare hashes |

   *Why:* the mapping rules do not depend on size, so the checks and the verify step stay valid.
