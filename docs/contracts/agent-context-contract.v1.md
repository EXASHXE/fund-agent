# Agent Context Contract v1

**Version:** 1.0
**Contract ID:** `fund_agent_context.v1`
**Effective:** v0.10.6

This document defines the machine-readable contract for `agent_context.json`
produced by `fund-agent` via `build_agent_context()`.

## Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_version` | string | Yes | Must be `fund_agent_context.v1` |
| `run_id` | string | Yes | Run identifier (may be empty string) |
| `overall_status` | string | Yes | One of: `ok`, `partial`, `needs_data`, `needs_manual_review`, `unavailable` |
| `confidence_level` | string | Yes | One of: `high`, `medium`, `low`, `unavailable` |
| `reason_codes` | list[string] | Yes | Zero or more codes from the reason_codes enumeration |
| `safe_to_analyze` | list[string] | Yes | Analysis targets the agent can safely pursue |
| `unsafe_to_infer` | list[string] | Yes | Inferences the agent must NOT make |
| `recommended_agent_questions` | list[string] | Yes | Data-quality questions for the user (not trading advice) |
| `artifact_paths` | dict[string, string] | Yes | Relative artifact paths within the run directory |
| `safety_constraints` | list[string] | Yes | Constraints from the safety_constraints enumeration |

## Reason Codes Enumeration

All `reason_codes` values must come from this stable set:

| Code | Meaning |
|------|---------|
| `no_valid_fund_codes` | No six-digit fund codes resolved — identity data needed |
| `name_only_funds` | Some funds resolved by name only (no fund code) |
| `nav_missing` | NAV snapshot is unavailable |
| `partial_nav_coverage` | Some trades lack trade-date NAV |
| `manual_review_transactions` | Conversion/refund/unknown transactions present |
| `stale_nav` | Latest NAV exceeds staleness threshold |
| `qdii_nav_lag` | QDII-like funds with potentially stale NAV |
| `fallback_holdings_used` | Valuation from existing portfolio_input, not reconstructed |
| `cashflow_only` | Some positions are cashflow-only (no valuation) |
| `estimated_only` | All positions are estimated (no confirmed valuation) |
| `identity_mismatch` | Some fund codes have code/name mismatch — valuation blocked for those funds |
| `identity_unverified` | Some fund codes have unverified manual override — valuation blocked until verified |
| `partial_valuation` | Some positions lack valuation — portfolio metrics incomplete |
| `redemption_fee_unknown` | Some funds have unknown redemption fees — confirmed P&L not available |
| `insufficient_trade_date_nav_coverage` | Some trades lack trade-date NAV — units derivation incomplete |

## Safety Constraints Enumeration

All `safety_constraints` values must come from this stable set:

| Constraint | Meaning |
|------------|---------|
| `not_formal_decision` | Output is not a formal investment Decision |
| `no_auto_trading` | No automated trading |
| `no_broker_or_order_execution` | No broker order execution |
| `estimated_values_are_not_confirmed` | Estimated values are not confirmed market values |
| `partial_not_complete_market_value` | Partial coverage does not represent complete market value |

## Safe-to-Analyze Values

Known safe-to-analyze scope items:

| Item | Meaning |
|------|---------|
| `cashflow_trend` | Cashflow trend analysis |
| `estimated_valuation_with_partial_coverage` | Estimated valuation (with coverage caveats) |
| `holdings_fallback` | Holdings fallback analysis |
| `transaction_quality` | Transaction quality assessment |
| `nav_coverage_quality` | NAV coverage quality assessment |

## Unsafe-to-Infer Values

Known unsafe-to-infer scope items:

| Item | Meaning |
|------|---------|
| `complete_market_value_if_coverage_partial` | Do not infer complete market value when coverage is partial |
| `confirmed_p_and_l_if_valuation_estimated` | Do not infer confirmed P&L when valuation is estimated |
| `trading_decision` | Do not make trading decisions |
| `broker_or_order_execution` | Do not execute broker orders |
| `valuation_if_identity_mismatch` | Do not infer valuation for funds with code/name mismatch |
| `valuation_if_identity_unverified` | Do not infer valuation for funds with unverified manual override |
| `complete_market_value_if_partial_valuation` | Do not infer complete market value when valuation coverage is partial |

## Artifact Paths

Default artifact paths (all relative to the run directory):

| Key | Default Path | Description |
|-----|-------------|-------------|
| `e2e_summary` | `e2e_summary.json` | Full pipeline summary |
| `report` | `report.md` | Composed report |
| `personal_health_report` | `personal_health_report.json` | Health report diagnostic |
| `portfolio` | `portfolio/confirmed_portfolio.private.json` | Reconstructed portfolio (only when reconstruction succeeded) |

### Path rules

- All paths MUST be relative (no leading `/`, no drive letters)
- Paths MUST NOT contain `private_data`, `local_data`, or `C:`
- The `portfolio` key is only present when `pipeline_steps.reconstruction_status == "reconstructed_from_ledger"`

## Validation Rules

1. `schema_version` must equal `fund_agent_context.v1`
2. `overall_status` must be one of the five allowed values
3. `confidence_level` must be one of the four allowed values
4. All `reason_codes` must come from the enumeration above
5. All `safety_constraints` must come from the enumeration above
6. All `artifact_paths` values must be relative paths
7. No `artifact_paths` value may contain `private_data` or absolute path indicators
8. `safe_to_analyze` must be empty when `overall_status` is `unavailable`
9. `recommended_agent_questions` must not contain trading advice (no buy/sell/trade as standalone verb)
