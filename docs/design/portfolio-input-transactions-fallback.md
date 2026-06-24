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

Controlled by `--transaction-source` flag and `decide_transaction_source()`:

| Mode | Alipay CSV exists | portfolio_input.transactions exists | Result |
|------|-------------------|-------------------------------------|--------|
| `auto` | yes | yes | alipay (precedence) |
| `auto` | yes | no | alipay |
| `auto` | no | yes | portfolio_input.transactions |
| `auto` | no | no | none (error) |
| `alipay` | yes | any | alipay |
| `alipay` | no | yes | none (error: no fallback) |
| `alipay` | no | no | none (error) |
| `portfolio_input` | any | yes | portfolio_input.transactions (ignores Alipay) |
| `portfolio_input` | yes | no | none (error: no fallback) |
| `portfolio_input` | no | no | none (error) |

Explicit modes are strict — they never silently fall back to the other source.

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

## Validation Visibility

Invalid transactions are not silently dropped. The adapter surfaces:

| Field | Location | Purpose |
|-------|----------|---------|
| `needs_manual_review` | Per-transaction | `True` if any validation warning |
| `validation_status` | Per-transaction | `"ok"` or `"warning"` |
| `valid_count` / `invalid_count` | Summary | How many passed/failed validation |
| `warning_count` | Summary | Total warnings across all transactions |
| `manual_review_count` | Summary | Count of transactions needing review |
| `invalid_fund_code_count` | Summary | Bad fund code count |
| `invalid_date_count` | Summary | Bad date count |
| `invalid_amount_count` | Summary | Non-numeric amount count |
| `unknown_transaction_type_count` | Summary | Unrecognized type count |

The E2E pipeline surfaces these in `e2e_summary.json` under the
`portfolio_input_transactions` key and adds a pipeline-level warning
when validation warnings exist. The report builder shows total/warnings/
manual_review counts in the reconstruction_status section, and adds a
limitation when manual review is needed.

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
