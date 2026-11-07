import json

import allure
import pytest
import requests

from api.data.authenticate import build_auth_headers
from api.utils.api_request import APIRequest

SENSITIVE_HEADERS = {"authorization", "cookie", "set-cookie", "x-api-key", "proxy-authorization"}


def _report_value(value):
    """Return a JSON-friendly representation of a requests value."""
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, (dict, list, tuple, int, float, bool, str)):
        return value
    return str(value)


def _redact_headers(headers):
    """Keep reports useful without exposing credentials or session cookies."""
    return {
        key: "[REDACTED]" if key.lower() in SENSITIVE_HEADERS else _report_value(value)
        for key, value in (headers or {}).items()
    }


def _body_for_report(body):
    body = _report_value(body)
    if isinstance(body, str):
        try:
            return json.loads(body)
        except (TypeError, ValueError):
            return body
    return body


def _response_body(response):
    try:
        return response.json()
    except (TypeError, ValueError):
        return response.text


@pytest.fixture(autouse=True)
def report_api_requests(monkeypatch):
    """Attach the full request and response for every `requests` call to Allure."""
    original_request = requests.sessions.Session.request

    def request_with_report(session, method, url, **kwargs):
        merged_headers = {**dict(session.headers), **(kwargs.get("headers") or {})}
        request_details = {
            "method": method.upper(),
            "url": url,
            "params": _report_value(kwargs.get("params")),
            "headers": _redact_headers(merged_headers),
            "body": _body_for_report(kwargs.get("json", kwargs.get("data"))),
        }
        response_details = {}
        try:
            response = original_request(session, method, url, **kwargs)
            response_details = {
                "status_code": response.status_code,
                "reason": response.reason,
                "elapsed_ms": int(response.elapsed.total_seconds() * 1000),
                "headers": _redact_headers(response.headers),
                "body": _response_body(response),
            }
        except requests.RequestException as error:
            response_details = {"status_code": None, "reason": None, "headers": {}, "body": str(error)}
            raise
        finally:
            operation = f"{method.upper()} {url.split('?')[0].rsplit('/', 1)[-1]}"
            allure.attach(
                json.dumps({"Request": request_details, "Response": response_details}, indent=2, default=str),
                name=f"{operation} - Request & Response",
                attachment_type=allure.attachment_type.JSON,
            )

        return response

    monkeypatch.setattr(requests.sessions.Session, "request", request_with_report)


@pytest.fixture(scope="session")
def api_client(api_config) -> APIRequest:
    """Authenticated API client built from config['api'] (auth type chosen by config)."""
    client = APIRequest(
        base_url=api_config.get("base_url", ""),
        headers=build_auth_headers(api_config),
        timeout=api_config.get("timeout", 30),
        verify=api_config.get("verify_ssl", True),
    )
    yield client
    client.close()
