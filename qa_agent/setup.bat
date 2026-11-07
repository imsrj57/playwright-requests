@echo off
python qa_agent/update_brain.py
if %ERRORLEVEL% EQU 0 (
  echo ========================================
  echo Review Agent setup complete
  echo ========================================
  echo Hooks are disabled for automatic git operations.
  echo Use the review tools manually for change review.
  echo.
  echo Repo brain     : generated
  echo   qa_agent/repo_brain.json
  echo.
  echo You only need to run this ONCE to refresh the repo brain.
  echo ========================================
) else (
  echo Failed to generate repo brain.
)
