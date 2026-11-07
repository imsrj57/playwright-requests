---
mode: 'agent'
description: 'Diagnose and fix a failing API test'
---

Read the conventions and agent spec, then follow them exactly.

#file:AI/conventions.md
#file:AI/agents/self-heal.md

## Scope in Copilot

**API tests only.** Follow the "API Path" section of the agent spec.

> UI test self-heal works best with live browser replay via Playwright MCP (Claude Code).
> For a failing UI test, use the `self-heal-ui` prompt or Claude Code `/self-heal-ui`,
> or manually inspect the DOM and compare with the page object locators.

## Your inputs

The user will provide a failing test file path and/or the pytest error output.
If neither is provided, check `allure-results/local/` for the latest failures or ask.
