# Portfolio Input Transactions Fallback Design

## Problem

When no Alipay CSV is available, users cannot run the personal plugin pipeline.
`portfolio_input.private.json` may contain a `transactions` array, but the E2E
pipeline currently only reads transactions from the Alipay CSV import path.

## Solution

Add a `portfolio_input.transactions` → ledger adapter so the pipeline can use
transactions embedded in `portfolio_input.private.json` as a fallback when no
Alipay CSV exists, or when the user explicitly chooses this source.

## Input Schema

Each transaction in `portfolio_input.transactions`:

| Field | Required | Type | Rules |
|-------|----------|------|-------|
| `trade_date` | yes | string | YYYY-MM-DD |
| `fund_code` | no | string | If present, must be 6 digits |
| `fund_name` | no | string | Chinese names OK here |
| `transaction_type` | yes | string | buy/sell/dividend/fee/conversion_in/conversion_out/refund/unknown |
| `amount` | yes | number | Must be numeric |
| `units` | no | number | Explicit share count |
| `nav` | no | number | Trade-date NAV |
| `source` | no | string | Default: portfolio_input.transactions |
| `note` | no | string | Not used in pipeline logic |

## Ledger Mapping

Adapter maps each portfolio_input transaction to the standard ledger format:

| Ledger field | Source |
|--------------|--------|
| `transaction_id` | Synthetic: `pi_txn_{index:06d}` |
| `source` | `portfolio_input.transactions` |
| `fund_code` | As-is from input |
| `fund_name` | As-is from input |
| `normalized_name` | Via `normalize_fund_name()` |
| `trade_date` | As-is |
| `action` | Mapped from `transaction_type` |
| `amount` | As-is |
| `units` / `shares` | From `units` field, if provided |
| `nav` | From `nav` field, if provided |
| `confirmation_type` | `user_provided_private_input` |
| `confirmation_source` | `portfolio_input_transactions` |
| `confidence` | `user_provided` |
| `ambiguous_portfolio_effect` | True for conversion/refund |

## Source Precedence

1. **Alipay CSV** (default when present): `transaction_source = alipay`
2. **portfolio_input.transactions** (fallback): `transaction_source = portfolio_input.transactions`
3. **Auto mode** (default): Alipay CSV takes precedence if both exist

## Valuation Semantics

| Condition | valuation_type | portfolio_input_source |
|-----------|---------------|----------------------|
| Transactions + trade-date NAV | `estimated` | `reconstructed_from_ledger` |
| Transactions + explicit units | `estimated` (units_source = user_provided) | `reconstructed_from_ledger` |
| Transactions only, no NAV | `cashflow_only` | `unavailable` |
| Transactions + holdings fallback | `cashflow_only` (txns) + valuation (holdings) | `existing_private_portfolio_input` |
| No transactions, holdings only | `none` | `existing_private_portfolio_input` |

Key rules:
- `latest_nav` alone does NOT create historical units
- Holdings fallback is NOT `reconstructed_from_ledger`
- Estimated is NOT confirmed
- Partial coverage must be labeled

## Privacy Rules

- No real fund names in logs/tests
- No real amounts in doctor/diagnostics output
- Synthetic transaction IDs only
- `note` field not propagated to report
- All validation errors report counts, not content

## Report Wording

| Source | Cashflow Label | Valuation Label |
|--------|---------------|-----------------|
| Alipay CSV | Alipay transactions | per valuation_type |
| portfolio_input.transactions | portfolio_input.transactions | per valuation_type |
| Holdings fallback | N/A | existing_private_portfolio_input |

No source should be labeled as broker/order execution.
