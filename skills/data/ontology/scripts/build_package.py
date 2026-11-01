#!/usr/bin/env python3
"""Step 10: build one module's release package from an answers file (references/release.md, rules 8 to 18;
the interview that fills the answers file: references/packaging-walkthrough.md).

Run (uv run --no-project --with rdflib --with pyyaml --with pyshacl python3 build_package.py ...):
  build_package.py build  <answers.yaml> --releases <dir>   write <dir>/<module>/<version>/, then check it
  build_package.py verify <answers.yaml> --releases <dir>   fail unless the written package equals a fresh
                                                             build (and, in git, its tag's copy)
  build_package.py tag    <answers.yaml> --releases <dir>   git only: tag the package's commit locally
  build_package.py git    --releases <dir>                  say which of the three setups applies

The answers file (templates/package-answers.yaml is a filled example) names one release of one module:
  module, version            "lending", "1.0.0" (or a candidate, "1.0.0-rc.1")
  ontology_iri               the module's IRI; the version IRI is <ontology_iri>/<version>
  title, description         English text for the header and the catalog record
  sources                    the Turtle files that make the module, relative to the answers file
  shapes                     optional; the module's own SHACL files (none gives an empty shapes.ttl)
  requires                   optional; {module: version}, each one already released under <dir>
  issued                     the cut date, YYYY-MM-DD; a candidate has none (release.md, rule 14)
  rights                     optional; replaces the header's dcterms:rights
  changes                    one line per change: what, why, classification
  known_gaps                 "none", or a list of {gap, reason, record} (release.md, rule 18)
  approval                   {who, recorded_in, words}; required for a release, absent for a candidate
  catalog_iri                optional; defaults to the parent of ontology_iri plus "catalog"

The package (release.md, rule 8; the layout check_packages.py reads): <module>.ttl (the sources merged, with
the header set from the answers: owl:versionIRI, owl:versionInfo, dcterms:title, dcterms:description,
dcterms:requires per dependency, dcterms:issued and dcterms:modified for a release; owl:imports refused,
rule 11), <module>.jsonld, shapes.ttl, catalog.ttl (one DCAT dataset and its distributions), CHANGELOG.md
(this release's entry with its Known gaps section) and manifest.json (each file's SHA-256, depends_on and
the triple count). The output is deterministic: dates come from the answers, never from the clock.

A package is written to a staging folder, checked with check_packages.check_package and
check_changelogs.check_text, and only then moved into place; a released folder is never overwritten
(rule 10). Git is optional (release.md, "Without a remote"): with no git the manifest's hashes are the whole
guarantee; with git, `tag` tags <module>-v<version> on the commit that last changed the package and `verify` also compares
the written files with the tag's copy; with a remote, `tag` waits until the package is on the remote's default branch (read from the remote itself),
tags the commit that brought it in there (rule 16), and says whether the remote holds the tag.
Nothing here pushes.

Exit 0 on success, 1 when a check fails, 2 when the arguments or the answers are wrong.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import yaml
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, XSD

import check_changelogs
import check_packages

DCAT = Namespace("http://www.w3.org/ns/dcat#")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
HEADER_SET = (OWL.versionIRI, OWL.versionInfo, DCTERMS.title, DCTERMS.description, DCTERMS.requires,
              DCTERMS.issued, DCTERMS.modified)


class Refusal(Exception):
    """A wrong answer or argument: exit 2 with the message."""


def text(answers, key, required=True):
    value = answers.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise Refusal(f"the answers file has no {key}")
        return None
    if not isinstance(value, str):
        raise Refusal(f"{key} must be text")
    return value.strip()


def read_answers(path):
    """The answers as a dict, checked for shape; raises Refusal."""
    try:
        with open(path, encoding="utf-8") as f:
            answers = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as exc:
        raise Refusal(f"cannot read the answers file: {exc}")
    if not isinstance(answers, dict):
        raise Refusal("the answers file is not a mapping")
    module, version = text(answers, "module"), str(answers.get("version") or "").strip()
    if not re.match(r"^[a-z0-9][a-z0-9-]*$", module):
        raise Refusal("module must be lower-case letters, digits and hyphens, such as lending")
    if not check_packages.VERSION.match(version):
        raise Refusal("version must be MAJOR.MINOR.PATCH, or a candidate such as 1.0.0-rc.1")
    answers["module"], answers["version"] = module, version
    for key in ("ontology_iri", "title", "description"):
        answers[key] = text(answers, key)
    candidate = "-" in version
    issued = answers.get("issued")
    issued = issued.isoformat() if hasattr(issued, "isoformat") else (str(issued).strip() if issued else None)
    if candidate and issued:
        raise Refusal("a candidate has no issued date (release.md, rule 14)")
    if not candidate and not (issued and DATE.match(issued)):
        raise Refusal("a release needs issued: YYYY-MM-DD, the cut date (release.md, rule 15)")
    answers["issued"] = issued
    for key in ("sources", "shapes", "changes"):
        value = answers.get(key) or []
        if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
            raise Refusal(f"{key} must be a list of text")
        answers[key] = [v.strip() for v in value]
    if not answers["sources"]:
        raise Refusal("sources must name at least one Turtle file")
    if not answers["changes"]:
        raise Refusal("changes must hold at least one line: what changed, why, and the classification")
    requires = answers.get("requires") or {}
    if not isinstance(requires, dict):
        raise Refusal("requires must map each module to its version, such as {core: 1.0.0}")
    answers["requires"] = {str(m): str(v) for m, v in requires.items()}
    gaps = answers.get("known_gaps")
    if isinstance(gaps, str) and gaps.strip().lower().rstrip(".") == "none":
        answers["known_gaps"] = []
    elif isinstance(gaps, list) and gaps and all(isinstance(g, dict) for g in gaps):
        for g in gaps:
            for field in ("gap", "reason", "record"):
                if not str(g.get(field) or "").strip():
                    raise Refusal(f"every known gap needs a {field} (release.md, rule 18)")
        answers["known_gaps"] = gaps
    else:
        raise Refusal('known_gaps must be "none" or a list of {gap, reason, record} (release.md, rule 18)')
    approval = answers.get("approval")
    if candidate:
        if approval:
            raise Refusal("a candidate carries no approval; it waits for one (release.md, rule 14)")
        answers["approval"] = None
    else:
        if not isinstance(approval, dict) or not all(str(approval.get(k) or "").strip() for k in ("who", "recorded_in", "words")):
            raise Refusal("a release needs approval: {who, recorded_in, words} (release.md, rules 6 and 7)")
        answers["approval"] = {k: str(approval[k]).strip() for k in ("who", "recorded_in", "words")}
    answers["rights"] = text(answers, "rights", required=False)
    answers["catalog_iri"] = text(answers, "catalog_iri", required=False) or answers["ontology_iri"].rsplit("/", 1)[0] + "/catalog"
    answers["_base"] = os.path.dirname(os.path.abspath(path))
    return answers


def parse(base, paths):
    g = Graph()
    for p in paths:
        try:
            g.parse(os.path.join(base, p), format="turtle")
        except Exception as exc:  # a missing file or an rdflib parser error
            raise Refusal(f"cannot read {p}: {exc}")
    return g


def dependency_iris(releases, requires):
    """{module: version IRI} from each dependency's released manifest; raises Refusal for an unreleased one."""
    iris = {}
    for dep, version in sorted(requires.items()):
        try:
            manifest = check_packages.read_manifest(releases, dep, version)
        except (OSError, ValueError):
            raise Refusal(f"requires {dep} {version}, which is not released under {releases} (release.md, rule 11)")
        iri = manifest.get("version_iri")
        if not isinstance(iri, str) or not iri:
            raise Refusal(f"{dep} {version}'s manifest names no version_iri")
        iris[dep] = iri
    return iris


def module_graph(answers, releases):
    a = answers
    g = parse(a["_base"], a["sources"])
    iri = URIRef(a["ontology_iri"])
    if any(True for _ in g.subject_objects(OWL.imports)):
        raise Refusal("a source holds owl:imports; name dependencies under requires instead (release.md, rule 11)")
    others = sorted({str(s) for s in g.subjects(RDF.type, OWL.Ontology) if s != iri}
                    | {str(s) for s in g.subjects(OWL.versionIRI, None) if s != iri})
    if others:
        raise Refusal(f"the sources declare the ontology {others[0]}, not ontology_iri {a['ontology_iri']}; "
                      "give the IRI the sources use, or change the sources (packaging-walkthrough.md, Q3)")
    for p in HEADER_SET:
        g.remove((iri, p, None))
    if a["rights"]:
        g.remove((iri, DCTERMS.rights, None))
        g.add((iri, DCTERMS.rights, Literal(a["rights"], lang="en")))
    g.bind("dcterms", DCTERMS)
    g.bind("owl", OWL)
    g.add((iri, RDF.type, OWL.Ontology))
    g.add((iri, DCTERMS.title, Literal(a["title"], lang="en")))
    g.add((iri, DCTERMS.description, Literal(a["description"], lang="en")))
    g.add((iri, OWL.versionInfo, Literal(a["version"])))
    g.add((iri, OWL.versionIRI, URIRef(f"{a['ontology_iri']}/{a['version']}")))
    for dep_iri in dependency_iris(releases, a["requires"]).values():
        g.add((iri, DCTERMS.requires, URIRef(dep_iri)))
    if a["issued"]:
        g.add((iri, DCTERMS.issued, Literal(a["issued"], datatype=XSD.date)))
        g.add((iri, DCTERMS.modified, Literal(a["issued"], datatype=XSD.date)))
    return g


def jsonld(g):
    """JSON-LD with nodes, keys and values in a fixed order, so a rebuild is byte-identical."""
    data = json.loads(g.serialize(format="json-ld"))
    nodes = data if isinstance(data, list) else data.get("@graph", [data])
    for node in nodes:
        for key, value in node.items():
            if isinstance(value, list):
                node[key] = sorted(value, key=lambda v: json.dumps(v, sort_keys=True))
    nodes.sort(key=lambda n: n.get("@id", ""))
    return json.dumps(nodes, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def catalog(a):
    module, version = a["module"], a["version"]
    base = f"{a['ontology_iri']}/releases/{version}"
    g = Graph()
    g.bind("dcat", DCAT)
    g.bind("dcterms", DCTERMS)
    g.bind("owl", OWL)
    cat, dataset = URIRef(a["catalog_iri"]), URIRef(f"{a['ontology_iri']}/{version}")
    g.add((cat, RDF.type, DCAT.Catalog))
    g.add((cat, DCAT.dataset, dataset))
    g.add((dataset, RDF.type, DCAT.Dataset))
    g.add((dataset, DCTERMS.title, Literal(f"{a['title']} {version}", lang="en")))
    g.add((dataset, DCTERMS.isVersionOf, URIRef(a["ontology_iri"])))
    g.add((dataset, OWL.versionInfo, Literal(version)))
    if a["issued"]:
        g.add((dataset, DCTERMS.issued, Literal(a["issued"], datatype=XSD.date)))
    for fname, media in ((f"{module}.ttl", "text/turtle"), (f"{module}.jsonld", "application/ld+json"),
                         ("shapes.ttl", "text/turtle")):
        dist = URIRef(f"{base}/{fname}")
        g.add((dataset, DCAT.distribution, dist))
        g.add((dist, RDF.type, DCAT.Distribution))
        g.add((dist, DCAT.downloadURL, dist))
        g.add((dist, DCAT.mediaType, Literal(media)))
    return g.serialize(format="turtle")


def changelog(a):
    when = a["issued"] or "candidate, not issued"
    lines = [f"# {a['module']} changelog", "", f"## {a['version']} ({when})", ""]
    lines += [f"- {c}" for c in a["changes"]]
    lines.append("")
    if a["approval"]:
        ap = a["approval"]
        lines += [f"Approved by {ap['who']}: \"{ap['words']}\" (recorded in {ap['recorded_in']}).", ""]
    else:
        lines += ["A release candidate: not yet approved (release.md, rule 14).", ""]
    if a["requires"]:
        lines += ["Requires " + ", ".join(f"{m} {v}" for m, v in sorted(a["requires"].items())) + ".", ""]
    lines += ["### Known gaps", ""]
    if a["known_gaps"]:
        for g in a["known_gaps"]:
            lines.append(f"- {str(g['gap']).strip().rstrip('.')}. Reason: {str(g['reason']).strip()} "
                         f"Record: {str(g['record']).strip()}")
    else:
        lines.append("None.")
    return "\n".join(lines) + "\n"


def build(answers, releases):
    """The package as {file name: text}, manifest last."""
    a = answers
    g = module_graph(a, releases)
    shapes = parse(a["_base"], a["shapes"])
    for prefix, ns in (("sh", "http://www.w3.org/ns/shacl#"),):
        shapes.bind(prefix, ns)
    files = {f"{a['module']}.ttl": g.serialize(format="turtle"), f"{a['module']}.jsonld": jsonld(g),
             "shapes.ttl": shapes.serialize(format="turtle"), "catalog.ttl": catalog(a),
             "CHANGELOG.md": changelog(a)}
    files["manifest.json"] = json.dumps({
        "module": a["module"], "version": a["version"], "release_candidate": "-" in a["version"],
        "ontology_iri": a["ontology_iri"], "version_iri": f"{a['ontology_iri']}/{a['version']}",
        "issued": a["issued"], "depends_on": dict(sorted(a["requires"].items())), "triples": len(g),
        "approved_by": a["approval"],
        "files": {n: hashlib.sha256(t.encode("utf-8")).hexdigest() for n, t in sorted(files.items())}},
        indent=2, sort_keys=False) + "\n"
    return files


def problems(releases, module, version, files):
    """What check_packages and check_changelogs find in a written package."""
    found = check_packages.check_package(releases, module, version)
    found += [m for _, m in check_changelogs.check_text(files["CHANGELOG.md"], f"{module} {version}")]
    return found


def write(answers, releases):
    a = answers
    final = os.path.join(releases, a["module"], a["version"])
    if os.path.exists(final):
        raise Refusal(f"{a['module']} {a['version']} is already released at {final}; a released package never "
                      "changes, so cut a new version (release.md, rule 10)")
    files = build(a, releases)
    module_dir = os.path.dirname(final)
    made_module_dir = not os.path.isdir(module_dir)
    os.makedirs(module_dir, exist_ok=True)
    staging = tempfile.mkdtemp(prefix=f".{a['version']}.staging-", dir=module_dir)
    kept = False
    try:
        for name, body in files.items():
            with open(os.path.join(staging, name), "w", encoding="utf-8", newline="\n") as f:
                f.write(body)
        # check_package reads <releases>/<module>/<version>, so the staged copy is checked under that name;
        # it stays only when both checks pass, and any failure or exception removes it.
        os.rename(staging, final)
        found = problems(releases, a["module"], a["version"], files)
        kept = not found
        return found
    finally:
        for path in (staging, final):
            if not kept and os.path.exists(path):
                shutil.rmtree(path)
        if not kept and made_module_dir and os.path.isdir(module_dir) and not os.listdir(module_dir):
            os.rmdir(module_dir)


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def git_setup(path):
    """("none", None, []) outside git; ("local", top, []) with no remote; ("remote", top, [names]) otherwise."""
    folder = path if os.path.isdir(path) else os.path.dirname(os.path.abspath(path)) or "."
    top = git("rev-parse", "--show-toplevel", cwd=folder)
    if top.returncode != 0:
        return "none", None, []
    remotes = [r for r in git("remote", cwd=folder).stdout.split() if r]
    return ("remote" if remotes else "local"), top.stdout.strip(), remotes


def tag_name(a):
    return f"{a['module']}-v{a['version']}"


def tag_on_remotes(top, remotes, tag):
    """The remotes that hold the tag (git ls-remote; reads only, never pushes)."""
    held = []
    for r in remotes:
        out = git("ls-remote", "--tags", r, f"refs/tags/{tag}", cwd=top)
        if out.returncode == 0 and out.stdout.strip():
            held.append(r)
    return held


def verify(answers, releases):
    a = answers
    folder = os.path.join(releases, a["module"], a["version"])
    if not os.path.isdir(folder):
        return [f"{a['module']} {a['version']}: no written package at {folder}"]
    fresh = build(a, releases)
    fails = []
    present = set(os.listdir(folder))
    for name in sorted(present - set(fresh)):
        fails.append(f"{name} is in the package but not in a fresh build")
    for name, body in fresh.items():
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            fails.append(f"{name} is missing")
            continue
        with open(path, "rb") as f:  # bytes, so a changed line ending is a difference too
            if f.read() != body.encode("utf-8"):
                fails.append(f"{name} differs from a fresh build")
    setup, top, _ = git_setup(releases)
    if setup != "none":
        tag = tag_name(a)
        if git("rev-parse", "-q", "--verify", f"refs/tags/{tag}", cwd=top).returncode != 0:
            print(f"INFO no tag {tag} yet; the manifest's hashes are the check until it is tagged")
        else:
            rel = os.path.relpath(os.path.realpath(folder), os.path.realpath(top))
            for name in sorted(present):
                shown = subprocess.run(["git", "show", f"{tag}:{rel}/{name}"], cwd=top, capture_output=True)
                with open(os.path.join(folder, name), "rb") as f:
                    if shown.returncode != 0 or shown.stdout != f.read():
                        fails.append(f"{name} differs from the copy tagged {tag}")
    return [f"{a['module']} {a['version']}: {m}" for m in fails]


def tag(answers, releases):
    """Tag the commit that holds the package (with a remote, after the merge). Returns (exit code, lines)."""
    a = answers
    setup, top, remotes = git_setup(releases)
    if setup == "none":
        return 2, ["not a git repository: there is nothing to tag, and the manifest's hashes are the whole guarantee"]
    folder = os.path.join(releases, a["module"], a["version"])
    rel = os.path.relpath(os.path.realpath(folder), os.path.realpath(top))
    if git("ls-files", "--error-unmatch", f"{rel}/manifest.json", cwd=top).returncode != 0:
        return 1, [f"commit the package first: {rel} is not in git"]
    if git("status", "--porcelain", "--", rel, cwd=top).stdout.strip():
        return 1, [f"commit the package first: {rel} has uncommitted changes"]
    name = tag_name(a)
    # Without a remote the tag goes on the commit that last changed the package, not on HEAD: a later, unrelated
    # commit must not become the release's commit. With a remote it waits for the merge (release.md, rule 16).
    commit = git("log", "-1", "--format=%H", "--", rel, cwd=top).stdout.strip()
    if setup == "remote":
        # The evidence is the remote's default branch as the remote reports it now (git ls-remote), never a cached
        # remote-tracking ref, so a branch deleted or rewritten on the remote cannot vouch for the merge. A fetch
        # first brings its commits here (it reads; it never pushes). Any failure, or a default branch that cannot
        # be named, stops the tag. The first remote git lists is the one asked.
        r = remotes[0]
        fetched = git("fetch", "--quiet", r, cwd=top)
        symref = git("ls-remote", "--symref", r, "HEAD", cwd=top)
        first = symref.stdout.splitlines()[0].split() if symref.returncode == 0 and symref.stdout.strip() else []
        if fetched.returncode != 0 or len(first) < 3 or first[0] != "ref:" or not first[1].startswith("refs/heads/"):
            return 1, [f"cannot read {r}'s default branch, so the merge cannot be confirmed"]
        listed = git("ls-remote", r, first[1], cwd=top)
        rows = [line.split("\t") for line in listed.stdout.splitlines() if line.strip()] if listed.returncode == 0 else []
        head_sha = rows[0][0] if len(rows) == 1 and rows[0][1:] == [first[1]] and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", rows[0][0]) else ""
        # The release's commit there is the earliest commit on the default branch's first-parent line whose
        # package folder is exactly this release's folder: the merge commit after a merge, the squash commit after
        # a squash, the package's own commit after a fast-forward. A later commit that edits the folder never wins.
        released = git("rev-parse", f"{commit}:{rel}", cwd=top).stdout.strip()
        brought = ""
        if head_sha:
            for c in git("log", "--first-parent", "--reverse", "--format=%H", head_sha, "--", rel, cwd=top).stdout.split():
                if git("rev-parse", f"{c}:{rel}", cwd=top).stdout.strip() == released:
                    brought = c
                    break
        if not brought:
            return 1, [f"{rel} is not on {r}'s default branch yet: tag it after the release merges (release.md, rule 16)"]
        commit = brought
    lines = []
    if git("rev-parse", "-q", "--verify", f"refs/tags/{name}", cwd=top).returncode == 0:
        lines.append(f"{name} already exists; nothing tagged")
    else:
        made = git("tag", name, commit, cwd=top)
        if made.returncode != 0:
            return 1, [f"git tag failed: {made.stderr.strip()}"]
        lines.append(f"tagged {name} on {commit[:7]}, the commit that holds the package (local)")
    if setup == "remote":
        held = tag_on_remotes(top, remotes, name)
        missing = [r for r in remotes if r not in held]
        if missing:
            lines.append(f"{name} is not on {', '.join(missing)}; push it when you are ready: git push {missing[0]} {name}")
        else:
            lines.append(f"{name} is on {', '.join(held)}")
    return 0, lines


def describe_setup(releases):
    setup, top, remotes = git_setup(releases)
    if setup == "none":
        return "no git: each package's manifest.json holds the SHA-256 of every file, and that is the whole guarantee"
    if setup == "local":
        return f"git with no remote ({top}): tag each committed release locally, <module>-v<version>"
    return f"git with a remote ({', '.join(remotes)}): tag each release and push the tag when the release has merged"


def main(argv):
    p = argparse.ArgumentParser(prog="build_package.py")
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("build", "verify", "tag"):
        s = sub.add_parser(name)
        s.add_argument("answers")
        s.add_argument("--releases", required=True)
    s = sub.add_parser("git")
    s.add_argument("--releases", required=True)
    try:
        args = p.parse_args(argv)
    except SystemExit:
        return 2
    try:
        if args.command == "git":
            print(describe_setup(args.releases))
            return 0
        answers = read_answers(args.answers)
        if args.command == "build":
            found = write(answers, args.releases)
            for line in found:
                print("FAIL", line)
            if found:
                return 1
            print(f"wrote {answers['module']} {answers['version']} to "
                  f"{os.path.join(args.releases, answers['module'], answers['version'])}; it passes the package and changelog checks")
            print(describe_setup(args.releases))
            return 0
        if args.command == "verify":
            found = verify(answers, args.releases)
            for line in found:
                print("FAIL", line)
            if found:
                return 1
            print(f"{answers['module']} {answers['version']} equals a fresh build")
            return 0
        code, lines = tag(answers, args.releases)
        for line in lines:
            print(line if code == 0 else f"ERROR {line}")
        return code
    except Refusal as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
