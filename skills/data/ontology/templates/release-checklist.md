<!-- Copy this list into the release pull request's body, one per release. Each item points to its rule; tick it only when the evidence named is in the PR. -->

# Release checklist: <module> <MAJOR.MINOR.PATCH>

- [ ] **Classified.** Major, minor or patch, by the meaning-change test (`release.md`, rules 3 and 4): <classification and one-line reason>.
- [ ] **Approval recorded.** The approver `release.md` rule 6 names has approved in writing; the manifest quotes the sentence and a test reads it from the answers file (rule 7): <record and answers file>.
- [ ] **Gate met.** The source-correction backlog is settled (`promotion.md`); the build, evidence and consumer-impact scan cite one commit (`release.md`, rule 17): <commit>.
- [ ] **Package builds and verifies.** The builder writes the package and `build_package.py verify` passes in the check script (`release.md`, rules 8 and 9).
- [ ] **Release compared with the one before.** A test reads this package and the previous one: every earlier IRI is still declared, nothing is newly deprecated in a minor or patch, and every deprecated term names its successor. For a first release, which has no earlier package, the test checks only that every deprecated term names its successor (`release.md`, rule 28): <the test>.
- [ ] **Figures pinned by hand.** The module's tests pin its counts, new IRIs and corrected statements, written from the decision (`release.md`, rule 29): <the tests>.
- [ ] **Mechanical checks compared.** `check_taxonomy.py` ran on this package and on the one it replaces: the findings this release fixes are gone, any new finding has a recorded decision, and the rest are unchanged. For a first release, its counts are recorded as the baseline and each finding has a recorded decision (`release.md`, rule 30): <before and after counts, or the baseline, and where they are recorded>.
- [ ] **Shapes pass.** The module's shapes and the whole-graph gate pass over the package's dependency closure: each report conforms (`shacl.md`, rule 7).
- [ ] **Regression passes.** Every competency question passes on the released packages (plus the example graph of a module under `new-module.md`, rule 9), or is partial, parked or waiting by a recorded decision that names what it waits for (the Step 11 gate in `SKILL.md`; `regression.md`, rule 11): <the command and commit that computed the counts>.
- [ ] **Catalog rebuilt.** The combined catalog lists the release and `build_catalog.py verify` passes (`release.md`, rule 19).
- [ ] **Changelog written.** One entry per change: what, why, who approved, classification (`release.md`, rule 18).
- [ ] **Known gaps stated.** The changelog's "Known gaps" section lists each gap with `Reason:` and `Record:`, or says "None."; `scripts/check_changelogs.py` passes (`release.md`, rule 18): <gaps, or none>.
- [ ] **Candidate cut.** The candidate label, `dcterms:issued` and the candidate package are handled as `release.md` rules 14 and 15 say.
- [ ] **Inputs outside Git recorded.** Each file the release read from a folder git ignores is listed by its path relative to the folder, with its SHA-256, in `release-inputs.json` at the archive's root (not in a package's manifest), the folder's path is nowhere, the release validates from its archive alone, and the folder check passes; or no such file (`release.md`, "Inputs kept outside Git").
- [ ] **Check script passes** on the head, and the review ran with every finding fixed or answered (`governance.md`, rules 15 and 20).
- [ ] **Tagged.** With a remote: tag the merge commit `<module>-v<version>` once the PR has merged; until then, records say the tag comes at merge (`release.md`, rule 16). With git and no remote: `build_package.py tag` on the commit that holds the package. With no git: not applicable; the manifest's hashes are the guarantee (`release.md`, "Without a remote").
- [ ] **Stores in step.** Once the release is tagged (with no git, once the approved candidate is cut and rebuilt as the issued release), the drift check reports every store current with that release, or the sync reloaded each one it did not from that release (`release.md`, "Keeping copies in step"): <the check's output>.
