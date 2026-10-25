"""Tests of run_projection.py with a stand-in for every command: no Docker, database or store.

Run: uv run --no-project --with rdflib python3 -m unittest test_run_projection
"""
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_projection as rp  # noqa: E402

HEAD = ("<https://x.org/{m}> a <http://www.w3.org/2002/07/owl#Ontology> ; "
        "<http://www.w3.org/2002/07/owl#versionIRI> <https://x.org/{m}/1.0.0> .\n")
TRIPLE = '<https://x.org/s> <https://x.org/p> "v" .\n'
REPORT = {"passed": True, "determinism_hash_sorted": "h", "determinism_hash_shuffled": "h"}


class FakeRun:
    """Records each command and plays its part: writes the files the real command would, answers
    docker logs with Neo4j's start line, and exits with the code set for a command name."""

    GRAPHS = [("a", ""), ("a", "/shapes"), ("b", ""), ("b", "/shapes")]

    def __init__(self, fail=None, report=None, graphs=None):
        self.calls, self.fail, self.report = [], fail or {}, report or REPORT
        # the graphs an export holds: (graph IRI, Turtle text)
        self.graphs = graphs or [(f"https://x.org/{m}/1.0.0{suffix}", HEAD.format(m=m) if not suffix else "")
                                 for m, suffix in self.GRAPHS]

    def __call__(self, cmd, cwd=None, env=None, capture=False):
        self.calls.append((list(cmd), cwd, dict(env) if env else None))
        text = " ".join(cmd)
        for name, code in self.fail.items():
            if name in text:
                return code, ""
        if cmd[:2] == ["docker", "compose"] and "logs" in cmd:
            return 0, "Started.\n"
        for flag in ("--output", "--report", "--out"):
            if flag in cmd:
                path = cmd[cmd.index(flag) + 1]
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    if path.endswith("projection-report.json"):
                        json.dump(self.report, f)
                    elif path.endswith("loadable.nt"):
                        f.write(TRIPLE)
                    else:
                        f.write("")
        if "--ttl-dir" in cmd:   # rdfstore.py export: one Turtle file per graph, listed in graphs.tsv
            ttl = cmd[cmd.index("--ttl-dir") + 1]
            os.makedirs(ttl)
            rows = []
            for n, (graph, text) in enumerate(self.graphs, 1):
                with open(os.path.join(ttl, f"graph-{n}.ttl"), "w", encoding="utf-8") as f:
                    f.write(text)
                rows.append(f"graph-{n}.ttl\t{graph}\n")
            with open(os.path.join(ttl, "graphs.tsv"), "w", encoding="utf-8") as f:
                f.writelines(rows)
        return 0, ""

    def scripts(self):
        """The skill or rdf-store script each command ran, in order, with its subcommand if any."""
        names = []
        for cmd, _, _ in self.calls:
            for i, part in enumerate(cmd):
                if part.endswith(".py"):
                    sub = cmd[i + 1] if i + 1 < len(cmd) and not cmd[i + 1].startswith("-") and \
                        not cmd[i + 1].startswith("/") else ""
                    names.append((os.path.basename(part) + " " + sub).strip())
                    break
            else:
                if cmd[:2] == ["docker", "compose"]:
                    names.append("docker " + " ".join(c for c in cmd if c in ("up", "down", "logs")))
                elif cmd[0] == "java":
                    names.append("robot")
        return names


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.jar = self.write("robot.jar", "jar")
        patch = mock.patch.object(rp, "ROBOT_SHA256", hashlib.sha256(b"jar").hexdigest())
        patch.start()
        self.addCleanup(patch.stop)
        for m in ("a", "b"):
            self.write(f"releases/{m}/1.0.0/{m}.ttl", HEAD.format(m=m))
            self.write(f"releases/{m}/1.0.0/shapes.ttl", "")
        self.write("whole/shapes.ttl", "")
        self.write("config.json", "{}")
        self.write("queries.json", "[]")
        self.write("target.env", "")
        self.write("dbx.env", "")

    def write(self, name, text):
        path = os.path.join(self.tmp, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def run_config(self, **extra):
        cfg = {"mode": "releases", "projection_config": "config.json", "out": "out", "releases": "releases", "robot_jar": "robot.jar",
               "data": ["releases/a/1.0.0/a.ttl", "releases/b/1.0.0/b.ttl"],
               "shapes": ["releases/a/1.0.0/shapes.ttl", "releases/b/1.0.0/shapes.ttl", "whole/shapes.ttl"],
               "release_graphs": ["shapes"], "queries": "queries.json", "target_env": "target.env", **extra}
        path = self.write("run.json", json.dumps(cfg))
        with mock.patch.object(rp, "inside_repository", return_value=False):
            return rp.read_config(path)

    def driver(self, cfg, fake):
        return rp.Driver(cfg, run=fake, ready=lambda url: True, sleep=lambda s: None, log=lambda line: None)


class Config(Base):
    def test_paths_are_made_absolute_against_the_configurations_folder(self):
        cfg = self.run_config()
        self.assertEqual(cfg["out"], os.path.join(self.tmp, "out"))
        self.assertEqual(cfg["data"][0], os.path.join(self.tmp, "releases/a/1.0.0/a.ttl"))
        self.assertEqual(cfg["target_env"], os.path.join(self.tmp, "target.env"))
        self.assertEqual(cfg["neo4j"], {"compose_project": "lpg-local", "bolt_port": 17711})

    def test_bad_configurations_are_refused(self):
        for extra in ({"other": 1}, {"inputs_script": "x.py"}, {"mode": "both"}, {"databricks": {"env": "dbx.env"}},
                      {"rebuild": {"source": "s3", "out": "re"}}, {"rebuild": {"source": "jena", "out": "out"}},
                      {"release_graphs": ["a/b"]}):
            with self.subTest(extra), self.assertRaises(rp.Refusal):
                self.run_config(**extra)

    def test_an_output_folder_inside_the_repository_is_refused(self):
        os.system(f"git init -q {self.tmp}")   # noqa: S605 (a test folder of our own)
        path = self.write("run.json", json.dumps({"mode": "files", "projection_config": "config.json", "out": "out",
                                                   "files": ["releases"]}))
        with self.assertRaises(rp.Refusal):
            rp.read_config(path)

    def test_the_plan_skips_a_step_whose_configuration_is_absent(self):
        cfg = self.run_config()
        rows = dict(rp.plan(cfg, None, {"triplestore"}))
        self.assertIsNone(rows["project"])
        self.assertIsNone(rows["copy"])
        self.assertEqual(rows["triplestore"], "--skip")
        self.assertEqual(rows["databricks"], "no databricks in the run configuration")
        self.assertEqual(rows["rebuild"], "no rebuild in the run configuration")
        self.assertEqual(dict(rp.plan(cfg, {"load"}))["project"], "not in --only")
        with self.assertRaises(rp.Refusal):
            rp.step_names("load,nope")


    def test_the_template_reads(self):
        cfg = rp.read_config(os.path.join(os.path.dirname(HERE), "templates", "run-config.json"))
        self.assertEqual(cfg["out"], os.path.expanduser("~/lpg-out/library"))
        self.assertEqual((cfg["mode"], cfg["rebuild"]["source"]), ("files", "jena"))

    def test_without_a_mode_the_user_is_asked_to_choose(self):
        import contextlib
        import io
        path = self.write("run.json", json.dumps({"projection_config": "config.json", "out": "out"}))
        shown = io.StringIO()
        with contextlib.redirect_stdout(shown):
            self.assertEqual(rp.main(["--config", path, "--plan"]), 2)
        self.assertIn("releases (recommended)", shown.getvalue())
        self.assertIn(rp.PACKAGING, shown.getvalue())

    def test_releases_mode_without_releases_points_to_the_packaging_walk_through(self):
        with self.assertRaises(rp.Refusal) as caught:
            self.run_config(releases="nowhere")
        self.assertIn(rp.PACKAGING, str(caught.exception))
        with self.assertRaises(rp.Refusal):
            self.run_config(files=["releases"])   # files belongs to files mode


class Steps(Base):
    def test_a_full_run_calls_every_script_in_order_and_removes_the_containers(self):
        fake = FakeRun()
        d = self.driver(self.run_config(), fake)
        d.run_steps(["project", "load", "review", "tags", "copy", "jena", "explore"])
        self.assertEqual(fake.scripts(), [
            "check_projection_rules.py", "validate_data.py", "build.py merge", "robot", "build.py inferred",
            "build.py loadable", "build.py check-serialised", "validate_data.py", "build.py manifest",
            "in_graph_shapes.py",
            "docker down", "docker up", "docker logs", "load_verify.py", "build.py check-report",
            "model_review.py",
            "module_tags.py tag", "module_tags.py check", "module_tags.py modules",
            "copy_graph.py", "module_tags.py check", "module_tags.py modules", "model_review.py",
            "docker down", "docker up", "rdfstore.py roundtrip",
            "docker down", "docker up", "rdfstore.py roundtrip", "explore.py compare", "explore.py compare",
            "docker down",                            # explore's Fuseki
            "docker down", "docker down"])            # then Jena's Fuseki and the local Neo4j
        self.assertEqual(d.passed, ["project", "load", "review", "tags", "copy", "jena", "explore"])

    def test_the_triplestore_fuseki_comes_from_the_skills_compose_profile(self):
        fake = FakeRun()
        d = self.driver(self.run_config(), fake)
        d.run_steps(["project", "load", "triplestore"])
        up = next(cmd for cmd, _, _ in fake.calls if "up" in cmd and "lpg-triplestore" in cmd)
        self.assertEqual(up[up.index("--profile") + 1], "fuseki")

    def test_no_command_carries_the_password_and_every_path_is_absolute(self):
        fake = FakeRun()
        d = self.driver(self.run_config(), fake)
        d.run_steps(["project", "load", "tags", "copy"])
        password = d.password()
        with open(os.path.join(d.out, "neo4j-run", "run.env")) as f:
            self.assertIn(password, f.read())
        self.assertEqual(oct(os.stat(os.path.join(d.out, "neo4j-run", "run.env")).st_mode & 0o777), "0o600")
        for cmd, _, env in fake.calls:
            self.assertNotIn(password, " ".join(cmd))
            for i, part in enumerate(cmd[:-1]):
                if part in ("--config", "--report", "--output", "--target-env", "--env", "--inferred", "--releases"):
                    self.assertTrue(os.path.isabs(cmd[i + 1]), cmd)
        load = next(env for cmd, _, env in fake.calls if any(c.endswith("load_verify.py") for c in cmd))
        self.assertEqual(load["NEO4J_PASSWORD"], password)
        copy = next(cmd for cmd, _, _ in fake.calls if any(c.endswith("copy_graph.py") for c in cmd))
        self.assertEqual(copy[copy.index("--target-env") + 1], os.path.join(self.tmp, "target.env"))
        self.assertNotIn("--replace", copy)

    def test_a_robot_jar_with_another_checksum_stops_before_any_command(self):
        self.write("robot.jar", "other")
        fake = FakeRun()
        with self.assertRaises(rp.Failed):
            self.driver(self.run_config(), fake).run_steps(["project"])
        self.assertEqual(fake.calls, [])

    def test_a_failed_load_removes_the_local_neo4j(self):
        fake = FakeRun(fail={"load_verify.py": 1})
        d = self.driver(self.run_config(), fake)
        d.run_steps(["project"])
        with self.assertRaises(rp.Failed):
            d.run_steps(["load"])
        self.assertEqual(fake.scripts()[-2:], ["load_verify.py", "docker down"])
        self.assertFalse(d.local_up)

    def test_one_failed_removal_does_not_stop_the_others(self):
        class Breaking(FakeRun):
            def __call__(self, cmd, cwd=None, env=None, capture=False):
                if "down" in cmd and "lpg-jena" in cmd and any("roundtrip" in c for c, _, _ in self.calls):
                    self.calls.append((list(cmd), cwd, None))
                    raise OSError("docker went away")
                return super().__call__(cmd, cwd, env, capture)
        fake = Breaking()
        d = self.driver(self.run_config(), fake)
        d.run_steps(["project", "load", "jena"])
        last = [cmd for cmd, _, _ in fake.calls[-2:]]
        self.assertIn("lpg-jena", last[0])
        self.assertIn("lpg-local", last[1])   # the local Neo4j still removed
        self.assertFalse(d.local_up)

    def test_a_failed_step_whose_clean_up_fails_keeps_its_own_failure_and_retries(self):
        class Breaking(FakeRun):
            downs = 0

            def __call__(self, cmd, cwd=None, env=None, capture=False):
                if "explore.py" in " ".join(cmd):
                    return 1, ""
                if "down" in cmd and "lpg-explore" in cmd and any("roundtrip" in c for c, _, _ in self.calls):
                    self.downs += 1
                    self.calls.append((list(cmd), cwd, None))
                    raise OSError("docker went away")
                return super().__call__(cmd, cwd, env, capture)
        fake, logged = Breaking(), []
        d = rp.Driver(self.run_config(), run=fake, ready=lambda url: True, sleep=lambda s: None, log=logged.append)
        with self.assertRaises(rp.Failed) as caught:
            d.run_steps(["project", "load", "explore"])
        self.assertIn("explore.py compare", str(caught.exception))
        self.assertEqual(fake.downs, 2)   # the step's own removal, then finish()'s retry
        self.assertEqual(sum("could not be removed" in line for line in logged), 2)
        self.assertIn("lpg-local", fake.calls[-1][0])   # the local Neo4j still removed
        self.assertEqual(len(d.fusekis), 1)               # still tracked: it was never removed

    def test_a_step_that_needs_the_local_neo4j_says_so(self):
        d = self.driver(self.run_config(), FakeRun())
        with self.assertRaises(rp.Failed):
            d.run_steps(["tags"])

    def test_the_inputs_script_supplies_the_lists(self):
        script = self.write("inputs.py", "")
        a, b = os.path.join(self.tmp, "a.ttl"), os.path.join(self.tmp, "s.ttl")

        def run(cmd, cwd=None, env=None, capture=False):
            return 0, (a if cmd[-1] == "data" else b) + "\n"
        cfg = self.run_config()
        del cfg["data"], cfg["shapes"]
        cfg["inputs_script"] = script
        d = rp.Driver(cfg, run=run, ready=lambda u: True, sleep=lambda s: None, log=lambda line: None)
        self.assertEqual((d.data, d.shapes), ([a], [b]))

        def relative(cmd, cwd=None, env=None, capture=False):
            return 0, "a.ttl\n"
        with self.assertRaises(rp.Failed):
            rp.Driver(cfg, run=relative)


class Rebuild(Base):
    def test_release_graphs_sit_beside_each_data_file(self):
        cfg = self.run_config()
        args = rp.release_graph_args(cfg["data"][:1], ["shapes"])
        shapes = os.path.join(self.tmp, "releases/a/1.0.0/shapes.ttl")
        self.assertEqual(args, [cfg["data"][0], "--graph", f"{shapes}=https://x.org/a/1.0.0/shapes", shapes])
        with self.assertRaises(rp.Failed):
            rp.release_graph_args(cfg["data"][:1], ["catalog"])

    def test_the_export_maps_to_the_inputs_and_other_shapes_come_from_the_repository(self):
        cfg = self.run_config()
        self.write("export/graphs.tsv", "graph-1.ttl\thttps://x.org/a/1.0.0\ngraph-2.ttl\thttps://x.org/a/1.0.0/shapes\n")
        export = os.path.join(self.tmp, "export")
        rows = rp.input_list(export, cfg["data"][:1], [cfg["shapes"][0], cfg["shapes"][2]], ["shapes"])
        self.assertEqual(rows, [("data", os.path.join(export, "graph-1.ttl"), False),
                                ("shapes", os.path.join(export, "graph-2.ttl"), False),
                                ("shapes", cfg["shapes"][2], True)])
        with self.assertRaises(rp.Failed):
            rp.input_list(export, cfg["data"], cfg["shapes"], ["shapes"])   # no graph for b

    def test_triples_compare_as_rdf_terms_and_a_changed_value_differs(self):
        xs = "<http://www.w3.org/2001/XMLSchema#string>"
        for side, text in (("a", f'<https://x.org/s> <https://x.org/p> "v"^^{xs} .\n'), ("b", TRIPLE),
                           ("c", '<https://x.org/s> <https://x.org/p> "w" .\n')):
            self.write(f"{side}/loadable.nt", text)
            self.write(f"{side}/inferred.nt", "")
        problems, lines = rp.compare_triples(os.path.join(self.tmp, "b"), os.path.join(self.tmp, "a"))
        self.assertEqual((problems, len(lines)), ([], 2))
        self.assertEqual(len(rp.compare_triples(os.path.join(self.tmp, "c"), os.path.join(self.tmp, "a"))[0]), 1)

    def test_reports_must_carry_exactly_the_two_equal_hashes(self):
        both = {"determinism_hash_sorted": "h", "determinism_hash_shuffled": "h"}
        a = self.write("a.json", json.dumps({**both, "nodes": 1}))
        b = self.write("b.json", json.dumps({**both, "nodes": 2}))
        changed = self.write("c.json", json.dumps({**both, "determinism_hash_shuffled": "g"}))
        one = self.write("d.json", json.dumps({"determinism_hash_sorted": "h"}))
        extra = self.write("e.json", json.dumps({**both, "other_hash": "x"}))
        empty = self.write("f.json", json.dumps({"determinism_hash_sorted": "", "determinism_hash_shuffled": ""}))
        self.assertEqual(rp.compare_reports(b, a)[0], [])
        for bad in (changed, one, extra):
            self.assertEqual(len(rp.compare_reports(bad, a)[0]), 1, bad)
            self.assertEqual(len(rp.compare_reports(a, bad)[0]), 1, bad)
        self.assertEqual(len(rp.compare_reports(empty, empty)[0]), 1)

    def rebuild(self, source, fake, **extra):
        cfg = self.run_config(rebuild={"source": source, "out": "re"}, replace_target=True, **extra)
        d = self.driver(cfg, fake)
        d.run_steps(["project", "load", "rebuild"])
        return d

    def test_a_rebuild_from_databricks_exports_compares_and_projects_the_export(self):
        fake = FakeRun()
        self.rebuild("databricks", fake, databricks={"env": "dbx.env", "table": "c.s.t"})
        names = fake.scripts()
        start = names.index("rdfstore.py export")
        self.assertEqual(names[start:start + 3], ["rdfstore.py export", "rdfstore.py pack", "rdfstore.py compare"])
        export = next(cmd for cmd, _, _ in fake.calls if "export" in cmd)
        self.assertEqual(export[export.index("--env") + 1], os.path.join(self.tmp, "dbx.env"))
        merge = [cmd for cmd, _, _ in fake.calls if "merge" in cmd][-1]
        ttl = os.path.join(self.tmp, "re", "databricks-export", "ttl")
        self.assertEqual(merge[-2:], [os.path.join(ttl, "graph-1.ttl"), os.path.join(ttl, "graph-3.ttl")])
        rules = [cmd for cmd, _, _ in fake.calls if any(c.endswith("check_projection_rules.py") for c in cmd)][-1]
        shapes = [rules[i + 1] for i, c in enumerate(rules) if c == "--shapes"]
        self.assertEqual(shapes, [os.path.join(ttl, "graph-2.ttl"), os.path.join(ttl, "graph-4.ttl"),
                                  os.path.join(self.tmp, "whole/shapes.ttl")])
        copy = [cmd for cmd, _, _ in fake.calls if any(c.endswith("copy_graph.py") for c in cmd)][-1]
        self.assertIn("--replace", copy)
        self.assertEqual(names[-4:], ["explore.py compare", "explore.py compare", "docker down", "docker down"])

    def test_a_rebuild_from_jena_loads_jena_first(self):
        fake = FakeRun()
        self.rebuild("jena", fake)
        names = fake.scripts()
        self.assertLess(names.index("rdfstore.py roundtrip"), names.index("rdfstore.py export"))

    def test_a_rebuild_whose_graph_hash_differs_fails(self):
        class Drifting(FakeRun):
            def __call__(self, cmd, cwd=None, env=None, capture=False):
                self.report = {**REPORT, "determinism_hash_sorted": "g", "determinism_hash_shuffled": "g"} \
                    if any(os.sep + "re" + os.sep in c for c in cmd) else REPORT
                return super().__call__(cmd, cwd, env, capture)
        fake = Drifting()
        with self.assertRaises(rp.Failed) as caught:
            self.rebuild("repo", fake)
        self.assertIn("determinism_hash_sorted", str(caught.exception))
        self.assertNotIn("module_tags.py tag", fake.scripts()[fake.scripts().index("build.py check-report") + 1:])


class Cli(Base):
    def test_plan_runs_nothing_and_bad_arguments_exit_2(self):
        path = self.write("run.json", json.dumps({"mode": "files", "projection_config": "config.json", "out": "out",
                                                   "files": ["releases"]}))
        import contextlib
        import io
        with mock.patch.object(rp, "inside_repository", return_value=False), \
                mock.patch.object(rp, "run_command") as run, contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(rp.main(["--config", path, "--plan"]), 0)
            run.assert_not_called()
            self.assertEqual(rp.main(["--config", path, "--only", "nope"]), 2)
            self.assertEqual(rp.main(["--plan"]), 2)
            self.assertEqual(rp.main(["--config", path, "--extra"]), 2)


PLAIN = ('<https://x.org/b1> a <https://x.org/Book> ; <https://x.org/title> "One" ; <https://x.org/by> <https://x.org/p1> .\n'
         '<https://x.org/b2> a <https://x.org/Book> ; <https://x.org/title> "Two", "Deux" .\n'
         '<https://x.org/Book> a <http://www.w3.org/2002/07/owl#Class> .\n')


class FilesMode(Base):
    def setUp(self):
        super().setUp()
        self.write("plain/books.ttl", PLAIN)
        self.write("plain/more/people.nt", '<https://x.org/p1> <https://x.org/name> "Ann" .\n')
        self.write("plain/notes.txt", "not RDF")
        self.write("named.ttl", '<https://x.org/s> <https://x.org/p> <https://x.org/o> .\n')

    def files_config(self, **extra):
        cfg = {"mode": "files", "projection_config": "config.json", "out": "out", "robot_jar": "robot.jar",
               "files": ["plain", "named.ttl", "releases/a/1.0.0/a.ttl"], "graphs": {"named.ttl": "https://x.org/named"},
               "queries": "queries.json", **extra}
        path = self.write("run.json", json.dumps(cfg))
        with mock.patch.object(rp, "inside_repository", return_value=False):
            return rp.read_config(path)

    def test_folders_expand_and_each_file_gets_a_graph_name(self):
        d = self.driver(self.files_config(), FakeRun())
        t = lambda p: os.path.join(self.tmp, p)   # noqa: E731
        self.assertEqual(d.data, [t("plain/books.ttl"), t("plain/more/people.nt"), t("named.ttl"), t("releases/a/1.0.0/a.ttl")])
        self.assertEqual(d.graphs, {
            t("plain/books.ttl"): (rp.FILE_GRAPH + "plain/books.ttl", "file name"),
            t("plain/more/people.nt"): (rp.FILE_GRAPH + "plain/more/people.nt", "file name"),
            t("named.ttl"): ("https://x.org/named", "graphs"),
            t("releases/a/1.0.0/a.ttl"): ("https://x.org/a/1.0.0", "owl:versionIRI")})

    def test_a_graphs_entry_cannot_rename_a_versioned_file_or_name_an_unlisted_one(self):
        for graphs in ({"releases/a/1.0.0/a.ttl": "https://x.org/other"}, {"elsewhere.ttl": "https://x.org/e"}):
            with self.subTest(graphs), self.assertRaises(rp.Failed):
                self.driver(self.files_config(graphs=graphs), FakeRun())
        with self.assertRaises(rp.Failed):
            self.driver(self.files_config(files=["plain/notes.txt"], graphs={}), FakeRun())
        with self.assertRaises(rp.Refusal):
            self.files_config(data=["named.ttl"])

    def test_without_shapes_default_shapes_come_from_the_data(self):
        from rdflib import Graph, Literal, Namespace, URIRef
        SH = Namespace("http://www.w3.org/ns/shacl#")
        shapes, count = rp.default_shapes([os.path.join(self.tmp, "plain/books.ttl")])
        self.assertEqual(count, 1)   # Book; owl:Class is vocabulary
        node = next(shapes.subjects(SH.targetClass, URIRef("https://x.org/Book")))
        props = {str(shapes.value(p, SH.path)): (shapes.value(p, SH.minCount), shapes.value(p, SH.maxCount))
                 for p in shapes.objects(node, SH.property)}
        self.assertEqual(props, {"https://x.org/title": (Literal(1), Literal(2)),
                                 "https://x.org/by": (None, Literal(1))})
        self.assertIsInstance(shapes, Graph)

    def test_default_shapes_count_subclass_instances_and_registered_inverse_ends(self):
        from rdflib import Literal, Namespace, URIRef
        SH = Namespace("http://www.w3.org/ns/shacl#")
        path = self.write("sub.ttl", PLAIN + '<https://x.org/Novel> <http://www.w3.org/2000/01/rdf-schema#subClassOf> <https://x.org/Book> .\n'
                                             '<https://x.org/b3> a <https://x.org/Novel> .\n'
                                             '<https://x.org/r1> <https://x.org/has> <https://x.org/b1> .\n')
        shapes, _ = rp.default_shapes([path], {"https://x.org/Book": ["https://x.org/has"]})
        node = next(shapes.subjects(SH.targetClass, URIRef("https://x.org/Book")))
        props = {}
        for prop in shapes.objects(node, SH.property):
            path_node = shapes.value(prop, SH.path)
            key = str(shapes.value(path_node, SH.inversePath) or path_node)
            props[key] = (shapes.value(prop, SH.minCount), shapes.value(prop, SH.maxCount))
        self.assertEqual(props["https://x.org/title"], (None, Literal(2)))   # b3, a Novel, has no title
        self.assertEqual(props["https://x.org/has"], (None, Literal(1)))     # only b1 is pointed at
        self.write("cfg.json", json.dumps({"prefixes": {"x": "https://x.org/"},
                                           "qualified_relations": [{"class": "x:Book", "ends": [], "inverse_ends": ["x:has"]}]}))
        self.assertEqual(rp.inverse_ends(os.path.join(self.tmp, "cfg.json")), {"https://x.org/Book": ["https://x.org/has"]})

    def test_a_files_run_names_graphs_everywhere_and_records_the_manifest(self):
        fake = FakeRun()
        d = self.driver(self.files_config(target_env="target.env"), fake)
        self.assertTrue(d.default_shapes)
        d.run_steps(["project", "load", "tags", "copy", "jena", "explore"])
        rules = next(cmd for cmd, _, _ in fake.calls if any(c.endswith("check_projection_rules.py") for c in cmd))
        self.assertNotIn("--releases", rules)
        self.assertEqual(rules[rules.index("--shapes") + 1], os.path.join(d.out, "default-shapes.ttl"))
        books = os.path.join(self.tmp, "plain/books.ttl")
        for cmd, _, _ in fake.calls:
            if any(c.endswith("module_tags.py") for c in cmd):
                self.assertIn(f"{books}={rp.FILE_GRAPH}plain/books.ttl", cmd)
                self.assertNotIn(f"{os.path.join(self.tmp, 'releases/a/1.0.0/a.ttl')}=https://x.org/a/1.0.0", cmd)
            if "roundtrip" in cmd:
                self.assertIn(f"{books}={rp.FILE_GRAPH}plain/books.ttl", cmd)
            if any(c.endswith("explore.py") for c in cmd):
                self.assertIn("--files", cmd)
        with open(os.path.join(d.out, "run-manifest.json")) as f:
            manifest = json.load(f)
        self.assertEqual(manifest["mode"], "files")
        self.assertEqual(manifest["data"][0]["sha256"], rp.sha256_file(books))
        self.assertEqual(manifest["data"][0]["graph_from"], "file name")
        self.assertTrue(manifest["default_shapes"])
        self.assertEqual(len(manifest["notes"]), 2)

    def test_a_files_rebuild_from_jena_keeps_each_files_graph_name(self):
        d0 = self.driver(self.files_config(), FakeRun())
        exported = []
        for p in d0.data:
            with open(p, encoding="utf-8") as f:
                exported.append((d0.graphs[p][0], f.read()))
        fake = FakeRun(graphs=list(reversed(exported)))   # the export lists graphs in its own order
        d = self.driver(self.files_config(rebuild={"source": "jena", "out": "re"}), fake)
        d.run_steps(["project", "load", "rebuild"])
        ttl = os.path.join(self.tmp, "re", "jena-export", "ttl")
        tags = [cmd for cmd, _, _ in fake.calls if any(c.endswith("module_tags.py") for c in cmd)]
        self.assertTrue(tags)
        last = tags[-1]
        books = os.path.join(ttl, "graph-4.ttl")
        self.assertIn(f"{books}={rp.FILE_GRAPH}plain/books.ttl", last)
        self.assertEqual(last[-4:], [books, os.path.join(ttl, "graph-3.ttl"), os.path.join(ttl, "graph-2.ttl"),
                                     os.path.join(ttl, "graph-1.ttl")])

    def test_a_rebuild_refuses_inputs_changed_since_the_run_it_compares_with(self):
        d = self.driver(self.files_config(rebuild={"source": "repo", "out": "re"}), FakeRun())
        d.run_steps(["project", "load"])
        self.write("plain/books.ttl", PLAIN + '<https://x.org/b3> a <https://x.org/Book> .\n')
        with self.assertRaises(rp.Failed) as caught:
            d.run_steps(["rebuild"])
        self.assertIn("run-manifest.json", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
