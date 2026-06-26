# Current Holdings Snapshot

## What is it?

A **current holdings snapshot** is a point-in-time record of your portfolio's current
state — what you hold, how many shares, and what each position is worth right now.

It is **not** transaction history. Transaction history records what you bought and sold
over time. The holdings snapshot records what you currently own.

## Why is it needed?

The fund-agent pipeline can reconstruct your portfolio from transaction history alone,
but without authoritative current holdings data, the reconstruction is limited:

- Without verified shares, `current_value` cannot be computed
- Without current value, portfolio metrics (weights, HHI, P&L) are unavailable
- Without verified fund codes, identity is uncertain

Providing a holdings snapshot gives the pipeline **authoritative current data** that
bypasses the need for complete NAV history and unit derivation.

## Source Priority

When both holdings snapshot and transaction history are available:

1. **Holdings snapshot** — authoritative source for current shares and market value
2. **Transaction-derived reconstruction** — explanatory context for cost basis and history
3. **Cashflow-only** — fallback when neither is available

If the two sources disagree (e.g., snapshot shows 5000 shares but reconstruction
shows 4800), the pipeline flags a `reconciliation_gap` and does not silently merge.

## How to Create One

### From Alipay Holdings Page

1. Open Alipay → Funds → My Holdings
2. Record each fund's: code, name, shares, current value, NAV, NAV date
3. Save as CSV or JSON using the template format

### CSV Format

```csv
as_of_date,fund_code,fund_name,shares,latest_nav,nav_date,current_value,holding_cost,holding_profit,holding_profit_pct,source,user_verified
2026-06-26,000001,My Fund,10000.00,1.50,2026-06-25,15000.00,10000.00,5000.00,0.50,alipay_holdings_page,true
```

### JSON Format

```json
{
  "schema_version": "current_holdings_snapshot.v1",
  "as_of_date": "2026-06-26",
  "source": "user_provided_holdings_snapshot",
  "positions": [
    {
      "fund_code": "000001",
      "fund_name": "My Fund",
      "shares": 10000.00,
      "latest_nav": 1.50,
      "nav_date": "2026-06-25",
      "current_value": 15000.00,
      "holding_cost": 10000.00,
      "source": "alipay_holdings_page",
      "user_verified": true
    }
  ]
}
```

## Field Reference

| Field | Required | Description |
|-------|----------|-------------|
| `as_of_date` | Yes | Date of the snapshot (YYYY-MM-DD) |
| `fund_code` | Recommended | 6-digit fund code; empty triggers identity resolution |
| `fund_name` | Yes | Fund name as shown on platform |
| `shares` | Recommended | Number of shares/units held |
| `latest_nav` | Optional | NAV per share on `nav_date` |
| `nav_date` | Optional | Date of the NAV value |
| `current_value` | Optional | Total current market value; if provided, recorded as `platform_reported` |
| `holding_cost` | Optional | Cost basis from platform; marked `platform_reported`, not mixed with reconstructed cost |
| `holding_profit` | Optional | Profit from platform; marked `platform_reported_profit` |
| `holding_profit_pct` | Optional | Profit percentage from platform |
| `source` | Recommended | Where this data came from (e.g., `alipay_holdings_page`) |
| `user_verified` | Recommended | Whether the user has verified this data (`true`/`false`) |

## Key Rules

1. **Empty values stay empty** — never convert missing data to zero
2. **`current_value` from snapshot is `platform_reported`** — not the same as reconstructed value
3. **`holding_profit` is `platform_reported_profit`** — must not be confused with reconstructed P&L
4. **Snapshot + transaction conflict** → flag `reconciliation_gap`, don't silently merge
5. **`fund_code` empty** → identity resolution will attempt to match by `fund_name`

## Using with fund-agent

```bash
# Auto-detect snapshot in private_data/
python scripts/fund_agent_personal_run.py \
  --private-data-dir private_data \
  --output-dir local_reports \
  --transaction-source auto

# Explicit snapshot path
python scripts/fund_agent_personal_run.py \
  --private-data-dir private_data \
  --output-dir local_reports \
  --transaction-source auto \
  --holdings-snapshot private_data/current_holdings_snapshot.private.csv
```

Auto-detection looks for:
- `private_data/current_holdings_snapshot.private.csv`
- `private_data/current_holdings_snapshot.private.json`
