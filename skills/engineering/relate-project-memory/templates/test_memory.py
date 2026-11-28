#!/usr/bin/env python3
"""Tests for scripts/memory.sh, the shared Relate project memory.

Installed by the relate-project-memory skill, which replaces this file on every
update. Change the skill's template, not this copy.

Each test uses its own store in a temporary directory through
PROJECT_MEMORY_DB, except the path tests, which run a copy of the script in a
temporary git repository. No test touches the real memory.

WithoutRelate runs everywhere, CI included: help, store paths, episode
validation and the missing-relate exit. WithRelate needs the relate binary and
skips where it is not installed.
"""
import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
import unittest

def find_repo(start):
    # The installer can put this file in tests/ or scripts/; walk up to the repo.
    path = start
    while not os.path.isfile(os.path.join(path, "scripts", "memory.sh")):
        parent = os.path.dirname(path)
        if parent == path:
            raise RuntimeError("no scripts/memory.sh above " + start)
        path = parent
    return path


REPO = find_repo(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.join(REPO, "scripts")
MEMORY = os.path.join(HERE, "memory.sh")
SLOT = "pump-101/owner"


def episode(eid, at, agent, facts, **extra):
    payload = {
        "episode": {"id": eid, "session": "s-" + eid, "agent": agent,
                    "kind": "decision", "at": at, "text": "evidence for " + eid},
        "mentions": [{"key": "pump-101", "name": "Pump 101"}],
        "facts": facts,
    }
    payload.update(extra)
    return payload


def fact(fid, text, slot=SLOT, **extra):
    return {"id": fid, "text": text, "slot": slot, "about": ["pump-101"], **extra}


def git_env():
    return {k: v for k, v in os.environ.items()
            if not k.startswith("GIT_") and k != "PROJECT_MEMORY_DB"}


def copy_script(dest):
    shutil.copytree(os.path.join(HERE, "memory"), os.path.join(dest, "memory"))
    shutil.copy(MEMORY, os.path.join(dest, "memory.sh"))
    return os.path.join(dest, "memory.sh")


def make_repo(root, name):
    env = git_env()
    repo = os.path.join(root, name)
    subprocess.run(["git", "init", "-q", repo], env=env, check=True)
    script = copy_script(os.path.join(repo, "scripts"))
    git = ["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run(git + ["add", "."], env=env, check=True)
    subprocess.run(git + ["commit", "-q", "-m", "init"], env=env, check=True)
    return repo, script, git


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "memory")
        # RELATE_AGENT_MODE=1 turns on relate's agent-mode row cap wherever the
        # tests run, so the tests that guard against it bite in CI too.
        self.env = dict(git_env(), PROJECT_MEMORY_DB=self.db, TMPDIR=self.tmp.name, RELATE_AGENT_MODE="1")

    def tearDown(self):
        self.tmp.cleanup()

    def run_memory(self, *args, stdin=None, script=MEMORY, env=None):
        return subprocess.run(["bash", script, *args], input=stdin, env=env or self.env,
                              capture_output=True, text=True, timeout=60)

    def rejected(self, payload):
        p = self.run_memory("remember", "-", stdin=json.dumps(payload))
        self.assertNotEqual(p.returncode, 0, p.stdout)
        return p.stderr


class WithoutRelate(Base):
    def test_help_prints_the_whole_header(self):
        p = self.run_memory("help")
        self.assertEqual(p.returncode, 0)
        self.assertTrue(p.stdout.rstrip().endswith("Output is JSON lines."), p.stdout[-200:])
        self.assertNotIn("#", p.stdout)

    def test_missing_relate_exits_3(self):
        env = dict(self.env, PATH="/usr/bin:/bin")
        self.assertIsNone(shutil.which("relate", path=env["PATH"]))
        p = self.run_memory("recall", "pump", env=env)
        self.assertEqual(p.returncode, 3, p.stderr)
        self.assertIn("relate is not installed", p.stderr)

    def test_remember_without_a_file_is_a_usage_error(self):
        p = self.run_memory("remember")
        self.assertEqual(p.returncode, 2, p.stderr)
        self.assertIn("usage:", p.stderr)

    def test_worktrees_resolve_one_store_path(self):
        repo, main_script, git = make_repo(self.tmp.name, "repo")
        tree = os.path.join(self.tmp.name, "tree")
        subprocess.run(git + ["worktree", "add", "-q", tree], env=git_env(), check=True)
        tree_script = os.path.join(tree, "scripts", "memory.sh")
        paths = {self.run_memory("path", script=s, env=git_env()).stdout.strip()
                 for s in (main_script, tree_script)}
        self.assertEqual(paths, {os.path.join(os.path.realpath(repo), ".relate-memory")})

    def test_git_dir_in_the_environment_is_ignored(self):
        repo, script, _ = make_repo(self.tmp.name, "repo")
        other, _, _ = make_repo(self.tmp.name, "other")
        expected = os.path.join(os.path.realpath(repo), ".relate-memory") + "\n"
        for git_dir in (".git", os.path.join(other, ".git")):
            with self.subTest(git_dir):
                env = dict(git_env(), GIT_DIR=git_dir, GIT_WORK_TREE=other)
                p = self.run_memory("path", script=script, env=env)
                self.assertEqual((p.returncode, p.stdout), (0, expected), p.stderr)

    def test_store_path_outside_git_fails(self):
        script = copy_script(os.path.join(self.tmp.name, "loose"))
        env = dict(git_env(), GIT_CEILING_DIRECTORIES=self.tmp.name)
        p = self.run_memory("path", script=script, env=env)
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual(p.stdout, "")

    def test_invalid_episodes_are_rejected_before_any_write(self):
        good = fact("f1", "A fact.")
        at = "2026-11-27T10:00:00Z"
        kind = lambda k: dict(episode("e1", at, "pi", [good]),
                              episode={"id": "e1", "session": "s", "agent": "pi",
                                       "kind": k, "at": at, "text": "t"})
        cases = {
            "episode.agent: missing string": {"episode": {"id": "x"}, "facts": [good]},
            "facts: needs at least one fact": episode("e1", at, "pi", []),
            "episode.at: not a UTC": episode("e1", "yesterday", "pi", [good]),
            "facts[0].validFrom: not a UTC": episode("e1", at, "pi", [fact("f1", "A fact.", validFrom="2026-11-27")]),
            "facts[0].validFrom: not a UTC ": episode("e1", at, "pi", [fact("f1", "A fact.", validFrom="2026-13-45T10:00:00Z")]),
            "facts[0].validFrom: not a UTC  ": episode("e1", at, "pi", [fact("f1", "A fact.", validFrom="2026-11-27T10:00:00.0000001Z")]),
            "episode.at: not a UTC ": episode("e1", "2026-11-27T10:00:00+99:99", "pi", [good]),
            "episode.at: not a UTC  ": episode("e1", "2026-11-27T10:00:00+18:30", "pi", [good]),
            "episode.at: not a UTC   ": episode("e1", "٢٠٢٦-11-27T10:00:00Z", "pi", [good]),
            "episode.kind: one of": kind("musing"),
            "episode.kind: one of ": kind(["decision"]),
            "mentions: not a list": episode("e1", at, "pi", [good], mentions=None),
            "mentions[0].key: lowercase entity key": episode("e1", at, "pi", [good], mentions=[{"key": " ", "name": "x"}]),
            "facts[0].about: needs": episode("e1", at, "pi", [dict(good, about=[])]),
            "facts[0].about[0]: lowercase ": episode("e1", at, "pi", [dict(good, about=[""])]),
            "facts[1].slot: repeats": episode("e1", at, "pi", [good, fact("f2", "Same slot.")]),
            "facts[0].slot: lowercase": episode("e1", at, "pi", [fact("f1", "A fact.", slot="Memory/Setup")]),
            "facts[0].slot: lowercase ": episode("e1", at, "pi", [fact("f1", "A fact.", slot="nosegment")]),
            "mentions[0].key: lowercase": episode("e1", at, "pi", [good], mentions=[{"key": " TRUE ", "name": "x"}]),
            "facts[0].about[0]: lowercase": episode("e1", at, "pi", [dict(good, about=["Pump 101"])]),
            "episode.at: in the future": episode("e1", "2999-01-01T00:00:00Z", "pi", [good]),
            "facts[0].validFrom: after episode.at": episode("e1", at, "pi", [fact("f1", "A plan.", validFrom="2026-11-28T00:00:00Z")]),
            "facts[1].id: repeats": episode("e1", at, "pi", [good, fact("f1", "Other slot.", slot="x/y")]),
        }
        for message, payload in cases.items():
            with self.subTest(message):
                stderr = self.rejected(payload)
                self.assertIn(message.strip(), stderr)
                self.assertNotIn("Traceback", stderr)
                self.assertFalse(os.path.exists(self.db))
        self.assertEqual([f for f in os.listdir(self.tmp.name) if f.startswith("project-memory.")], [])

    def test_non_json_constants_are_rejected_before_any_write(self):
        for constant in ("NaN", "Infinity", "-Infinity", "1e309", "-1e309", '"\\ud800"'):
            with self.subTest(constant):
                body = json.dumps(episode("e1", "2026-11-27T10:00:00Z", "pi", [fact("f1", "A fact.")]))
                p = self.run_memory("remember", "-", stdin=body[:-1] + ', "confidence": ' + constant + "}")
                self.assertNotEqual(p.returncode, 0)
                self.assertIn("is not readable JSON", p.stderr)
                self.assertNotIn("Traceback", p.stderr)
                self.assertFalse(os.path.exists(self.db))


@unittest.skipUnless(shutil.which("relate"), "relate is not installed")
class WithRelate(Base):
    def remember(self, payload):
        p = self.run_memory("remember", "-", stdin=json.dumps(payload))
        self.assertEqual(p.returncode, 0, p.stderr)
        return p

    def rows(self, *args):
        p = self.run_memory(*args)
        self.assertEqual(p.returncode, 0, p.stderr)
        return [json.loads(line) for line in p.stdout.splitlines() if line.startswith("{")]

    def cypher(self, statement, read_only=False):
        args = ["relate", "query", "--database", self.db, "--mode", "jsonl", statement]
        if read_only:
            args.insert(4, "--read-only")
        p = subprocess.run(args, capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        return [json.loads(line) for line in p.stdout.splitlines() if line.startswith("{")]

    def assert_check_passes(self):
        p = self.run_memory("check")
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_reads_and_check_before_init_report_no_memory(self):
        for args in (("recall", "pump"), ("check",)):
            with self.subTest(args):
                p = self.run_memory(*args)
                self.assertEqual(p.returncode, 0)
                self.assertIn("no memory yet", p.stderr)
                self.assertEqual(p.stdout, "")

    def test_correction_supersedes_and_keeps_history(self):
        self.remember(episode("e1", "2026-11-27T10:00:00Z", "claude-code",
                              [fact("f1", "The maintenance lead owns pump 101.")]))
        self.remember(episode("e2", "2026-11-27T11:00:00Z", "codex",
                              [fact("f2", "The shift engineer owns pump 101.")]))

        current = self.rows("recall", "pump", "owns")
        self.assertEqual([r["memory"] for r in current], ["The shift engineer owns pump 101."])
        self.assertEqual((current[0]["agent"], current[0]["episode"]), ("codex", "e2"))
        self.assertEqual(current[0]["evidence"], "evidence for e2")

        history = self.rows("history", SLOT)
        self.assertEqual([h["episode"] for h in history], ["e2", "e1"])
        self.assertIsNone(history[0]["closed"])
        self.assertIsNotNone(history[1]["closed"])

        self.assertEqual([r["episode"] for r in self.rows("about", "pump-101")], ["e2"])
        self.assert_check_passes()

    def test_later_write_wins_whatever_the_learned_time(self):
        self.remember(episode("e1", "2026-11-27T11:05:00Z", "codex", [fact("f1", "Newer by clock.")]))
        self.remember(episode("e2", "2026-11-27T11:00:00Z", "kimi", [fact("f2", "Written later.")]))
        self.assertEqual([r["memory"] for r in self.rows("brief")], ["Written later."])
        self.assert_check_passes()

    def test_a_closed_range_never_ends_before_it_starts(self):
        self.remember(episode("e1", "2026-11-27T11:05:00Z", "codex", [fact("f1", "Learned first.")]))
        self.remember(episode("e2", "2026-11-27T10:00:00Z", "kimi", [fact("f2", "True since earlier.")]))
        closed = [h for h in self.rows("history", SLOT) if h["closed"]]
        self.assertEqual(len(closed), 1)
        self.assertGreaterEqual(closed[0]["validTo"], closed[0]["validFrom"])

    def test_replaying_episodes_changes_nothing(self):
        first = episode("e1", "2026-11-27T10:00:00Z", "claude-code", [fact("f1", "First value.")])
        second = episode("e2", "2026-11-27T10:00:00Z", "codex", [fact("f2", "Second value.")])
        for payload in (first, second, first, second):
            self.remember(payload)
        self.assertEqual([r["memory"] for r in self.rows("brief")], ["Second value."])
        self.assertEqual(len(self.rows("history", SLOT)), 2)
        self.assert_check_passes()

    def test_accepted_datetimes_are_ones_relate_parses(self):
        for i, at in enumerate(("2026-11-20T10:00Z", "2026-11-20T10:00:00+18:00",
                                "2026-11-20T10:00:00-18:00", "2026-11-20T10:00:00.123456Z")):
            with self.subTest(at):
                self.remember(episode(f"e{i}", at, "pi", [fact(f"f{i}", f"At {at}.", slot=f"time/{i}")]))
        self.assert_check_passes()

    def test_brief_orders_newest_first_and_validates_n(self):
        for i in range(3):
            self.remember(episode(f"e{i}", "2026-11-27T10:00:00Z", "pi",
                                  [fact(f"f{i}", f"Fact {i}.", slot=f"test/slot-{i}")]))
        self.assertEqual([r["memory"] for r in self.rows("brief", "2")], ["Fact 2.", "Fact 1."])
        for bad in ("", "0", "-1", "two", "1; MATCH (n) DETACH DELETE n"):
            with self.subTest(bad):
                self.assertEqual(self.run_memory("brief", bad).returncode, 2)

    def test_capped_reads_say_when_they_cut_and_relate_adds_no_cap(self):
        self.remember(episode("e1", "2026-11-27T10:00:00Z", "pi", [fact("f1", "Seed.")]))
        self.cypher("MATCH (ep:Episode {id: 'e1'}) MATCH (e:Entity {key: 'pump-101'}) "
                    "UNWIND range(1, 510) AS i "
                    "CREATE (f:Fact:CurrentFact {id: 'bulk-' + toString(i), slot: 'bulk/s' + toString(i), "
                    "text: 'Bulk ' + toString(i), recordedAt: datetime()})-[:FROM]->(ep), (f)-[:ABOUT]->(e)")
        self.cypher("MATCH (ep:Episode {id: 'e1'}) UNWIND range(1, 104) AS i "
                    "CREATE (:Fact {id: 'old-' + toString(i), slot: $slot, text: 'Old', closedAt: datetime(), "
                    "recordedAt: datetime() - duration({days: i})})-[:FROM]->(ep)".replace("$slot", repr(SLOT)))
        for args, cap in ((("history", SLOT), 100), (("about", "pump-101"), 100), (("slots",), 500)):
            with self.subTest(args):
                p = self.run_memory(*args)
                self.assertEqual(p.returncode, 0, p.stderr)
                rows = [line for line in p.stdout.splitlines() if line.startswith("{")]
                self.assertEqual(len(rows), cap)
                self.assertNotIn("rowCap", p.stdout)
                self.assertIn(f"showing the first {cap} rows; more exist", p.stderr)
        p = self.run_memory("brief", "300")
        self.assertEqual(len([line for line in p.stdout.splitlines() if line.startswith("{")]), 300)
        self.assertNotIn("rowCap", p.stdout)
        p = self.run_memory("history", "unit/none")
        self.assertEqual((p.stdout, "more exist" in p.stderr), ("", False))

    def test_asof_answers_what_agents_believed_then(self):
        self.remember(episode("e1", "2026-01-01T00:00:00Z", "pi", [fact("f1", "First belief.")]))
        time.sleep(0.05)
        self.remember(episode("e2", "2026-02-01T00:00:00Z", "pi", [fact("f2", "Corrected belief.")]))
        recorded = {h["episode"]: h["recorded"] for h in self.rows("history", SLOT)}
        self.assertEqual([r["memory"] for r in self.rows("asof", recorded["e1"])], ["First belief."])
        self.assertEqual([r["memory"] for r in self.rows("asof", recorded["e2"])], ["Corrected belief."])
        today = recorded["e2"][:10]
        self.assertEqual([r["memory"] for r in self.rows("asof", today)], ["Corrected belief."])
        self.assertEqual(self.rows("asof", "2000-01-01"), [])
        self.assertEqual(self.run_memory("asof", "2026-11-27T10:00:00.123456789Z").returncode, 0)
        self.assertTrue(recorded["e2"].endswith("Z"), recorded["e2"])
        self.assertEqual([r["memory"] for r in self.rows("asof", "9999-12-31")], ["Corrected belief."])
        self.assertEqual([r["memory"] for r in self.rows("asof", "9999-12-31T23:59:59.999999Z")], ["Corrected belief."])
        for bad in ("", "yesterday", "2026-13-01", "2026-02-30", "2026-11-27T10:00:00", "2026-11-27 10:00Z",
                    "2026-11-27T10:00:00+18:30", ("2026-11-27", "10:00Z")):
            with self.subTest(bad):
                p = self.run_memory("asof", *(bad if isinstance(bad, tuple) else (bad,)))
                self.assertEqual(p.returncode, 2, p.stderr)
                self.assertIn("usage:", p.stderr)

    def test_asof_follows_the_recipe_for_a_change_planned_ahead(self):
        # The cookbook's payments case: the move to us-east-1 is recorded on
        # 20 February and valid from 1 March, so on 25 February the log still
        # believed eu-west-1, even though its record was already closed.
        self.assertEqual(self.run_memory("init").returncode, 0)
        self.cypher("CREATE (ep:Episode {id: 'e1', agent: 'pi', text: 'x', at: datetime('2024-01-01T09:00:00Z')}) "
                    "CREATE (:Fact {id: 'd3', slot: 'payments/region', text: 'payments runs in eu-west-1', "
                    "validFrom: datetime('2024-01-01T00:00:00Z'), validTo: datetime('2024-03-01T00:00:00Z'), "
                    "recordedAt: datetime('2024-01-01T09:00:00Z'), closedAt: datetime('2024-02-20T09:00:00Z')})-[:FROM]->(ep) "
                    "CREATE (:Fact:CurrentFact {id: 'd8', slot: 'payments/region', text: 'payments runs in us-east-1', "
                    "validFrom: datetime('2024-03-01T00:00:00Z'), recordedAt: datetime('2024-02-20T09:00:00Z')})-[:FROM]->(ep)")
        for when, believed in (("2024-02-10", ["payments runs in eu-west-1"]),
                               ("2024-02-25", ["payments runs in eu-west-1"]),
                               ("2024-02-25T00:00:00Z", ["payments runs in eu-west-1"]),
                               ("2024-03-05", ["payments runs in us-east-1"]),
                               ("2023-12-31", [])):
            with self.subTest(when):
                self.assertEqual([r["memory"] for r in self.rows("asof", when)], believed)

    def test_asof_gives_one_belief_per_slot_on_older_stores(self):
        # Stores written before future-dated facts were refused can hold a plan
        # replaced by an earlier change; asof must still give one belief per slot.
        self.assertEqual(self.run_memory("init").returncode, 0)
        self.cypher("CREATE (ep:Episode {id: 'e1', agent: 'pi', text: 'x', at: datetime('2024-01-01T09:00:00Z')}) "
                    "CREATE (:Fact {id: 'f1', slot: 'region/now', text: 'eu-west-1', "
                    "validFrom: datetime('2024-01-01T00:00:00Z'), validTo: datetime('2024-03-01T00:00:00Z'), "
                    "recordedAt: datetime('2024-01-01T09:00:00Z'), closedAt: datetime('2024-02-20T09:00:00Z')})-[:FROM]->(ep) "
                    "CREATE (:Fact:CurrentFact {id: 'f3', slot: 'region/now', text: 'us-west-2', "
                    "validFrom: datetime('2024-02-22T00:00:00Z'), recordedAt: datetime('2024-02-22T09:00:00Z')})-[:FROM]->(ep)")
        self.assertEqual([r["memory"] for r in self.rows("asof", "2024-02-25")], ["us-west-2"])

    def test_asof_by_date_respects_zone_offsets(self):
        self.assertEqual(self.run_memory("init").returncode, 0)
        # B starts at 20:00 Chicago time on the 27th, which is 02:00 UTC on the 28th.
        self.cypher("CREATE (ep:Episode {id: 'e1', agent: 'pi', text: 'x', at: datetime('2026-11-01T00:00:00Z')}) "
                    "CREATE (:Fact {id: 'a', slot: 'zone/test', text: 'Before.', "
                    "validFrom: datetime('2026-11-01T00:00:00Z'), validTo: datetime('2026-11-27T20:00:00-06:00'), "
                    "recordedAt: datetime('2026-11-01T00:00:00Z'), closedAt: datetime('2026-11-27T18:00:00Z')})-[:FROM]->(ep) "
                    "CREATE (:Fact:CurrentFact {id: 'b', slot: 'zone/test', text: 'After.', "
                    "validFrom: datetime('2026-11-27T20:00:00-06:00'), recordedAt: datetime('2026-11-27T18:00:00Z')})-[:FROM]->(ep)")
        self.assertEqual([r["memory"] for r in self.rows("asof", "2026-11-27")], ["Before."])
        self.assertEqual([r["memory"] for r in self.rows("asof", "2026-11-28")], ["After."])

    def test_asof_by_day_keeps_a_fact_closed_on_a_later_day(self):
        self.assertEqual(self.run_memory("init").returncode, 0)
        self.cypher("CREATE (ep:Episode {id: 'e1', agent: 'pi', text: 'x', at: datetime('2026-11-20T00:00:00Z')}) "
                    "CREATE (:Fact {id: 'old', slot: 'day/test', text: 'Closed next day.', "
                    "validFrom: datetime('2026-11-20T00:00:00Z'), validTo: datetime('2026-11-26T00:00:00Z'), "
                    "recordedAt: datetime('2026-11-25T08:00:00Z'), closedAt: datetime('2026-11-26T00:00:00Z')})-[:FROM]->(ep) "
                    "CREATE (:Fact {id: 'same', slot: 'day/same', text: 'Closed same day.', "
                    "validFrom: datetime('2026-11-20T00:00:00Z'), validTo: datetime('2026-11-25T23:59:59.999999999Z'), "
                    "recordedAt: datetime('2026-11-25T08:00:00Z'), closedAt: datetime('2026-11-25T23:59:59.999999999Z')})-[:FROM]->(ep)")
        self.assertEqual([r["memory"] for r in self.rows("asof", "2026-11-25")], ["Closed next day."])
        self.assertEqual(self.rows("asof", "2026-11-26"), [])
        self.assertEqual([r["memory"] for r in self.rows("asof", "2026-11-25T12:00:00Z")], ["Closed same day.", "Closed next day."])

    def test_extra_arguments_are_usage_errors(self):
        self.remember(episode("e1", "2026-11-27T10:00:00Z", "pi", [fact("f1", "A fact.")]))
        for args in (("about", "pump-101", "x"), ("history", SLOT, "x"), ("brief", "5", "x"),
                     ("slots", "x"), ("check", "x"), ("path", "x"), ("init", "x"), ("remember", "-", "x")):
            with self.subTest(args):
                p = self.run_memory(*args)
                self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
                self.assertIn("usage:", p.stderr)

    def test_time_rule_boundaries(self):
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        iso = lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ")
        cases = {
            "validFrom equal to at": (episode("e1", "2026-11-20T10:00:00Z", "pi",
                                              [fact("f1", "Same.", validFrom="2026-11-20T10:00:00Z")]), True),
            "at four and a half minutes ahead": (episode("e2", iso(now + timedelta(minutes=4, seconds=30)), "pi",
                                                         [fact("f2", "Clock skew.", slot="skew/ok")]), True),
            "at five and a half minutes ahead": (episode("e3", iso(now + timedelta(minutes=5, seconds=30)), "pi",
                                             [fact("f3", "Too far.", slot="skew/no")]), "episode.at: in the future"),
            "validFrom with nanoseconds": (episode("e5", "2026-11-20T10:00:00Z", "pi",
                                                   [fact("f5", "Fine.", slot="nano/no", validFrom="2026-11-20T10:00:00.000000999Z")]),
                                           "facts[0].validFrom: not a UTC"),
            "validFrom one second after at": (episode("e4", "2026-11-20T10:00:00Z", "pi",
                                                      [fact("f4", "Later.", slot="later/no", validFrom="2026-11-20T10:00:01Z")]),
                                              "facts[0].validFrom: after episode.at"),
        }
        for name, (payload, expected) in cases.items():
            with self.subTest(name):
                p = self.run_memory("remember", "-", stdin=json.dumps(payload))
                self.assertNotIn("Traceback", p.stderr)
                if expected is True:
                    self.assertEqual(p.returncode, 0, p.stderr)
                else:
                    self.assertEqual(p.returncode, 1, p.stderr)
                    self.assertIn(expected, p.stderr)

    def test_a_save_that_supersedes_many_slots_prints_every_row(self):
        # remember prints one row per replaced slot; relate's agent-mode cap of
        # 100 rows must not cut that output.
        n = 120
        first = episode("e1", "2026-11-20T10:00:00Z", "pi",
                        [fact(f"a{i}", f"Old {i}.", slot=f"bulk/s{i}") for i in range(n)])
        second = episode("e2", "2026-11-21T10:00:00Z", "pi",
                         [fact(f"b{i}", f"New {i}.", slot=f"bulk/s{i}") for i in range(n)])
        self.remember(first)
        p = self.remember(second)
        self.assertEqual(sum(1 for line in p.stdout.splitlines() if '"replaced"' in line), n)
        self.assertNotIn("rowCap", p.stdout)

    def test_string_parameters_stay_strings(self):
        self.remember(episode("e1", "2026-11-27T10:00:00Z", "cursor",
                              [{"id": "f1", "text": "Flag 42 is true.", "slot": "true/42", "about": ["true"]}],
                              mentions=[]))
        self.assertEqual(len(self.rows("about", "true")), 1)
        self.assertEqual(len(self.rows("history", "true/42")), 1)
        self.assertEqual(len(self.rows("recall", "42")), 1)

    def test_missing_arguments_are_usage_errors(self):
        self.remember(episode("e1", "2026-11-27T10:00:00Z", "pi", [fact("f1", "A fact.")]))
        for args in (("about",), ("about", ""), ("history",), ("history", ""),
                     ("recall",), ("recall", ""), ("recall", " "), ("recall", "", "")):
            with self.subTest(args):
                p = self.run_memory(*args)
                self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
                self.assertIn("usage:", p.stderr)

    def test_fact_id_reused_by_another_episode_is_rejected(self):
        self.remember(episode("e1", "2026-11-27T10:00:00Z", "pi", [fact("f1", "Original.")]))
        stderr = self.rejected(episode("e2", "2026-11-27T11:00:00Z", "pi", [fact("f1", "Reused id.")]))
        self.assertIn("fact id belongs to episode e1", stderr)
        self.assertEqual([r["memory"] for r in self.rows("brief")], ["Original."])

    def test_episode_id_reused_for_different_content_is_rejected(self):
        self.remember(episode("e1", "2026-11-27T10:00:00Z", "pi", [fact("f1", "Original.")]))
        stderr = self.rejected(episode("e1", "2026-11-27T10:00:00Z", "pi", [fact("f2", "Sneaked in.")]))
        self.assertIn("episode id already used for different content", stderr)
        self.assertEqual(len(self.rows("history", SLOT)), 1)

    def test_orphan_fact_id_is_not_reused(self):
        self.assertEqual(self.run_memory("init").returncode, 0)
        self.cypher("CREATE (:Fact {id: 'f1', text: 'written by hand'})")
        stderr = self.rejected(episode("e1", "2026-11-27T10:00:00Z", "pi", [fact("f1", "Merged on?")]))
        self.assertIn("fact id belongs to episode (none)", stderr)
        p = self.run_cypher_script(dict(episode("e1", "2026-11-27T10:00:00Z", "pi", [fact("f1", "Raced.")]),
                                        fingerprint="x"))
        self.assertIn("by zero", p.stdout + p.stderr)

    def test_creator_killed_mid_build_leaves_nothing_in_the_way(self):
        # A slow relate keeps the first writer inside its build long enough to kill it.
        slow = os.path.join(self.tmp.name, "bin")
        os.makedirs(slow)
        real = shutil.which("relate")
        with open(os.path.join(slow, "relate"), "w") as fh:
            # Build first, then linger, so the kill lands while the build folder exists.
            fh.write(f"#!/bin/bash\n{real} \"$@\"\nstatus=$?\nsleep 3\nexit $status\n")
        os.chmod(os.path.join(slow, "relate"), 0o755)
        env = dict(self.env, PATH=slow + os.pathsep + self.env["PATH"])
        builds = lambda: [f for f in os.listdir(self.tmp.name) if f.startswith("memory.init.")]
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGKILL):
            with self.subTest(sig.name):
                shutil.rmtree(self.db, ignore_errors=True)
                proc = subprocess.Popen(["bash", MEMORY, "init"], env=env, start_new_session=True,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(1.5)
                self.assertEqual(len(builds()), 1, "the build folder should exist mid-build")
                os.killpg(proc.pid, sig)  # the whole group, as Ctrl-C or a closed terminal would
                proc.wait(timeout=30)
                # The kill must land before the rename: no store, and a failed exit.
                expected = {signal.SIGINT: 130, signal.SIGTERM: 143, signal.SIGHUP: 129}.get(sig, -sig)
                self.assertEqual(proc.returncode, expected, sig.name)
                self.assertFalse(os.path.exists(self.db), "the killed creator must not finish the store")
                if self._group_alive(proc.pid):
                    os.killpg(proc.pid, signal.SIGKILL)
                if sig is not signal.SIGKILL:
                    self.assertEqual(builds(), [], f"the trap removes the build on {sig.name}")
                start = time.monotonic()
                p = self.run_memory("init")
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertLess(time.monotonic() - start, 10)
                self.assert_check_passes()

    @staticmethod
    def _group_alive(pgid):
        try:
            os.killpg(pgid, 0)
            return True
        except ProcessLookupError:
            return False

    def make_build(self, path, hours_old):
        os.makedirs(path)
        when = time.time() - hours_old * 3600
        os.utime(path, (when, when))
        return path

    def test_old_builds_are_swept_on_every_init_and_fresh_ones_kept(self):
        self.assertEqual(self.run_memory("init").returncode, 0)
        old = self.make_build(self.db + ".init.111.1", 2)
        fresh = self.make_build(self.db + ".init.222.2", 0)
        self.assertEqual(self.run_memory("init").returncode, 0)
        self.assertFalse(os.path.exists(old))
        self.assertTrue(os.path.exists(fresh))

    def test_sweep_matches_the_store_name_literally_and_through_a_symlink(self):
        real = os.path.join(self.tmp.name, "real")
        os.makedirs(real)
        link = os.path.join(self.tmp.name, "link")
        os.symlink(real, link)
        db = os.path.join(link, "mem[1]")
        own = self.make_build(os.path.join(real, "mem[1].init.111.1"), 2)
        other = self.make_build(os.path.join(real, "mem1.init.111.1"), 2)
        p = self.run_memory("init", env=dict(self.env, PROJECT_MEMORY_DB=db))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertFalse(os.path.exists(own))
        self.assertTrue(os.path.exists(other))
        self.assertTrue(os.path.isdir(real))

    def test_waiters_never_fail_while_another_creates_the_store(self):
        for _ in range(5):
            shutil.rmtree(self.db, ignore_errors=True)
            procs = [subprocess.Popen(["bash", MEMORY, "init"], env=self.env, stdout=subprocess.DEVNULL,
                                      stderr=subprocess.PIPE, text=True) for _ in range(6)]
            for proc in procs:
                _, err = proc.communicate(timeout=60)
                self.assertEqual(proc.returncode, 0, err)
        self.assert_check_passes()

    def test_trailing_slash_and_missing_parent_are_handled(self):
        for db in (self.db + "/", os.path.join(self.tmp.name, "new", "dir", "memory")):
            with self.subTest(db):
                start = time.monotonic()
                p = self.run_memory("init", env=dict(self.env, PROJECT_MEMORY_DB=db))
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertLess(time.monotonic() - start, 10)
                self.assertTrue(os.path.isdir(db.rstrip("/")))

    def test_episode_without_a_fingerprint_is_not_reused(self):
        self.assertEqual(self.run_memory("init").returncode, 0)
        self.cypher("CREATE (:Episode {id: 'e1', text: 'written by hand'})")
        stderr = self.rejected(episode("e1", "2026-11-27T10:00:00Z", "pi", [fact("f1", "Merged on?")]))
        self.assertIn("episode id already used for different content", stderr)
        p = self.run_cypher_script(dict(episode("e1", "2026-11-27T10:00:00Z", "pi", [fact("f1", "Raced.")]),
                                        fingerprint="x"))
        self.assertIn("by zero", p.stdout + p.stderr)

    def run_cypher_script(self, payload):
        # Run remember.cypher straight through relate, past the script's own
        # checks, as a writer that raced another would.
        path = os.path.join(self.tmp.name, "race.json")
        with open(path, "w") as fh:
            json.dump(payload, fh)
        with open(os.path.join(HERE, "memory", "remember.cypher")) as script:
            return subprocess.run(["relate", "query", "--database", self.db, "--mode", "jsonl",
                                   "--fetch-params", "m=" + path], stdin=script,
                                  capture_output=True, text=True, timeout=30)

    def test_guards_inside_the_transaction_roll_back_the_episode(self):
        self.remember(episode("e0", "2026-11-27T09:00:00Z", "pi", [fact("f0", "Kept.", slot="keep/me")]))
        stolen_fact = episode("e1", "2026-11-27T10:00:00Z", "pi",
                              [fact("f1", "New fact.", slot="new/slot"), fact("f0", "Stolen id.", slot="other/slot")],
                              fingerprint="x")
        stolen_episode = episode("e0", "2026-11-27T09:00:00Z", "pi",
                                 [fact("f9", "Sneaked in.", slot="new/slot")], fingerprint="y")
        for name, payload in (("fact guard", stolen_fact), ("episode guard", stolen_episode)):
            with self.subTest(name):
                p = self.run_cypher_script(payload)
                self.assertNotEqual(p.returncode, 0)
                self.assertIn("by zero", p.stdout + p.stderr)
                self.assertEqual([r["slot"] for r in self.rows("slots")], ["keep/me"])
        self.assertEqual(self.cypher("MATCH (e:Episode {id: 'e1'}) RETURN count(e) AS n", True), [{"n": 0}])
        self.assert_check_passes()

    def test_check_fails_on_each_kind_of_corruption(self):
        corruptions = {
            "two current facts": "MATCH (ep:Episode {id: 'e1'}) CREATE (:Fact:CurrentFact {id: 'x', slot: 'corrupt/slot', text: 't'})-[:FROM]->(ep)",
            "no current fact": "MATCH (f:Fact {id: 'f1'}) SET f.closedAt = datetime() REMOVE f:CurrentFact",
            "closed but still labelled": "MATCH (f:Fact {id: 'f1'}) SET f.closedAt = datetime()",
            "open but unlabelled": "MATCH (f:Fact {id: 'f1'}) REMOVE f:CurrentFact",
            "no source episode": "MATCH (f:Fact {id: 'f1'})-[r:FROM]->() DELETE r",
            "two source episodes": "MATCH (f:Fact {id: 'f1'}) CREATE (f)-[:FROM]->(:Episode {id: 'e9'})",
            "current label without Fact": "MATCH (ep:Episode {id: 'e1'}) CREATE (:CurrentFact {id: 'y', slot: 'corrupt/slot', text: 't'})-[:FROM]->(ep)",
            "superseded fact keeps its label": "MATCH (ep:Episode {id: 'e1'}) CREATE (:Fact:CurrentFact {id: 'old', slot: 'corrupt/slot', text: 't', closedAt: datetime()})-[:FROM]->(ep)",
            "fact without a slot": "MATCH (ep:Episode {id: 'e1'}) CREATE (:Fact:CurrentFact {id: 'z', text: 't'})-[:FROM]->(ep)",
        }
        for name, statement in corruptions.items():
            with self.subTest(name):
                shutil.rmtree(self.db, ignore_errors=True)
                self.remember(episode("e1", "2026-11-27T10:00:00Z", "pi", [fact("f1", "Base fact.", slot="corrupt/slot")]))
                self.assert_check_passes()
                self.cypher(statement)
                p = self.run_memory("check")
                self.assertEqual(p.returncode, 1, name + ": " + p.stdout + p.stderr)
                self.assertIn("slots without exactly one current fact", p.stderr)
                if name in ("current label without Fact", "superseded fact keeps its label"):
                    # These keep one current Fact and one source, so only the label check can catch them.
                    self.assertIn('"current":1,"mislabelled":1,"badSources":0', p.stderr)

    def test_locked_store_is_retried(self):
        self.assertEqual(self.run_memory("init").returncode, 0)
        holder = subprocess.Popen(["relate", "query", "--database", self.db, "--mode", "jsonl"],
                                  stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL, text=True)
        try:
            holder.stdin.write("CREATE (:Holder);\n")
            holder.stdin.flush()
            time.sleep(1)
            writer = subprocess.Popen(["bash", MEMORY, "remember", "-"], stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      env=self.env, text=True)
            writer.stdin.write(json.dumps(episode("e1", "2026-11-27T10:00:00Z", "pi",
                                                  [fact("f1", "Waited for the lock.")])))
            writer.stdin.close()
            writer.stdin = None
            time.sleep(2)
            self.assertIsNone(writer.poll(), "the writer should still be retrying")
        finally:
            holder.stdin.close()
            holder.stdin = None
            holder.wait(timeout=30)
        _, err = writer.communicate(timeout=60)
        self.assertEqual(writer.returncode, 0, err)
        self.assertEqual([r["memory"] for r in self.rows("brief")], ["Waited for the lock."])

    def concurrent(self, payloads):
        procs = []
        for payload in payloads:
            proc = subprocess.Popen(["bash", MEMORY, "remember", "-"], stdin=subprocess.PIPE,
                                    env=self.env, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True)
            proc.stdin.write(json.dumps(payload))
            proc.stdin.close()
            proc.stdin = None
            procs.append(proc)
        for proc in procs:
            _, err = proc.communicate(timeout=60)
            self.assertEqual(proc.returncode, 0, err)

    def test_concurrent_first_writers_all_land(self):
        self.concurrent([episode(f"e{i}", f"2026-11-27T1{i}:00:00Z", f"agent-{i}",
                                 [fact(f"f{i}", f"Fact number {i}.", slot=f"test/slot-{i}")])
                         for i in range(4)])
        self.assertEqual(len(self.rows("slots")), 4)
        self.assert_check_passes()

    def test_concurrent_writers_to_one_slot_leave_one_current_fact(self):
        self.concurrent([episode(f"e{i}", "2026-11-27T10:00:00Z", f"agent-{i}",
                                 [fact(f"f{i}", f"Value {i}.")]) for i in range(4)])
        self.assertEqual(len(self.rows("brief")), 1)
        self.assertEqual(len(self.rows("history", SLOT)), 4)
        self.assert_check_passes()

    def test_worktrees_share_one_store(self):
        repo, main_script, git = make_repo(self.tmp.name, "repo")
        tree = os.path.join(self.tmp.name, "tree")
        subprocess.run(git + ["worktree", "add", "-q", tree], env=git_env(), check=True)
        payload = json.dumps(episode("e1", "2026-11-27T10:00:00Z", "pi", [fact("f1", "Shared.")]))
        p = self.run_memory("remember", "-", stdin=payload,
                            script=os.path.join(tree, "scripts", "memory.sh"), env=git_env())
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("Shared.", self.run_memory("brief", script=main_script, env=git_env()).stdout)

    def test_dropbox_conflicted_copies_stop_saves_and_warn_reads(self):
        self.remember(episode("e1", "2026-11-27T10:00:00Z", "pi", [fact("f1", "Before the conflict.")]))
        conflict = os.path.join(self.db, "manifest (Laptop's conflicted copy 2026-11-28).json")
        with open(conflict, "w") as fh:
            fh.write("{}")
        p = self.run_memory("remember", "-", stdin=json.dumps(
            episode("e2", "2026-11-27T11:00:00Z", "pi", [fact("f2", "After the conflict.")])))
        self.assertEqual(p.returncode, 4, p.stderr)
        self.assertIn("conflicted copies", p.stderr)
        self.assertEqual(self.run_memory("check").returncode, 4)
        p = self.run_memory("brief")
        self.assertEqual(p.returncode, 0)
        self.assertIn("warning: Dropbox conflicted copies", p.stderr)
        os.remove(conflict)
        self.assertEqual([r["memory"] for r in self.rows("brief")], ["Before the conflict."])
        self.assert_check_passes()

    def test_many_conflicted_copies_still_exit_4(self):
        self.assertEqual(self.run_memory("init").returncode, 0)
        for i in range(3000):
            open(os.path.join(self.db, f"part (Laptop's conflicted copy {i:04d}).bin"), "w").close()
        for args in (("check",), ("init",)):
            with self.subTest(args):
                p = self.run_memory(*args)
                self.assertEqual(p.returncode, 4, p.stderr[-300:])
                self.assertEqual(p.stderr.count("conflicted copy"), 20)

    def test_conflicts_are_found_through_a_symlinked_store(self):
        self.assertEqual(self.run_memory("init").returncode, 0)
        open(os.path.join(self.db, "manifest (Laptop's conflicted copy).json"), "w").close()
        link = os.path.join(self.tmp.name, "linked")
        os.symlink(self.db, link)
        p = self.run_memory("check", env=dict(self.env, PROJECT_MEMORY_DB=link))
        self.assertEqual(p.returncode, 4, p.stderr)

    def test_mcp_server_serves_the_store_read_only(self):
        self.remember(episode("e1", "2026-11-27T10:00:00Z", "pi", [fact("f1", "Served.")]))
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ]
        p = subprocess.run(["relate", "serve", "--mcp", "stdio", "--database", self.db, "--read-only=live"],
                           input="".join(json.dumps(m) + "\n" for m in messages),
                           capture_output=True, text=True, timeout=30)
        self.assertIn('"read_cypher"', p.stdout, p.stderr)

    def test_skill_example_runs_as_written(self):
        skill = os.path.join(REPO, ".agents", "skills", "project-memory", "SKILL.md")
        with open(skill, encoding="utf-8") as fh:
            body = fh.read()
        example = body.split("<<'JSON'\n", 1)[1].split("\nJSON\n", 1)[0]
        p = self.run_memory("remember", "-", stdin=example)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("memory: saved episode", p.stdout)


if __name__ == "__main__":
    unittest.main()
