"""
TEMPLATE — copy this file to start a new API test module, then delete it.

Run:  pytest api/tests/example_api_test.py --test-env=qa
Needs API_BASE_URL (and auth vars if API_AUTH_TYPE != none) — see .env.example.
"""
import allure
import pytest

from api.utils.api_request import assert_status


@pytest.fixture(autouse=True)
def _require_api_config(api_config):
    if not api_config.get("base_url") or "example.com" in api_config["base_url"]:
        pytest.skip("API_BASE_URL not configured")


@allure.feature("Example")
@pytest.mark.example
@pytest.mark.apisanity
def test_example_health_check(api_client):
    response = api_client.get("/health")  # replace with a real endpoint
    assert_status(response, 200)
