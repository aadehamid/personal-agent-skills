"""Regression tests. Most cases are bugs that were actually hit while validating
the knowledge-management corpus by hand; the test names say which."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from kb import checks, citers, config, coverage, dupes, quotes
from kb import vault as V
from kb.cli import app


# ---------------------------------------------------------------- fixtures

def write(p: Path, text: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def raw(vault: Path, name: str, url: str, body: str = "body text", refs: list[str] | None = None,
        quote_url: bool = True) -> Path:
    u = f'"{url}"' if quote_url else url
    r = "wiki_refs: []\n" if not refs else "wiki_refs:\n" + "".join(f"  - {x}\n" for x in refs)
    return write(vault / "Raw" / name,
                 f"---\nurl: {u}\ntitle: T\ntype: Source\nfetch_status: ingested\n{r}---\n\n{body}\n")


def page(vault: Path, rel: str, body: str, sources: list[str] | None = None) -> Path:
    src = "".join(f"  - id: s{i}\n    resource: {s}\n    title: t\n" for i, s in enumerate(sources or []))
    fm = f"---\ntype: summary\ntitle: X\nsources:\n{src}updated: 2026-01-01\n---\n" if sources is not None \
        else "---\ntype: summary\ntitle: X\nupdated: 2026-01-01\n---\n"
    return write(vault / rel, fm + "\n" + body + "\n")


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    v = tmp_path / "Vault"
    (v / "Raw").mkdir(parents=True)
    write(v / "Wiki" / "index.md", "# Index\n")
    write(v / "Wiki" / "log.md", "# Log\n\n## 2026-01-02\n* x\n\n## 2026-01-01\n* y\n")
    return v


def bundle(v: Path, **kw) -> config.Bundle:
    return config.Bundle(name="Test", path=v, **kw)


# ---------------------------------------------------------- exact citation

def test_cite_regex_does_not_match_hashed_duplicate_prefix():
    # `foo.md` counted as cited because `foo-0041df.md` contains it.
    rx = V.cite_regex("doc-lucas-beyer-intro.md")
    assert not rx.search("see doc-lucas-beyer-intro-0041df.md")
    assert not rx.search("see x-doc-lucas-beyer-intro.md")
    assert rx.search("resource: ../../Raw/doc-lucas-beyer-intro.md")
    assert rx.search("`[source: doc-lucas-beyer-intro.md]`")


def test_cite_regex_matches_url_encoded_name():
    assert V.cite_regex("a b.md").search("[x](../Raw/a%20b.md)")


def test_coverage_ignores_log_mentions_and_prefix_matches(vault):
    raw(vault, "foo.md", "https://a")
    raw(vault, "foo-0041df.md", "https://b")
    page(vault, "Wiki/summaries/s.md", "cites [it](../../Raw/foo-0041df.md) only")
    write(vault / "Wiki" / "log.md", "# Log\n\n## 2026-01-01\n* removed foo.md\n")
    r = coverage.run(bundle(vault))
    assert [u["file"] for u in r.data["uncited"]] == ["foo.md"]
    assert r.exit_code == 1


def test_coverage_uncited_ok_and_stale_entries(vault):
    raw(vault, "dup.md", "https://a")
    r = coverage.run(bundle(vault, uncited_ok={"dup.md": "duplicate", "gone.md": "x"}))
    assert r.exit_code == 0
    assert r.data["uncited_ok"][0]["reason"] == "duplicate"
    assert any("gone.md" in w for w in r.warnings)


# ------------------------------------------------------------------ dupes

def test_dupes_quoted_and_unquoted_urls_are_the_same_source(vault):
    # The sync's URL guard missed `url: "..."` vs `url: ...`; kb must not.
    raw(vault, "a.md", "https://x.com/post/", quote_url=True)
    raw(vault, "a-bf4dbf.md", "http://x.com/post", quote_url=False)
    raw(vault, "other.md", "https://x.com/different")
    (r,) = dupes.run([bundle(vault)])
    assert r.exit_code == 1
    assert list(r.data["exact"].values()) == [["a-bf4dbf.md", "a.md"]]


def test_dupes_cross_bundle_is_information_only(tmp_path):
    a, b = tmp_path / "A", tmp_path / "B"
    raw(a, "x.md", "https://same")
    raw(b, "y.md", "https://same")
    reps = dupes.run([config.Bundle("A", a), config.Bundle("B", b)], cross=True)
    assert all(r.exit_code == 0 for r in reps)
    assert reps[-1].data["cross"]


# ----------------------------------------------------------------- quotes

SRC = ("There’s no single best model, as every problem has different needs. "
       "Older OCR was brittle. It was used to train [72 models on the Hub](https://hf.co/x). "
       "HTML is one of the most popular output formats. **The main challenge** lies here.")


def qpage(vault: Path, body: str) -> Path:
    write(vault / "Raw" / "src.md", f"---\nurl: u\n---\n{SRC}\n")
    return page(vault, "Wiki/summaries/p.md", body, sources=["../../Raw/src.md"])


def test_quotes_curly_apostrophe_drift(vault):
    p = qpage(vault, 'They say "There\'s no single best model".')
    assert quotes.run(p, None, []).data["counts"]["drift"] == 1


def test_quotes_exact_curly_passes(vault):
    p = qpage(vault, "They say “There’s no single best model, as every problem has different needs.”")
    assert quotes.run(p, None, []).data["counts"]["verified"] == 1


def test_quotes_changed_terminal_punctuation_is_drift_not_verified(vault):
    # Codex review: the source continues "model, as ..."; a period is a change.
    p = qpage(vault, "They say “There’s no single best model.”")
    assert quotes.run(p, None, []).data["counts"]["drift"] == 1


def test_quotes_case_drift(vault):
    p = qpage(vault, 'HTML is "One of the most popular" formats.')
    assert quotes.run(p, None, []).data["counts"]["drift"] == 1


def test_quotes_link_and_bold_markup_stripped_both_sides(vault):
    p = qpage(vault, 'Used to train "72 models on the Hub". And "The main challenge lies here".')
    c = quotes.run(p, None, []).data["counts"]
    assert c["verified"] == 2 and c["missing"] == 0


def test_quotes_short_quote_does_not_shift_pairing(vault):
    # A minimum-length filter skipped "brittle" and paired its closing mark
    # with the next opening one, producing 16 false misses.
    p = qpage(vault, 'It was "brittle", and an invented "open models always win".')
    c = quotes.run(p, None, []).data["counts"]
    assert c == {"verified": 1, "drift": 0, "missing": 1, "short": 0, "ignored": 0}


def test_quotes_unbalanced_paragraph_fails_closed(vault):
    p = qpage(vault, 'He said "invented and then "other".')
    r = quotes.run(p, None, [])
    assert r.exit_code == 1 and any("do not pair" in f for f in r.failures)


def test_quotes_unclosed_curly_fails_closed(vault):
    p = qpage(vault, "Claim: “invented guarantee")
    assert quotes.run(p, None, []).exit_code == 1


def test_quotes_blockquote_checked_status_callout_skipped(vault):
    p = qpage(vault, "> Partial. One source so far.\n\ntext\n\n> Older OCR was brittle.")
    r = quotes.run(p, None, [])
    assert r.data["counts"]["verified"] == 1 and len(r.data["quotes"]) == 1


def test_quotes_ellipsis_fragments_checked_separately(vault):
    p = qpage(vault, '"There’s no single best model ... every problem has different needs"')
    assert quotes.run(p, None, []).data["counts"]["verified"] == 1


def test_quotes_code_spans_ignored(vault):
    p = qpage(vault, 'Run `kb --name "not a quote"` now.')
    assert quotes.run(p, None, []).data["quotes"] == []


def test_quotes_no_sources_is_a_failure(vault):
    p = page(vault, "Wiki/summaries/n.md", '"anything"')
    assert quotes.run(p, None, []).exit_code == 1


# -------------------------------------------------------- wiki_refs / check

def test_wiki_refs_parses_names_with_spaces_and_quotes():
    fm = 'url: x\nwiki_refs:\n  - Wiki/concepts/Reward Model.md\n  - "Wiki/summaries/a.md"\n'
    assert V.wiki_refs(fm) == ["Wiki/concepts/Reward Model.md", "Wiki/summaries/a.md"]


def test_check_wiki_refs_malformed_ref_is_warning_not_failure(vault):
    page(vault, "Wiki/summaries/s.md", "cites [r](../../Raw/r.md)")
    raw(vault, "r.md", "https://a", refs=["Wiki/summaries/s"])
    r = checks.Report("check")
    checks.check_wiki_refs(r, bundle(vault))
    assert not r.failures and any("missing `.md`" in w for w in r.warnings)


def test_check_wiki_refs_non_citing_wiki_page_fails(vault):
    page(vault, "Wiki/summaries/s.md", "cites something else")
    raw(vault, "r.md", "https://a", refs=["Wiki/summaries/s.md"])
    r = checks.Report("check")
    checks.check_wiki_refs(r, bundle(vault))
    assert any("not reciprocated" in f for f in r.failures)


def test_check_stamp_in_future_fails(vault):
    write(vault / "Wiki" / "summaries" / "s.md",
          '---\ntype: summary\nupdated: 2026-01-01\ngenerated: { by: "agent:x", at: "2999-01-01T00:00:00Z" }\n---\nx\n')
    r = checks.Report("check")
    checks.check_stamps(r, bundle(vault), None)
    assert any("future" in f for f in r.failures)


def test_check_log_order(vault):
    write(vault / "Wiki" / "log.md", "# Log\n\n## 2026-01-01\n\n## 2026-01-02\n")
    r = checks.Report("check")
    checks.check_log(r, bundle(vault))
    assert any("newest-first" in f for f in r.failures)


# ------------------------------------------------------------------ citers

def test_citers_lists_lines_and_flags_unlisted(vault):
    raw(vault, "r.md", "https://a")
    page(vault, "Wiki/summaries/s.md", "line one\nsee [r](../../Raw/r.md) here")
    r = citers.run(bundle(vault), "r")
    assert r.data["citing_pages"] == ["Wiki/summaries/s.md"]
    assert r.data["lines"][0]["line"] == 8
    assert any("not in its wiki_refs" in w for w in r.warnings)


# --------------------------------------------------------------------- CLI

def _cfg(tmp_path: Path, v: Path) -> Path:
    return write(tmp_path / "knowledge-ingest.config.json",
                 json.dumps({"bundles": [{"name": "Test", "path": str(v)}]}))


def test_cli_exit_codes_and_json(tmp_path, vault):
    raw(vault, "r.md", "https://a")
    cfg = _cfg(tmp_path, vault)
    runner = CliRunner()
    res = runner.invoke(app, ["--config", str(cfg), "coverage", "Test", "--json"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["reports"][0]["uncited"][0]["file"] == "r.md"
    page(vault, "Wiki/summaries/s.md", "[r](../../Raw/r.md)")
    assert runner.invoke(app, ["--config", str(cfg), "coverage", "Test"]).exit_code == 0


def test_cli_unknown_bundle_is_usage_error(tmp_path, vault):
    res = CliRunner().invoke(app, ["--config", str(_cfg(tmp_path, vault)), "coverage", "Nope"])
    assert res.exit_code == 2


def test_cli_sync_sim_without_simulator_is_usage_error(tmp_path, vault):
    res = CliRunner().invoke(app, ["--config", str(_cfg(tmp_path, vault)), "sync-sim"])
    assert res.exit_code == 2


def test_config_discovery_walks_up(tmp_path, vault, monkeypatch):
    _cfg(tmp_path, vault)
    sub = tmp_path / "a" / "b"
    sub.mkdir(parents=True)
    monkeypatch.chdir(sub)
    monkeypatch.delenv("KB_CONFIG", raising=False)
    assert config.load().bundles[0].name == "Test"


# ------------------------------------------- Codex review 2026-10-04 (kb CLI)

def test_quotes_no_substring_inside_a_word(vault):
    write(vault / "Raw" / "w.md", "---\nurl: u\n---\nWe concatenate. Counting is software dependents.\n")
    p = page(vault, "Wiki/summaries/w.md", 'A "cat" and "is software dependent".', sources=["../../Raw/w.md"])
    c = quotes.run(p, None, []).data["counts"]
    assert c["verified"] == 0 and c["missing"] == 2


def test_quotes_ellipsis_fragments_must_be_in_order(vault):
    write(vault / "Raw" / "o.md", "---\nurl: u\n---\nomega came first, then much later alpha.\n")
    p = page(vault, "Wiki/summaries/o.md", '"alpha ... omega"', sources=["../../Raw/o.md"])
    assert quotes.run(p, None, []).data["counts"]["verified"] == 0


def test_quotes_never_span_two_sources(vault):
    write(vault / "Raw" / "a.md", "---\nurl: u\n---\nthe very last\n")
    write(vault / "Raw" / "b.md", "---\nurl: v\n---\nfirst of all\n")
    p = page(vault, "Wiki/summaries/ab.md", '"last first of"', sources=["../../Raw/a.md", "../../Raw/b.md"])
    assert quotes.run(p, None, []).data["counts"]["verified"] == 0


def test_quotes_literal_underscore_and_asterisk_are_kept(vault):
    write(vault / "Raw" / "u.md", "---\nurl: u\n---\nset foo_bar to x*y now\n")
    p = page(vault, "Wiki/summaries/u.md", '"set foobar to" and "x y now"', sources=["../../Raw/u.md"])
    assert quotes.run(p, None, []).data["counts"]["verified"] == 0


def test_quotes_source_frontmatter_and_html_are_not_evidence(vault):
    write(vault / "Raw" / "h.md", '---\nurl: u\ntitle: Invented Guarantee\n---\n<img alt="Hidden promise here"> body\n')
    p = page(vault, "Wiki/summaries/h.md", '"Invented Guarantee" and "Hidden promise here"', sources=["../../Raw/h.md"])
    assert quotes.run(p, None, []).data["counts"]["missing"] == 2


def test_quotes_indented_blockquote_checked_and_status_word_exact(vault):
    p = qpage(vault, "text\n\n   > invented guarantee here\n\nmore\n\n> Noteworthy invented line")
    c = quotes.run(p, None, []).data["counts"]
    assert c["missing"] == 2


def test_mention_regex_rejects_backup_suffix_but_allows_sentence_period():
    rx = V.mention_regex("foo.md")
    assert not rx.search("obsolete foo.md.bak")
    assert rx.search("see foo.md.")


def test_cite_regex_accepts_only_citation_forms():
    # Codex re-review: bare mentions (`cp foo.md /tmp`, "obsolete foo.md") certified coverage.
    rx = V.cite_regex("foo.md")
    for bare in ["cp foo.md /tmp", "obsolete foo.md", "foo.md..bak", "see foo.md."]:
        assert not rx.search(bare), bare
    for cite in ["resource: ../../Raw/foo.md", "[x](../../Raw/foo.md)", "[x](../../Raw/foo.md#sec)",
                 "[x](<../../Raw/foo.md>)", "`[source: foo.md]`", "per Raw/foo.md."]:
        assert rx.search(cite), cite


def test_raw_files_include_uppercase_extension(vault):
    write(vault / "Raw" / "UP.MD", "---\nurl: u\n---\nx\n")
    assert [p.name for p in V.raw_files(vault)] == ["UP.MD"]


def test_wiki_refs_inline_list_and_comments():
    assert V.wiki_refs("wiki_refs: [Wiki/a.md, 'Wiki/b c.md']") == ["Wiki/a.md", "Wiki/b c.md"]
    assert V.wiki_refs("wiki_refs:\n  - Wiki/a.md # primary\n") == ["Wiki/a.md"]


def test_check_inline_wiki_refs_to_missing_page_fails(vault):
    write(vault / "Raw" / "r.md", "---\nurl: u\nwiki_refs: [Wiki/missing.md]\n---\nx\n")
    r = checks.Report("check")
    checks.check_wiki_refs(r, bundle(vault))
    assert any("missing page" in f for f in r.failures)


def test_check_unlisted_citer_fails(vault):
    page(vault, "Wiki/summaries/s.md", "cites [r](../../Raw/r.md)")
    raw(vault, "r.md", "https://a")
    r = checks.Report("check")
    checks.check_wiki_refs(r, bundle(vault))
    assert any("not in its wiki_refs" in f for f in r.failures)


def test_check_learning_path_ref_needs_transitive_citation(vault):
    raw(vault, "r.md", "https://a", refs=["Learning Path/1 - Stage.md"])
    write(vault / "Learning Path" / "1 - Stage.md", "# Stage\n\nnothing relevant\n")
    r = checks.Report("check")
    checks.check_wiki_refs(r, bundle(vault))
    assert any("neither cites it" in f for f in r.failures)
    page(vault, "Wiki/summaries/s.md", "cites [r](../../Raw/r.md)")
    write(vault / "Learning Path" / "1 - Stage.md", "# Stage\n\n[s](../Wiki/summaries/s.md)\n")
    raw(vault, "r.md", "https://a", refs=["Learning Path/1 - Stage.md", "Wiki/summaries/s.md"])
    r = checks.Report("check")
    checks.check_wiki_refs(r, bundle(vault))
    assert not r.failures


def test_nested_index_page_is_not_reserved(vault):
    raw(vault, "r.md", "https://a")
    write(vault / "Wiki" / "topics" / "index.md", "---\ntype: index\n---\ncites [r](../../Raw/r.md)\n")
    assert coverage.run(bundle(vault)).exit_code == 0


def test_check_missing_validator_fails_closed(tmp_path, vault):
    cfg = config.Config(path=None, root=None, bundles=[])
    r = checks.run(bundle(vault), cfg, None)
    assert any("no schema validator" in f for f in r.failures)


def test_check_anchored_link_is_checked(vault):
    page(vault, "Wiki/summaries/s.md", "[x](missing.md#anchor)")
    r = checks.Report("check")
    checks.check_links(r, bundle(vault))
    assert any("missing.md" in f for f in r.failures)


def test_json_envelope_is_stable_and_errors_are_json(tmp_path, vault):
    cfg = _cfg(tmp_path, vault)
    runner = CliRunner()
    one = json.loads(runner.invoke(app, ["--config", str(cfg), "coverage", "Test", "--json"]).stdout)
    assert set(one) >= {"status", "reports"} and isinstance(one["reports"], list)
    res = runner.invoke(app, ["--config", str(tmp_path / "missing.json"), "coverage", "--json"])
    assert res.exit_code == 2 and json.loads(res.stdout)["status"] == "error"


def test_malformed_config_is_exit_2(tmp_path, vault):
    bad = write(tmp_path / "bad.json", "{not json")
    res = CliRunner().invoke(app, ["--config", str(bad), "coverage", "--json"])
    assert res.exit_code == 2 and json.loads(res.stdout)["status"] == "error"


def test_sync_sim_rejects_malformed_simulator_output(tmp_path, vault):
    cfg = write(tmp_path / "c.json", json.dumps({"bundles": [{"name": "Test", "path": str(vault)}],
                                                 "sync_simulator": "python3 -c 'print(\"{}\")'"}))
    res = CliRunner().invoke(app, ["--config", str(cfg), "sync-sim", "--json"])
    assert res.exit_code == 2


def test_dupes_reports_unnormalizable_url(vault, monkeypatch):
    raw(vault, "a.md", "https://x/a")
    def boom(u):
        raise ValueError("bad")
    monkeypatch.setattr(dupes, "loose_norm", boom)
    (r,) = dupes.run([bundle(vault)])
    assert r.exit_code == 1 and any("could not be normalized" in f for f in r.failures)


def test_urls_module_ships_inside_package():
    from kb.urls import norm
    assert norm("https://www.youtube.com/watch?v=abc&t=3") == "youtube:abc"


# ------------------------------------------- Codex re-review 2026-10-04 (kb CLI)

def _src(vault, name, body):
    write(vault / "Raw" / name, f"---\nurl: u\n---\n{body}\n")
    return f"../../Raw/{name}"


def test_quotes_punctuation_ending_fragment_needs_boundary(vault):
    src = _src(vault, "c.md", "This uses C++17 templates and foo-bar values.")
    p = page(vault, "Wiki/summaries/c.md", '"uses C++" and "values foo-"', sources=[src])
    assert quotes.run(p, None, []).data["counts"]["verified"] == 0


def test_quotes_tiny_ellipsis_fragments_fail(vault):
    src = _src(vault, "t.md", "a bc d")
    p = page(vault, "Wiki/summaries/t.md", '"a ... bc"', sources=[src])
    r = quotes.run(p, None, [])
    assert r.exit_code == 1 and r.data["counts"]["short"] == 1


def test_quotes_short_quote_fails_not_warns(vault):
    src = _src(vault, "s.md", "x*y")
    p = page(vault, "Wiki/summaries/s.md", '"xy"', sources=[src])
    assert quotes.run(p, None, []).exit_code == 1


def test_quotes_escaped_emphasis_stays_literal(vault):
    src = _src(vault, "e.md", r"beware \*danger\* here")
    p = page(vault, "Wiki/summaries/e.md", '"beware danger here"', sources=[src])
    assert quotes.run(p, None, []).data["counts"]["verified"] == 0


def test_quotes_autolinks_keep_their_url(vault):
    src = _src(vault, "l.md", "alpha <https://source.example> omega")
    p = page(vault, "Wiki/summaries/l.md", '"alpha <https://invented.example> omega"', sources=[src])
    assert quotes.run(p, None, []).data["counts"]["verified"] == 0


def test_quotes_hidden_html_is_not_evidence(vault):
    src = _src(vault, "x.md", "<script>Invented Guarantee</script> <span hidden>Secret claim here</span> <!-- Comment claim -->")
    p = page(vault, "Wiki/summaries/x.md", '"Invented Guarantee", "Secret claim here", "Comment claim"', sources=[src])
    assert quotes.run(p, None, []).data["counts"]["missing"] == 3


def test_quotes_note_sentence_blockquote_is_checked(vault):
    p = qpage(vault, "> Note this guarantee is real\n\ntext\n\n> **Note:** a status callout")
    rows = quotes.run(p, None, []).data["quotes"]
    assert len(rows) == 1 and rows[0]["verdict"] == "missing"


def test_quotes_inch_mark_is_not_a_quote_mark(vault):
    p = qpage(vault, 'The 5" screen is standard, and older OCR was "brittle".')
    r = quotes.run(p, None, [])
    assert r.exit_code == 0 and r.data["counts"]["verified"] == 1


def test_wiki_refs_flow_list_respects_quoted_commas():
    assert V.wiki_refs('wiki_refs: ["Wiki/A, B.md", c.md]') == ["Wiki/A, B.md", "c.md"]


def test_wiki_refs_scalar_is_rejected():
    with pytest.raises(V.RefsError):
        V.wiki_refs("wiki_refs: Wiki/a.md")


def test_check_scalar_wiki_refs_fails(vault):
    write(vault / "Raw" / "r.md", "---\nurl: u\nwiki_refs: Wiki/a.md\n---\nx\n")
    r = checks.Report("check")
    checks.check_wiki_refs(r, bundle(vault))
    assert any("must be a list" in f for f in r.failures)


def test_check_angled_link_with_space_and_anchor(vault):
    page(vault, "Wiki/summaries/s.md", "[x](<missing file.md#anchor>)")
    r = checks.Report("check")
    checks.check_links(r, bundle(vault))
    assert any("missing file.md" in f for f in r.failures)


def test_citers_labels_mentions_vs_citations(vault):
    raw(vault, "r.md", "https://a")
    page(vault, "Wiki/summaries/a.md", "see [r](../../Raw/r.md)")
    page(vault, "Wiki/summaries/b.md", "the old r.md file")
    r = citers.run(bundle(vault), "r")
    assert r.data["citing_pages"] == ["Wiki/summaries/a.md"]
    assert r.data["mentioning_pages"] == ["Wiki/summaries/b.md"]


def test_entry_json_on_typer_usage_error(monkeypatch, capsys, tmp_path, vault):
    from kb.cli import entry
    monkeypatch.setattr("sys.argv", ["kb", "--config", str(_cfg(tmp_path, vault)), "coverage", "--nope", "--json"])
    with pytest.raises(SystemExit) as ex:
        entry()
    assert ex.value.code == 2
    assert json.loads(capsys.readouterr().out)["status"] == "error"


def test_bundles_json_has_envelope(tmp_path, vault):
    out = CliRunner().invoke(app, ["--config", str(_cfg(tmp_path, vault)), "bundles", "--json"]).stdout
    assert json.loads(out)["reports"] == []


def test_check_ingest_wrapper_forwards_validator(tmp_path, vault):
    import subprocess, sys
    wrapper = Path(__file__).resolve().parents[2] / "scripts" / "check_ingest.py"
    cfg = _cfg(tmp_path, vault)
    res = subprocess.run([sys.executable, str(wrapper), str(vault), "--validator", "/nonexistent.py"],
                         capture_output=True, text=True, env={**os.environ, "KB_CONFIG": str(cfg)})
    assert res.returncode == 1 and "validator not found" in res.stdout


# ------------------------------------- Codex second re-review 2026-10-04 (kb CLI)

def test_quotes_token_boundaries_on_punctuation(vault):
    src = _src(vault, "p.md", r"It uses C++ templates. Beware \*danger\* here.")
    p = page(vault, "Wiki/summaries/p.md", '"uses C+", "danger", "uses C++ templates"', sources=[src])
    c = quotes.run(p, None, []).data["counts"]
    assert c["verified"] == 1 and c["missing"] == 2  # only the whole-token quote verifies


def test_quotes_angle_brackets_that_are_not_html_stay(vault):
    src = _src(vault, "g.md", "Use vector<int> here.")
    p = page(vault, "Wiki/summaries/g.md", '"Use vector<float> here" and "Use vector<int> here"', sources=[src])
    c = quotes.run(p, None, []).data["counts"]
    assert c["verified"] == 1 and c["missing"] == 1


def test_quotes_css_hidden_text_is_not_evidence(vault):
    src = _src(vault, "css.md", '<span style="display: none">Invented promise here</span> visible')
    p = page(vault, "Wiki/summaries/css.md", '"Invented promise here"', sources=[src])
    assert quotes.run(p, None, []).data["counts"]["missing"] == 1


def test_quotes_inline_code_content_can_be_quoted(vault):
    src = _src(vault, "ic.md", "Run `kb check` before review.")
    p = page(vault, "Wiki/summaries/ic.md", '"Run kb check before review"', sources=[src])
    assert quotes.run(p, None, []).data["counts"]["verified"] == 1


def test_quotes_digit_ending_quotation_pairs(vault):
    src = _src(vault, "v.md", "the guide says version 2 is current")
    p = page(vault, "Wiki/summaries/v.md", 'The source says "version 2" exactly.', sources=[src])
    r = quotes.run(p, None, [])
    assert r.exit_code == 0 and r.data["counts"]["verified"] == 1


def test_quotes_checks_actually_ran(vault):
    # Codex: tests asserting only verified == 0 could pass if extraction skipped the quote.
    src = _src(vault, "r.md", "real text here")
    p = page(vault, "Wiki/summaries/r.md", 'one "invented claim here" only', sources=[src])
    rows = quotes.run(p, None, []).data["quotes"]
    assert [(q["quote"], q["verdict"]) for q in rows] == [("invented claim here", "missing")]


def test_cli_rejects_empty_ignore(tmp_path, vault):
    src = _src(vault, "r.md", "real text here")
    pg = page(vault, "Wiki/summaries/r.md", '"invented claim here"', sources=[src])
    res = CliRunner().invoke(app, ["quotes", str(pg), "--ignore", "", "--json"])
    assert res.exit_code == 2 and json.loads(res.stdout)["status"] == "error"


def test_cli_rejects_invalid_since(tmp_path, vault):
    for bad in ["not-a-date", "2026-02-30", "9999-99-99"]:
        res = CliRunner().invoke(app, ["--config", str(_cfg(tmp_path, vault)), "check", "Test", "--since", bad, "--json"])
        assert res.exit_code == 2, bad


def test_cite_regex_needs_the_raw_target_and_live_context():
    assert not V.cites("foo.md", "[self](foo.md)")
    assert not V.cites("foo.md", "[w](../Wiki/foo.md)")
    assert not V.cites("foo.md", "```\nresource: ../../Raw/foo.md\n```")
    assert not V.cites("foo.md", "<!-- [x](../../Raw/foo.md) -->")
    assert V.cites("foo.md", "[x](../../Raw/foo.md)")


def test_config_relative_bundle_path_resolves_from_config_dir(tmp_path, monkeypatch):
    proj = tmp_path / "proj"
    (proj / "vault" / "Raw").mkdir(parents=True)
    write(proj / "knowledge-ingest.config.json", json.dumps({"bundles": [{"name": "V", "path": "vault"}]}))
    monkeypatch.chdir(tmp_path)
    cfg = config.load(str(proj / "knowledge-ingest.config.json"))
    assert cfg.bundles[0].path == proj / "vault"


def test_missing_bundle_or_raw_folder_is_a_failure(tmp_path):
    empty = tmp_path / "NoRaw"
    empty.mkdir()
    for r in [coverage.run(config.Bundle("x", empty)), coverage.run(config.Bundle("y", tmp_path / "nope")),
              dupes.run([config.Bundle("z", empty)])[0]]:
        assert r.exit_code == 1


def test_config_field_types_are_validated(tmp_path, vault):
    bad = write(tmp_path / "c.json", json.dumps({"bundles": [{"name": 3, "path": str(vault)}]}))
    res = CliRunner().invoke(app, ["--config", str(bad), "coverage", "--json"])
    assert res.exit_code == 2 and json.loads(res.stdout)["status"] == "error"


def test_yaml_wiki_refs_forms():
    assert V.wiki_refs("wiki_refs:\n- Wiki/a.md\n") == ["Wiki/a.md"]            # unindented list
    assert V.wiki_refs('wiki_refs:\n  - "Wiki/a.md" # c\n') == ["Wiki/a.md"]  # quoted + comment
    assert V.fm_value('url: "https://x.test/a" # note', "url") == "https://x.test/a"


def test_invalid_yaml_frontmatter_fails_check(vault):
    write(vault / "Raw" / "bad.md", "---\nurl: [unclosed\n---\nx\n")
    r = checks.Report("check")
    checks.check_readable(r, bundle(vault))
    assert any("not valid YAML" in f for f in r.failures)


def test_invalid_utf8_fails_check(vault):
    (vault / "Raw" / "bin.md").write_bytes(b"---\nurl: u\n---\n\xff\xfe bad\n")
    r = checks.Report("check")
    checks.check_readable(r, bundle(vault))
    assert any("not valid UTF-8" in f for f in r.failures)


def test_link_extractor_forms():
    t = ("[a](<x y.md#s> 'T') [b](p(1).md) [c][r]\n[r]: ref.md \"t\"\n"
         "\\[not](esc.md) `[code](c.md)`\n```\n[fence](f.md)\n```\n[h](HTTPS://e.test/x.md)")
    assert V.md_link_targets(t) == ["x y.md", "p(1).md", "ref.md"]


def test_dupes_missing_or_empty_url_fails(vault):
    write(vault / "Raw" / "nourl.md", "---\ntitle: t\n---\nx\n")
    write(vault / "Raw" / "empty.md", "---\nurl: https://\n---\nx\n")
    (r,) = dupes.run([bundle(vault)])
    assert r.exit_code == 1 and len(r.failures) == 2


def test_sync_sim_must_prove_requested_drop(tmp_path, vault):
    out = json.dumps({"checked": 0, "writes": [], "dropped": []})
    cfg = write(tmp_path / "c.json", json.dumps({"bundles": [{"name": "Test", "path": str(vault)}],
                                                 "sync_simulator": f"python3 -c 'print({out!r})'"}))
    res = CliRunner().invoke(app, ["--config", str(cfg), "sync-sim", "--drop", str(vault / "Raw" / "x.md"), "--json"])
    assert res.exit_code == 2 and json.loads(res.stdout)["status"] == "error"


def test_sync_sim_missing_executable_is_config_error(tmp_path, vault):
    cfg = write(tmp_path / "c.json", json.dumps({"bundles": [{"name": "Test", "path": str(vault)}],
                                                 "sync_simulator": "/no/such/simulator"}))
    res = CliRunner().invoke(app, ["--config", str(cfg), "sync-sim", "--json"])
    assert res.exit_code == 2 and json.loads(res.stdout)["status"] == "error"


def test_json_envelope_records_config_and_note(tmp_path, vault):
    cfg = _cfg(tmp_path, vault)
    out = json.loads(CliRunner().invoke(app, ["--config", str(cfg), "coverage", "--json"]).stdout)
    assert out["config"] == str(cfg.resolve()) and "independent review" in out["note"]
    assert out["reports"][0]["bundle_path"] == str(vault)
