"""Tests for check_taxonomy.py, check_requirements.py, templates/check.sh and the shapes skeleton.

Run from this folder:
  uv run --no-project --with rdflib --with pyyaml --with pyshacl python3 -m unittest test_checks

Each one-break test breaks a shipped template in one way and asserts that exactly the
named check fires with its message, so a check that passes vacuously, or fires for the
wrong reason, fails here.
"""
import contextlib
import copy
import io
import os
import shutil
import subprocess
import tempfile
import unittest

import yaml
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS, XSD

import check_requirements
import check_taxonomy

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = os.path.join(HERE, "..", "templates")
SKELETON = os.path.join(TEMPLATES, "ontology-skeleton.ttl")
SHAPES = os.path.join(TEMPLATES, "shapes-skeleton.ttl")
REQUIREMENTS = os.path.join(TEMPLATES, "requirements.yaml")
LIB = "https://id.example.org/library/"


def lib(name):
    return URIRef(LIB + name)


def skeleton():
    return Graph().parse(SKELETON, format="turtle")


def requirements():
    with open(REQUIREMENTS, encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_main(main, argv):
    """Call a checker's main() and return (exit code, everything it printed)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = main(argv)
    return code, out.getvalue()


class OneBreak:
    """assertOnly: every failure has the expected check name, and one has the fragment."""

    def assertOnly(self, fails, name, fragment):
        self.assertTrue(fails, f"expected {name!r} containing {fragment!r}, got no failure")
        self.assertEqual({n for n, _ in fails}, {name}, f"unexpected checks fired: {fails}")
        self.assertTrue(any(fragment in m for _, m in fails), f"no {fragment!r} in {fails}")


class TaxonomyChecks(OneBreak, unittest.TestCase):
    def broken(self, mutate, name, fragment):
        g = skeleton()
        mutate(g)
        self.assertOnly(check_taxonomy.check(g), name, fragment)

    def test_skeleton_passes(self):
        self.assertEqual(check_taxonomy.check(skeleton()), [])

    # blank-node and untagged
    def test_blank_node(self):
        self.broken(lambda g: g.add((lib("Loan"), RDFS.seeAlso, BNode())), "blank-node", "lib:Loan rdfs:seeAlso")

    def test_untagged_literal(self):
        self.broken(lambda g: g.set((lib("Copy"), RDFS.label, Literal("Copy"))),
                    "untagged", 'lib:Copy rdfs:label "Copy" has no language tag')

    def test_xsd_string_counts_as_untagged(self):
        self.broken(lambda g: g.set((lib("Copy"), SKOS.definition, Literal("A copy.", datatype=XSD.string))),
                    "untagged", "lib:Copy skos:definition")

    # label
    def test_concept_without_preferred_label(self):
        self.broken(lambda g: g.remove((lib("overdue"), SKOS.prefLabel, None)), "label", "lib:overdue has no skos:prefLabel")

    def test_two_preferred_labels_in_one_language(self):
        self.broken(lambda g: g.add((lib("overdue"), SKOS.prefLabel, Literal("Late", lang="en"))),
                    "label", "lib:overdue has 2 skos:prefLabel values in language en")

    def test_class_without_label(self):
        self.broken(lambda g: g.remove((lib("Member"), RDFS.label, None)), "label", "lib:Member has no rdfs:label")

    def test_property_without_label(self):
        self.broken(lambda g: g.remove((lib("borrower"), RDFS.label, None)), "label", "lib:borrower has no rdfs:label")

    # definition
    def test_concept_without_definition(self):
        self.broken(lambda g: g.remove((lib("renewal"), SKOS.definition, None)), "definition", "lib:renewal has no skos:definition")

    def test_class_without_definition(self):
        self.broken(lambda g: g.remove((lib("Copy"), SKOS.definition, None)), "definition", "lib:Copy has no skos:definition")

    def test_property_without_definition(self):
        self.broken(lambda g: g.remove((lib("dueDate"), SKOS.definition, None)), "definition", "lib:dueDate has no skos:definition")

    # notation
    def test_concept_without_notation(self):
        self.broken(lambda g: g.remove((lib("returned"), SKOS.notation, None)), "notation", "lib:returned has no skos:notation")

    def test_duplicate_notation_in_scheme(self):
        self.broken(lambda g: g.set((lib("overdue"), SKOS.notation, Literal("LS-1"))), "notation", 'share the notation "LS-1"')

    # scheme
    def test_concept_in_no_scheme(self):
        self.broken(lambda g: g.remove((lib("renewal"), SKOS.inScheme, None)), "scheme", "lib:renewal is in no skos:ConceptScheme")

    def test_listed_top_concept_without_top_concept_of(self):
        def mutate(g):
            g.remove((lib("returned"), SKOS.topConceptOf, None))
            g.add((lib("returned"), SKOS.broader, lib("on-loan")))
        self.broken(mutate, "scheme", "lib:loan-state lists lib:returned as a top concept, but lib:returned has no skos:topConceptOf it")

    # parent
    def test_two_parents(self):
        self.broken(lambda g: g.add((lib("renewal"), SKOS.broader, lib("lending-activity"))), "parent", "lib:renewal has 2 skos:broader parents")

    def test_floating_concept(self):
        self.broken(lambda g: g.remove((lib("renewal"), SKOS.broader, None)), "parent", "lib:renewal has 0 skos:broader parents")

    def test_top_concept_with_parent(self):
        self.broken(lambda g: g.add((lib("overdue"), SKOS.broader, lib("on-loan"))), "parent", "lib:overdue is a top concept and also has skos:broader")

    def test_undeclared_parent(self):
        def mutate(g):
            g.set((lib("renewal"), SKOS.broader, lib("circulatoin")))
        g = skeleton()
        mutate(g)
        fails = check_taxonomy.check(g)
        self.assertIn(("parent", "lib:renewal has parent lib:circulatoin, which is not a declared skos:Concept"), fails)

    def test_cycle(self):
        def mutate(g):
            g.remove((lib("circulation"), SKOS.topConceptOf, None))
            g.remove((lib("lending"), SKOS.hasTopConcept, None))
            g.add((lib("circulation"), SKOS.broader, lib("renewal")))
        self.broken(mutate, "parent", "skos:broader cycle")

    # collision
    def test_label_collision_ignores_case(self):
        self.broken(lambda g: g.set((lib("overdue"), SKOS.prefLabel, Literal("on LOAN", lang="en"))), "collision", 'share the label "on loan"')

    # property-kind
    def test_property_of_two_kinds(self):
        g = skeleton()
        g.add((lib("dueDate"), RDF.type, OWL.ObjectProperty))
        fails = check_taxonomy.check(g)
        # Two kinds also makes the range wrong for one of them, so both checks fire.
        self.assertEqual({n for n, _ in fails}, {"property-kind", "kind-range"}, fails)
        self.assertIn(("property-kind", "lib:dueDate is typed 2 of owl:ObjectProperty and "
                                        "owl:DatatypeProperty; it needs exactly one"), fails)

    def test_bare_rdf_property(self):
        def mutate(g):
            g.remove((lib("loanOf"), RDF.type, OWL.ObjectProperty))
            g.add((lib("loanOf"), RDF.type, RDF.Property))
        self.broken(mutate, "property-kind", "lib:loanOf is typed 0")

    # domain-range
    def test_property_with_two_domains(self):
        self.broken(lambda g: g.add((lib("dueDate"), RDFS.domain, lib("Copy"))), "domain-range", "lib:dueDate has 2 rdfs:domain values")

    def test_property_without_range(self):
        self.broken(lambda g: g.remove((lib("borrower"), RDFS.range, None)), "domain-range", "lib:borrower has 0 rdfs:range values")

    def test_literal_range(self):
        self.broken(lambda g: g.set((lib("dueDate"), RDFS.range, RDFS.Literal)), "domain-range", "lib:dueDate has range rdfs:Literal")

    def test_misspelled_range(self):
        self.broken(lambda g: g.set((lib("borrower"), RDFS.range, lib("Membr"))),
                    "domain-range", "lib:borrower has rdfs:range lib:Membr, which is neither declared")

    def test_allowed_namespace_resolves(self):
        g = skeleton()
        g.set((lib("borrower"), RDFS.range, URIRef("https://example.org/people#Person")))
        self.assertTrue(check_taxonomy.check(g))
        self.assertEqual(check_taxonomy.check(g, ["https://example.org/people#"]), [])

    # kind-range
    def test_object_property_with_datatype_range(self):
        self.broken(lambda g: g.set((lib("borrower"), RDFS.range, XSD.string)),
                    "kind-range", "lib:borrower is an owl:ObjectProperty but its range xsd:string is a datatype")

    def test_datatype_property_with_class_range(self):
        self.broken(lambda g: g.set((lib("dueDate"), RDFS.range, lib("Copy"))),
                    "kind-range", "lib:dueDate is an owl:DatatypeProperty but its range lib:Copy is not a datatype")

    # untyped
    def test_untyped_concept(self):
        def mutate(g):
            g.add((lib("hold"), SKOS.inScheme, lib("lending")))
            g.add((lib("hold"), SKOS.broader, lib("circulation")))
            g.add((lib("hold"), SKOS.prefLabel, Literal("Hold", lang="en")))
        self.broken(mutate, "untyped", "lib:hold has SKOS or RDFS term properties but no rdf:type")

    def test_notation_and_version_need_no_tag(self):
        self.assertFalse([f for f in check_taxonomy.check(skeleton()) if f[0] == "untagged"])

    # the command line
    def test_cli_pass_is_0(self):
        code, out = run_main(check_taxonomy.main, [SKELETON])
        self.assertEqual(code, 0)
        self.assertIn("all checks pass", out)

    def test_cli_failure_is_1(self):
        g = skeleton()
        g.remove((lib("renewal"), SKOS.definition, None))
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "broken.ttl")
            g.serialize(path, format="turtle")
            code, out = run_main(check_taxonomy.main, [path])
        self.assertEqual(code, 1)
        self.assertIn("FAIL definition: lib:renewal has no skos:definition", out)

    def test_cli_bad_input_is_2(self):
        self.assertEqual(run_main(check_taxonomy.main, [])[0], 2)
        self.assertEqual(run_main(check_taxonomy.main, [REQUIREMENTS])[0], 2)
        self.assertEqual(run_main(check_taxonomy.main, ["--allow-namespace=", SKELETON])[0], 2)


class RequirementsChecks(OneBreak, unittest.TestCase):
    def broken(self, mutate, name, fragment):
        req = requirements()
        mutate(req)
        self.assertOnly(check_requirements.check(req), name, fragment)

    def test_template_passes(self):
        self.assertEqual(check_requirements.check(requirements()), [])

    # top-level schema
    def test_missing_field(self):
        self.broken(lambda r: r.pop("constraints"), "schema", "missing field 'constraints'")

    def test_empty_purpose(self):
        self.broken(lambda r: r.update(purpose=None), "schema", "'purpose' must be one non-empty sentence")

    def test_users_not_a_list(self):
        self.broken(lambda r: r.update(users="staff"), "schema", "'users' must be a non-empty list")

    def test_constraints_not_a_list(self):
        self.broken(lambda r: r.update(constraints=None), "schema", "'constraints' must be a list of strings")

    def test_empty_use_cases(self):
        self.broken(lambda r: r.update(use_cases=[]), "schema", "'use_cases' must be a non-empty list")

    def test_use_case_without_text(self):
        self.broken(lambda r: r["use_cases"][0].pop("text"), "schema", "use case 1 needs an 'id' and a 'text'")

    def test_duplicate_use_case(self):
        self.broken(lambda r: r["use_cases"][1].update(id="UC1"), "schema", "use case UC1 is used twice")

    def test_malformed_scope(self):
        req = requirements()
        req["scope"] = ["lending"]
        fails = check_requirements.check(req)
        # With no usable scope, every need is also unlisted; the schema failure comes first.
        self.assertEqual(fails[0][0], "schema")
        self.assertIn("'scope' needs 'in'", fails[0][1])

    def test_empty_question_list(self):
        self.broken(lambda r: r.update(competency_questions=[]), "schema", "'competency_questions' must be a non-empty list")

    # competency questions
    def test_question_without_rationale(self):
        self.broken(lambda r: r["competency_questions"][0].pop("rationale"), "schema", "CQ1 has no 'rationale'")

    def test_bad_priority(self):
        self.broken(lambda r: r["competency_questions"][0].update(priority="high"), "schema", "CQ1 priority 'high' is not must, should or could")

    def test_bad_lock_status(self):
        self.broken(lambda r: r["competency_questions"][0].update(status="answerable"), "schema", "CQ1 status 'answerable' is not drafted or locked")

    def test_duplicate_question_id(self):
        self.broken(lambda r: r["competency_questions"][1].update(id="CQ1"), "schema", "CQ1 is used twice")

    def test_needs_not_a_list(self):
        self.broken(lambda r: r["competency_questions"][0].update(needs="lending"), "schema", "CQ1 'needs' must be a list")

    # conflicts
    def test_need_out_of_scope(self):
        self.broken(lambda r: r["competency_questions"][0]["needs"].append("fines"), "conflict", "CQ1 needs 'fines', which scope.out excludes")

    def test_rationale_names_out_of_scope_area(self):
        self.broken(lambda r: r["competency_questions"][1].update(rationale="Requires the fines history."),
                    "conflict", "CQ2 rationale names 'fines'")

    def test_need_not_in_scope(self):
        self.broken(lambda r: r["competency_questions"][0].update(needs=["membership"]),
                    "conflict", "CQ1 needs 'membership', which scope.in does not list")

    def test_area_in_and_out(self):
        self.broken(lambda r: r["scope"]["out"].append("Lending"), "conflict", "area 'lending' is both in and out of scope")

    # inputs
    def test_missing_input_kind(self):
        self.broken(lambda r: r["inputs"].pop("semantic_evidence"), "inputs", "input 'semantic_evidence' needs a status")

    def test_bad_input_status(self):
        self.broken(lambda r: r["inputs"]["purpose"].update(status="partial"), "inputs", "input 'purpose' needs a status")

    def test_thin_input_needs_note(self):
        self.broken(lambda r: r["inputs"]["representative_data"].update(note=""), "inputs", "input 'representative_data' is thin and needs a note")

    def test_inputs_not_a_mapping(self):
        def mutate(r):
            r["inputs"] = []
        req = requirements()
        mutate(req)
        fails = check_requirements.check(req)
        self.assertIn(("inputs", "'inputs' must map each of the six kinds to {status, note}"), fails)

    # assumptions
    def test_bad_assumption_status(self):
        self.broken(lambda r: r["assumptions"][0].update(status="maybe"), "assumptions", "A1 needs a status of ASSUMED or confirmed")

    def test_assumption_without_text(self):
        self.broken(lambda r: r["assumptions"][0].pop("text"), "assumptions", "A1 needs an 'id', a 'text' and a 'record' field")

    def test_confirmed_assumption_needs_record(self):
        self.broken(lambda r: r["assumptions"][0].update(status="confirmed"), "assumptions", "A1 is confirmed but names no decision record")

    # the command line
    def test_cli_exit_codes(self):
        self.assertEqual(run_main(check_requirements.main, [REQUIREMENTS])[0], 0)
        self.assertEqual(run_main(check_requirements.main, [])[0], 2)
        self.assertEqual(run_main(check_requirements.main, [os.path.join(HERE, "missing.yaml")])[0], 2)
        req = requirements()
        req["competency_questions"][0]["needs"].append("fines")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "requirements.yaml")
            with open(path, "w", encoding="utf-8") as f:
                yaml.safe_dump(req, f)
            code, out = run_main(check_requirements.main, [path])
        self.assertEqual(code, 1)
        self.assertIn("FAIL conflict: CQ1 needs 'fines'", out)


class ShapesSkeleton(unittest.TestCase):
    """The shapes skeleton works with pySHACL, and check_taxonomy is not meant for it."""

    def validate(self, data_ttl):
        from pyshacl import validate
        data = Graph().parse(SKELETON, format="turtle")
        data.parse(data=data_ttl, format="turtle")
        conforms, _, text = validate(data, shacl_graph=Graph().parse(SHAPES, format="turtle"))
        return conforms, text

    PREFIXES = "@prefix lib: <%s> . @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n" % LIB

    def test_valid_loan_conforms(self):
        conforms, text = self.validate(self.PREFIXES + (
            "lib:m1 a lib:Member . lib:c1 a lib:Copy .\n"
            "lib:loan1 a lib:Loan ; lib:borrower lib:m1 ; lib:loanOf lib:c1 ;"
            ' lib:dueDate "2026-11-01"^^xsd:date ; lib:loanState lib:on-loan .'))
        self.assertTrue(conforms, text)

    def test_value_from_wrong_list_fails(self):
        conforms, text = self.validate(self.PREFIXES + (
            "lib:m1 a lib:Member . lib:c1 a lib:Copy .\n"
            "lib:loan1 a lib:Loan ; lib:borrower lib:m1 ; lib:loanOf lib:c1 ;"
            ' lib:dueDate "2026-11-01"^^xsd:date ; lib:loanState lib:circulation .'))
        self.assertFalse(conforms)
        self.assertIn("LoanShape-loanState", text)

    def test_shapes_hold_blank_nodes_so_check_taxonomy_skips_them(self):
        fails = check_taxonomy.check(Graph().parse(SHAPES, format="turtle"))
        self.assertIn("blank-node", {n for n, _ in fails})


class CheckScriptSkeleton(unittest.TestCase):
    """templates/check.sh, copied into a fresh repository, behaves as its comments say."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self.env.update(GIT_PAGER="cat", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        os.makedirs(os.path.join(self.tmp, "scripts"))
        shutil.copy(os.path.join(TEMPLATES, "check.sh"), os.path.join(self.tmp, "scripts", "check.sh"))
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.org")
        self.git("config", "user.name", "test")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.tmp, env=self.env, check=True,
                       stdin=subprocess.DEVNULL, capture_output=True)

    def commit(self):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "state")

    def edit_script(self, transform):
        path = os.path.join(self.tmp, "scripts", "check.sh")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        with open(path, "w", encoding="utf-8") as f:
            f.write(transform(text))

    def run_script(self):
        return subprocess.run(["bash", "scripts/check.sh"], cwd=self.tmp, env=self.env,
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=300)

    @staticmethod
    def drop_todos(text):
        return "\n".join(l for l in text.split("\n") if not l.startswith("# TODO:"))

    def test_unfilled_skeleton_fails(self):
        self.commit()
        result = self.run_script()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("still the skeleton", result.stderr)

    def test_filled_skeleton_passes(self):
        self.edit_script(self.drop_todos)
        self.commit()
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("all checks passed", result.stdout)

    def test_write_guard_catches_a_dropped_execute_bit(self):
        tool = os.path.join(self.tmp, "tool.sh")
        with open(tool, "w") as f:
            f.write("echo hi\n")
        os.chmod(tool, 0o755)
        self.edit_script(lambda t: self.drop_todos(t).replace(
            'after="$(snapshot)"', 'chmod -x tool.sh\nafter="$(snapshot)"', 1))
        self.commit()
        os.chmod(tool, 0o755)
        result = self.run_script()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("the checks changed the working tree", result.stderr)

    def test_taxonomy_line_checks_data_and_skips_shapes(self):
        modules = os.path.join(self.tmp, "modules", "lending")
        os.makedirs(modules)
        shutil.copy(SKELETON, os.path.join(modules, "lending.ttl"))
        shutil.copy(SHAPES, os.path.join(modules, "lending-shapes.ttl"))
        os.makedirs(os.path.join(self.tmp, "scripts", "ontology"))
        shutil.copy(os.path.join(HERE, "check_taxonomy.py"), os.path.join(self.tmp, "scripts", "ontology"))
        taxonomy_line = "# TODO: find modules -name '*.ttl'"

        def fill(text):
            lines = []
            for line in text.split("\n"):
                if line.startswith(taxonomy_line):
                    lines.append(line[len("# TODO: "):])
                elif not line.startswith("# TODO:"):
                    lines.append(line)
            return "\n".join(lines)
        self.edit_script(fill)
        self.commit()
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("all checks pass", result.stdout)

        with open(os.path.join(modules, "lending.ttl"), "a", encoding="utf-8") as f:
            f.write('\nlib:Copy rdfs:comment "untagged" .\n')
        self.commit()
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAIL untagged", result.stdout)


if __name__ == "__main__":
    unittest.main()
