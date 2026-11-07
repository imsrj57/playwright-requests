# conftest.py — shared fixtures for UI (Playwright) and API (requests) tests
import os
import shutil
import sys
from pathlib import Path

import allure
import pytest
import pytest_asyncio

from common.config_loader import load_config
from ui.pages.BasePage import BasePage
from ui.utils.DriverManager import DriverManager

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")


# ---------------------------------------------------------------- CLI options
def pytest_addoption(parser):
    parser.addoption("--test-env", action="store", default="qa",
                     help="Environment config to load from config/<env>.json (e.g. qa, uat)")
    parser.addoption("--test-browser", action="store", default="chrome",
                     help="Browser to run UI tests on (chrome/chromium, firefox, webkit, edge)")
    parser.addoption("--headless", action="store_true", default=False,
                     help="Force headless browser (headless is automatic when CI=true)")


# ---------------------------------------------------------------- Config
@pytest.fixture(scope="session")
def config(request) -> dict:
    """Resolved environment config (secrets come from env vars / .env)."""
    return load_config(request.config.getoption("--test-env"))


@pytest.fixture(scope="session")
def ui_config(config) -> dict:
    return config.get("ui", {})


@pytest.fixture(scope="session")
def api_config(config) -> dict:
    return config.get("api", {})


# ---------------------------------------------------------------- Browser
_BROWSER_ALIASES = {"chrome": "chromium", "edge": "chromium", "chromium": "chromium",
                    "firefox": "firefox", "webkit": "webkit"}
# "chrome" uses Playwright's bundled Chromium; "edge" needs Microsoft Edge installed.
_BROWSER_CHANNELS = {"edge": "msedge"}


@pytest_asyncio.fixture(scope="function")
async def base(request):
    """A BasePage wrapping a fresh Playwright page for each test."""
    requested = request.config.getoption("--test-browser").lower()
    browser_name = _BROWSER_ALIASES.get(requested, requested)
    headless = True if request.config.getoption("--headless") else None

    driver_manager = DriverManager(browser_name, headless=headless,
                                   channel=_BROWSER_CHANNELS.get(requested))
    await driver_manager.start()

    base_page = BasePage(driver_manager)
    await base_page.init_page()

    yield base_page

    # Attach a screenshot to Allure when the test body failed
    rep = getattr(request.node, "rep_call", None)
    if rep is not None and rep.failed and base_page.page:
        try:
            png = await base_page.page.screenshot(full_page=True)
            allure.attach(png, name="Failure Screenshot", attachment_type=allure.attachment_type.PNG)
        except Exception as e:  # page may already be closed
            print(f"[conftest] could not capture failure screenshot: {e}")

    if base_page.page:
        await base_page.page.close()
    await driver_manager.quit()


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Expose the test outcome on the item (item.rep_setup / rep_call / rep_teardown)."""
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)


# ---------------------------------------------------------------- Allure housekeeping
def pytest_configure(config):
    # Skip in CI — CI builds use unique allure dirs per build so they're always fresh
    if os.environ.get("CI") or os.environ.get("BUILD_NUMBER") or os.environ.get("JENKINS_URL"):
        return

    allure_dir = config.getoption("--alluredir", default=None)
    if not allure_dir:
        return

    allure_path = Path(allure_dir)
    if allure_path.exists() and any(allure_path.iterdir()):
        print(f"\n[conftest] allure-results not empty — clearing {allure_path} before run")
        shutil.rmtree(allure_path)
        allure_path.mkdir(parents=True)


# ---------------------------------------------------------------- Database (optional)
@pytest.fixture(scope="session")
def db_conn(config):
    """Session-scoped DB connection; skips the test if DB_* env vars are not set."""
    db_cfg = config.get("db", {})
    if not db_cfg.get("server"):
        pytest.skip("DB not configured (set DB_SERVER / DB_USER / DB_PASSWORD)")
    from DB.db_utils import create_connection  # lazy: pyodbc only needed when used

    conn = create_connection(db_cfg)
    yield conn
    conn.close()
