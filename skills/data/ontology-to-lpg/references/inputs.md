# Inputs: what the projection reads, and the gaps it may carry

Serves the inputs step. Read it before the first projection run, and whenever a module is released, added or given a new namespace. The configuration it describes is `templates/projection-config.json`. `check_projection_rules.py`, `validate_data.py` and `build.py` read it; `in_graph_shapes.py` reads only the shapes.

The configuration's keys:

| Key | What it holds |
|---|---|
| `rule4`, `rule4_reason` | The Rule 4 option (`4a` or `4b`) and why, copied from the projection policy (`design-rules.md`, "Where the Rule 4 choice is recorded"). |
| `own_namespaces` | Every namespace you own whose terms appear as predicates or classes (rule 3). A namespace that holds only individuals may be left out. |
| `prefixes` | One prefix per namespace, in the order the loader adds them (rules 3 and 4). |
| `qualified_relations` | Each qualified-relation class with its `ends` and `inverse_ends` (rule 3). |
| `packages` | Each released module's pinned version (rule 1). |
| `release_exceptions` | Each listed rule gap and its fix (rule 5). |
| `versions` | The tool versions the run used (`running.md`, rule 2). |
| `lpg_name_property` | Optional: the annotation property that carries Rule 5 names. |

Data files and shape files are not in the configuration: pass them to each script on its command line (`--shapes` for shapes), in the same order every time, because the shapes fingerprint depends on the order.

## Rules

1. **Project the released packages, each at its newest version, not the working source files.** Pin each module's version by hand in the configuration (`packages`), and check the pins against the release folder: the check fails when a module has a newer release than its pin, when a module has a release and no pin, and when a pin names a version with no release folder (`check_projection_rules.py --releases <folder>`). The release folder holds one folder per module, and in it one folder per release named by its version: `<folder>/<module>/<X.Y.Z>/`. Only names of the form `X.Y.Z` count as releases, so a candidate folder such as `1.2.0-rc.1` is ignored. For the library example, build the folder from the templates: `mkdir -p releases/lending/1.1.0 && cp templates/library-module.ttl releases/lending/1.1.0/lending.ttl && cp templates/library-shapes.ttl releases/lending/1.1.0/shapes.ttl`, then run the checker with `--releases releases` on `releases/lending/1.1.0/lending.ttl`. Each release folder holds the package the ontology's release step built: the module's Turtle (`<module>.ttl`), its shapes (`shapes.ttl`) and its manifest, with a DCAT record, a changelog and other formats beside them. The projection reads the module Turtle as data and `shapes.ttl` as shapes. *Why:* consumers get what was released, so the projection must test the releases; a pin by hand makes a new release a visible change, and the folder check stops the pin going stale. Where one module was released against an older version of another, the projection still takes each module's newest release; each package's own release checks keep testing the versions it pinned.

2. **Run each package's own shapes, plus every shape that checks the whole graph.** Pass every package's `shapes.ttl` and every whole-graph shape file to each script with `--shapes`; the manifest fingerprints each one (`running.md`, rule 3). *Why:* a package's shapes are part of its release, and a cross-module shape catches a break that no single package's shapes can see.

3. **Apply Rules 1 and 2 to the predicates of every namespace you own whose terms are predicates or classes, and give each its fixed prefix.** List in `own_namespaces` every namespace you own whose terms the data uses as predicates or classes (a namespace that holds only individuals, such as `https://id.example.org/library/work/`, may be left out: no rule checks an individual's namespace), and give it the prefix its package uses where it has one (`prefixes`). Register each qualified-relation class with its ends (`qualified_relations`, `design-rules.md`, rule 4). *Why:* a rule checked on one module lets every later module break it, and a namespace missing from the list is never checked.

4. **Register the standard namespaces too.** Every namespace that a predicate or a class in the data uses (RDF, RDFS, OWL, SKOS, DCMI terms, ORG, PROV-O, DCAT, XSD and any other) needs one prefix in `prefixes`. *Why:* the loader adds exactly these prefixes, in this order, so n10s never invents one.

5. **List each rule gap in a released module as a release exception, with its fix, and fail on an unlisted gap or on a listed gap that no longer occurs.** A gap in a released module (a property with no range, a property with no cardinality shape) can close only in that module's next release, because released packages never change. Only a Rule 1, Rule 2 or Rule 5 failure can be listed. Key each exception by the checker's exact message (a term may be written as a CURIE, as the checker prints it, or as a full IRI, bare or in angle brackets), and say in its fix which release closes it and what that release adds:

   ```json
   "release_exceptions": {
     "Rule 1: lib:shelfmark has no single concrete range":
       "lending 1.0.0 declares no rdfs:range; the next lending release adds rdfs:range xsd:string"
   }
   ```

   *Why:* the list lets the projection run without hiding the gap; failing on a stale entry means the list always describes the releases, so it shrinks as releases close the gaps. A blank node, a missing prefix, a broken qualified relation, a refused value or a stale pin is a data error, not a release gap: the checker fails on it even when it is listed.

6. **When a release closes a gap, remove its exception in the same change that moves the pin.** *Why:* the check fails until both are done, which is the point.
