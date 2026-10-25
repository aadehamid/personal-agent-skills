# No loss: graphs, skolemization, the proof, reading a diff

## Graphs

One release file is one named graph, so a store keeps each module apart and an export says where each triple came from. For a Turtle or N-Triples file the graph IRI is the file's owl:versionIRI (exactly one distinct value; two different ones stop the run), the same name the release catalog uses for that version; with no version IRI, the ontology IRI; with no single owl:Ontology header (a shapes or catalog file, say), the name you give with `--graph FILE=IRI`, such as `<version IRI>/shapes`. A `--graph` must name one of the input files. An N-Quads file keeps the graph names it carries and takes no `--graph`. Two files that would write one graph stop the run: merging them would hide which file a triple came from.

Every quad has a named graph. A default-graph quad in an N-Quads input stops the run, because the round trip publishes named graphs only and reads the store's default graph back as extra: anything there fails the comparison.

Blank nodes are standardized apart: each input file, and each graph a Graph Store Protocol store returns, is its own document, so `_:b0` in two of them means two nodes. The script renames every blank node into its file's own scope before it builds the dataset.

The exchange format is N-Quads (RDF 1.1 N-Quads, a W3C Recommendation), because its fourth term carries the graph. `pack` and `export` write sorted N-Quads; the Delta table is the same four terms as columns.

## Skolemization

A blank node has no name outside its file, so a store renames it and a consumer cannot point at it. Skolemization replaces each blank node with an IRI under `<authority>/.well-known/genid/` (RDF 1.1 Concepts, section 3.5), which marks it as a stand-in for a blank node.

`skolemize` makes the IRIs stable: it canonicalizes the file with RDFC-1.0, which gives every blank node a label that depends only on the graph's shape, and hashes the graph IRI with that label into the genid. The same release always gives the same IRIs; the same shape in another graph gets other IRIs. It refuses a genid the file already uses as an IRI in any position, a literal's datatype included, so a blank node never merges with a named resource. It also refuses what the stores refuse (RDF 1.2 triple terms and literals with a base direction), so a file it accepts is one the round trip accepts. A released file never changes, so its genids never move. A file that does change can renumber its blank nodes: RDFC-1.0 labels follow the shape of the whole graph.

Skolemize once, beside the release, and give every store the skolemized files when a consumer needs stable IRIs. `skolemize` writes `<out>/<file name>` and refuses an output that is one of its inputs or that two inputs would share.

## The proof

The no-loss proof is the RDFC-1.0 hash. RDF Dataset Canonicalization (RDFC-1.0, a W3C Recommendation of 21 May 2024) gives every dataset one canonical form, blank nodes included. The script canonicalizes each side once with pyoxigraph's implementation, writes each quad in canonical N-Quads form, sorts the lines, and takes the SHA-256 of the text. Equal hashes mean the two datasets are isomorphic: every triple, literal, datatype, language tag and graph came back, and nothing was added.

Counts per graph and per predicate are in the report as a quick look. They are not the proof: a store that rewrites `"plain"` as `"plain "` keeps every count.

RDFC-1.0's worst case is exponential in the number of blank nodes that cannot be told apart by their surroundings. Skolemizing does not avoid it, since `skolemize` canonicalizes too. A release built from code rarely comes near it; if canonicalization runs long, give those nodes IRIs in the build itself.

## Reading a diff

On a failed comparison the report's `diff` lists quads missing from the store's copy (`-`) and extra in it (`+`), first twenty of each, with the totals in `missing` and `extra`, and `graph_counts` gives each graph's count on both sides. Match the pattern to its cause:

- **Extra quads in graphs you did not load, or in `(default graph)`:** stale content from an earlier load. Empty the store (an in-memory Fuseki: restart it), then run again.
- **One quad missing and one extra with the same subject and predicate:** the store rewrote a value: a literal's lexical form, its datatype, its language tag, or an IRI turned into a literal. Find what the store does to that term.
- **Quads missing with no extras:** the store refused part of a load, or the export dropped a term kind. Check the store's log.
- **Blank-node lines on both sides that look alike:** each side is canonicalized on its own, so a changed neighbourhood of a blank node shows as one line out and one in. Skolemize, and the diff becomes exact.

For Databricks, a report with `"published": false` means the staging copy already differed and the live table was left as it was.
