# Copilot Instructions

Read `AI/README.md` for the full AI assistance layer overview.
Read `AI/conventions.md` for test writing rules before helping with any test.

## Quick map

| Task | Read first |
|---|---|
| Fix a failing test | `AI/agents/self-heal.md` |
| Write a new test | `AI/agents/write-test.md` |
| Review a test | `AI/agents/review-test.md` |

## Repo layout (quick ref)

- UI tests: `ui/tests/` — async Playwright + pytest
- API tests: `api/tests/` — sync requests + pytest
- Page objects: `ui/pages/` (`BasePage`, `LoginPage`)
- API builders / payload factories: `api/data/`
- API client, asserts, waits: `api/utils/`
- Config loader: `common/config_loader.py` — `config/<env>.json` + env vars / `.env`
- Review tools: `qa_agent/` (manual review tooling)
- Import graph: `qa_agent/repo_brain.json`
