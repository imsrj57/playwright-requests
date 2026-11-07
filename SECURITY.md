# Security Policy

## Secrets

This framework is designed so that **no secret ever lives in the repository**:

- `config/<env>.json` contains only `${ENV_VAR}` placeholders and safe defaults.
- Real values come from environment variables (CI secret variables) or a local `.env` file, which is git-ignored. `.env.example` lists every variable.
- Personal overrides go in `config/<env>.local.json`, also git-ignored.
- API request/response attachments in Allure redact `Authorization`, `Cookie`, `Set-Cookie`, `X-API-Key` and `Proxy-Authorization` headers; the HTML report masks JWTs in stack traces.
- The `Secret scan` GitHub workflow runs [gitleaks](https://github.com/gitleaks/gitleaks) on every push and pull request.

If you fork this repo, never commit `.env`, `*.local.json`, screenshots or reports from a real environment.

## Reporting a vulnerability

Please do **not** open a public issue for security problems. Use GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
("Security" tab → "Report a vulnerability") and include steps to reproduce.
