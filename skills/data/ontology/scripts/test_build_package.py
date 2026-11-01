"""Tests for build_package.py.

Run from this folder:
  uv run --no-project --with rdflib --with pyyaml --with pyshacl python3 -m unittest test_build_package

The library skeleton is packaged from templates/package-answers.yaml; each one-break test changes one answer
or one file and expects the named refusal. The git tests make throwaway repositories (no git, local git, and
local git with a bare remote) with GIT_* cleared, so they never touch the repository they run in.
"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest

import yaml

import build_package

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = os.path.join(HERE, "..", "templates")
ANSWERS = os.path.join(TEMPLATES, "package-answers.yaml")
CLEAN_ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
CORE_TTL = """@prefix owl: <http://www.w3.org/2002/07/owl#> .
<https://id.example.org/library/core> a owl:Ontology .
<https://id.example.org/library/Thing> a owl:Class .
"""


def run(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = build_package.main(argv)
    return code, out.getvalue()


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, env=CLEAN_ENV, capture_output=True, text=True, check=True)


class Workspace(unittest.TestCase):
    """A temporary project: the skeleton files, an answers file next to them, and a releases folder."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        self.saved_env = dict(os.environ)
        for k in [k for k in os.environ if k.startswith("GIT_")]:
            del os.environ[k]
        self.addCleanup(os.environ.update, self.saved_env)
        for name in ("ontology-skeleton.ttl", "shapes-skeleton.ttl"):
            shutil.copy(os.path.join(TEMPLATES, name), self.root)
        with open(ANSWERS, encoding="utf-8") as f:
            self.answers = yaml.safe_load(f)
        self.releases = os.path.join(self.root, "releases")

    def write_answers(self, **changes):
        answers = dict(self.answers)
        for key, value in changes.items():
            if value is None:
                answers.pop(key, None)
            else:
                answers[key] = value
        path = os.path.join(self.root, "answers.yaml")
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(answers, f, sort_keys=False)
        return path

    def build(self, **changes):
        return run(["build", self.write_answers(**changes), "--releases", self.releases])

    def manifest(self, module="lending", version="1.0.0"):
        with open(os.path.join(self.releases, module, version, "manifest.json"), encoding="utf-8") as f:
            return json.load(f)

    def release_core(self):
        with open(os.path.join(self.root, "core.ttl"), "w", encoding="utf-8") as f:
            f.write(CORE_TTL)
        path = os.path.join(self.root, "core-answers.yaml")
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump({"module": "core", "version": "1.0.0", "ontology_iri": "https://id.example.org/library/core",
                            "title": "Library core", "description": "The core classes.", "sources": ["core.ttl"],
                            "issued": "2026-10-20", "changes": ["First release, a major."], "known_gaps": "none",
                            "approval": {"who": "The ontology owner", "recorded_in": "decisions/0001.md",
                                         "words": "Approve core 1.0.0."}}, f)
        code, out = run(["build", path, "--releases", self.releases])
        self.assertEqual(code, 0, out)


class Build(Workspace):
    def test_the_library_package_matches_its_expected_manifest(self):
        code, out = self.build()
        self.assertEqual(code, 0, out)
        m = self.manifest()
        self.assertEqual({k: m[k] for k in ("module", "version", "release_candidate", "ontology_iri", "version_iri",
                                            "issued", "depends_on", "triples")},
                         {"module": "lending", "version": "1.0.0", "release_candidate": False,
                          "ontology_iri": "https://id.example.org/library/lending",
                          "version_iri": "https://id.example.org/library/lending/1.0.0",
                          "issued": "2026-10-25", "depends_on": {}, "triples": 97})
        self.assertEqual(sorted(m["files"]), ["CHANGELOG.md", "catalog.ttl", "lending.jsonld", "lending.ttl", "shapes.ttl"])
        self.assertEqual(m["approved_by"], {"who": "The ontology owner", "recorded_in": "decisions/0003-lending-release.md",
                                            "words": "Approve lending 1.0.0."})
        self.assertEqual(sorted(os.listdir(os.path.join(self.releases, "lending"))), ["1.0.0"])  # no staging left

    def test_two_builds_are_byte_identical(self):
        self.assertEqual(self.build()[0], 0)
        first = self.manifest()["files"]
        shutil.rmtree(self.releases)
        self.assertEqual(self.build()[0], 0)
        self.assertEqual(self.manifest()["files"], first)

    def test_the_header_is_set_from_the_answers(self):
        self.build()
        with open(os.path.join(self.releases, "lending", "1.0.0", "lending.ttl"), encoding="utf-8") as f:
            ttl = f.read()
        self.assertIn('owl:versionInfo "1.0.0"', ttl)
        self.assertNotIn("0.1.0-rc.1", ttl)          # the skeleton's own draft version is replaced
        self.assertIn('dcterms:issued "2026-10-25"^^xsd:date', ttl)

    def test_a_changed_source_fails_verify(self):
        path = self.write_answers()
        self.assertEqual(run(["build", path, "--releases", self.releases])[0], 0)
        self.assertEqual(run(["verify", path, "--releases", self.releases])[0], 0)
        with open(os.path.join(self.root, "ontology-skeleton.ttl"), "a", encoding="utf-8") as f:
            f.write('\nlib:lending skos:editorialNote "changed after release"@en .\n')
        code, out = run(["verify", path, "--releases", self.releases])
        self.assertEqual(code, 1)
        self.assertIn("lending.ttl differs from a fresh build", out)

    def test_a_hand_edit_to_the_package_fails_verify(self):
        path = self.write_answers()
        run(["build", path, "--releases", self.releases])
        with open(os.path.join(self.releases, "lending", "1.0.0", "CHANGELOG.md"), "a", encoding="utf-8") as f:
            f.write("edited\n")
        code, out = run(["verify", path, "--releases", self.releases])
        self.assertEqual(code, 1)
        self.assertIn("CHANGELOG.md differs from a fresh build", out)

    def test_a_crlf_edit_to_the_package_fails_verify(self):
        path = self.write_answers()
        run(["build", path, "--releases", self.releases])
        ttl = os.path.join(self.releases, "lending", "1.0.0", "lending.ttl")
        with open(ttl, "rb") as f:
            text = f.read()
        with open(ttl, "wb") as f:
            f.write(text.replace(b"\n", b"\r\n"))
        code, out = run(["verify", path, "--releases", self.releases])
        self.assertEqual(code, 1)
        self.assertIn("lending.ttl differs from a fresh build", out)

    def test_a_released_package_is_never_overwritten(self):
        self.assertEqual(self.build()[0], 0)
        before = self.manifest()
        code, out = self.build(description="Something else.")
        self.assertEqual(code, 2)
        self.assertIn("already released", out)
        self.assertEqual(self.manifest(), before)

    def test_known_gaps_must_be_stated(self):
        code, out = self.build(known_gaps=None)
        self.assertEqual(code, 2)
        self.assertIn("known_gaps", out)
        code, out = self.build(known_gaps=[{"gap": "Holds", "reason": "no export", "record": ""}])
        self.assertEqual(code, 2)
        self.assertIn("every known gap needs a record", out)
        self.assertFalse(os.path.exists(os.path.join(self.releases, "lending")))

    def test_none_is_a_known_gaps_answer(self):
        code, out = self.build(known_gaps="none")
        self.assertEqual(code, 0, out)
        with open(os.path.join(self.releases, "lending", "1.0.0", "CHANGELOG.md"), encoding="utf-8") as f:
            self.assertIn("### Known gaps\n\nNone.\n", f.read())

    def test_a_dependency_on_an_unreleased_version_fails(self):
        code, out = self.build(requires={"core": "1.0.0"})
        self.assertEqual(code, 2)
        self.assertIn("requires core 1.0.0, which is not released", out)
        self.assertFalse(os.path.exists(os.path.join(self.releases, "lending")))

    def test_a_released_dependency_is_named_on_the_header_and_in_the_manifest(self):
        self.release_core()
        code, out = self.build(requires={"core": "1.0.0"})
        self.assertEqual(code, 0, out)
        self.assertEqual(self.manifest()["depends_on"], {"core": "1.0.0"})
        with open(os.path.join(self.releases, "lending", "1.0.0", "lending.ttl"), encoding="utf-8") as f:
            self.assertIn("dcterms:requires <https://id.example.org/library/core/1.0.0>", f.read())

    def test_a_candidate_has_no_issued_date_and_no_approval(self):
        code, out = self.build(version="1.0.0-rc.1", issued=None, approval=None)
        self.assertEqual(code, 0, out)
        m = self.manifest(version="1.0.0-rc.1")
        self.assertEqual((m["release_candidate"], m["issued"], m["approved_by"]), (True, None, None))
        code, out = self.build(version="1.0.0-rc.2", approval=None)
        self.assertEqual(code, 2)
        self.assertIn("a candidate has no issued date", out)

    def test_a_release_needs_its_approval_and_date(self):
        code, out = self.build(approval=None)
        self.assertEqual(code, 2)
        self.assertIn("a release needs approval", out)
        code, out = self.build(issued=None)
        self.assertEqual(code, 2)
        self.assertIn("a release needs issued", out)

    def test_an_iri_other_than_the_sources_ontology_is_refused(self):
        code, out = self.build(ontology_iri="https://id.example.org/library/other")
        self.assertEqual(code, 2)
        self.assertIn("the sources declare the ontology https://id.example.org/library/lending", out)
        self.assertFalse(os.path.exists(os.path.join(self.releases, "lending")))

    def test_another_subject_with_a_version_iri_is_refused(self):
        with open(os.path.join(self.root, "ontology-skeleton.ttl"), "a", encoding="utf-8") as f:
            f.write("\nlib:stray owl:versionIRI <https://id.example.org/library/stray/1.0.0> .\n")
        code, out = self.build()
        self.assertEqual(code, 2)
        self.assertIn("https://id.example.org/library/stray", out)

    def test_an_import_is_refused(self):
        with open(os.path.join(self.root, "ontology-skeleton.ttl"), "a", encoding="utf-8") as f:
            f.write("\nlib:lending owl:imports <https://id.example.org/library/core/1.0.0> .\n")
        code, out = self.build()
        self.assertEqual(code, 2)
        self.assertIn("owl:imports", out)

    def test_a_checker_that_raises_leaves_nothing_behind(self):
        real = build_package.check_packages.check_package
        def boom(*args):
            raise OSError("unreadable")
        build_package.check_packages.check_package = boom
        try:
            with self.assertRaises(OSError):
                build_package.write(build_package.read_answers(self.write_answers()), self.releases)
        finally:
            build_package.check_packages.check_package = real
        self.assertFalse(os.path.exists(os.path.join(self.releases, "lending")))

    def test_a_package_that_breaks_its_shapes_is_not_left_behind(self):
        with open(os.path.join(self.root, "ontology-skeleton.ttl"), "a", encoding="utf-8") as f:
            f.write("\nlib:loan-1 a lib:Loan .\n")   # a loan with no borrower breaks LoanShape-borrower
        code, out = self.build()
        self.assertEqual(code, 1)
        self.assertIn("FAIL lending 1.0.0", out)
        self.assertFalse(os.path.exists(os.path.join(self.releases, "lending", "1.0.0")))


class Git(Workspace):
    def test_a_malformed_branch_head_from_the_remote_is_refused_cleanly(self):
        git("init", "-q", cwd=self.root)
        git("remote", "add", "origin", "unused", cwd=self.root)
        path = self.write_answers()
        run(["build", path, "--releases", self.releases])
        self.commit_all()
        real = build_package.git
        def fake(*args, cwd):
            if args[:2] == ("ls-remote", "--symref"):
                return subprocess.CompletedProcess(args, 0, "ref: refs/heads/main\tHEAD\n", "")
            if args[0] == "ls-remote":
                return subprocess.CompletedProcess(args, 0, "refs/heads/main\n", "")   # no SHA
            if args[0] == "fetch":
                return subprocess.CompletedProcess(args, 0, "", "")
            return real(*args, cwd=cwd)
        build_package.git = fake
        try:
            code, out = run(["tag", path, "--releases", self.releases])
        finally:
            build_package.git = real
        self.assertEqual(code, 1)
        self.assertIn("is not on origin's default branch yet", out)

    def commit_all(self):
        git("add", "-A", cwd=self.root)
        git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "release", cwd=self.root)

    def test_without_git_the_manifest_is_the_guarantee(self):
        path = self.write_answers()
        code, out = run(["build", path, "--releases", self.releases])
        self.assertEqual(code, 0, out)
        self.assertIn("no git", out)
        code, out = run(["tag", path, "--releases", self.releases])
        self.assertEqual(code, 2)
        self.assertIn("not a git repository", out)

    def test_local_git_tags_the_committed_package_and_verify_compares_the_tag(self):
        git("init", "-q", cwd=self.root)
        path = self.write_answers()
        code, out = run(["build", path, "--releases", self.releases])
        self.assertIn("git with no remote", out)
        code, out = run(["tag", path, "--releases", self.releases])
        self.assertEqual(code, 1)
        self.assertIn("commit the package first", out)
        self.commit_all()
        code, out = run(["tag", path, "--releases", self.releases])
        self.assertEqual(code, 0, out)
        self.assertIn("the commit that holds the package (local)", out)
        self.assertEqual(run(["verify", path, "--releases", self.releases])[0], 0)
        # Rewrite the package and its sources the same way: a fresh build agrees, the tag does not.
        shutil.rmtree(os.path.join(self.releases, "lending", "1.0.0"))
        with open(os.path.join(self.root, "ontology-skeleton.ttl"), "a", encoding="utf-8") as f:
            f.write('\nlib:lending skos:editorialNote "rewritten"@en .\n')
        self.assertEqual(run(["build", path, "--releases", self.releases])[0], 0)
        code, out = run(["verify", path, "--releases", self.releases])
        self.assertEqual(code, 1)
        self.assertIn("lending.ttl differs from the copy tagged lending-v1.0.0", out)

    def test_verify_finds_a_tagged_copy_that_differs_only_in_line_endings(self):
        git("init", "-q", cwd=self.root)
        git("config", "core.autocrlf", "false", cwd=self.root)
        path = self.write_answers()
        self.assertEqual(run(["build", path, "--releases", self.releases])[0], 0)
        ttl = os.path.join(self.releases, "lending", "1.0.0", "lending.ttl")
        with open(ttl, "rb") as f:
            lf = f.read()
        with open(ttl, "wb") as f:
            f.write(lf.replace(b"\n", b"\r\n"))
        self.commit_all()
        self.assertEqual(run(["tag", path, "--releases", self.releases])[0], 0)
        with open(ttl, "wb") as f:  # the working file now equals a fresh build; only the tag's copy differs
            f.write(lf)
        code, out = run(["verify", path, "--releases", self.releases])
        self.assertEqual(code, 1)
        self.assertIn("lending.ttl differs from the copy tagged lending-v1.0.0", out)
        self.assertNotIn("differs from a fresh build", out)

    def test_the_tag_goes_on_the_package_commit_not_a_later_one(self):
        git("init", "-q", cwd=self.root)
        path = self.write_answers()
        self.assertEqual(run(["build", path, "--releases", self.releases])[0], 0)
        self.commit_all()
        package_commit = git("rev-parse", "HEAD", cwd=self.root).stdout.strip()
        with open(os.path.join(self.root, "notes.txt"), "w", encoding="utf-8") as f:
            f.write("an unrelated change\n")
        self.commit_all()
        code, out = run(["tag", path, "--releases", self.releases])
        self.assertEqual(code, 0, out)
        self.assertEqual(git("rev-list", "-n", "1", "lending-v1.0.0", cwd=self.root).stdout.strip(), package_commit)

    def test_with_a_remote_the_tag_goes_on_the_merge_commit(self):
        bare = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, bare)
        git("init", "-q", "--bare", "-b", "main", cwd=bare)
        git("init", "-q", "-b", "main", cwd=self.root)
        git("remote", "add", "origin", bare, cwd=self.root)
        with open(os.path.join(self.root, "README"), "w", encoding="utf-8") as f:
            f.write("project\n")
        self.commit_all()
        git("checkout", "-q", "-b", "release", cwd=self.root)
        path = self.write_answers()
        self.assertEqual(run(["build", path, "--releases", self.releases])[0], 0)
        self.commit_all()
        git("checkout", "-q", "main", cwd=self.root)
        git("-c", "user.name=t", "-c", "user.email=t@t", "merge", "-q", "--no-ff", "-m", "merge release", "release", cwd=self.root)
        merge_commit = git("rev-parse", "HEAD", cwd=self.root).stdout.strip()
        git("push", "-q", "origin", "main", cwd=self.root)
        git("fetch", "-q", "origin", cwd=self.root)
        code, out = run(["tag", path, "--releases", self.releases])
        self.assertEqual(code, 0, out)
        self.assertEqual(git("rev-list", "-n", "1", "lending-v1.0.0", cwd=self.root).stdout.strip(), merge_commit)

    def remote_with_release_branch(self):
        bare = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, bare)
        git("init", "-q", "--bare", "-b", "main", cwd=bare)
        git("init", "-q", "-b", "main", cwd=self.root)
        git("remote", "add", "origin", bare, cwd=self.root)
        with open(os.path.join(self.root, "README"), "w", encoding="utf-8") as f:
            f.write("project\n")
        self.commit_all()
        git("checkout", "-q", "-b", "release", cwd=self.root)
        path = self.write_answers()
        self.assertEqual(run(["build", path, "--releases", self.releases])[0], 0)
        self.commit_all()
        git("checkout", "-q", "main", cwd=self.root)
        return path

    def test_with_a_remote_a_squash_merge_is_tagged_from_the_feature_branch(self):
        path = self.remote_with_release_branch()
        git("merge", "-q", "--squash", "release", cwd=self.root)
        git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "squash release", cwd=self.root)
        squash = git("rev-parse", "HEAD", cwd=self.root).stdout.strip()
        git("push", "-q", "origin", "main", cwd=self.root)
        git("checkout", "-q", "release", cwd=self.root)
        code, out = run(["tag", path, "--releases", self.releases])
        self.assertEqual(code, 0, out)
        self.assertEqual(git("rev-list", "-n", "1", "lending-v1.0.0", cwd=self.root).stdout.strip(), squash)

    def test_with_a_remote_a_later_edit_of_the_package_is_not_the_tag(self):
        path = self.remote_with_release_branch()
        git("-c", "user.name=t", "-c", "user.email=t@t", "merge", "-q", "--no-ff", "-m", "merge release", "release", cwd=self.root)
        merge_commit = git("rev-parse", "HEAD", cwd=self.root).stdout.strip()
        with open(os.path.join(self.releases, "lending", "1.0.0", "CHANGELOG.md"), "a", encoding="utf-8") as f:
            f.write("edited after the merge\n")
        self.commit_all()
        git("push", "-q", "origin", "main", cwd=self.root)
        git("checkout", "-q", "release", cwd=self.root)
        code, out = run(["tag", path, "--releases", self.releases])
        self.assertEqual(code, 0, out)
        self.assertEqual(git("rev-list", "-n", "1", "lending-v1.0.0", cwd=self.root).stdout.strip(), merge_commit)
        self.assertEqual(run(["verify", path, "--releases", self.releases])[0], 0)

    def test_with_a_remote_a_package_only_on_a_side_branch_is_not_tagged(self):
        bare = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, bare)
        git("init", "-q", "--bare", "-b", "main", cwd=bare)
        git("init", "-q", "-b", "main", cwd=self.root)
        git("remote", "add", "origin", bare, cwd=self.root)
        with open(os.path.join(self.root, "README"), "w", encoding="utf-8") as f:
            f.write("project\n")
        self.commit_all()
        git("push", "-q", "origin", "main", cwd=self.root)
        git("checkout", "-q", "-b", "release", cwd=self.root)
        path = self.write_answers()
        self.assertEqual(run(["build", path, "--releases", self.releases])[0], 0)
        self.commit_all()
        git("push", "-q", "origin", "release", cwd=self.root)   # pushed, but not merged into main
        code, out = run(["tag", path, "--releases", self.releases])
        self.assertEqual(code, 1)
        self.assertIn("is not on origin's default branch yet", out)

    def test_with_a_remote_it_says_whether_the_tag_is_pushed_and_never_pushes(self):
        bare = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, bare)
        git("init", "-q", "--bare", "-b", "main", cwd=bare)
        git("init", "-q", cwd=self.root)
        git("remote", "add", "origin", bare, cwd=self.root)
        path = self.write_answers()
        code, out = run(["build", path, "--releases", self.releases])
        self.assertIn("git with a remote (origin)", out)
        self.commit_all()
        code, out = run(["tag", path, "--releases", self.releases])
        self.assertEqual(code, 1)
        self.assertRegex(out, "default branch")   # rule 16: not before the merge (nothing on main yet)
        git("push", "-q", "origin", "HEAD:refs/heads/main", cwd=self.root)
        git("fetch", "-q", "origin", cwd=self.root)
        code, out = run(["tag", path, "--releases", self.releases])
        self.assertEqual(code, 0, out)
        self.assertIn("lending-v1.0.0 is not on origin; push it when you are ready: git push origin lending-v1.0.0", out)
        self.assertEqual(subprocess.run(["git", "ls-remote", "--tags", bare], env=CLEAN_ENV, capture_output=True,
                                        text=True).stdout.strip(), "")
        git("push", "-q", "origin", "lending-v1.0.0", cwd=self.root)
        # main is rewritten on the remote to a commit without the package; the cached origin/main still has it.
        package_commit = git("rev-parse", "HEAD", cwd=self.root).stdout.strip()
        git("checkout", "-q", "--orphan", "other", cwd=self.root)
        git("rm", "-rq", "--cached", ".", cwd=self.root)
        with open(os.path.join(self.root, "README"), "w", encoding="utf-8") as f:
            f.write("unrelated\n")
        git("add", "README", cwd=self.root)
        git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "unrelated", cwd=self.root)
        git("push", "-q", "-f", "origin", "other:main", cwd=self.root)
        git("checkout", "-q", "-f", package_commit, cwd=self.root)
        git("tag", "-d", "lending-v1.0.0", cwd=self.root)
        git("push", "-q", "origin", ":refs/tags/lending-v1.0.0", cwd=self.root)
        code, out = run(["tag", path, "--releases", self.releases])
        self.assertEqual(code, 1)   # the stale origin/main no longer vouches for the merge
        self.assertIn("is not on origin's default branch yet", out)
        git("push", "-q", "-f", "origin", f"{package_commit}:refs/heads/main", cwd=self.root)
        code, out = run(["tag", path, "--releases", self.releases])
        self.assertEqual(code, 0, out)
        git("push", "-q", "origin", "lending-v1.0.0", cwd=self.root)
        code, out = run(["tag", path, "--releases", self.releases])
        self.assertIn("lending-v1.0.0 already exists; nothing tagged", out)
        self.assertIn("lending-v1.0.0 is on origin", out)


if __name__ == "__main__":
    unittest.main()
