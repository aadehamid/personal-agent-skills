# No loss: graphs, skolemization, the proof, reading a diff

## Graphs

One release file is one named graph, so a store keeps each module apart and an export says where each triple came from. The graph IRI is the file's owl:versionIRI, the same name the release catalog uses for that version; with no version IRI, the ontology IRI; with no single owl:Ontology header (a shapes or catalog file, say), the name you give with `--graph FILE=IRI`, such as `<version IRI>/shapes`. Two files that would share a graph stop the run: merging them in one graph would hide which file a triple came from.

The exchange format is N-Quads (RDF 1.1 N-Quads, a W3C Recommendation), because its fourth column carries the graph. `pack` writes one sorted N-Quads file; the Delta table is the same four terms as columns.

## Skolemization

A blank node has no name outside its file, so a store renames it and a consumer cannot point at it. Skolemization replaces each blank node with an IRI under `<authority>/.well-known/genid/` (RDF 1.1 Concepts, section 3.5), which marks it as a stand-in for a blank node.

`skolemize` makes the IRIs stable: it canonicalizes the file with RDFC-1.0, which gives every blank node a label that depends only on the graph's shape, and hashes the graph IRI with that label into the genid. The same release always gives the same IRIs; the same shape in another graph gets other IRIs. A released file never changes, so its genids never move. A file that does change can renumber its blank nodes: RDFC-1.0 labels follow the shape of the whole graph.

Skolemize once, beside the release, and give every store the skolemized files when a consumer needs stable IRIs.

## The proof

The no-loss proof is the RDFC-1.0 hash. RDF Dataset Canonicalization (RDFC-1.0, a W3C Recommendation of 21 May 2024) gives every dataset one canonical form, blank nodes included. The script canonicalizes each side with pyoxigraph's implementation, writes each quad in canonical N-Quads form, sorts the lines, and takes the SHA-256 of the text. Equal hashes mean the two datasets are isomorphic: every triple, literal, datatype, language tag and graph came back, and nothing was added.

Counts per graph and per predicate are in the report as a quick look. They are not the proof: a store that rewrites `"plain"` as `"plain "` keeps every count.

RDFC-1.0's worst case is exponential in the number of blank nodes that look alike. Releases built from code rarely come near it; skolemize first if canonicalization runs long.

## Reading a diff

On a failed round trip the report's `diff` lists quads missing from the store's copy (`-`) and extra in it (`+`), first twenty of each, and `graph_counts` gives each graph's count on both sides. Match the pattern to its cause:

- **Extra quads in graphs you did not load:** a stale graph from an earlier load. The round trip clears only the graphs it loads and exports everything, so leftovers fail it on purpose. Empty the store (an in-memory Fuseki: restart it), then run again.
- **One quad missing and one extra with the same subject and predicate:** the store rewrote a value: a literal's lexical form, its datatype or its language tag. Find what the store does to that datatype.
- **Quads missing with no extras:** the store refused part of a load, or the export dropped a term kind. Check the load's HTTP status and the store's log.
- **Blank-node lines on both sides that look alike:** each side is canonicalized on its own, so a changed neighbourhood of a blank node shows as one line out and one in. Skolemize, and the diff becomes exact.
