# api/data/authenticate.py
"""
Generic authentication helpers.

Auth behaviour is driven by `config["api"]["auth"]["type"]`:

  none                      -> no auth header
  bearer                    -> Authorization: Bearer <token>
  basic                     -> Authorization: Basic base64(username:password)
  api_key                   -> <api_key_header>: <api_key>
  oauth_client_credentials  -> POST token_url (grant_type=client_credentials), use access_token

All secret values must come from environment variables / .env — see `.env.example`.
"""

import base64
from typing import Optional

import allure
import requests


def basic_auth_header(username: str, password: str) -> dict:
    encoded = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("utf-8")
    return {"Authorization": f"Basic {encoded}"}


def bearer_auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@allure.step("Fetch OAuth2 access token (client credentials)")
def get_client_credentials_token(
    token_url: str,
    client_id: str,
    client_secret: str,
    scope: Optional[str] = None,
    extra_data: Optional[dict] = None,
    timeout: float = 30,
) -> str:
    data = {"grant_type": "client_credentials"}
    if scope:
        data["scope"] = scope
    if extra_data:
        data.update(extra_data)

    response = requests.post(
        token_url,
        data=data,
        auth=(client_id, client_secret),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=timeout,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Token request failed: {response.status_code} {response.text[:500]}")

    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("access_token not found in token response")
    return token


@allure.step("Fetch access token (password grant)")
def get_password_grant_token(token_url: str, username: str, password: str,
                             client_id: Optional[str] = None, client_secret: Optional[str] = None,
                             timeout: float = 30) -> str:
    data = {"grant_type": "password", "username": username, "password": password}
    auth = (client_id, client_secret) if client_id and client_secret else None
    response = requests.post(token_url, data=data, auth=auth, timeout=timeout)
    if response.status_code != 200:
        raise RuntimeError(f"Token request failed: {response.status_code} {response.text[:500]}")
    return response.json()["access_token"]


def build_auth_headers(api_config: dict) -> dict:
    """Return the auth headers to attach to every request, based on config."""
    auth = api_config.get("auth", {}) or {}
    auth_type = (auth.get("type") or "none").lower()

    if auth_type == "none":
        return {}
    if auth_type == "bearer":
        return bearer_auth_header(_require(auth, "token"))
    if auth_type == "basic":
        return basic_auth_header(_require(auth, "username"), _require(auth, "password"))
    if auth_type == "api_key":
        return {auth.get("api_key_header") or "x-api-key": _require(auth, "api_key")}
    if auth_type == "oauth_client_credentials":
        token = get_client_credentials_token(
            token_url=_require(auth, "token_url"),
            client_id=_require(auth, "client_id"),
            client_secret=_require(auth, "client_secret"),
            scope=auth.get("scope"),
            timeout=api_config.get("timeout", 30),
        )
        return bearer_auth_header(token)

    raise ValueError(f"Unsupported api.auth.type: {auth_type}")


def _require(auth: dict, key: str) -> str:
    value = auth.get(key)
    if not value:
        raise ValueError(f"api.auth.{key} is empty — set the matching environment variable (see .env.example)")
    return value
