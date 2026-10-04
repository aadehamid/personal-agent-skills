"""Typer entry point for `kb`."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

import typer

from . import __version__, checks, citers, config, coverage, dupes, quotes, syncsim
from .report import emit_all, emit_error

HELP = """Read-only validation for knowledge-ingest bundles.

Every command reports and nothing edits, so any agent can run any of them safely.
Checks fail closed: anything that could not be checked is a failure, not a pass.
Exit codes: 0 clean (warnings allowed), 1 failures found, 2 usage/config error.
Add --json to any command: stdout is always {"status": ..., "reports": [...]}.

\b
Typical use:
  kb coverage                    what is still unprocessed, in every bundle
  kb check "AI Engineering" --since 2026-10-04   Gate A after an ingest
  kb quotes <page.md>...         quotations verbatim in each page's sources
  kb citers <bundle> <raw.md>    before moving or deleting a source
  kb dupes                       Raw files that are the same source
  kb sync-sim --drop <raw.md>    would the sync put a deleted file back?

None of this checks whether an unquoted sentence is true to its source. That is
the independent review (Gate B).

\b
Config: --config, then $KB_CONFIG, then knowledge-ingest.config.json in the
current directory or a parent, then ~/.config/kb/config.json.
"""

app = typer.Typer(help=HELP, no_args_is_help=True, add_completion=False,
                  rich_markup_mode=None, pretty_exceptions_enable=False)

JsonOpt = typer.Option(False, "--json", help="Machine-readable JSON output.")


class _Fail(Exception):
    """A usage/config problem found by kb itself (exit 2)."""


def _cfg(ctx: typer.Context) -> config.Config:
    try:
        return config.load(ctx.obj.get("config") if ctx.obj else None)
    except config.ConfigError as e:
        raise _Fail(str(e)) from e


def _bundles(cfg: config.Config, refs: list[str] | None, default_all: bool) -> list[config.Bundle]:
    if refs:
        try:
            return [cfg.bundle(r) for r in refs]
        except config.ConfigError as e:
            raise _Fail(str(e)) from e
    if default_all:
        if not cfg.bundles:
            raise _Fail("no bundles configured; pass a bundle path or a --config")
        return cfg.bundles
    raise _Fail("name at least one bundle (or use --all)")


def _run(as_json: bool, build) -> None:
    """Run a command body; map kb's own usage/config errors to exit 2 (JSON-safe)."""
    try:
        reports = build()
    except (_Fail, config.ConfigError) as e:
        emit_error(str(e), as_json)
        raise typer.Exit(2)
    raise typer.Exit(emit_all(reports, as_json))


def _version(v: bool) -> None:
    if v:
        typer.echo(f"kb {__version__}")
        raise typer.Exit()


@app.callback()
def main(ctx: typer.Context,
         config_path: Optional[str] = typer.Option(None, "--config", help="Path to knowledge-ingest.config.json."),
         version: bool = typer.Option(False, "--version", callback=_version, is_eager=True,
                                      help="Show the version and exit.")) -> None:
    ctx.obj = {"config": config_path}


@app.command()
def bundles(ctx: typer.Context, as_json: bool = JsonOpt) -> None:
    """List the configured bundles and where the config was found."""
    try:
        cfg = _cfg(ctx)
    except _Fail as e:
        emit_error(str(e), as_json)
        raise typer.Exit(2)
    if as_json:
        typer.echo(json.dumps({"status": "clean", "reports": [], "config": str(cfg.path) if cfg.path else None,
                               "validator": str(cfg.validator) if cfg.validator else None,
                               "sync_simulator": cfg.sync_simulator,
                               "bundles": [{"name": b.name, "path": str(b.path), "shape": b.shape,
                                            "exists": b.path.is_dir()} for b in cfg.bundles]}, indent=2))
        return
    typer.echo(f"config: {cfg.path or '(none found)'}")
    for b in cfg.bundles:
        typer.echo(f"  {b.name:<28} {b.shape:<8} {b.path}{'' if b.path.is_dir() else '  (MISSING)'}")


@app.command()
def check(ctx: typer.Context,
          bundle: Optional[List[str]] = typer.Argument(None, help="Bundle name(s) or path(s)."),
          all_: bool = typer.Option(False, "--all", help="Check every configured bundle."),
          since: Optional[str] = typer.Option(None, help="YYYY-MM-DD: pages updated on/after this need a `generated` stamp."),
          validator: Optional[Path] = typer.Option(None, "--validator", help="Schema validator script; overrides the config's `validator`."),
          as_json: bool = JsonOpt) -> None:
    """Gate A: schema validator, links, wiki_refs reciprocity, stamps, Learning Path, index, log."""
    def build():
        cfg = _cfg(ctx)
        return [checks.run(b, cfg, since, validator) for b in _bundles(cfg, bundle, default_all=all_)]
    _run(as_json, build)


@app.command("coverage")
def coverage_cmd(ctx: typer.Context,
                 bundle: Optional[List[str]] = typer.Argument(None, help="Bundle(s); default all."),
                 as_json: bool = JsonOpt) -> None:
    """Raw sources that no page cites by exact filename (the unprocessed backlog)."""
    _run(as_json, lambda: [coverage.run(b) for b in _bundles(_cfg(ctx), bundle, True)])


@app.command("dupes")
def dupes_cmd(ctx: typer.Context,
              bundle: Optional[List[str]] = typer.Argument(None, help="Bundle(s); default all."),
              cross: bool = typer.Option(False, "--cross", help="Also list URLs present in more than one bundle."),
              as_json: bool = JsonOpt) -> None:
    """Raw files sharing a URL (exact = FAIL, normalized-only = WARN)."""
    _run(as_json, lambda: dupes.run(_bundles(_cfg(ctx), bundle, True), cross))


@app.command("quotes")
def quotes_cmd(pages: List[Path] = typer.Argument(..., help="Wiki page(s) to check.", exists=True, dir_okay=False),
               source: Optional[List[Path]] = typer.Option(None, "--source", help="Permitted source file (repeatable). Default: each page's `sources` frontmatter."),
               ignore: Optional[List[str]] = typer.Option(None, "--ignore", help="Skip quotations containing this text (repeatable)."),
               as_json: bool = JsonOpt) -> None:
    """Every quotation verbatim in the permitted sources (verified / DRIFT / MISSING)."""
    srcs = [s.resolve() for s in source] if source else None
    _run(as_json, lambda: [quotes.run(p.resolve(), srcs, ignore or []) for p in pages])


@app.command("citers")
def citers_cmd(ctx: typer.Context,
               bundle: str = typer.Argument(..., help="Bundle name or path."),
               raw: str = typer.Argument(..., help="Raw filename (with or without .md)."),
               as_json: bool = JsonOpt) -> None:
    """Every page and line that cites a Raw file, by exact filename. Run before moving or deleting it."""
    def build():
        cfg = _cfg(ctx)
        try:
            return [citers.run(cfg.bundle(bundle), raw)]
        except config.ConfigError as e:
            raise _Fail(str(e)) from e
    _run(as_json, build)


@app.command("sync-sim")
def sync_sim_cmd(ctx: typer.Context,
                 drop: Optional[List[Path]] = typer.Option(None, "--drop", help="Raw file to treat as deleted (repeatable)."),
                 as_json: bool = JsonOpt) -> None:
    """Run the project's sync simulator: would the sync recreate a deleted file, or write anything?"""
    _run(as_json, lambda: [syncsim.run(_cfg(ctx), [str(d) for d in (drop or [])])])


def entry() -> None:
    """Console entry point. Typer/Click usage errors (unknown option, missing file,
    bad value) happen before any command runs; in --json mode they still produce a
    JSON error object on stdout with exit 2, so the JSON contract is total."""
    import sys

    Abort = typer.Abort  # public in every Typer version
    try:  # Typer < 0.27 depends on Click; Typer >= 0.27 vendors it as typer._click
        from click.exceptions import UsageError
    except ImportError:
        from typer._click.exceptions import UsageError

    as_json = "--json" in sys.argv[1:]
    try:
        rc = app(standalone_mode=False)
    except UsageError as e:
        if as_json:
            emit_error(e.format_message(), True)
        else:
            e.show()
        sys.exit(2)
    except Abort:
        emit_error("aborted", as_json)
        sys.exit(1)
    sys.exit(rc if isinstance(rc, int) else 0)


if __name__ == "__main__":
    entry()
