"""
Tiny JSON key/value store for passing data between tests or flows
(e.g. an ID created in one test and verified in another).

Files live in `test_data/runtime/<flow>_runtime_data.json` (git-ignored).

    write_value("order_id", "12345", flow_name="checkout")
    read_value("order_id", flow_name="checkout")
"""

import json
import os
from typing import Any

RUNTIME_DIR = "test_data/runtime"


def ensure_runtime_dir() -> None:
    os.makedirs(RUNTIME_DIR, exist_ok=True)


def get_runtime_file(flow_name: str = "default") -> str:
    ensure_runtime_dir()
    return os.path.join(RUNTIME_DIR, f"{flow_name}_runtime_data.json")


def _read(flow_name: str) -> dict:
    path = get_runtime_file(flow_name)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def write_value(key: str, value: Any, flow_name: str = "default") -> None:
    data = _read(flow_name)
    data[key] = value
    with open(get_runtime_file(flow_name), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def read_value(key: str, flow_name: str = "default", default: Any = None, required: bool = False) -> Any:
    data = _read(flow_name)
    if required and key not in data:
        raise KeyError(f"'{key}' not found in {get_runtime_file(flow_name)}")
    return data.get(key, default)


def append_value(key: str, value: Any, flow_name: str = "default") -> None:
    """Append to a list stored under `key` (creates it if missing)."""
    data = _read(flow_name)
    data.setdefault(key, []).append(value)
    with open(get_runtime_file(flow_name), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def clear_runtime_data(flow_name: str = "default") -> None:
    with open(get_runtime_file(flow_name), "w", encoding="utf-8") as f:
        json.dump({}, f, indent=4)


def list_runtime_files() -> list:
    ensure_runtime_dir()
    return [os.path.join(RUNTIME_DIR, n) for n in os.listdir(RUNTIME_DIR) if n.endswith("_runtime_data.json")]
