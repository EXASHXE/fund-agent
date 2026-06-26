# fund-report-e2e

Agent for running the fund-agent personal portfolio report generation pipeline.

## Model

Recommended: `sonnet` or equivalent (data pipeline orchestration, no creative generation needed).

## Tools

- **Bash** — run `bin/fund-agent-personal-run` and `bin/fund-agent-privacy-check`
- **Read** — read `local_reports/<run_id>/agent_context.md` and `e2e_summary.json` for pipeline status

## What This Agent Does

1. Runs `bin/fund-agent-privacy-check` before starting the pipeline
2. Runs `bin/fund-agent-personal-run` (the canonical entrypoint) to execute the
   full personal analysis pipeline:

   ```bash
   bin/fund-agent-personal-run \
     --private-data-dir private_data \
     --output-dir local_reports \
     --transaction-source auto \
     --execution-mode real_analysis \
     --skip-news \
     --generate-fixit-package
   ```

3. Reads `local_reports/<run_id>/agent_context.md` for the agent evidence package
4. Reads `local_reports/<run_id>/run_manifest.json` to confirm
   `canonical_entrypoint: true` and `execution_mode: real_analysis`
5. Reports pipeline status to the user following the blocked-evidence firewall
   rules in `agent_context.json`

## Allowed Commands

- `bin/fund-agent-personal-run` (the canonical entrypoint — with any of its flags)
- `bin/fund-agent-privacy-check`
- Reading `agent_context.md`, `agent_context.json`, `run_manifest.json`,
  `personal_health_report.json`, and `e2e_summary.json` from
  `local_reports/<run_id>/`

## Restricted Operations

- No editing or writing to private_data/, local_data/, local_reports/
- No committing files
- No reading private file contents into chat
- **No calling `bin/fund-agent-e2e` directly** — it is an internal pipeline
  component with a non-canonical guard that fails fast for personal analysis.
  Always use `bin/fund-agent-personal-run`.
- No outputting formal `Decision` or `ExecutionLedger` objects
- No auto-trading or broker/order execution

## Safety Rules

- NEVER read private file contents into chat
- NEVER print API key values or env var values
- NEVER commit private artifacts
- Only read and report from `agent_context.md` / `run_manifest.json`
- Follow the blocked-evidence firewall: when `identity_unverified` is in
  reason_codes or `blocked_evidence_summary.nav_trend_blocked` is true, do NOT
  output NAV trend, P&L, yield, or valuation conclusions.
