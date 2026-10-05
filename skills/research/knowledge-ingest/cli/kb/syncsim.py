"""`kb sync-sim`: would the project's sync recreate or overwrite anything?

Sync logic is project-specific, so kb does not simulate it itself. The config
names a `sync_simulator` command; kb runs it with `--drop <file>` per file and
`--json`, and requires JSON of this shape (anything else is a config error, never
a clean result):

    {"checked": int, "dropped": [str], "writes": [{"dest": str, "kind": "create"|"refresh",
                                                   "recreates_dropped": bool, ...}],
     "dropped_missing": [str]}           # optional

`dropped` must echo every requested --drop path, and `checked` must be positive when
anything was dropped: output that does not prove the requested work ran is rejected.

The command runs with the config file's directory as its working directory.
"""
from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path

from .config import Config, ConfigError
from .report import Report


def _key(p: str) -> str:
    q = Path(p).expanduser()
    return str(q.parent.resolve() / q.name)


def _validate(res: object, drops: list[str]) -> dict:
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
    missing = res.get("dropped_missing", [])
    if not isinstance(missing, list) or not all(isinstance(m, str) for m in missing):
        raise ConfigError("sync simulator `dropped_missing` must be a list of strings")
    if drops:
        echoed = res.get("dropped")
        if not isinstance(echoed, list) or not all(isinstance(d, str) for d in echoed):
            raise ConfigError("sync simulator output needs a `dropped` list echoing the --drop paths")
        absent = {_key(d) for d in drops} - {_key(d) for d in echoed}
        if absent:
            raise ConfigError(f"sync simulator did not apply these --drop paths: {sorted(absent)}")
        if res["checked"] < 1:
            raise ConfigError("sync simulator checked 0 sources for a requested drop; nothing was simulated")
    return res


def run(cfg: Config, drops: list[str]) -> Report:
    if not cfg.sync_simulator:
        raise ConfigError("no `sync_simulator` command in knowledge-ingest.config.json")
    cmd = (shlex.split(cfg.sync_simulator)
           + [a for d in drops for a in ("--drop", str(Path(d).expanduser()))] + ["--json"])
    try:
        p = subprocess.run(cmd, cwd=cfg.root, capture_output=True, text=True)
    except OSError as e:
        raise ConfigError(f"cannot run sync simulator {cmd[0]!r}: {e}") from e
    if p.returncode != 0:
        raise ConfigError(f"sync simulator failed ({p.returncode}): {p.stderr.strip() or p.stdout.strip()}")
    try:
        res = _validate(json.loads(p.stdout), drops)
    except json.JSONDecodeError as e:
        raise ConfigError(f"sync simulator did not return JSON: {e}") from e
    r = Report("sync-sim", f"{len(drops)} file(s) treated as deleted" if drops else "current vault state")
    r.footer = False
    requested = {_key(d) for d in drops}
    for m in res.get("dropped_missing", []):
        if _key(m) in requested:
            # a requested drop that does not exist is a typo or a stale path: the preflight
            # did not test what you meant to delete
            r.fail(f"--drop path does not exist, so nothing real was simulated for it: {m}")
        else:
            r.warn(f"simulator reported a missing drop path: {m}")
    for w in res["writes"]:
        line = f"{w['kind']}: {w['dest']}"
        if w["recreates_dropped"]:
            r.fail(f"the sync would RECREATE a dropped file. {line}")
        else:
            r.warn(f"the sync would write. {line}")
    r.ok(f"{res['checked']} sources simulated, {len(res['writes'])} write(s)")
    r.data["simulation"] = res
    return r
