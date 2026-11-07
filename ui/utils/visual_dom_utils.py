"""
DOM snapshot helpers for Playwright — detect structural page changes.

    snap = await get_dom_snapshot(base.page)
    assert_dom_matches_baseline(snap, "home_page")
"""

import json
import os
from typing import Optional, Tuple

DEFAULT_DOM_BASELINE_DIR = "UIeye/dom_snapshots"


async def get_dom_snapshot(page) -> dict:
    return {"dom_html": await page.content()}


def get_baseline_dom_path(name: str, baseline_dir: str = DEFAULT_DOM_BASELINE_DIR) -> str:
    os.makedirs(baseline_dir, exist_ok=True)
    return os.path.join(baseline_dir, f"{name}.json")


def load_snapshot(filepath: str) -> Optional[dict]:
    if not os.path.exists(filepath):
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_snapshot(snapshot: dict, filepath: str) -> None:
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)


def compare_snapshots(base: dict, current: dict) -> Tuple[bool, str]:
    if base == current:
        return True, ""
    base_len, current_len = len(base.get("dom_html", "")), len(current.get("dom_html", ""))
    if base_len != current_len:
        return False, f"DOM length mismatch: baseline {base_len} chars != current {current_len} chars"
    return False, "DOM content differs"


def assert_dom_matches_baseline(snapshot: dict, name: str, baseline_dir: str = DEFAULT_DOM_BASELINE_DIR) -> None:
    path = get_baseline_dom_path(name, baseline_dir)
    baseline = load_snapshot(path)
    if baseline is None:
        save_snapshot(snapshot, path)
        return
    ok, msg = compare_snapshots(baseline, snapshot)
    assert ok, f"DOM snapshot '{name}' changed: {msg}"
