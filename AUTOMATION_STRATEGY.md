# Automation Strategy & Implementation Notes

How the baseline is meant to be used, what review tooling exists, and recommended next optimisations.
Setup and day-to-day usage: `README.md`.

---

## Principles

- **Layered:** tests → page objects (`ui/pages/`) / builders (`api/data/`) → utils. Tests contain intent and assertions only.
- **Config-driven:** every environment-specific value lives in `config/<env>.json` as a `${VAR}` placeholder; secrets come from env vars / `.env` / CI secrets.
- **Deterministic waits:** polling helpers (`api/utils/wait_utils.py`) and `BasePage` waits — never fixed sleeps.
- **Observable:** every API call and every UI failure is attached to Allure automatically.
- **Fail soft on missing config:** template tests skip when their base URL / credentials are not set, so a fresh clone runs green.

## Suite tiers

| Tier | Markers | When |
|---|---|---|
| Sanity | `sanity`, `apisanity`, `uisanity` | Every change / smoke after deploy |
| Regression | `regression`, `apiregression`, `uiregression` | Before merge, nightly / scheduled pipeline |
| DB-backed | `db` | Only where a DB connection is configured |
| Load | any marker via `api/utils/run_locust.py` | On demand |

---

## Review tooling (`qa_agent/`, manual — no git hooks)

```
qa_agent/
├── setup.bat               ← Rebuilds the repo brain (one-off convenience)
├── update_brain.py         ← Rebuilds repo_brain.json (run after adding, deleting, renaming or moving files)
├── impact_analyzer.py      ← Uses the import graph to find which tests a change affects
├── quality_checker.py      ← Scans Python files: unregistered markers, hardcoded URLs/credentials, fixture misuse
├── results_checker.py      ← Validates Allure results (date, regression tag, pass rate)
├── push_override.py        ← Records a single-use override reason for the results check
├── review_summary_cli.py   ← ack / apply / show / post-pr for qa_agent/review_summary.json
├── audit.py                ← Branch alignment + audit trail helpers
├── repo_brain.json         ← Cached import graph (git-ignored)
└── hooks/post_merge_handler.py ← Optional brain rebuild after pull
```

`.github/workflows/attach-review-summary.yml` posts `qa_agent/review_summary.json` as a PR comment when present.

### Review decision flow

```
change set
    │
    ▼
[1] Quality check      ← changed Python files
    │
    ▼
[2] Impact analysis    ← import graph → affected tests
    │
    ├── no test impact (pipeline, docs, config) ──► results check skipped
    │
    └── test impact
            ▼
        [3] Results check
                ├── no results                         → block
                ├── results not from today             → block (override allowed)
                ├── no regression tag in results       → block
                ├── pass rate < 80%                    → block (override allowed)
                ├── impacted tests missing from results→ block
                └── otherwise                          → pass
```

Accepted regression tags: `regression`, `uiregression`, `apiregression`. Sanity runs do not satisfy the results check.

```bash
pytest -m regression --test-env=uat --alluredir=allure-results/local
python qa_agent/push_override.py --reason "your reason here"   # single-use override
```

---

## Recommended optimisations (not yet implemented)

### 1. Session-scoped browser
Today `base` launches a browser per test. Keep one browser per worker session and create a fresh **context** per test (isolated cookies/storage).
Requires `asyncio_default_fixture_loop_scope = session` and validation with `pytest-xdist`; earlier attempts hung on event-loop interaction, so test carefully.
Expected gain: roughly 30–40% less UI runtime.

### 2. Safe multi-user switch
For flows that need two users (e.g. maker/checker), add `BasePage.switch_user()` that closes the current page **and context** and opens a new context — reusing the same context leaks the first user's session.

### 3. Leaner BasePage waits
`click_element` / `input_element` wait for network idle before and DOM stability after each action. Prefer: wait visible → act → wait for network idle only after actions that trigger navigation or requests. Avoid polling full `page.content()` for stability.
Expected gain: roughly 20–30% per-test wall time.

### 4. Split API and UI workers in CI
API tests do not need a browser. Run `api/tests` with more workers (`-n4 --dist=loadfile`) separately from `ui/tests` so browser workers are not starved.

### 5. Report before exit in the pipeline
Generate the enhanced report before the step exits on test failure, so the publish step always finds its folder.

---

## Running locally

```bash
pytest -m regression --test-env=uat --test-browser=chrome -n2 --alluredir=allure-results/local
pytest -m uisanity --test-env=uat --test-browser=chrome -n2
pytest ui/tests/<file> --test-env=uat --test-browser=chrome
python qa_agent/update_brain.py
```
