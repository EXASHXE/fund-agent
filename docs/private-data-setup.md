# Personal Data Setup and Scenario Guide

This guide explains how to set up private data files, run the personal
portfolio E2E pipeline, and interpret the reconstruction scenarios
(A / B / C2 / D2).

## Private Data Directory Structure

```
private_data/
  alipay_record.private.csv          # Raw Alipay export (never committed)
  manual_transactions.private.csv    # Curated transaction entries
  portfolio_input.private.json       # Current holding snapshot (authoritative)
  fund_identity_overrides.private.yaml  # Manual fund code → identity mappings
  nav_overrides.private.json         # Trade-date NAV overrides for reconstruction
```

All files matching `*.private.*` and the `private_data/` directory are
in `.gitignore`. **Never commit real portfolio data.**

## Override Files

### fund_identity_overrides.private.yaml

Maps fund names (from Alipay/product descriptions) to canonical fund
codes and metadata. Used when fund codes cannot be resolved automatically.

```yaml
overrides:
  "蚂蚁财富-示例基金A-买入":
    fund_code: "110011"
    fund_name: "易方达蓝筹精选"
    fund_type: "equity"
```

### nav_overrides.private.json

Provides trade-date NAV values for reconstructing position units from
cashflow-only transaction history. Keys are `fund_code`, values are
date→NAV maps.

```json
{
  "110011": {
    "2026-01-15": 2.5432,
    "2026-02-10": 2.6100
  }
}
```

## Reconstruction Scenarios

The E2E pipeline handles four reconstruction scenarios depending on what
data is available:

### Scenario A: Raw Alipay CSV, No Overrides

**Input**: `alipay_record.private.csv` only.

**Expected behavior**:
- Transactions parsed: yes (`txns > 0`)
- Ledger transactions: yes (`ledger txns > 0`)
- Identity schema version: `fund_identity_resolution.v2`
- `valid_fund_codes_count`: 0 or very low
- `name_only_count > 0` (fund names not resolved to codes)
- `resolved_fund_code`: null for name-only entries
- Report does **not** show fake `0.00` values
- Report does **not** label cashflow as valuation

### Scenario B: Alipay CSV + Identity Overrides, No NAV

**Input**: `alipay_record.private.csv` + `fund_identity_overrides.private.yaml`.

**Expected behavior**:
- `valid_fund_codes_count > 0`
- `manual_override_matches_count > 0`
- Status: `partial`
- `reconstruction_status`: `nav_unavailable`
- `portfolio_input_source`: `unavailable`
- Warnings do **not** include "no resolved fund codes"

### Scenario C2: Alipay CSV + Identity Overrides + Trade-date NAV Overrides

**Input**: `alipay_record.private.csv` + identity overrides + `nav_overrides.private.json`.

**Expected behavior**:
- `reconstruction_status`: `reconstructed_from_ledger`
- Positions: `> 0`
- Estimated positions: `> 0`
- `cashflow_only` positions may exist
- `units_estimated` populated: `> 0`
- `current_value` populated: `> 0`
- Partial valuation coverage is clearly noted
- `estimated_current_value_total` is **not** presented as complete portfolio value

### Scenario D2: Existing portfolio_input Fallback

**Input**: `portfolio_input.private.json` (pre-built snapshot).

**Expected behavior**:
- When reconstruction is not available: `portfolio_input_source` = `existing_private_portfolio_input`
- Report does **not** use `reconstructed_from_ledger` wording
- Report clearly states cashflow comes from Alipay, valuation from existing private portfolio input

## Valuation Type Distinctions

The pipeline distinguishes four valuation types for positions:

| Type | Meaning | Report Treatment |
|------|---------|-----------------|
| `confirmed` | NAV-verified current value from provider | Full precision shown |
| `estimated` | Units estimated from cashflow + NAV overrides | Labeled as estimated |
| `cashflow_only` | Only transaction cashflow known, no NAV | No fake `0.00` value shown |
| `none` | No valuation data at all | Marked as missing |

### Key Rules

- **cashflow_only** positions must **not** display fake `0.00` as current value.
- **estimated** positions must **not** be presented as confirmed/verified.
- **fallback** source must **not** be labeled as `reconstructed_from_ledger`.
- **Partial valuation coverage** means only some positions have NAV; the
  total is an estimate, not a complete portfolio market value.

## Running Scenarios

```bash
# Scenario A: raw CSV only
bin/fund-agent-e2e --skip-akshare --skip-news

# Scenario B: add identity overrides
# (place fund_identity_overrides.private.yaml in private_data/)
bin/fund-agent-e2e --skip-akshare --skip-news

# Scenario C2: add NAV overrides
# (place nav_overrides.private.json in private_data/)
bin/fund-agent-e2e --skip-akshare --skip-news --as-of 2026-06-20

# Scenario D2: use existing portfolio_input
bin/fund-agent-e2e --skip-akshare --skip-news

# Dry run (no subprocess execution)
bin/fund-agent-e2e --dry-run
```

## Safety Boundaries

- fund-agent does **not** place orders or execute trades.
- fund-agent does **not** run an autonomous trading loop.
- `fund_analysis` does **not** output formal `Decision` objects.
- `suggested_rebalance_plan` is analysis advice, not trade instructions.
- Formal `Decision` / `ExecutionLedger` can only be produced by
  `decision_support` skill.
- Real E2E output stays in `local_reports/` — never commit.
