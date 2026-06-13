# Provider Snapshot Flow

## Overview

fund-agent core does not fetch live data. Host collects data and builds a `provider_data_snapshot` that fund-agent consumes.

## Steps

1. Host runs provider adapters (AkShare, Eastmoney, Xueqiu) to collect data
2. Host builds `provider_data_snapshot` JSON conforming to `schemas/provider_data_snapshot.schema.json`
3. Host passes snapshot reference or inline data to fund-agent workflow
4. fund-agent uses snapshot data for analysis

## Schema

See `schemas/provider_data_snapshot.schema.json` for full schema.

Key sections:
- `fund_nav_history` — NAV history by fund code
- `benchmark_index_history` — benchmark/index data
- `fund_profiles` — fund profile data
- `fund_holdings` — fund holdings data
- `fee_schedules` — fee schedule data
- `redemption_rules` — redemption rules

## What NOT to do

- Do not fetch data inside fund-agent core runtime
- Do not commit real provider data
- Do not commit provider credentials
- Do not assume snapshot data is always complete
