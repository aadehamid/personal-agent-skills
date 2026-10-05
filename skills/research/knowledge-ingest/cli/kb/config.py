"""Find and read knowledge-ingest.config.json, and resolve bundles from it."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_NAME = "knowledge-ingest.config.json"
USER_DEFAULT = Path.home() / ".config" / "kb" / "config.json"


class ConfigError(Exception):
    pass


@dataclass
class Bundle:
    name: str
    path: Path
    shape: str = "concept"
    sources: str | None = None
    # filename -> reason: Raw files that are uncited on purpose (recorded decisions)
    uncited_ok: dict[str, str] = field(default_factory=dict)


@dataclass
class Config:
    path: Path | None
    root: Path | None
    bundles: list[Bundle]
    validator: Path | None = None
    sync_simulator: str | None = None

    def bundle(self, ref: str) -> Bundle:
        """A bundle by config name (case-insensitive) or by filesystem path."""
        for b in self.bundles:
            if b.name.lower() == ref.lower():
                return b
        p = Path(ref).expanduser()
        if p.is_dir():
            p = p.resolve()
            for b in self.bundles:
                if b.path.resolve() == p:
                    return b
            return Bundle(name=p.name, path=p)
        names = ", ".join(b.name for b in self.bundles) or "(none configured)"
        raise ConfigError(f"no bundle named or located at {ref!r}. Known bundles: {names}")


def find_config(explicit: str | None = None) -> Path | None:
    """--config, then $KB_CONFIG, then walk up from cwd, then ~/.config/kb/config.json."""
    if explicit:
        p = Path(explicit).expanduser()
        if not p.exists():
            raise ConfigError(f"config not found: {p}")
        return p
    env = os.environ.get("KB_CONFIG")
    if env:
        p = Path(env).expanduser()
        if not p.exists():
            raise ConfigError(f"$KB_CONFIG points at a missing file: {p}")
        return p
    for d in [Path.cwd(), *Path.cwd().parents]:
        if (d / CONFIG_NAME).exists():
            return d / CONFIG_NAME
    if USER_DEFAULT.exists():
        return USER_DEFAULT
    return None


def load(explicit: str | None = None) -> Config:
    path = find_config(explicit)
    if path is None:
        return Config(path=None, root=None, bundles=[])
    real = path.resolve()  # the user default is usually a symlink into the project
    root = real.parent
    try:
        data = json.loads(real.read_text())
    except (OSError, json.JSONDecodeError) as e:
        raise ConfigError(f"cannot read config {real}: {e}") from e
    if not isinstance(data, dict) or not isinstance(data.get("bundles", []), list):
        raise ConfigError(f"config {real} must be an object with a `bundles` list")

    def opt_str(key: str) -> str | None:
        v = data.get(key)
        if v is not None and not isinstance(v, str):
            raise ConfigError(f"config {real}: `{key}` must be a string")
        return v or None

    def rel(v: str | None) -> Path | None:
        """Relative paths resolve from the config file's folder, never the caller's CWD."""
        if not v:
            return None
        p = Path(v).expanduser()
        return p if p.is_absolute() else root / p

    bundles = []
    for i, b in enumerate(data.get("bundles", [])):
        if not isinstance(b, dict):
            raise ConfigError(f"config {real}: bundles[{i}] must be an object")
        for key in ("name", "path"):
            if not isinstance(b.get(key), str) or not b[key].strip():
                raise ConfigError(f"config {real}: bundles[{i}].{key} must be a non-empty string")
        for key in ("shape", "sources"):
            if b.get(key) is not None and not isinstance(b[key], str):
                raise ConfigError(f"config {real}: bundles[{i}].{key} must be a string")
        ok = b.get("uncited_ok", {})
        if not isinstance(ok, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in ok.items()):
            raise ConfigError(f"config {real}: bundles[{i}].uncited_ok must map filename -> reason (strings)")
        bundles.append(Bundle(name=b["name"], path=rel(b["path"]), shape=b.get("shape") or "concept",
                              sources=b.get("sources"), uncited_ok=dict(ok)))
    return Config(path=real, root=root, bundles=bundles,
                  validator=rel(opt_str("validator")),
                  sync_simulator=opt_str("sync_simulator"))
