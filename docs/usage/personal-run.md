# Personal Run — Agent-facing Evidence Package

`bin/fund-agent-personal-run` produces a **deterministic evidence package** for
external agents to consume. It is NOT the final analysis interface — agents
interpret, follow up, and synthesize.

## Core Principle

- **fund-agent** generates deterministic evidence
- **External agent** interprets, asks follow-up questions, synthesizes analysis
- **CLI** is the host/agent entry point, not the end-user analysis interface

## Usage

### First run (full pipeline)

```bash
bin/fund-agent-personal-run \
  --private-data-dir private_data \
  --output-dir local_reports \
  --transaction-source auto \
  --skip-akshare \
  --skip-news
```

### Subsequent agent re-read (skip pipeline)

```bash
bin/fund-agent-personal-run \
  --agent-context-only \
  --run-dir local_reports/20260701-153000
```

### Flags

| Flag | Default | Purpose |
|------|---------|---------|
| `--private-data-dir` | `private_data/` | Private data directory (applies to both doctor and E2E) |
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
| `--summary-path` | off | Path to existing e2e_summary.json (skip pipeline) |
| `--run-dir` | off | Path to run directory containing e2e_summary.json (skip pipeline) |

### Deterministic Mode

`--skip-akshare` and `--skip-news` are **on by default**. This keeps the core
runtime deterministic and offline. Live data should be injected by the
host/agent explicitly — the CLI does not become a live research system.

## --private-data-dir

The `--private-data-dir` flag applies to **both** the private data doctor and
the E2E pipeline. This ensures they check the same directory. Default is
`private_data/` (relative to repo root).

## Execution Modes

### Default mode (full pipeline)

1. Run private data doctor (with `--private-data-dir`)
2. Run E2E pipeline (with `--private-data-dir`)
3. Build personal_health_report
4. Build agent_context (md + json)
5. Write all artifacts to output directory
6. Print concise console summary

### --health-report-only

Two behaviors:

- **With `--summary-path` or `--run-dir`**: Reads the existing e2e_summary.json
  and prints only the personal_health_report JSON. Does NOT run doctor or E2E.
- **Without `--summary-path` or `--run-dir`**: Runs the full pipeline, then
  prints only the personal_health_report JSON.

Does NOT replace agent analysis — it is a data quality diagnostic, not an
interpretation.

### --agent-context-only

Two behaviors:

- **With `--summary-path` or `--run-dir`**: Reads the existing e2e_summary.json,
  generates and prints agent_context.md, and writes agent_context.md/json to
  the run directory. Does NOT run doctor or E2E.
- **Without `--summary-path` or `--run-dir`**: Runs the full pipeline, then
  prints only the agent_context.md.

### Recommended agent workflow

1. **First run**: `bin/fund-agent-personal-run` — produces full evidence package
2. **Agent re-read**: `bin/fund-agent-personal-run --agent-context-only --run-dir local_reports/<run_id>`
   — reads existing summary, regenerates agent context without re-running pipeline

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

## Privacy

Never output:
- Real transaction IDs
- Order IDs
- API keys
- Private absolute paths
- Raw CSV rows
- Unredacted notes

All artifact paths in `agent_context` are **relative** (within the run directory).
The `run_manifest.json` contains `private_data_configured` (boolean) but never
the actual private_data_dir path.

## This Is Not a Trading System

- fund-agent generates evidence, agents interpret
- No formal Decision from fund_analysis
- No broker/order execution
- No auto trading
- Estimated values are not confirmed market values

## Agent Consumption

For the full agent consumption protocol, see
[agent-consumption.md](agent-consumption.md). It covers:

- How to let Claude Code / Codex / OpenCode consume the evidence package
- Agent reading order and response structure
- What agents must NOT do
- Live data extension workflow
- Prompt templates in `docs/agent-integration/prompts/`

Contract reference: `docs/contracts/agent-context-contract.v1.md`
