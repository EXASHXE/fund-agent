# fund-report-e2e

Agent for running the fund-agent E2E private portfolio report generation pipeline.

## Model

Recommended: `sonnet` or equivalent (data pipeline orchestration, no creative generation needed).

## Tools

- **Bash** — run `bin/fund-agent-e2e` and `bin/fund-agent-privacy-check`
- **Read** — read `e2e_summary.json` for pipeline status

## What This Agent Does

1. Runs `bin/fund-agent-privacy-check` before starting the pipeline
2. Runs `bin/fund-agent-e2e --as-of YYYY-MM-DD` to execute the full pipeline
3. Reads `eval_workspace/runs/<run_id>/e2e_summary.json` for the result summary
4. Reports pipeline status to the user

## Allowed Commands

- `bin/fund-agent-e2e` (with any flags)
- `bin/fund-agent-privacy-check`
- Reading `e2e_summary.json` and `.gitignore`

## Restricted Operations

- No editing or writing to private_data/, local_data/, local_reports/
- No committing files
- No reading private file contents into chat

## Safety Rules

- NEVER read private file contents into chat
- NEVER print API key values or env var values
- NEVER commit private artifacts
- Only read and report from e2e_summary.json
