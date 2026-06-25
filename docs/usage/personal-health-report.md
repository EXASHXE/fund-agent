# Personal Health Report

The personal health report is a lightweight summary layer that aggregates
existing E2E pipeline outputs into a single structured view. It answers:
"Is my data complete enough for a meaningful valuation? What should I fix next?"

## What It Is

- A **data-quality diagnostic** for your portfolio reconstruction
- A **fix-it checklist** of next steps to improve data completeness
- Counts and status labels only — no real fund names, amounts, or paths

## What It Is NOT

- Not investment advice
- Not a formal Decision (only `decision_support` produces those)
- Not a trading signal or rebalancing recommendation
- Not a broker or order execution tool

## Accessing the Health Report

The health report is automatically included in `e2e_summary.json` under the
`personal_health_report` key whenever you run the E2E pipeline. It consumes
NAV coverage diagnostics from the reconstruction summary
(`confirmed_portfolio.private.json` → `summary.nav_coverage_summary`) to
populate coverage counts, stale NAV, and QDII-like detection.

### Via personal-run (recommended for agent consumption)

```bash
bin/fund-agent-personal-run --skip-akshare --skip-news
```

This produces a full evidence package including `personal_health_report.json`
and `agent_context.md`. Agents should read `agent_context.md` first — it
explains what data is safe to analyze and what should not be inferred.

See [personal-run.md](personal-run.md) for the full agent-facing workflow,
and [agent-consumption.md](agent-consumption.md) for the agent consumption protocol.

### Via E2E pipeline directly

```bash
bin/fund-agent-e2e --skip-akshare --skip-news
```

To print only the health report section:

```bash
bin/fund-agent-e2e --health-report-only --skip-akshare --skip-news
```

The `--health-report-only` flag does **not** skip pipeline steps or change
calculations — it only affects console output. It does NOT replace agent
analysis — it is a data quality diagnostic, not an interpretation.

## Interpreting Overall Status

| Status | Meaning |
|--------|---------|
| `ok` | All positions have full NAV coverage, no manual review needed |
| `partial` | Some positions have partial NAV or estimated valuation |
| `needs_data` | Missing identity data, NAV, or transaction source |
| `needs_manual_review` | Conversion/refund/unknown transactions present |
| `unavailable` | No transaction source or portfolio input |

## Interpreting Confidence Level

| Level | Meaning |
|-------|---------|
| `high` | Full NAV coverage, reconstructed from ledger, no warnings |
| `medium` | Partial NAV coverage or estimated valuation |
| `low` | Name-only funds, no NAV, or significant data gaps |
| `unavailable` | No data at all |

## Reason Code Glossary

| Code | Meaning |
|------|---------|
| `no_valid_fund_codes` | No six-digit fund codes resolved — identity data needed |
| `nav_missing` | NAV snapshot is unavailable |
| `partial_nav_coverage` | Some trades lack trade-date NAV |
| `manual_review_transactions` | Conversion/refund/unknown transactions present |
| `stale_nav` | Latest NAV exceeds staleness threshold |
| `qdii_nav_lag` | QDII-like funds with potentially stale NAV |
| `fallback_holdings_used` | Valuation from existing portfolio_input, not reconstructed |
| `cashflow_only` | Some positions are cashflow-only (no valuation) |
| `estimated_only` | All positions are estimated (no confirmed valuation) |
| `name_only_funds` | Some funds resolved by name only (no fund code) |

**`no_valid_fund_codes` vs `name_only_funds`:** When no valid six-digit
fund codes exist at all, `no_valid_fund_codes` fires. If some funds were
resolved by name only (but still lack a valid code), `name_only_funds`
fires additionally. Both can appear together — this means identity
overrides are needed to map fund names to codes.

## Fix-it Checklist

The checklist provides **data-quality next steps**, not trading advice:

- "Add fund_identity_overrides for N name-only fund(s)" — identity data is missing
- "Add trade-date NAV overrides for N fund(s) with missing coverage" — NAV gaps exist
- "Review N conversion/refund/unknown transaction(s)" — manual review needed
- "Check NAV freshness for N fund(s) with stale NAV" — NAV may be outdated
- "Provide portfolio_input.holdings for N position(s) without valuation" — no valuation possible
- "Add explicit units for N cashflow-only transaction(s) if available" — units missing

## Usage with Different Data Sources

### Alipay CSV Only (no overrides)

Expected: `needs_data` or `partial`, low confidence. The checklist will ask
for identity overrides and NAV data.

### With Identity Overrides, No NAV

Expected: `needs_data`, low/medium confidence. The checklist will ask for
NAV overrides.

### With Identity + Partial NAV

Expected: `partial`, medium confidence. The checklist will ask for
trade-date NAV for missing coverage.

### With Holdings Fallback (portfolio_input)

Expected: `partial` or `ok` depending on valuation source. The reason code
`fallback_holdings_used` indicates the valuation came from existing
portfolio_input, not reconstructed from ledger.

### With portfolio_input.transactions

Expected: `needs_manual_review` if conversion/refund/unknown transactions
are present. The checklist will ask to review those transactions.

## Example Redacted Output

```json
{
  "schema_version": "personal_health_report.v1",
  "overall_status": "partial",
  "confidence_level": "medium",
  "reason_codes": ["partial_nav_coverage"],
  "data_sources": {
    "transaction_source": "alipay",
    "valuation_source": "reconstructed_from_ledger",
    "identity_source": "direct_fund_code"
  },
  "valuation_quality": {
    "positions_total": 3,
    "confirmed_count": 0,
    "estimated_full_coverage_count": 1,
    "estimated_partial_coverage_count": 2,
    "cashflow_only_count": 0,
    "unavailable_count": 0,
    "manual_review_count": 0,
    "estimated_current_value_total_is_partial": true
  },
  "nav_coverage": {
    "full": 1,
    "partial": 2,
    "none": 0,
    "latest_only": 0,
    "stale_count": 0,
    "qdii_like_count": 0
  },
  "fix_it_checklist": [
    "Add trade-date NAV overrides for 2 fund(s) with missing coverage"
  ],
  "safety_notes": [
    "This is not a formal investment decision — no BUY/SELL/HOLD instruction.",
    "No broker/order execution capability.",
    "No auto trading.",
    "Estimated values are not confirmed market values.",
    "Partial coverage means incomplete valuation."
  ]
}
```

## Interpreting Identity Source

| Source | Meaning |
|--------|---------|
| `direct_fund_code` | Fund codes were present directly in the data (no overrides needed) |
| `manual_override` | Fund codes were resolved via `fund_identity_overrides.private.yaml` |
| `overrides` | Overrides file was loaded (may have validation warnings) |
| `name_only` | Some funds resolved by name only (no fund code) |
| `unavailable` | No identity data available |

## Safety Notes

The health report always includes these safety notes:

1. This is not a formal investment decision — no BUY/SELL/HOLD instruction
2. No broker/order execution capability
3. No auto trading
4. Estimated values are not confirmed market values
5. Partial coverage means incomplete valuation

## Agent Consumption

When consumed by an external agent, the health report is embedded in
`agent_context.json` via `build_agent_context()`. Agents should read
`agent_context.md` first and follow the consumption contract in
`docs/contracts/agent-context-contract.v1.md`.

See [agent-consumption.md](agent-consumption.md) for the full protocol.
