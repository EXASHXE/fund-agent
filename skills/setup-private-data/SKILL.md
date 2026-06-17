---
name: setup-private-data
description: Use when setting up or verifying private data files for the fund-agent pipeline
---

# Setup Private Data

Guide the user to place private data files in the correct locations for the fund-agent pipeline.

## Private Data Directory

Place all private data files in `private_data/` at the repo root. This directory is gitignored and will never be committed.

## Required Files

| File | Purpose | Required |
|---|---|---|
| `portfolio_input.private.json` | Portfolio holdings data | Yes (or reconstruction inputs) |
| `alipay_record_*.csv` | Alipay transaction CSV | For reconstruction |
| `investment_plan.private.yaml` | Investment plan | For reconstruction |

## Optional Files

| File | Purpose |
|---|---|
| `provider_data_snapshot.private.json` | Provider/NAV data |
| `manual_transactions.private.csv` | Manual transaction adjustments |

## API Keys

If you have API keys for news/providers, set them as environment variables:

- `TAVILY_API_KEY` — Tavily web search
- `BOCHA_API_KEY` — Bocha financial news
- `SERPAPI_KEY` — SerpAPI web search
- `FINNHUB_API_KEY` — Finnhub financial data

Do **NOT** create `.env` files or store keys in any tracked file.

## Safety Rules

- **NEVER** read or print the contents of private data files into chat
- **NEVER** print or echo API key values
- **NEVER** commit private data files
- Only confirm whether files exist and their sizes
- If the user asks you to inspect private data, suggest running `bin/fund-agent-e2e` instead

## Verification

After the user places files, verify setup by running:

```bash
bin/fund-agent-e2e --dry-run
```

This prints what the pipeline would do without executing.
