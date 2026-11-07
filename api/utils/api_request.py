# api/utils/api_request.py
"""Thin, reusable wrapper around `requests.Session` for API tests."""

from typing import Any, Optional

import allure
import requests


class APIRequest:
    def __init__(
        self,
        base_url: str,
        access_token: Optional[str] = None,
        headers: Optional[dict] = None,
        timeout: float = 30,
        verify: bool = True,
    ):
        self.base_url = (base_url or "").rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.verify = verify
        self.session.headers.update({"Accept": "application/json"})
        if headers:
            self.session.headers.update(headers)
        if access_token:
            self.set_bearer_token(access_token)

    # ------------------------------------------------------------ headers
    def set_bearer_token(self, token: str) -> None:
        self.session.headers["Authorization"] = f"Bearer {token}"

    def set_header(self, key: str, value: str) -> None:
        self.session.headers[key] = value

    def remove_header(self, key: str) -> None:
        self.session.headers.pop(key, None)

    # ------------------------------------------------------------ core
    def build_url(self, endpoint: str) -> str:
        if endpoint.startswith(("http://", "https://")):
            return endpoint
        return f"{self.base_url}/{endpoint.lstrip('/')}"

    def request(self, method: str, endpoint: str, **kwargs: Any) -> requests.Response:
        url = self.build_url(endpoint)
        kwargs.setdefault("timeout", self.timeout)
        with allure.step(f"{method.upper()} {endpoint}"):
            response = self.session.request(method.upper(), url, **kwargs)
        self._log_request_response(method, url, response)
        return response

    def get(self, endpoint: str, params: Optional[dict] = None, **kwargs) -> requests.Response:
        return self.request("GET", endpoint, params=params, **kwargs)

    def post(self, endpoint: str, json: Any = None, data: Any = None, **kwargs) -> requests.Response:
        return self.request("POST", endpoint, json=json, data=data, **kwargs)

    def put(self, endpoint: str, json: Any = None, data: Any = None, **kwargs) -> requests.Response:
        return self.request("PUT", endpoint, json=json, data=data, **kwargs)

    def patch(self, endpoint: str, json: Any = None, data: Any = None, **kwargs) -> requests.Response:
        return self.request("PATCH", endpoint, json=json, data=data, **kwargs)

    def delete(self, endpoint: str, **kwargs) -> requests.Response:
        return self.request("DELETE", endpoint, **kwargs)

    # Backwards-compatible names
    def send_get_request(self, endpoint, params=None):
        return self.get(endpoint, params=params)

    def send_post_request(self, endpoint, data=None, json_data=None):
        return self.post(endpoint, json=json_data, data=data)

    def close(self) -> None:
        self.session.close()

    # ------------------------------------------------------------ helpers
    @staticmethod
    def _log_request_response(method: str, url: str, response: requests.Response) -> None:
        print(f"{method.upper()} {url} -> {response.status_code} ({int(response.elapsed.total_seconds() * 1000)} ms)")


# ---------------------------------------------------------------- assertions
def assert_status(response: requests.Response, expected: int | tuple | list = 200) -> None:
    allowed = expected if isinstance(expected, (list, tuple, set)) else [expected]
    assert response.status_code in allowed, (
        f"Expected status {list(allowed)} but got {response.status_code}. Body: {response.text[:2000]}"
    )


def assert_json_keys(response: requests.Response, *keys: str) -> dict:
    body = response.json()
    missing = [k for k in keys if k not in body]
    assert not missing, f"Response JSON missing keys {missing}. Body: {body}"
    return body


def assert_json_schema(response: requests.Response, schema: dict) -> None:
    """Validate a response body against a JSON schema (requires `jsonschema`)."""
    import jsonschema

    jsonschema.validate(instance=response.json(), schema=schema)
