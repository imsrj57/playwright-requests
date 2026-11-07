"""
Self-healing locator helper for Playwright.

Give an element a logical name plus an ordered list of candidate selectors.
The first selector that resolves to a visible element wins and is cached in
`ui/utils/healing_cache.json`, so the next run tries it first.

    healer = HealingLocator(base.page)
    submit = await healer.find("submit_button", ["#submit", "button[type=submit]", "text=Save"])
    await submit.click()
"""

import json
from pathlib import Path
from typing import List, Optional

from playwright.async_api import Locator, Page

CACHE_FILE = Path(__file__).with_name("healing_cache.json")


class HealingLocator:
    def __init__(self, page: Page, cache_file: Path = CACHE_FILE, timeout_ms: int = 3000):
        self.page = page
        self.cache_file = Path(cache_file)
        self.timeout_ms = timeout_ms
        self.cache = self._load_cache()

    def _load_cache(self) -> dict:
        try:
            return json.loads(self.cache_file.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_cache(self) -> None:
        self.cache_file.write_text(json.dumps(self.cache, indent=2), encoding="utf-8")

    async def find(self, name: str, candidates: List[str]) -> Locator:
        cached: Optional[str] = self.cache.get(name)
        ordered = ([cached] if cached else []) + [c for c in candidates if c != cached]

        for selector in ordered:
            locator = self.page.locator(selector).first
            try:
                await locator.wait_for(state="visible", timeout=self.timeout_ms)
            except Exception:
                continue
            if selector != cached:
                print(f"[HealingLocator] '{name}' resolved via fallback: {selector}")
                self.cache[name] = selector
                self._save_cache()
            return locator

        raise AssertionError(f"Element '{name}' not found with any candidate selector: {ordered}")
