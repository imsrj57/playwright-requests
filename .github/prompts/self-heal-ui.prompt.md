---
mode: 'agent'
description: 'Diagnose and fix a failing UI test'
---

Read the conventions and agent spec, then follow them exactly.

#file:AI/conventions.md
#file:AI/agents/self-heal.md

## Scope in Copilot

**UI tests only.** Follow the "UI Path" section of the agent spec.
Use the failing test file from `ui/tests/` and any imported page objects in `ui/pages/`.
If live browser replay is not available, still identify the likely locator/wait issue and propose exact file/line fixes.

## Your inputs

The user will provide a failing UI test file path and/or the pytest error output.
If neither is provided, ask before proceeding.
