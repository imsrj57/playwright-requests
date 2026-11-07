# Contributing

Thanks for helping improve the framework!

1. Fork and create a branch: `git checkout -b feature/<short-name>`.
2. Set up: `pip install -r requirements.txt && playwright install`.
3. Follow the rules in [`AI/conventions.md`](AI/conventions.md):
   - no `time.sleep()` in tests — use `api/utils/wait_utils.py`
   - no hardcoded URLs or credentials — use `config/` + env vars
   - no raw Playwright calls in tests — use page objects in `ui/pages/`
4. Run the checks locally:
   ```bash
   python -m compileall -q api ui common DB qa_agent
   pytest --collect-only -q
   python qa_agent/update_brain.py   # if you changed imports
   ```
5. Open a pull request describing what changed and why. CI must be green.

Never include real environment data (URLs, users, screenshots, reports) in a PR.
