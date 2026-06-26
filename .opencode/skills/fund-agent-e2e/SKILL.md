---
name: fund-agent-e2e
description: Internal pipeline debugging only. For personal fund analysis, use bin/fund-agent-personal-run instead.
---

# fund-agent E2E Pipeline (internal)

> **M7.8: This skill is for internal pipeline debugging/development only.**
> **For personal portfolio analysis, DO NOT run `bin/fund-agent-e2e` directly.**
> **Use the canonical entrypoint instead:**

```bash
bin/fund-agent-personal-run \
  --private-data-dir private_data \
  --output-dir local_reports \
  --transaction-source auto \
  --execution-mode real_analysis \
  --skip-news \
  --generate-fixit-package
```

## Why not call bin/fund-agent-e2e directly?

`scripts/fund_agent_e2e.py` is an **internal pipeline component**, not a
user-facing entrypoint. Since M7.7 it has a non-canonical personal-analysis
guard that **fails fast** (exit code 1, error
`non_canonical_personal_analysis_entrypoint`) whenever it detects personal /
`private_data` analysis without canonical provenance.

Direct calls to `bin/fund-agent-e2e` for personal analysis are blocked because
they would:

- Bypass the doctor, health-report, holdings-snapshot-overlay, and
  agent-context steps.
- Produce `local_reports/real_portfolio_report.md` (the forbidden legacy flat
  report path) or `eval_workspace/runs/<run_id>/` (not a user-visible final
  output).
- Skip `agent_context.json` / `agent_context.md` / `run_manifest.json`, which
  are mandatory for the agent evidence package.

## Canonical personal analysis

For ANY request that looks like personal fund / portfolio analysis — including
short prompts like "帮我做分析报告", "分析我的基金组合", or "新的流水数据在
private_data" — the agent MUST:

1. Read `skills/fund-analysis/SKILL.md` (the primary skill) first.
2. Run `bin/fund-agent-personal-run` (the canonical entrypoint).
3. Read `local_reports/<run_id>/agent_context.md` for the evidence package.
4. Follow the blocked-evidence firewall rules in `agent_context.json`.

The canonical output directory is `local_reports/<run_id>/` and MUST contain
`agent_context.json`, `agent_context.md`, `personal_health_report.json`,
`report.md`, and `run_manifest.json` with `canonical_entrypoint: true`.

## When this skill is actually useful

Only for:
- Debugging the internal pipeline with synthetic fixtures (tests must pass
  `--allow-noncanonical-test-run`).
- Inspecting `e2e_summary.json` structure during development.

## Safety Rules

- NEVER read private file contents into chat (private_data/, *.private.json, etc.)
- NEVER print API key values or env var values
- NEVER commit private artifacts
- NEVER call `bin/fund-agent-e2e` for personal analysis — use
  `bin/fund-agent-personal-run` instead.
