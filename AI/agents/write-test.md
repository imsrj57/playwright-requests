# Write-Test Agent

Generate a new test in team style. Read `AI/conventions.md` first.

## Inputs

- **Type**: `api` or `ui`
- **Description**: scenario to test (e.g. "create item — missing required name returns 400")

---

## Step 1 — Learn from existing code

Do NOT generate from generic knowledge. Read these first:

**If api:**
- `api/tests/example_api_test.py` and any existing `api/tests/*_test.py` for the same feature
- `api/conftest.py` (fixtures `api_client`, auto request/response attachment)
- `api/utils/api_request.py`, `api/utils/wait_utils.py`
- `api/data/validation_utils.py` (for negative / data-driven cases)

**If ui:**
- `ui/tests/example_ui_test.py` and any existing `ui/tests/*_test.py` for the same feature
- `conftest.py` (root — `base`, `ui_config`)
- `ui/pages/BasePage.py`, `ui/pages/login.py`

Then read the specific `api/data/` or `ui/pages/` files relevant to the scenario.

---

## Step 2 — Check the import graph

Read `qa_agent/repo_brain.json` (rebuild with `python qa_agent/update_brain.py` if stale):
- Identify which builders / page objects already exist for this scenario
- Import only what exists — do not invent modules
- If a new builder (`api/data/`) or page object (`ui/pages/`) is needed, create it as a separate file and say so

---

## Step 3 — Write the test

Match existing file style — same structure, naming, patterns.

**API test skeleton:**
```
imports: allure, pytest, api.utils.api_request asserts, api.data builders
optional autouse fixture that skips when api.base_url is not configured
@allure.title / suite markers
def test_<scenario>(api_client):
    payload = build_<thing>_payload(...)          # from api/data/
    response = api_client.post("/<endpoint>", json=payload)
    assert_status(response, 201)
    body = assert_json_keys(response, "id")
    (async state? -> wait_for_state(...), never time.sleep)
```

**Negative cases:** parametrize over case dicts, `apply_case(base_payload, case)`, then `assert_case_simple(response, case)`.

**UI test skeleton:**
```
imports: allure, pytest, get_value, page objects from ui/pages/
optional autouse fixture that skips when ui.base_url is not configured
@allure.title / suite markers
async def test_<scenario>(base, ui_config):
    username = get_value(ui_config, "users.default.username", required=True)
    password = get_value(ui_config, "users.default.password", required=True)
    await LoginPage(base).login(ui_config["base_url"], username, password)
    page = <PageClass>(base)
    await page.<action>(...)
    assert await page.<query>() == expected, "..."
```
Locators belong in the page object class, not the test module.

---

## Step 4 — File placement

- New scenario for an existing feature → add a function to the existing test file
- New feature → new file `<feature>_test.py` in `api/tests/` or `ui/tests/`

---

## Checklist before finishing

- [ ] Markers are registered in `pytest.ini` and follow `AI/conventions.md`
- [ ] `@allure.title` (or module/class `@allure.feature`) present
- [ ] No hardcoded URLs, credentials or tokens
- [ ] No `time.sleep`; no raw Playwright calls in the test
- [ ] Correct import paths (no phantom imports)

## Tell the user

1. Complete test code (plus any new builder / page object)
2. Which file it goes in
3. Run command: `pytest <path> --test-env=uat ...`
4. Any new config keys / env vars required (add to `config/*.json` and `.env.example`)
5. If new imports added: `python qa_agent/update_brain.py`
