# Automation Baseline — Agent Entry Point

Read this file first. Then follow the pointers below.

## What this repo is

Generic UI + API test automation baseline (pytest):
- `ui/tests/` — Playwright UI tests (async pytest), page objects in `ui/pages/`
- `api/tests/` — API tests (sync pytest + requests), builders in `api/data/`
- `common/config_loader.py` — environment config + secrets resolution
- `DB/db_utils.py` — optional SQL Server helpers
- `qa_agent/` — manual review tooling (no git hooks installed)
	- CLI: `qa_agent/review_summary_cli.py` — manage `qa_agent/review_summary.json` and optionally post it to a PR
	- Workflow: `.github/workflows/attach-review-summary.yml` — posts `qa_agent/review_summary.json` as a PR comment when present

Setup and usage: `README.md`. AI layer overview: `AI/README.md`.

## AI assistance

All agent specs live in `AI/agents/`. Read the relevant one before acting.

| What you want to do | Read |
|---|---|
| Fix a failing test | `AI/agents/self-heal.md` |
| Write a new test | `AI/agents/write-test.md` |
| Review a test | `AI/agents/review-test.md` |
| Understand test rules | `AI/conventions.md` |

## Start here when debugging

| Problem | File to read |
|---|---|
| Impact / what to retest | `qa_agent/repo_brain.json` (rebuild with `python qa_agent/update_brain.py`) |
| Raw request/response of last run | `allure-results/local/` |
| Environment config | `config/<env>.json` (+ `.env`, see `.env.example`) |
| Fixtures | `conftest.py`, `api/conftest.py` |
| API request builders | `api/data/` |
| UI page objects | `ui/pages/` |

## Key rules (never violate)

- No `time.sleep()` in tests — use `api/utils/wait_utils.py`
- No hardcoded URLs/credentials — read from `config/` (secrets via env vars / `.env`)
- No raw Playwright calls in test functions — use page objects in `ui/pages/`
- After changing imports: `python qa_agent/update_brain.py`

## Validation commands

```bash
# Full regression
pytest -m regression --test-env=uat --test-browser=chrome -n2 --alluredir=allure-results/local

# API only
pytest -m apiregression --test-env=uat

# UI only
pytest -m uiregression --test-env=uat

# Single file
pytest ui/tests/<file> --test-env=uat --test-browser=chrome

# Rebuild import graph
python qa_agent/update_brain.py
```
