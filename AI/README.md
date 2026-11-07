# AI Assistance Layer

Agent specs and test conventions for Claude Code, Copilot, and Codex.
Everything in this folder is version-controlled and team-shared.

## What's here

| Path | Purpose |
|---|---|
| `AI/conventions.md` | Test writing rules — all agents read this first |
| `AI/agents/self-heal.md` | Diagnose and fix failing tests |
| `AI/agents/write-test.md` | Generate new tests in team style |
| `AI/agents/review-test.md` | Review test quality before pushing |

## How to invoke

**Claude Code** (slash commands in `.claude/commands/`):
```
/project:self-heal [api|ui] <file>
/project:self-heal-ui <file>
/project:write-test [api|ui] <description>
/project:review-test <file>
```

**Copilot**: prompt files in `.github/prompts/` (same specs).

**Codex / any AI**: say what you want — the AI reads `AGENTS.md` and this folder.

## Key runtime files agents use

| File | What it contains |
|---|---|
| `qa_agent/repo_brain.json` | Import graph — which file is imported by which test (`python qa_agent/update_brain.py`) |
| `allure-results/local/` | Raw request/response JSON and failure screenshots from the last local run |
| `config/<env>.json` | Environment config (secrets are `${VAR}` placeholders resolved from env / `.env`) |
| `.mcp.json` | Playwright MCP server used for live browser diagnosis (Claude Code) |
