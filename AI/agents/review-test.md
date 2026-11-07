# Review-Test Agent

Review a test file against team conventions. Read `AI/conventions.md` first.

## Inputs

- A test file path, or
- A git diff (review changed lines only)

---

## Context to load

1. `AI/conventions.md`
2. The target test file
3. `qa_agent/repo_brain.json` → check `test_imports_test` and `imports` for this file
4. Optionally run `qa_agent/quality_checker.py` logic mentally: markers, hardcoded URLs/credentials, fixture names

---

## Checklist

**Structure**
- [ ] File in `api/tests/` or `ui/tests/`
- [ ] Name: `<name>_test.py`
- [ ] Test functions prefixed `test_`

**Markers**
- [ ] `@allure.title` on every test (or `@allure.feature` on module/class)
- [ ] At least one suite marker (`apiregression`, `apisanity`, `uiregression`, `uisanity`, `regression`, `sanity`)
- [ ] All markers registered in `pytest.ini`
- [ ] `db` marker when `db_conn` is used

**Imports and structure**
- [ ] No request-building logic in the test file — belongs in `api/data/`
- [ ] No Playwright calls or locators in test functions — belongs in `ui/pages/`
- [ ] No test file importing another test file (`repo_brain.json` → `test_imports_test`)
- [ ] All imports resolve to files that exist

**Fixtures and config**
- [ ] `config`, `api_config`, `ui_config`, `api_client`, `base`, `db_conn` not redefined
- [ ] `scope="session"` for expensive shared setup (tokens, clients)
- [ ] No hardcoded credentials, tokens or URLs — via `config/` / `get_value`
- [ ] Test skips cleanly when required config is missing

**Assertions**
- [ ] No bare `assert response`
- [ ] Status asserted (`assert_status`) and specific fields checked
- [ ] Meaningful assertion messages that show actual values

**Anti-patterns**
- [ ] No `time.sleep()` — use `api/utils/wait_utils.py`
- [ ] No manual request/response attachments duplicating the auto-attach in `api/conftest.py`
- [ ] No hardcoded test data that should come from `api/data/` or `test_data/`

---

## Report format

```
[BLOCK] What is wrong
  Line: ~<n>  |  Fix: <concrete suggestion>

[WARN] What is wrong
  Line: ~<n>  |  Fix: <concrete suggestion>

[SUGGEST] Improvement
  Line: ~<n>  |  Fix: <concrete suggestion>
```

End with:
```
Total: X block / Y warn / Z suggest
Verdict: READY TO PUSH | NEEDS FIXES | ADVISORY
```
