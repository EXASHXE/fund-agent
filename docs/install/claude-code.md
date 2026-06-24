# Claude Code Install

> Scope: install `fund-agent` as a Claude Code plugin.

## Local dev install

```bash
claude --plugin-dir /path/to/fund-agent
```

Claude Code expects the official plugin layout at the repo root:

- `.claude-plugin/plugin.json` — plugin metadata (name, version, description, author)
- `skills/e2e-report/SKILL.md` — E2E portfolio report generation
- `skills/setup-private-data/SKILL.md` — private data file setup
- `skills/audit-privacy/SKILL.md` — privacy audit before commits
- `agents/fund-report-e2e.md` — E2E report agent
- `agents/fund-data-auditor.md` — privacy auditor agent
- `bin/fund-agent-e2e` — shared E2E pipeline runner

Skills and agents live beside `.claude-plugin/`, not inside it.

## Invocation

```
/fund-agent:e2e-report --as-of YYYY-MM-DD
```

## Marketplace

Claude Code marketplace publishing is **not yet implemented**. Use
`--plugin-dir` for local development.

## What this plugin does NOT do

- Does not fetch data or call provider APIs
- Does not place trades or interact with brokers
- Does not print private file contents or API key values
- Does not commit private artifacts

## Prerequisites

- Claude Code CLI installed
- Python 3.11+ (for `bin/fund-agent-e2e` runner)
- Optional: provider API keys for live data (see `.env.example`)
