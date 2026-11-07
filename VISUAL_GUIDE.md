# CI Pipeline Reporting — Visual Guide

How test results are reported in `Automation-pipeline.yml` (Azure DevOps).

## Flow

```
pytest -m <tag> --alluredir=<results>
        │
        ├──► report_generator_enhanced.py ──► Enhanced-Test-Report artifact (HTML + JSON, small, fast)
        │                                     summary also printed to the pipeline log
        │
        └──► raw Allure results ───────────► Allure-Results-<BuildNumber> artifact (download, view locally)
```

The quick report is generated after tests finish (a few seconds of overhead); the full Allure report is not rendered in the pipeline, so it never blocks the run.

## Pipeline parameters

| Parameter | Values |
|---|---|
| `test_env` | `qa`, `uat` |
| `test_tag` | `sanity`, `regression`, `apisanity`, `apiregression`, `uisanity`, `uiregression` |
| `test_browser` | `chrome`, `edge`, `firefox` |

Secrets are pipeline secret variables mapped to the env vars listed in `.env.example`.

## Quick summary (example)

```
=======================================================================
TEST EXECUTION SUMMARY
=======================================================================
Total Tests: 45
✓ Passed: 42
✗ Failed: 2
⚠ Skipped: 1
⛔ Broken: 0
Duration: 234.50s
=======================================================================
```

## Viewing the full Allure report

1. Download the `Allure-Results-<BuildNumber>` artifact and extract it.
2. Run:
   ```bash
   allure serve <extracted-folder>
   # or
   allure generate <extracted-folder> -o allure-report && allure open allure-report
   ```
3. The report includes steps, request/response attachments (auth headers redacted), failure screenshots and trends.

## When to use what

| Need | Use |
|---|---|
| Is the build green? Which tests failed? | Enhanced-Test-Report |
| Why did a test fail (steps, payloads, screenshots)? | Full Allure report |
| Trends over time | Archive the summary JSON per build |
