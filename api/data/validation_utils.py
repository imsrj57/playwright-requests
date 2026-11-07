"""
Helpers for data-driven positive/negative API cases.

A case is a dict such as:
    {
      "name": "email missing",
      "remove_keys": ["email"],
      "overrides": {"address": {"zip": ""}},
      "should_succeed": false,
      "expected_status": 400,
      "expected_response_contains": "email is required",
      "success_key": "id"            # key expected in a 200 body (optional)
    }
"""
import json
import re


def _prefixed(root, key):
    return f"{root}.{key}" if root else key


def get_validation_fields(case, root=""):
    """Return the dotted field names a data-driven negative case touches
    (from `remove_keys` and `overrides`), optionally prefixed with `root`."""
    fields = []
    for key in case.get("remove_keys", []):
        if key:
            fields.append(_prefixed(root, key))

    overrides = case.get("overrides", {})
    for key, value in overrides.items():
        if isinstance(value, dict):
            if value:
                for subkey in value:
                    fields.append(_prefixed(root, f"{key}.{subkey}"))
            else:
                fields.append(_prefixed(root, key))
        else:
            fields.append(_prefixed(root, key))

    return [field for field in fields if field]


def normalize_validation_text(value):
    if not isinstance(value, str):
        return ""
    token = value.lower()
    token = re.sub(r"[^a-z0-9]+", "", token)
    return token


def response_mentions_validation_field(response_body, fields):
    if not fields:
        return False

    normalized_raw = ""
    if isinstance(response_body, (dict, list)):
        normalized_raw = normalize_validation_text(json.dumps(response_body, indent=2))
    else:
        normalized_raw = normalize_validation_text(str(response_body))

    actual_fields = set()
    if isinstance(response_body, list):
        for item in response_body:
            if isinstance(item, dict):
                actual_fields.add(normalize_validation_text(item.get("Field")))
                actual_fields.add(normalize_validation_text(item.get("ErrorDescription")))
    elif isinstance(response_body, dict):
        actual_fields.add(normalize_validation_text(response_body.get("Field")))
        actual_fields.add(normalize_validation_text(response_body.get("ErrorDescription")))

    for field in fields:
        normalized = normalize_validation_text(field)
        field_suffix = normalize_validation_text(field.split(".")[-1])

        if normalized and any(normalized in actual for actual in actual_fields if actual):
            return True

        if field_suffix and any(actual.endswith(field_suffix) for actual in actual_fields if actual):
            return True

        if normalized and normalized in normalized_raw:
            return True

    return False


def response_contains_expected_text(response_body, expected_text):
    if not expected_text:
        return False

    normalized_expected = normalize_validation_text(expected_text)
    if not normalized_expected:
        return False

    if isinstance(response_body, (dict, list)):
        normalized_raw = normalize_validation_text(json.dumps(response_body, indent=2))
    else:
        normalized_raw = normalize_validation_text(str(response_body))

    if normalized_expected in normalized_raw:
        return True

    if isinstance(response_body, list):
        for item in response_body:
            if isinstance(item, dict):
                if normalized_expected in normalize_validation_text(item.get("Field")):
                    return True
                if normalized_expected in normalize_validation_text(item.get("ErrorDescription")):
                    return True
    elif isinstance(response_body, dict):
        if normalized_expected in normalize_validation_text(response_body.get("Field")):
            return True
        if normalized_expected in normalize_validation_text(response_body.get("ErrorDescription")):
            return True

    return False


def build_default_expected_response(case, root=""):
    validation_fields = get_validation_fields(case, root=root)
    if not validation_fields:
        return None

    field = validation_fields[0]
    field_suffix = field.split('.')[-1]
    case_name = case.get('name', '').lower()

    if any(token in case_name for token in ('empty', 'spaces', 'null', 'required', 'missing')):
        verb = 'is required'
    elif any(token in case_name for token in ('invalid', 'special', 'numeric', 'sql', 'xss', 'boolean', 'not valid')):
        verb = 'is invalid'
    else:
        verb = 'is required'

    return f'{_prefixed(root, field_suffix)} {verb}'


def assert_case_result(response, should_succeed, case, root=""):
    case_name = case.get('name', 'Unnamed case')
    assert response is not None and isinstance(response, dict), f"{case_name}: response is invalid"
    status_code = response.get('status_code')
    response_body = response.get('body')

    assert status_code is not None, f"{case_name}: response did not return an HTTP status code"

    if should_succeed:
        assert status_code == 200, (
            f"{case_name}: expected HTTP 200 but got {status_code}. Response body: {response_body}"
        )
        assert isinstance(response_body, dict), (
            f"{case_name}: expected JSON response body but got {type(response_body).__name__}: {response_body}"
        )
        success_key = case.get('success_key')
        if success_key:
            assert success_key in response_body, (
                f"{case_name}: expected '{success_key}' in response body but got {response_body}"
            )
    else:
        assert not (500 <= status_code < 600), (
            f"{case_name}: server error HTTP {status_code} should be treated as failure. Response body: {response_body}"
        )

        allowed_status_codes = case.get('allowed_status_codes', [200, 400, 422])

        if status_code == 200:
            assert 200 in allowed_status_codes, (
                f"{case_name}: HTTP 200 is not an allowed success response for this case. Response body: {response_body}"
            )
            return

        assert status_code in allowed_status_codes, (
            f"{case_name}: expected one of {allowed_status_codes} for validation case but got {status_code}. Response body: {response_body}"
        )

        expected_text = case.get('expected_response_contains') or build_default_expected_response(case, root=root)
        assert response_contains_expected_text(response_body, expected_text), (
            f"{case_name}: expected response to contain '{expected_text}', but got {response_body}"
        )


def assert_case_simple(response, case, root=""):
    """Simpler assertion flow: case may provide `expected_status` and
    `expected_response_contains`. If not provided, falls back to
    assert_case_result behavior.
    """
    status_code = response.get('status_code')
    response_body = response.get('body')

    expected_status = case.get('expected_status')
    expected_text = case.get('expected_response_contains')

    if expected_status is not None:
        if isinstance(expected_status, (list, tuple, set)):
            assert status_code in expected_status, (
                f"{case.get('name','case')}: expected one of {list(expected_status)} "
                f"but got {status_code}. Response body: {response_body}"
            )
            return
        if expected_status == 200:
            # expect success
            assert status_code == 200, (
                f"{case.get('name','case')}: expected HTTP 200 but got {status_code}. Response body: {response_body}"
            )
            assert isinstance(response_body, dict), (
                f"{case.get('name','case')}: expected JSON response body but got {type(response_body).__name__}: {response_body}"
            )
            success_key = case.get('success_key')
            if success_key:
                assert success_key in response_body, (
                    f"{case.get('name','case')}: expected '{success_key}' in response body but got {response_body}"
                )
        else:
            assert not (500 <= status_code < 600), (
                f"{case.get('name','case')}: server error HTTP {status_code} should be treated as failure. Response body: {response_body}"
            )
            assert status_code == expected_status, (
                f"{case.get('name','case')}: expected HTTP {expected_status} but got {status_code}. Response body: {response_body}"
            )
            if expected_text:
                assert response_contains_expected_text(response_body, expected_text), (
                    f"{case.get('name','case')}: expected response to contain '{expected_text}', but got {response_body}"
                )
    else:
        # fallback to existing, more flexible assertion
        assert_case_result(response, case.get('should_succeed', False), case, root=root)


def apply_case(base_entity, case, root=""):
    """Apply `case['overrides']` and `case['remove_keys']` to a base entity dict.
    `root` is used only for message generation; the function treats overrides as
    the direct keys to merge into `base_entity`.
    """
    entity = base_entity.copy()
    entity.update(case.get('overrides', {}))

    # Deep-merge nested dict overrides instead of replacing them wholesale
    for nested_key, nested_value in case.get('overrides', {}).items():
        if isinstance(nested_value, dict) and isinstance(base_entity.get(nested_key), dict):
            entity[nested_key] = {**base_entity[nested_key], **nested_value}

    for key in case.get('remove_keys', []):
        entity.pop(key, None)
    return entity



# Backwards-compatible alias
assert_transaction_result = assert_case_result
