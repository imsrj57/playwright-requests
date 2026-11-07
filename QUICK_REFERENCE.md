# Quick Reference

Cheat sheet for daily use. Details: `README.md`, rules: `AI/conventions.md`.

## Commands

```bash
# Suites
pytest -m regression    --test-env=uat --test-browser=chrome -n2 --alluredir=allure-results/local
pytest -m apiregression --test-env=uat
pytest -m uiregression  --test-env=uat --test-browser=chrome
pytest -m "apisanity or uisanity" --test-env=qa

# Narrow down
pytest api/tests/<file>_test.py -v
pytest api/tests/<file>_test.py::test_<name> -v
pytest api/tests -k "<keyword>" -v
pytest ui/tests/<file>_test.py --test-browser=firefox --headless

# Rerun flaky failures (pytest-rerunfailures)
pytest -m uiregression --reruns 1

# Reports
allure serve allure-results/local
python report_generator_enhanced.py allure-results/local reports/enhanced

# Tooling
python qa_agent/update_brain.py                 # after adding/moving files or changing imports
python enhancement/generate_markers_list.py     # list markers used vs registered
python qa_agent/review_summary_cli.py show
```

## Fixtures

| Fixture | Use |
|---|---|
| `config` / `api_config` / `ui_config` | Resolved env config sections |
| `api_client` | Authenticated `APIRequest` (`get/post/put/patch/delete`, `set_bearer_token`) |
| `base` | `BasePage` on a fresh Playwright page |
| `db_conn` | DB connection (skips if not configured) |

## Helpers

| Need | Use |
|---|---|
| Assert status / keys / schema | `assert_status`, `assert_json_keys`, `assert_json_schema` (`api/utils/api_request.py`) |
| Wait for async state | `wait_for_condition`, `wait_for_state`, `wait_for_key`, `wait_for_db_record` (`api/utils/wait_utils.py`) |
| Negative / data-driven cases | `apply_case`, `assert_case_simple`, `assert_case_result` (`api/data/validation_utils.py`) |
| Auth headers | `build_auth_headers(api_config)` (`api/data/authenticate.py`) |
| UI actions | `BasePage`: `goto`, `click_element`, `input_element`, `select_dropdown_option`, `wait_for_loader`, `take_screenshot` |
| Login | `LoginPage(base).login(url, username, password)` (`ui/pages/login.py`) |
| Resilient locators | `HealingLocator(page).find(name, [selectors...])` (`ui/utils/healing_driver.py`) |
| Visual regression | `check_visual_regression(page, name=..., threshold=...)` (`ui/utils/visual_regression_pillow.py`) |
| Share data between tests | `write_value` / `read_value` (`ui/utils/runtime_data.py`) |
| SQL | `fetch_all`, `fetch_one`, `execute` (`DB/db_utils.py`) |
| Nested config value | `get_value(cfg, "a.b.c", required=True)` (`common/config_loader.py`) |

## Config env vars

`API_BASE_URL`, `API_AUTH_TYPE`, `API_TOKEN_URL`, `API_CLIENT_ID`, `API_CLIENT_SECRET`, `API_USERNAME`, `API_PASSWORD`, `API_TOKEN`, `API_KEY_HEADER`, `API_KEY`,
`UI_BASE_URL`, `UI_USERNAME`, `UI_PASSWORD`, `UI_ADMIN_USERNAME`, `UI_ADMIN_PASSWORD`,
`DB_SERVER`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` — template in `.env.example`.

## Negative-testing checklist (API)

- Missing required field → 400/422 (never 500)
- Wrong type / format / out-of-range value → 400/422
- Missing required query parameter → 400 (not 404)
- Null nested object → 400/422
- Missing / invalid auth → 401/403
- Error body names the offending field (`expected_response_contains`)
