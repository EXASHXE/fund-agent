---
name: fund-agent-setup-private-data
description: Use when setting up or verifying private data files for the fund-agent pipeline
---

# fund-agent Setup Private Data

Guide the user to place private data files in the correct locations.

## Private Data Directory

Place all private data in `private_data/` at the repo root. This directory is gitignored.

## Required Files

| File | Purpose | Required |
|---|---|---|
| `portfolio_input.private.json` | Portfolio holdings data | Yes (or reconstruction inputs) |
| `alipay_record_*.csv` | Alipay transaction CSV | For reconstruction |
| `investment_plan.private.yaml` | Investment plan | For reconstruction |

## API Keys

Set as environment variables — never in tracked files:
- `TAVILY_API_KEY`, `BOCHA_API_KEY`, `SERPAPI_KEY`, `FINNHUB_API_KEY`

## Safety Rules

- NEVER read or print private data file contents into chat
- NEVER print or echo API key values
- NEVER commit private data files
- Only confirm whether files exist and their sizes
