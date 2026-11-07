"""
Environment config loader.

Config files live in `config/<env>.json` and must NEVER contain real secrets.
Any string value may reference an environment variable using `${VAR_NAME}` or
`${VAR_NAME:-default}`. Values are resolved at load time from:

  1. Real environment variables (CI secrets, shell exports)
  2. A local `.env` file at the repo root (git-ignored, see `.env.example`)

Optional local overrides: `config/<env>.local.json` (git-ignored) is deep-merged
on top of `config/<env>.json` when present.
"""

import json
import os
import re
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv is optional
    load_dotenv = None

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"
_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-(.*?))?\}")


def _load_dotenv_once() -> None:
    env_file = REPO_ROOT / ".env"
    if load_dotenv and env_file.exists():
        load_dotenv(env_file, override=False)


def _resolve(value: Any) -> Any:
    """Recursively expand ${VAR} / ${VAR:-default} placeholders."""
    if isinstance(value, dict):
        return {k: _resolve(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve(v) for v in value]
    if isinstance(value, str):
        def repl(match):
            name, default = match.group(1), match.group(2)
            return os.environ.get(name, default if default is not None else "")
        return _ENV_PATTERN.sub(repl, value)
    return value


def _deep_merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(env: str = "qa") -> dict:
    """Load and resolve `config/<env>.json` (+ optional `<env>.local.json`)."""
    _load_dotenv_once()

    config_path = CONFIG_DIR / f"{env}.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Environment config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    local_path = CONFIG_DIR / f"{env}.local.json"
    if local_path.exists():
        with open(local_path, "r", encoding="utf-8") as f:
            data = _deep_merge(data, json.load(f))

    return _resolve(data)


def get_value(config: dict, dotted_key: str, default: Any = None, required: bool = False) -> Any:
    """Read a nested value, e.g. get_value(cfg, "ui.users.default.username")."""
    node: Any = config
    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            if required:
                raise KeyError(f"Missing required config key: {dotted_key}")
            return default
        node = node[part]
    if required and node in (None, ""):
        raise KeyError(f"Config key '{dotted_key}' is empty — set its environment variable")
    return node
