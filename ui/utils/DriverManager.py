import os
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext


class DriverManager:
    """
    CI / Local Ready Playwright Driver Manager.

    Optimized for:
    - Low RAM CI VM (4 GB)
    - pytest -n 2 parallel execution
    - Stable & faster regression runs
    """

    def __init__(
        self,
        browser: str = "chromium",
        headless: Optional[bool] = None,
        enable_video: bool = False,
        enable_trace: bool = False,
        slow_mo: Optional[int] = None,
        channel: Optional[str] = None,
    ):
        self.browser_name = browser.lower()
        # Optional branded channel for chromium ("chrome", "msedge")
        self.channel = channel if self.browser_name == "chromium" else None

        # Detect CI
        self.is_ci = os.getenv("CI", "false").lower() == "true"

        # Headless defaults
        self.headless = headless if headless is not None else self.is_ci

        # ❌ NEVER slow down CI
        self.slow_mo = slow_mo if slow_mo is not None else 0

        # ❌ Disable heavy features automatically in CI
        self.enable_video = enable_video and not self.is_ci
        self.enable_trace = enable_trace and not self.is_ci

        self._playwright = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None

        # ---------- Launch Arguments (memory safe) ----------
        self.launch_args = [
            "--disable-gpu",
            "--disable-infobars",
            "--disable-notifications",
            "--disable-extensions",
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--no-first-run",
        ]

        # Start maximized only for local runs
        if not self.is_ci:
            self.launch_args.append("--start-maximized")

        # ---------- Context Options ----------
        if self.is_ci:
            # Deterministic viewport for CI
            self.context_options = {
                "viewport": {"width": 1920, "height": 1080},
                "ignore_https_errors": True,
            }
        else:
            # Local: real browser window
            self.context_options = {
                "no_viewport": True,
                "ignore_https_errors": True,
            }

        # Video only if explicitly enabled and NOT CI
        if self.enable_video:
            self.context_options["record_video_dir"] = "videos"

    async def start(self) -> BrowserContext:
        """Start Playwright, browser, and context (one per worker)."""
        self._playwright = await async_playwright().start()

        browser_type = getattr(self._playwright, self.browser_name, None)
        if not browser_type:
            raise ValueError(f"Unsupported browser: {self.browser_name}")

        launch_kwargs = {"headless": self.headless, "slow_mo": self.slow_mo}
        if self.browser_name == "chromium":
            launch_kwargs["args"] = self.launch_args
            if self.channel:
                launch_kwargs["channel"] = self.channel
        self.browser = await browser_type.launch(**launch_kwargs)

        self.context = await self.browser.new_context(**self.context_options)

        # ❌ Tracing disabled in CI by design
        if self.enable_trace:
            await self.context.tracing.start(
                screenshots=True,
                snapshots=True,
                sources=True,
            )

        return self.context

    async def reopen(self) -> BrowserContext:
        """
        Recreate context without relaunching browser.
        Use sparingly (keeps memory under control).
        """
        if self.context:
            await self.context.close()

        self.context = await self.browser.new_context(**self.context_options)

        if self.enable_trace:
            await self.context.tracing.start(
                screenshots=True,
                snapshots=True,
                sources=True,
            )

        return self.context

    async def stop_tracing(self, trace_path: str = "trace.zip"):
        """Stop tracing and save trace (local debug only)."""
        if self.context and self.enable_trace:
            await self.context.tracing.stop(path=trace_path)

    async def quit(self):
        """Clean shutdown of context, browser, and Playwright."""
        if self.context:
            if self.enable_trace:
                await self.context.tracing.stop(path="trace.zip")
            await self.context.close()

        if self.browser:
            await self.browser.close()

        if self._playwright:
            await self._playwright.stop()
