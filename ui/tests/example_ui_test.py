"""
TEMPLATE — copy this file to start a new UI test module, then delete it.

Run:  pytest ui/tests/example_ui_test.py --test-env=qa --test-browser=chrome
Needs UI_BASE_URL, UI_USERNAME, UI_PASSWORD — see .env.example.
Rule: no raw Playwright calls in tests — go through page objects in ui/pages/.
"""
import allure
import pytest

from common.config_loader import get_value
from ui.pages.login import LoginPage


@pytest.fixture(autouse=True)
def _require_ui_config(ui_config):
    if not ui_config.get("base_url") or "example.com" in ui_config["base_url"]:
        pytest.skip("UI_BASE_URL not configured")


@allure.feature("Example")
@pytest.mark.example
@pytest.mark.uisanity
async def test_example_login(base, ui_config):
    username = get_value(ui_config, "users.default.username", required=True)
    password = get_value(ui_config, "users.default.password", required=True)
    await LoginPage(base).login(ui_config["base_url"], username, password)
