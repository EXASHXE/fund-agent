# Personal Run Command — Agent-facing Evidence Package

## Overview

`bin/fund-agent-personal-run` is a CLI entry point that produces a **deterministic
evidence package** for external agents (Claude, Codex, OpenCode, etc.) to consume.
It is NOT the final analysis interface — agents interpret, follow up, and synthesize.

## Core Principle

- **fund-agent** generates deterministic evidence
- **External agent** interprets, asks follow-up questions, synthesizes analysis
- **CLI** is the host/agent entry point, not the end-user analysis interface

## Command

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
| `--transaction-source` | `auto` | Transaction source routing |
| `--skip-akshare` | **on by default** | No live provider calls, deterministic only |
| `--skip-news` | **on by default** | No news research, deterministic only |
| `--health-report-only` | off | Print only personal_health_report |
| `--agent-context-only` | off | Regenerate agent_context from existing e2e_summary |
| `--run-id` | auto-generated | Run identifier |
| `--dry-run` | off | Print steps without executing |

### Deterministic Mode

`--skip-akshare` and `--skip-news` are **default on**. This keeps the core runtime
deterministic and offline. Live data should be injected by the host/agent explicitly.

## Execution Steps

1. Run private data doctor (`run_doctor()`)
2. Run E2E pipeline (`fund_agent_e2e.main()`)
3. Load e2e_summary.json
4. Build personal_health_report
5. Build agent_context (md + json)
6. Write all artifacts to output directory
7. Print concise console summary

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

### Privacy Rules

NEVER output:
- Real transaction IDs
- Order IDs
- API keys
- Private absolute paths
- Raw CSV rows
- Unredacted notes

All artifact paths in agent_context are **relative** (within the run directory).

## Agent Context

### agent_context.json Schema

```json
{
  "schema_version": "fund_agent_context.v1",
  "run_id": "...",
  "overall_status": "...",
  "confidence_level": "...",
  "reason_codes": [],
  "safe_to_analyze": [],
  "unsafe_to_infer": [],
  "recommended_agent_questions": [],
  "artifact_paths": {
    "e2e_summary": "e2e_summary.json",
    "report": "report.md",
    "personal_health_report": "personal_health_report.json"
  },
  "safety_constraints": []
}
```

### agent_context.md Sections

1. **Data readiness** — overall_status, confidence_level, reason_codes, missing data
2. **Safe-to-analyze scope** — what the agent can safely analyze
3. **Unsafe-to-infer scope** — what the agent should NOT infer
4. **Evidence map** — relative artifact paths
5. **Suggested agent follow-up questions** — data quality questions (not trading advice)
6. **Safety constraints** — not formal Decision, no auto trading, etc.

## Console Output

Default console output is concise:

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

## Module Structure

- `src/tools/portfolio/agent_context.py` — `build_agent_context()`, `render_agent_context_markdown()`
- `scripts/fund_agent_personal_run.py` — CLI orchestrator
- `bin/fund-agent-personal-run` — POSIX entry point
- `bin/fund-agent-personal-run.cmd` — Windows entry point
