---
name: e2e-report
description: Use when running the fund-agent private portfolio E2E report generation pipeline
disable-model-invocation: true
---

# E2E Report Generation

Run the fund-agent private portfolio E2E report pipeline from start to finish.

## Invocation

```
/fund-agent:e2e-report --as-of YYYY-MM-DD
```

## What This Skill Does

1. Detects the repo root and available private data
2. Runs the full v0.10.5 pipeline via `bin/fund-agent-e2e`:
   - Import Alipay transactions (if CSV exists)
   - Generate planned transactions (if investment plan exists)
   - Build transaction ledger
   - Resolve fund identities
   - Build fund data snapshot
   - Reconstruct portfolio from ledger
   - Build knowledge graph context
   - Build news snapshot (graceful skip if no API keys)
   - Build factor snapshot
   - Analyze portfolio and produce markdown report
3. Reads **only** `e2e_summary.json` for the summary — never private file contents
4. Reports pipeline status and output paths

## Runner

```bash
bin/fund-agent-e2e --as-of YYYY-MM-DD
```

Additional flags:
- `--use-live-provider` — enable live provider data fetch
- `--skip-news` — skip news snapshot step
- `--skip-akshare` — skip AkShare-dependent steps
- `--dry-run` — print pipeline steps without executing
- `--output-report PATH` — custom report output path
- `--run-id ID` — custom run identifier

## Safety Rules

- **NEVER** read private file contents into chat (private_data/, *.private.json, etc.)
- **NEVER** print API key values or env var values
- **NEVER** commit private artifacts
- Only summarize `e2e_summary.json` fields (run_id, steps_completed, pipeline_version)
- If a step fails, report the error from e2e_summary.json, not from private data files
- The runner handles graceful degradation — missing provider keys are not errors

## Output

The runner writes:
- `local_reports/real_portfolio_report.md` — the markdown report
- `eval_workspace/runs/<run_id>/e2e_summary.json` — pipeline execution summary

After the runner completes, report:
1. Whether the pipeline succeeded or failed
2. Which steps completed (from e2e_summary.json)
3. The output report path
4. Any warnings about missing data (no news, low confidence factors, etc.)

Do **not** paste the report contents — tell the user where to find it.
