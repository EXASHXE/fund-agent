# Personal Health Report Design

## Problem

The E2E pipeline produces detailed artifacts (NAV coverage, valuation quality,
identity resolution, transaction validation), but users cannot quickly assess
their portfolio's overall data health at a glance. There is no unified summary
that answers: "Is my data complete enough for a meaningful valuation? What
should I fix next?"

## Personal Health Report Model

A lightweight summary layer that aggregates existing pipeline outputs into a
single structured report. No new business calculations — only counts, status
labels, and data-quality next steps.

### Schema: `personal_health_report.v1`

```json
{
  "schema_version": "personal_health_report.v1",
  "overall_status": "ok|partial|needs_data|needs_manual_review|unavailable",
  "confidence_level": "high|medium|low|unavailable",
  "reason_codes": ["..."],
  "data_sources": {
    "transaction_source": "alipay|portfolio_input.transactions|none",
    "valuation_source": "reconstructed_from_ledger|existing_private_portfolio_input|derived_from_transactions|unavailable",
    "identity_source": "overrides|direct_fund_code|name_only|unavailable"
  },
  "valuation_quality": {
    "positions_total": 0,
    "confirmed_count": 0,
    "estimated_full_coverage_count": 0,
    "estimated_partial_coverage_count": 0,
    "cashflow_only_count": 0,
    "unavailable_count": 0,
    "manual_review_count": 0,
    "estimated_current_value_total_is_partial": false
  },
  "nav_coverage": {
    "full": 0,
    "partial": 0,
    "none": 0,
    "latest_only": 0,
    "stale_count": 0,
    "qdii_like_count": 0
  },
  "fix_it_checklist": ["..."],
  "safety_notes": ["..."]
}
```

### Overall Status Determination

| overall_status | Condition |
|---|---|
| `ok` | All positions have full NAV coverage, no manual review needed, valuation available |
| `partial` | Some positions have partial NAV or estimated valuation, but data exists |
| `needs_data` | Missing identity data, NAV, or transaction source |
| `needs_manual_review` | Manual-review transactions present |
| `unavailable` | No transaction source, no portfolio input |

Priority: `unavailable` > `needs_manual_review` > `needs_data` > `partial` > `ok`

### Confidence Level Determination

| confidence_level | Condition |
|---|---|
| `high` | Full NAV coverage, reconstructed from ledger, no warnings |
| `medium` | Partial NAV coverage or estimated valuation |
| `low` | Name-only funds, no NAV, or significant data gaps |
| `unavailable` | No data at all |

### Reason Codes

| Code | Meaning |
|---|---|
| `no_valid_fund_codes` | No six-digit fund codes resolved |
| `nav_missing` | NAV snapshot unavailable |
| `partial_nav_coverage` | Some trades lack trade-date NAV |
| `manual_review_transactions` | Conversion/refund/unknown transactions present |
| `stale_nav` | Latest NAV exceeds staleness threshold |
| `qdii_nav_lag` | QDII-like funds with potentially stale NAV |
| `fallback_holdings_used` | Valuation from existing portfolio_input, not reconstructed |
| `cashflow_only` | Some positions are cashflow-only (no valuation) |
| `estimated_only` | All positions are estimated (no confirmed valuation) |
| `name_only_funds` | Some funds resolved by name only (no fund code) |

### Fix-it Checklist Rules

Checklist items are data-quality next steps, NOT trading advice:

1. If `name_only_count > 0`: "Add fund_identity_overrides for N name-only fund(s)"
2. If `nav_missing` or `partial_nav_coverage`: "Add trade-date NAV overrides for N fund(s) with missing coverage"
3. If `manual_review_count > 0`: "Review N conversion/refund/unknown transaction(s)"
4. If `stale_count > 0`: "Check NAV freshness for N fund(s) with stale NAV"
5. If `qdii_like_count > 0` and `stale_count > 0`: "Check NAV freshness for N QDII-like fund(s) with potentially lagged NAV"
6. If `unavailable_count > 0` or no valuation: "Provide portfolio_input.holdings if valuation is unavailable"
7. If `cashflow_only_count > 0`: "Add explicit units for N cashflow-only transaction(s) if available"

### Privacy Rules

- No real fund names in checklist/reason codes
- No real amounts (counts only by default)
- No transaction IDs, order IDs, or notes
- No private file paths
- No API keys/tokens

### Safety Notes (always included)

1. This is not a formal investment decision — no BUY/SELL/HOLD instruction
2. No broker/order execution capability
3. No auto trading
4. Estimated values are not confirmed market values
5. Partial coverage means incomplete valuation
