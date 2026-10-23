# Running the projection: where each step runs, pins, reports and scale

Serves the running step. Read it when setting up the projection in a repository, its CI or a workstation, and before each rerun.

## Rules

1. **Split the steps by what they need.** CI runs check and serialise, which need only an RDF library and a SHACL engine, as one command (for example `pipeline.py build --verify`), and checks that the committed report matches the current inputs and passed. A workstation runs reason (ROBOT needs Java 11 or later), load and verify (they need a Neo4j container, so Docker). *Why:* CI images rarely run Java and Docker together, and the committed report (rule 3) carries the workstation's result into CI.

2. **Pin every tool by version, and every downloaded jar by its SHA-256, and check the checksums before each run.** Record the Neo4j, n10s, APOC and ROBOT versions in the manifest, and each jar's download URL and SHA-256 in the projection's README. Take the n10s jar that matches the Neo4j version from the neosemantics releases (for Neo4j 2025.06, `neosemantics-2025.06.1.jar`) and mount it as the container's `/plugins` folder; the Neo4j image installs APOC itself through `NEO4J_PLUGINS='["apoc"]'`; allow both with `NEO4J_dbms_security_procedures_unrestricted='apoc.*,n10s.*'`. If a checksum differs, stop. *Why:* a different jar changes which constraints run in the graph and how values round-trip.

3. **Commit a manifest and a report that go stale on their own.** The manifest records the SHA-256 of each input and shape file, the triple counts, the input fingerprint (`pipeline.md`, rule 5), the Rule 4 choice, the release exceptions and the pinned versions. The verify step writes the report: the input fingerprint, a fingerprint over every shape file, the in-graph violation count, the mutant's violation count, the constraints loaded, the round-trip lost and added counts, both determinism hashes, the node and relationship counts, and samples of any failure. CI rebuilds the manifest and fails when it differs from the committed one, and fails when the report's two fingerprints differ from the current inputs and shapes, or when the report did not pass. Test that editing one shape file changes the shapes fingerprint. *Why:* a projection result that outlives its inputs is a false pass, and a shape can change while the loaded triples do not.

4. **Commit `inferred.nt`, the manifest and the report together, after a full workstation run.** Keep `loadable.nt` and the downloads out of the repository; they are rebuilt from the Turtle files. *Why:* the three describe one run, and CI compares them with each other.

5. **Remove the container and any temporary database password after each run.** Bind the container's Bolt port to a non-default port on localhost. *Why:* a forgotten container with a known password is an open database on the workstation.

6. **Change only the loader as the graph grows:**

   | Size | Loader | What changes |
   |---|---|---|
   | Up to about 10M triples | n10s `rdf.import.fetch` | Nothing |
   | About 10M to 1B+ triples | Generate node and relationship CSVs from `loadable.nt` and `inferred.nt` with the same mapping, then `neo4j-admin database import` | Only the load step |
   | Incremental updates | Load each delta with n10s (MERGE by `uri`); delete with `n10s.rdf.delete` | Add a periodic full rebuild and compare hashes |

   *Why:* the mapping rules do not depend on size, so the checks and the verify step stay valid.
