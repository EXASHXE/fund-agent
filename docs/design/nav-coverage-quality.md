# NAV Coverage Quality Design

## Problem

The reconstruction pipeline estimates units and current_value from transactions
and NAV data, but lacks structured diagnostics about NAV coverage quality,
stale NAV, and special transaction effects. Users cannot easily see why a
position is `cashflow_only` vs `estimated`, or which positions need manual
review due to conversions, refunds, or missing trade-date NAV.

## NAV Coverage Model

Each fund position has a NAV coverage status derived from its transactions:

| coverage_status | Condition |
|-----------------|-----------|
| `full` | All buy/sell transactions have trade-date NAV or explicit units |
| `partial` | Some buy/sell transactions have trade-date NAV, but not all |
| `none` | No trade-date NAV available for any buy/sell transaction |
| `latest_only` | Only latest NAV available (no trade-date NAV, but latest_nav exists) |

Rules:
1. `trade_nav_coverage_ratio` only counts buy/sell transactions that need NAV.
2. buy/sell with explicit `units` do not require trade-date NAV for unit
   estimation, but the NAV coverage gap is still recorded.
3. dividend/fee do not require trade-date NAV.
4. conversion_in/conversion_out/refund default to `manual_review_required`.
5. `latest_nav` alone does NOT create historical units.
6. QDII-like detection is opt-in from fund_profile data — no guessing.

## Valuation Quality State Machine

Extends the existing `valuation_type` (none/cashflow_only/estimated/valuation)
with a finer `valuation_quality` label:

| valuation_quality | valuation_type | NAV coverage | Meaning |
|-------------------|---------------|-------------|---------|
| `confirmed` | valuation | full | Broker-confirmed NAV |
| `estimated_full_coverage` | estimated | full | Units estimated with complete trade-date NAV |
| `estimated_partial_coverage` | estimated | partial | Units estimated with partial NAV — value is approximate |
| `cashflow_only` | cashflow_only | any | No units or current_value — cashflow only |
| `unavailable` | none | none | No data at all |
| `manual_review_required` | any | any | Conversion/refund/unknown present, or validation warnings |

Transition rules:
- `estimated_full_coverage` requires `units_source` in (`transaction_units`, `trade_date_nav`)
  AND `trade_nav_coverage_ratio` == 1.0
- `estimated_partial_coverage` when `units_source` == `partial_trade_date_nav`
  OR `trade_nav_coverage_ratio` < 1.0
- `manual_review_required` overrides when `has_manual_review` is True
- `latest_only` coverage_status does NOT promote `cashflow_only` to `estimated`
  unless explicit units exist

## QDII Stale NAV Treatment

QDII funds may have delayed NAV publication (T+1 or T+2). The pipeline:
1. Reads `is_qdii` from fund profile or factor snapshot if available.
2. If `is_qdii` is not set, does NOT guess.
3. Stale NAV thresholds (warning only, not failure):
   - Domestic (default): latest_nav older than 7 calendar days
   - QDII-like: latest_nav older than 10 calendar days
4. Stale warnings appear in `latest_nav_stale_days` and `data_quality` flags.

## Conversion/Refund/Fee Semantics

| Transaction | Units Effect | Valuation Effect | Manual Review |
|-------------|-------------|-----------------|---------------|
| buy | Increase | cost_basis += amount | No |
| sell | Decrease | cost_basis reduced proportionally | No |
| dividend | None | dividends_received tracked | No |
| fee | None | fees_paid tracked | No |
| conversion_in | Skipped | Ambiguous | Yes |
| conversion_out | Skipped | Ambiguous | Yes |
| refund | Skipped | Ambiguous | Yes |
| unknown | Skipped | Unknown | Yes |

Rules:
- conversion/refund/unknown → `manual_review_required = True`
- fee does not change units; visible in `fees_paid` and report
- dividend does not change units unless `dividend_reinvest` (backlog item)
- conversion_in/out pairs are NOT auto-matched in v0.10.6

## Report Wording Rules

1. `estimated_current_value_total` must always be labelled "estimated".
2. If coverage is partial: "partial estimated value", not "portfolio value".
3. `cashflow_only` does not display fake `0.00`.
4. Fallback holdings remain `existing_private_portfolio_input`, not
   `reconstructed_from_ledger`.
5. No formal buy/sell Decision from fund_analysis.
6. NAV coverage section shows:
   - Full trade-date NAV coverage: N fund(s)
   - Partial NAV coverage: N fund(s)
   - No trade-date NAV coverage: N fund(s)
   - Stale latest NAV: N fund(s)
   - QDII-like positions: N fund(s), latest NAV may lag
7. Valuation quality section shows counts per quality level.
8. Special transactions section notes manual review requirements.

## Privacy Rules

- No real fund names in logs/tests
- No real amounts in diagnostics output
- Counts-only summary
- Stale NAV warnings show days, not amounts
- `is_qdii_like` is a boolean flag, not a fund identifier
