# Agent Context Consumption Contract

**Version:** 1.0
**Effective:** v0.10.6
**Scope:** Defines how external agents (Claude Code, Codex, OpenCode, or any
host) should consume `agent_context.md` / `agent_context.json` produced by
`fund-agent`.

## 1. Division of Labor

### fund-agent

- Deterministic evidence package generator
- Produces: ledger, identity, NAV coverage, reconstruction,
  `personal_health_report`, `agent_context`
- Does NOT:
  - Make network calls or fetch live data
  - Output formal `Decision` or `ExecutionLedger`
  - Execute broker orders
  - Auto-trade

### External agent

- Reads `agent_context.md` / `agent_context.json`
- Explains data quality to the user
- Reads necessary artifacts via the evidence map
- Asks follow-up questions about missing data
- Calls host / live providers when the user explicitly allows it
- Does NOT draw pseudo-certain conclusions beyond available evidence

## 2. Agent Required Reading Order

When an agent encounters a fund-agent run directory, it should read
artifacts in this order:

1. `agent_context.json` — machine-readable status, scope, and constraints
2. `agent_context.md` — human-readable summary of the same data
3. `e2e_summary.json` — full pipeline summary (if deeper detail needed)
4. `personal_health_report.json` — data quality diagnostic and fix-it checklist
5. `report.md` — composed report (if user wants narrative)
6. Reconstructed portfolio / ledger — only if the agent needs position-level
   detail and the evidence map indicates it is available

## 3. Analysis Boundaries

### Agent MAY analyze

- Data quality and completeness
- Transaction source reliability
- NAV coverage quality (full / partial / none)
- The difference between `estimated`, `cashflow_only`, and `confirmed`
  valuation
- Which data needs supplementation
- Portfolio structural exposure — but must cite evidence and state confidence

### Agent MUST NOT

- Treat `estimated` as `confirmed`
- Treat `partial` valuation as complete portfolio market value
- Treat `cashflow_only` as current valuation
- Generate formal `Decision` or `ExecutionLedger` objects
- Output broker order execution instructions
- Auto-trade
- Fabricate `fund_code`, NAV, or holdings
- Leak private paths or real transaction details

## 4. Agent Response Contract

When an agent responds to a user based on fund-agent evidence, it should
structure its output as follows:

### Required sections

1. **Data readiness** — overall status, confidence, reason codes
2. **What I can analyze now** — safe-to-analyze scope from agent_context
3. **What is unsafe to infer** — unsafe-to-infer scope from agent_context
4. **Key findings with evidence** — each finding cites its artifact source
5. **Missing data / fix-it checklist** — from personal_health_report
6. **Questions for user** — recommended_agent_questions or custom follow-ups
7. **Optional next run command** — e.g. `bin/fund-agent-personal-run --agent-context-only --run-dir ...`

### Formatting rules

- Every quantitative claim must reference an artifact or evidence item
- Confidence qualifiers (`estimated`, `partial`, `high confidence`) must be
  stated explicitly
- When data is insufficient, say so rather than guessing
- Never present estimated values as confirmed market values

## 5. Live Data Extension

When the user explicitly requests live data (news, real-time NAV, etc.):

1. The agent should call the host's MCP provider or live data API
2. The agent must label live data as such — separate from deterministic
   fund-agent evidence
3. Live data does NOT upgrade `estimated` to `confirmed` in fund-agent terms
4. The agent should suggest re-running `fund-agent-personal-run` with
   `--no-skip-akshare` if the user wants live NAV integrated into the
   deterministic pipeline

## 6. Privacy

- Never output private paths (`private_data/`, `local_data/`)
- Never output real transaction IDs, order IDs, or API keys
- All artifact paths in `agent_context` are relative to the run directory
- Agent responses should use counts and status labels, not raw amounts
