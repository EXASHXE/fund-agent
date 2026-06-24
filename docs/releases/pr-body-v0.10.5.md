# v0.10.5 Personal Plugin — Functional Freeze

## Status

- **Head:** `3cb72f5`
- **Branch:** `t1.0` — open PR, **not merged, not tagged, not released**
- **Freeze:** personal-plugin functional freeze achieved

## Completed Capabilities

- **Alipay CSV real E2E:** 100 transactions parsed, ledger 100 evidence-confirmed transactions
- **Identity schema v2** with `fund_identity_overrides.private.yaml` support
- **Valid six-digit fund code resolution**
- **NAV overrides** (trade-date)
- **Reconstructed from ledger** (`reconstructed_from_ledger`) when transactions + NAV available
- **Valuation type state machine:** `none` → `cashflow_only` → `estimated` → `valuation` (confirmed source only)
- **Partial valuation coverage**
- **`existing_private_portfolio_input` fallback**

## Report Semantics

- No fake `0.00` — unknown values are `None`, not zero
- Cashflow ≠ valuation — clearly separated
- Estimated ≠ confirmed — distinct labels
- `transactions_only` source label distinct from `existing_private_portfolio_input`
- No `reconstructed_from_ledger` wording for fallback/cashflow-only scenarios

## Gates

| Gate | Result |
|------|--------|
| `test_fast` | 2338 passed |
| `test_identity_nav` | 70 passed |
| `test_plugin_smoke` | 236 passed |
| Privacy check | PASS |
| Workflow/report/public_api/architecture | 438 passed |
| Full pytest | 4177 passed, 16 skipped, 1 warning |

## Remaining Limitations

- Provider/live data is optional (not required for freeze)
- v0.10.6 backlog covers:
  - Architecture cleanup
  - `portfolio_input.transactions` fallback
  - Provider/NAV enhancement
  - QDII/conversion/refund/fee refinement

## Merge Policy

Final merge/tag only after **explicit user approval**.
