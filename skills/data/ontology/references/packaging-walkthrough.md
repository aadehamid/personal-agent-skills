# Packaging walk-through: from files to a release

Read it when a user has ontology files and no release packages yet, or asks how to make one. You run an **interview**: one question at a time, each shown with a short example and the reason it is needed, until the answers file is full; then `scripts/build_package.py` packages the release. The rules behind each answer are in `release.md`; this file is the order you ask in and the words you use.

Write every question for the user in plain words (the clear-writing skill). Ask one, wait for the answer, confirm it back in a line, then ask the next. Offer the default when the user has no view.

## Step 1. Offer the choice, with the recommendation

Show this table first, then recommend releases:

| | Releases | Plain RDF files |
|---|---|---|
| Good for | anything more than one person relies on, or that changes over time | a quick trial |
| What you get | proof that a store holds exactly the approved version (every file's SHA-256 is in a manifest); pinned dependencies; old results stay reproducible, because a release never changes | start in minutes; a load can still be proved complete, by hashing the files at load time |
| What it costs | one-time setup per module: a version, a changelog and a manifest, which this interview and `build_package.py` produce | no versions to pin, so loading "the same thing" twice relies on nobody editing the files in between |

Say: "I recommend releases. I'll ask you about a dozen short questions, show an example for each, and then package everything for you."

Done when the user has chosen. Plain files: stop here and point them to the `rdf-store` skill, which loads and proves any RDF files. Releases: go on.

## Step 2. Find out where the project keeps its files

Run `build_package.py git --releases <folder>` and tell the user what it found, in one sentence:

- **No git:** each package's manifest holds the SHA-256 of every file, and that is the whole guarantee. Git is not needed.
- **Git, no remote:** you will also tag each release on this machine, so the release can be checked against its tag later.
- **Git with a remote:** the same, and the tag is pushed once the release is approved and merged (`release.md`, rule 16). You never push without the user's say-so.

Done when the user knows which setup applies and where `releases/` will live.

## Step 3. The interview

Ask these in order. Each answer goes into a copy of `templates/package-answers.yaml` (the filled example for the library skeleton), saved in the project as `release/<module>-<version>.yaml`, such as `release/lending-1.0.0.yaml`. Keep it: `verify` rebuilds the package from the same answers every time the check script runs. Ask the whole set once per module; for a second module, start again at Q1.

**Q1. Module name.** "What short name should this module have? It becomes a folder name and part of the tag." Example: `lending`. Why: the name keys the folder, the file names and the tag `lending-v1.0.0`. Default: the main Turtle file's name, lower-case, words joined by hyphens.

**Q2. Version.** "Which version is this? For a first release that's usually 1.0.0. If it still waits for approval, we make a candidate, 1.0.0-rc.1." Example: `1.0.0`. Why: consumers pin a version, and a candidate can never be mistaken for a release (`release.md`, rules 2 and 14). Default: `1.0.0-rc.1` until someone has approved it, then `1.0.0`. For a later release, classify the change first (`release.md`, rules 3 and 4).

**Q3. The module's IRI.** "What is the module's web address, the IRI in its owl:Ontology line? Versions get added after it." Example: `https://id.example.org/library/lending` gives the version IRI `https://id.example.org/library/lending/1.0.0`. Why: that IRI names the module in every store and every dependency; changing it later changes the module's identity. Default: the subject of the `owl:Ontology` line already in their file. It must be that IRI: the build refuses a source whose `owl:Ontology` names a different one, so change the file first if the IRI should change. The package's catalog record names the catalog as the parent of this IRI plus `catalog`; when the project's modules sit under different parents, set `catalog_iri` in each answers file to one shared IRI, because the combined catalog refuses two (`release.md`, rule 19).

**Q4. Title and one-line description.** "What should the module be called, and what is in it, in one sentence?" Example: "Library lending: lending activities, loan states, and the classes and properties a loan needs." Why: they go on the header and in the catalog record people search. Default: the existing `dcterms:title`, and a sentence drafted from the file for them to correct.

**Q5. Source files.** "Which Turtle files make up this module?" Example: `ontology-skeleton.ttl`. Why: these files, merged, become the module's one Turtle file; anything left out is not released. Default: the Turtle files in their folder that are not shapes. A file in another format converts first (RDF/XML or JSON-LD with rdflib; spreadsheets through `promotion.md`, "From a spreadsheet to triples").

**Q6. Shapes.** "Do you have SHACL shapes that check this module's data? If not, that's fine for now." Example: `shapes-skeleton.ttl`. Why: the package is checked against its shapes before it is written, and projections use them to decide properties versus relationships. Default: none (an empty `shapes.ttl` is written; Step 9's rules say when to add shapes).

**Q7. What it builds on.** "Does this module use terms from another module you have released? Which one, and which version?" Example: "lending 1.0.0 requires core 1.0.0", written `requires: {core: 1.0.0}`. Why: the version is pinned on the header and in the manifest, so the package always loads the same dependency (`release.md`, rules 11 and 12); the build stops if that version is not released yet. Default: none. A dependency that is not released yet gets packaged first.

**Q8. Release date.** "What date should this release carry?" Example: `2026-10-25`. Why: it goes into `dcterms:issued`, and the build never reads the clock, so rebuilding gives the same files. Default: today. A candidate has no date.

**Q9. Rights.** "Under what terms may people use it? A licence that names real licence text, or 'All rights reserved.'" Example: `All rights reserved.` Why: a release states its terms, and an empty licence link claims terms nobody can read (`release.md`, rule 22). Default: whatever the header already says; ask only if it says nothing.

**Q10. What changed.** "In a line or two: what does this release add or change, and why?" Example: "First release of the lending module, a major." Why: the changelog is how a consumer learns what changed without diffing Turtle (`release.md`, rule 18). Default: "First release" for 1.0.0.

**Q11. Known gaps.** "What does this release still not cover that someone might expect? For each gap: why, and where it is recorded. 'None' is a fine answer." Example: "Holds are not modelled. Reason: no holds export exists yet. Record: parked list, trigger 'a holds export'." Why: a consumer reads what the release is not yet fit for in the same place as what changed (`release.md`, rule 18); a gap needs a reason and a record. Default: none.

**Q12. Approval.** "Who approved this release, where is that written down, and what were their exact words?" Example: "The ontology owner, in decisions/0003-lending-release.md: 'Approve lending 1.0.0.'" Why: the manifest quotes the approval, so a release cannot claim one it lacks (`release.md`, rules 6 and 7). Default: none, which makes it a candidate (Q2); come back when it is approved.

Done when every question has an answer the user has confirmed, and the answers file holds them.

## Step 4. Build, show, check

1. Run `build_package.py build release/<module>-<version>.yaml --releases releases`. It refuses a wrong or missing answer with the reason (exit 2): fix that answer with the user and run it again.
2. Show the user what it wrote: the folder tree (`<module>.ttl`, `.jsonld`, `shapes.ttl`, `catalog.ttl`, `CHANGELOG.md`, `manifest.json`) and the manifest's version, dependencies, triple count and approval.
3. Run `build_package.py verify release/<module>-<version>.yaml --releases releases`, and add the same line to the project's check script (`templates/check.sh`, section 3), so a later edit to a source or to the package fails the check.
4. Tag it, by the setup from Step 2, with `build_package.py tag release/<module>-<version>.yaml --releases releases`:
   - **Git, no remote:** once the package and its answers file are committed. It tags `<module>-v<version>` on the commit that holds the package.
   - **Git with a remote:** only after the release has merged (`release.md`, rule 16). Before that, `tag` refuses and says to wait. After the merge it tags the commit that brought the package in and says whether the remote holds the tag; pushing the tag is the user's call.
   - **No git:** nothing to tag; the manifest is the guarantee.
5. Build the combined catalog of every package (`release.md`, rule 19): ask the user for the catalog's title and one-sentence description, run `build_catalog.py build --releases releases --title "<title>" --description "<sentence>"`, and add its `verify` line to the check script (`templates/check.sh`, section 3). Repeat the build after each later package.

Done when the package passes `build` and `verify`, the user has seen its manifest, the combined catalog lists it and passes `verify`, and (with git) it is tagged, or, with a remote, the user knows to tag it after the merge.
