#!/usr/bin/env python3
"""Deprecated wrapper: Gate A now lives in the `kb` CLI (`kb check`).

Kept so existing commands keep working. It forwards to `kb check`, using the
installed `kb` if there is one, else `uv run` against the skill's cli/ package.
--validator is forwarded and overrides the config's `validator`.

    python3 scripts/check_ingest.py "<vault>" [--since YYYY-MM-DD]
    # same as: kb check "<vault>" [--since YYYY-MM-DD]
"""
import shutil
import subprocess
import sys
from pathlib import Path

CLI = Path(__file__).resolve().parents[1] / "cli"

CONFIG = None  # generic copy: kb finds the project's config itself
args = sys.argv[1:]  # --validator and --since are forwarded unchanged to `kb check`
kb = shutil.which("kb")
cmd = [kb] if kb else ["uv", "run", "--project", str(CLI), "kb"]
pre = ["--config", str(CONFIG)] if CONFIG else []
sys.exit(subprocess.call([*cmd, *pre, "check", *args]))
