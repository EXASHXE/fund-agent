---
name: fund-agent-e2e
description: Use when running the fund-agent private portfolio E2E report generation pipeline
---

# fund-agent E2E Pipeline

Run the fund-agent private portfolio E2E report pipeline from start to finish.

## Runner

```bash
bin/fund-agent-e2e --as-of YYYY-MM-DD
```

## Pipeline Steps

1. Import Alipay transactions (if CSV exists in private_data/)
2. Generate planned transactions (if investment plan exists)
3. Build transaction ledger
4. Resolve fund identities
5. Build fund data snapshot (skipped if --skip-akshare)
6. Reconstruct portfolio from ledger
7. Build knowledge graph context
8. Build news snapshot (graceful skip if no API keys, or --skip-news)
9. Build factor snapshot
10. Analyze portfolio and produce markdown report

## Flags

- `--as-of YYYY-MM-DD` — portfolio reconstruction date (default: today)
- `--use-live-provider` — enable live provider data fetch
- `--skip-news` — skip news snapshot step
- `--skip-akshare` — skip AkShare-dependent steps
- `--dry-run` — print pipeline steps without executing
- `--output-report PATH` — custom report output path
- `--run-id ID` — custom run identifier

## Output

- `local_reports/real_portfolio_report.md` — the markdown report
- `eval_workspace/runs/<run_id>/e2e_summary.json` — pipeline summary

## Safety Rules

- NEVER read private file contents into chat (private_data/, *.private.json, etc.)
- NEVER print API key values or env var values
- NEVER commit private artifacts
- Only summarize e2e_summary.json fields (run_id, steps_completed, pipeline_version)
