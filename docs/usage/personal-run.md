# Personal Run — Agent-facing Evidence Package

`bin/fund-agent-personal-run` produces a **deterministic evidence package** for
external agents to consume. It is NOT the final analysis interface — agents
interpret, follow up, and synthesize.

## Core Principle

- **fund-agent** generates deterministic evidence
- **External agent** interprets, asks follow-up questions, synthesizes analysis
- **CLI** is the host/agent entry point, not the end-user analysis interface

## Usage

```bash
bin/fund-agent-personal-run \
  --private-data-dir private_data \
  --output-dir local_reports \
  --transaction-source auto \
  --skip-akshare \
  --skip-news
```

### Flags

| Flag | Default | Purpose |
|------|---------|---------|
| `--private-data-dir` | `private_data/` | Private data directory |
| `--output-dir` | `local_reports/` | Output root directory |
| `--transaction-source` | `auto` | Transaction source: auto, alipay, portfolio_input |
| `--skip-akshare` | **on** | No live provider calls (deterministic mode) |
| `--no-skip-akshare` | off | Allow AkShare-dependent steps (live mode) |
| `--skip-news` | **on** | No news research (deterministic mode) |
| `--no-skip-news` | off | Allow news snapshot step (live mode) |
| `--run-id` | auto-generated | Run identifier |
| `--dry-run` | off | Print steps without executing |
| `--health-report-only` | off | Print only personal_health_report JSON |
| `--agent-context-only` | off | Print only agent_context.md |

### Deterministic Mode

`--skip-akshare` and `--skip-news` are **on by default**. This keeps the core
runtime deterministic and offline. Live data should be injected by the
host/agent explicitly — the CLI does not become a live research system.

## Execution Steps

1. Run private data doctor
2. Run E2E pipeline
3. Build personal_health_report
4. Build agent_context (md + json)
5. Write all artifacts to output directory
6. Print concise console summary

## Output Directory

```
local_reports/<run_id>/
├── e2e_summary.json
├── personal_health_report.json
├── agent_context.md
├── agent_context.json
├── report.md
└── run_manifest.json
```

## Agent Context

Agents should **read `agent_context.md` first**. It contains:

1. **Data readiness** — overall status, confidence, reason codes
2. **Safe-to-analyze scope** — what the agent can safely analyze
3. **Unsafe-to-infer scope** — what the agent should NOT infer
4. **Evidence map** — relative artifact paths
5. **Suggested follow-up questions** — data quality questions (not trading advice)
6. **Safety constraints** — not formal Decision, no auto trading, etc.

For structured consumption, read `agent_context.json` (schema: `fund_agent_context.v1`).

## Console Output

Default output is concise — not a full report:

```
Fund Agent evidence package created.

Run ID: 20260701-153000
Status: PARTIAL
Confidence: MEDIUM
Reason codes: partial_nav_coverage, manual_review_transactions

Artifacts:
- local_reports/20260701-153000/agent_context.md
- local_reports/20260701-153000/e2e_summary.json
- local_reports/20260701-153000/report.md

Next:
Ask your agent to read agent_context.md and continue the analysis.
```

## --health-report-only

Prints only the personal health report JSON. Does NOT replace agent analysis —
it is a data quality diagnostic, not an interpretation.

## --agent-context-only

Regenerates `agent_context.md` and `agent_context.json` from an existing
`e2e_summary.json`. Useful when the E2E pipeline has already run and you only
need to refresh the agent context.

## Privacy

Never output:
- Real transaction IDs
- Order IDs
- API keys
- Private absolute paths
- Raw CSV rows
- Unredacted notes

All artifact paths in `agent_context` are **relative** (within the run directory).

## This Is Not a Trading System

- fund-agent generates evidence, agents interpret
- No formal Decision from fund_analysis
- No broker/order execution
- No auto trading
- Estimated values are not confirmed market values
