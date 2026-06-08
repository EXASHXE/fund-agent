# Decision Support Fixtures

**Fixtures are fake/sample data only.**

These fixtures exercise the `decision_support` runtime skill with deterministic
JSON payloads. They are used for contract verification, regression testing, and
golden snapshots.

**IMPORTANT DISCLAIMERS:**

- Fake/sample data only. Not investment advice.
- Not real-time market data.
- Not real personal holdings or transaction data.
- The host owns real data fetching, provider SDK integration, and credentials.
- `decision_support` may emit formal `Decision` / `ExecutionLedger` artifacts.
- `decision_support` does not execute trades, place orders, or connect to
  brokerage systems.
- `fund_analysis` `suggested_rebalance_plan` is not a formal order or decision.

## Fixture Files

### `single_active_buy_with_evidence.json`
- Input mode: `single_decision`
- `requested_action: BUY` with a non-empty `evidence_graph` containing two
  positive evidence items.
- Includes `target_trade_amount`, `portfolio_context`, `risk_profile`,
  `constraints`, and `risk_budget`.
- Expected: `OK` status with a formal `Decision` and `ExecutionLedger` artifact.
- Deterministic mode enabled for stable test output.

### `single_active_buy_without_evidence_invalid.json`
- Input mode: `single_decision`
- `requested_action: BUY` with an empty `evidence_graph`.
- Expected: `FAILED` status with a `CONTRACT_VIOLATION` error, because active
  decisions require at least one real evidence anchor.

### `single_passive_hold_without_evidence.json`
- Input mode: `single_decision`
- `requested_action: HOLD` with an empty `evidence_graph`.
- Includes `why_not_buy`, `why_not_sell`, `missing_evidence` fields.
- Expected: `OK` status with a `WAIT` or `HOLD` decision; passive actions do
  not require evidence anchors.

### `trade_plan_selected_trade_with_caps.json`
- Input mode: `trade_plan_decision`
- `trade_plan.suggested_trade_plan` with two trades; `selected_trade_ids`
  selects only the first.
- `portfolio_context.cash_available` is low (3000.0), `max_buy_amount` is
  5000.0, and requested amount is 10000.0.
- Expected: `OK` status with the BUY amount capped to 3000.0 (cash available)
  and `cap_reasons` in the decision output.

### `trade_plan_forbidden_action_skipped.json`
- Input mode: `trade_plan_decision`
- `trade_plan` contains a SELL action, but `constraints.forbidden_actions`
  includes `SELL`.
- `selected_trade_ids` selects the forbidden trade.
- Expected: `PARTIAL` status with a `WAIT` decision because the forbidden trade
  is skipped with a warning. The forbidden action must not be emitted as a
  valid formal decision.

### `trade_plan_no_evidence_downgraded.json`
- Input mode: `trade_plan_decision`
- `trade_plan` contains an active BUY trade, but `evidence_graph` has no items.
- Expected: The active BUY is downgraded to `HOLD` with an explanation that no
  real evidence anchor is available. Output status is `OK` with a `HOLD`
  decision.
