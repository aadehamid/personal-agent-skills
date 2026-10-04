"""`kb sync-sim`: would the project's sync recreate or overwrite anything?

Sync logic is project-specific, so kb does not simulate it itself. The config
names a `sync_simulator` command; kb runs it with `--drop <file>` per file and
`--json`, and requires JSON of this shape (anything else is a config error, never
a clean result):

    {"checked": int, "writes": [{"dest": str, "kind": "create"|"refresh",
                                 "recreates_dropped": bool, ...}],
     "dropped_missing": [str]}           # optional

The command runs with the config file's directory as its working directory.
"""
from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path

from .config import Config, ConfigError
from .report import Report


def _validate(res: object) -> dict:
    if not isinstance(res, dict):
        raise ConfigError("sync simulator output must be a JSON object")
    if not isinstance(res.get("checked"), int) or isinstance(res.get("checked"), bool):
        raise ConfigError("sync simulator output needs an integer `checked`")
    writes = res.get("writes")
    if not isinstance(writes, list):
        raise ConfigError("sync simulator output needs a `writes` list")
    for i, w in enumerate(writes):
        if not (isinstance(w, dict) and isinstance(w.get("dest"), str)
                and w.get("kind") in ("create", "refresh")
                and isinstance(w.get("recreates_dropped"), bool)):
            raise ConfigError(f"sync simulator `writes[{i}]` needs str `dest`, "
                              f"`kind` create|refresh and bool `recreates_dropped`")
    if not isinstance(res.get("dropped_missing", []), list):
        raise ConfigError("sync simulator `dropped_missing` must be a list")
    return res


def run(cfg: Config, drops: list[str]) -> Report:
    if not cfg.sync_simulator:
        raise ConfigError("no `sync_simulator` command in knowledge-ingest.config.json")
    cmd = (shlex.split(cfg.sync_simulator)
           + [a for d in drops for a in ("--drop", str(Path(d).expanduser()))] + ["--json"])
    p = subprocess.run(cmd, cwd=cfg.root, capture_output=True, text=True)
    if p.returncode != 0:
        raise ConfigError(f"sync simulator failed ({p.returncode}): {p.stderr.strip() or p.stdout.strip()}")
    try:
        res = _validate(json.loads(p.stdout))
    except json.JSONDecodeError as e:
        raise ConfigError(f"sync simulator did not return JSON: {e}") from e
    r = Report("sync-sim", f"{len(drops)} file(s) treated as deleted" if drops else "current vault state")
    r.footer = False
    for m in res.get("dropped_missing", []):
        r.warn(f"--drop file does not exist (already deleted?): {m}")
    for w in res["writes"]:
        line = f"{w['kind']}: {w['dest']}"
        if w["recreates_dropped"]:
            r.fail(f"the sync would RECREATE a dropped file. {line}")
        else:
            r.warn(f"the sync would write. {line}")
    r.ok(f"{res['checked']} sources simulated, {len(res['writes'])} write(s)")
    r.data["simulation"] = res
    return r
