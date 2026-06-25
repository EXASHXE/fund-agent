# Agent Consumption Guide

How to use fund-agent with Claude Code, Codex, OpenCode, or any external
agent host.

## Quick Start

### 1. First run — generate evidence package

**Real analysis** (recommended):

```bash
bin/fund-agent-personal-run --no-skip-akshare --skip-news
```

**Offline / debugging**:

```bash
bin/fund-agent-personal-run --skip-akshare --skip-news
```

This produces a deterministic evidence package in `local_reports/<run_id>/`:

```
local_reports/<run_id>/
├── agent_context.md          ← Read this first
├── agent_context.json        ← Machine-readable context
├── e2e_summary.json          ← Full pipeline summary
├── personal_health_report.json
├── report.md
└── run_manifest.json
```

### 2. Re-read existing run (skip pipeline)

```bash
bin/fund-agent-personal-run --agent-context-only --run-dir local_reports/<run_id>
```

### 3. Tell your agent to read agent_context.md

Give your agent the `agent_context.md` file and the prompt template from
`docs/agent-integration/prompts/analyze-agent-context.en.md` (or `.zh.md`
for Chinese).

## What the Agent Should Read

In this order:

1. `agent_context.json` — machine-readable status, scope, and constraints
2. `agent_context.md` — human-readable summary
3. `e2e_summary.json` — full pipeline summary (if deeper detail needed)
4. `personal_health_report.json` — data quality diagnostic
5. `report.md` — composed report
6. Reconstructed portfolio / ledger — only if position-level detail is needed

## How the Agent Should Respond

Structure the response as:

1. **Data readiness** — overall status, confidence, reason codes
2. **What I can analyze now** — from `safe_to_analyze`
3. **What is unsafe to infer** — from `unsafe_to_infer`
4. **Key findings with evidence** — each finding cites its artifact source
5. **Missing data / fix-it checklist** — from `personal_health_report`
6. **Questions for user** — from `recommended_agent_questions`
7. **Next run command** — e.g. `bin/fund-agent-personal-run --agent-context-only --run-dir ...`

## What the Agent Must NOT Do

- Output formal `Decision` or `ExecutionLedger` objects
- Issue broker order execution instructions
- Auto-trade
- Treat `estimated` values as `confirmed` market values
- Treat partial valuation as complete portfolio market value
- Treat `cashflow_only` as current valuation
- Fabricate `fund_code`, NAV, or holdings
- Leak private paths or real transaction details
- Call `FundAnalysisSkill().run()` directly for personal portfolio analysis
- Construct `SkillInput` manually for personal portfolio analysis
- Read `confirmed_portfolio.private.json` as final report input
- Use `local_reports/skill_output` as personal analysis result
- Convert missing `current_value` / `null` / `None` to `0.0`
- Calculate P&L, HHI, max holding, contribution, or risk flags from `cashflow_only` positions
- Continue analysis if `agent_context.json` is missing

## Short User Intent

A user may simply say: "请使用本仓库的 fund-analysis skill 做一次个人基金组合分析。新的流水数据在 private_data。"

The agent must automatically:
1. Read `skills/fund-analysis/SKILL.md` to identify the canonical workflow
2. Run `bin/fund-agent-personal-run --no-skip-akshare --skip-news`
3. Read `local_reports/<run_id>/agent_context.json`
4. Output a contract-compliant analysis

Do NOT require the user to repeat safety constraints or entrypoint instructions.

## Identity Source

The `personal_health_report.data_sources.identity_source` field tells you how
fund codes were resolved:

| Source | Meaning | Agent follow-up |
|--------|---------|-----------------|
| `direct_fund_code` | Codes in data directly | None needed |
| `manual_override` | From `fund_identity_overrides.private.yaml` | Verify overrides are current |
| `name_only` | Some funds by name only | Suggest adding overrides |
| `unavailable` | No identity data | Suggest setting up overrides |

## Live Data

fund-agent runs in **deterministic mode** by default (`--skip-akshare`,
`--skip-news` are on). When the user wants live data:

1. The agent should call the host's MCP provider or live data API
2. Live data must be labeled separately from fund-agent evidence
3. Live data does NOT upgrade `estimated` to `confirmed`
4. Suggest re-running with `--no-skip-akshare` if live NAV should be
   integrated into the deterministic pipeline

See `docs/agent-integration/prompts/live-provider-extension.zh.md` for
the live data extension prompt template.

## Privacy

- Never commit `private_data/`, `local_data/`, `local_reports/`,
  `eval_workspace/`, or real Alipay CSV
- Never commit API keys, cookies, tokens, transaction IDs, or order IDs
- All artifact paths in `agent_context` are relative
- Agent responses should use counts and status labels, not raw amounts

## Host-Specific Integration

### Claude Code

1. Install fund-agent as a plugin (see `docs/install/claude-code.md`)
2. Run `bin/fund-agent-personal-run` to generate the evidence package
3. Use the `analyze-agent-context.zh.md` prompt template
4. Claude Code reads `agent_context.md` and follows the consumption contract

### Codex

1. Install fund-agent (see `docs/install/codex.md`)
2. Run the personal-run command
3. Provide `agent_context.json` as input context
4. Codex follows the same consumption contract

### OpenCode

1. Install the OpenCode plugin (see `docs/install/opencode.md`)
2. The plugin provides metadata and doc-reader functionality
3. Run the personal-run command separately
4. Provide the agent context to OpenCode

## Example Agent Output

```
## Data Readiness
- Status: partial
- Confidence: medium
- Reason codes: partial_nav_coverage, manual_review_transactions

## What I Can Analyze Now
- Cashflow trend
- NAV coverage quality
- Transaction quality

## What Is Unsafe to Infer
- Complete portfolio market value (NAV coverage is partial)
- Confirmed P&L (valuation is estimated)

## Key Findings
- [Source: personal_health_report] 2 funds missing trade-date NAV
- [Source: e2e_summary] 1 transaction requires manual review

## Missing Data
- Add trade-date NAV overrides for 2 fund(s) with missing coverage
- Review 1 conversion/refund transaction

## Questions for User
- Do you have fund_identity_overrides for name-only funds?
- Should live NAV be queried?

## Next Step
bin/fund-agent-personal-run --agent-context-only --run-dir local_reports/20260701-153000
```

## References

- Design: `docs/design/agent-context-consumption-contract.md`
- Contract: `docs/contracts/agent-context-contract.v1.md`
- Prompt templates: `docs/agent-integration/prompts/`
- Personal run: `docs/usage/personal-run.md`
- Health report: `docs/usage/personal-health-report.md`
