# Self-Heal Agent

Fix a failing test. Read `AI/conventions.md` first.

## Identify the test type

- No file given → ask the user for the failing test or pytest output; otherwise inspect the latest results in `allure-results/local/` (status `failed`/`broken`)
- `api/tests/` → **API path**
- `ui/tests/` → **UI path**

---

## API Path

**Gather context:**
1. Pytest output — failed test name + error
2. `allure-results/local/*-result.json` + attachments — raw HTTP request, response, status code (auto-attached by `api/conftest.py`)
3. The failing test file
4. `qa_agent/repo_brain.json` → find imports → read each `api/data/` file it uses
5. `config/<env>.json` → which `api.*` keys / env vars are involved (never print secret values)

**Classify and fix:**

| Symptom | Cause | Fix |
|---|---|---|
| Wrong status code | API contract changed or bad payload | Fix assertion or payload builder in `api/data/` |
| `KeyError` / missing field | Response schema changed | Update field access / `assert_json_keys` / schema |
| Validation case fails | Expected message or status changed | Update the case dict (`expected_status`, `expected_response_contains`) |
| State not ready yet | Async backend processing | Use `wait_for_state` / `wait_for_condition` — never `time.sleep()` |
| 401 / 403 | Token / credential / auth type issue | Check `api.auth.*` config and env vars |
| Network / timeout / 5xx outage | Environment issue | Report — do NOT change test code |

**Rules:**
- Fix the test or `api/data/` file — not application source code
- Never hardcode credentials or URLs — always from `config/` / env vars
- If environment issue: report root cause, stop

**Run after fixing:** `pytest <file> --test-env=uat --alluredir=allure-results/local`

---

## UI Path

**Gather context:**
1. Pytest output — failed step + error
2. Failure screenshot in `allure-results/local/` (attached by the `base` fixture)
3. The failing test file from `ui/tests/`
4. All `ui/pages/` files it imports
5. `qa_agent/repo_brain.json` — confirm import chain

**Live browser diagnosis via Playwright MCP (Claude Code, `.mcp.json`):**
1. Navigate to `ui.base_url` from the resolved config for the env
2. Log in with the configured test user (`ui.users.default`) the same way `ui/pages/login.py` does — use test credentials from env / `.env` only
3. Replay the test steps up to the failure
4. On failure: screenshot + inspect actual DOM (element state, selector, visibility, URL)
5. Close browser

**Classify and fix:**

| Symptom | Cause | Fix location |
|---|---|---|
| `TimeoutError` on locator | Selector drifted | Update locator in the page object (or add candidates via `HealingLocator`) |
| Found but not interactable | Overlay / loading state | Use `wait_for_loader` / `wait_for_dom_stability` in the page object |
| Wrong page after navigation | Login/redirect issue | Fix `ui/pages/login.py` locators or `LOGGED_IN_INDICATOR` |
| Wrong text content | UI label changed | Update expected string in test |
| Visual diff fails | Intended UI change | Re-baseline with `update_baseline=True` only if change is confirmed |
| Element gone entirely | Feature restructured | Escalate — do not remove assertions |

**Rules:**
- Fix locators/waits in `ui/pages/` — not inline in the test
- Prefer `id`, `data-testid` or role/text selectors over positional XPath
- Never remove an assertion because it's hard — escalate

**Run after fixing:** `pytest ui/tests/<file> --test-env=uat --test-browser=chrome --alluredir=allure-results/local`

---

## Output

1. What changed (file, line, why)
2. Exact rerun command
3. Whether `python qa_agent/update_brain.py` is needed
4. If not fixed: root cause + what human action is needed
