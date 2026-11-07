# Test Conventions

Rules for writing and reviewing tests in this repo.
All agents read this before acting. Changes must be PRed.

## Where things live

| What | Where |
|---|---|
| API tests | `api/tests/<name>_test.py` |
| UI tests | `ui/tests/<name>_test.py` |
| API request builders / payload factories | `api/data/` only — never inside test files |
| API client + assertions | `api/utils/api_request.py` (`APIRequest`, `assert_status`, `assert_json_keys`, `assert_json_schema`) |
| Negative / data-driven cases | `api/data/validation_utils.py` (`apply_case`, `assert_case_simple`, `assert_case_result`) |
| Polling / waiting | `api/utils/wait_utils.py` — no inline sleep loops |
| UI page objects | `ui/pages/` (extend `BasePage` helpers) — no Playwright calls in test functions |
| Shared UI helpers | `ui/utils/` (healing locators, visual regression, runtime data) |
| DB helpers | `DB/db_utils.py` via the `db_conn` fixture |
| Static test data | `test_data/` |
| Environment config | `config/<env>.json` — values only via `${VAR}` placeholders, no real secrets |

Templates to copy: `api/tests/example_api_test.py`, `ui/tests/example_ui_test.py`.

## Naming

- Files: `<name>_test.py` (repo convention; tooling in `qa_agent/` looks for `*_test.py`)
- Test functions: `test_<scenario>` (snake_case)
- Helpers inside test files: snake_case, no `test_` prefix
- Page objects: one class per page/component, locators as class attributes

## Markers

Only markers registered in `pytest.ini` are allowed:
`regression`, `sanity`, `apiregression`, `apisanity`, `uiregression`, `uisanity`, `db`, `example`.

Every test function gets:
```python
@allure.title("Human-readable scenario name")   # or @allure.feature on the module/class
@pytest.mark.apiregression                      # suite marker: api*/ui* regression or sanity
```
Add `@pytest.mark.db` when the test uses `db_conn`. New feature markers must be registered in `pytest.ini` first.
UI tests are `async def`; `asyncio_mode = auto` is set, so `@pytest.mark.asyncio` is optional.

## Fixtures (from conftest — do not redefine)

| Fixture | Scope | What it is |
|---|---|---|
| `config` | session | Resolved `config/<env>.json` |
| `api_config` / `ui_config` | session | `config["api"]` / `config["ui"]` |
| `api_client` | session | `APIRequest` with auth headers from `config.api.auth` |
| `base` | function | `BasePage` on a fresh Playwright page; failure screenshot attached to Allure |
| `db_conn` | session | DB connection; skips when DB is not configured |

Read nested values with `get_value(cfg, "users.default.username", required=True)`.

## Imports

**API tests**
```python
from api.utils.api_request import assert_status, assert_json_keys
from api.data.<builder_module> import build_<thing>_payload
```

**UI tests**
```python
from common.config_loader import get_value
from ui.pages.login import LoginPage
from ui.pages.<page_module> import <PageClass>
```

## Allure

- Every `requests` call in API tests is attached automatically (request + response, auth headers redacted) by `api/conftest.py` — do not add manual request/response attachments.
- Wrap logical steps with `with allure.step(...)` or `@allure.step` on page-object / builder methods.
- UI failure screenshots are attached automatically by the `base` fixture.

## Assertions

```python
assert_status(response, 200)                     # or (200, 201)
body = assert_json_keys(response, "id", "name")
assert body["name"] == expected_name, f"unexpected name: {body}"
```
- No bare `assert response` — assert status and specific fields
- Always include a message that shows the actual value

## Hard rules

- No `time.sleep()` in tests — use `api/utils/wait_utils.py`
- No hardcoded URLs, credentials, tokens or env values in tests or page objects
- No Playwright calls (`.click`, `.fill`, `.locator`, `page.goto`) in test functions — page objects only
- No test file importing another test file; share data via `api/data/`, `test_data/` or `ui/utils/runtime_data.py`
- Tests skip cleanly (not fail) when their required config is missing
- After adding new imports → `python qa_agent/update_brain.py`
