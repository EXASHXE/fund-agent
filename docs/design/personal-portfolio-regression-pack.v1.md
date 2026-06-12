# Personal Portfolio Regression Pack v1.1

## Purpose

The personal portfolio regression pack turns recurring Chinese retail
mutual-fund advisory questions into deterministic test fixtures. It protects
fund-agent's business judgment, formal decision boundaries, Chinese report
quality, risk discipline, short-holding fee handling, cash budget constraints,
profit protection, drawdown confirmation, overlap analysis, and report-only
routing.

This pack is regression data, not live market integration. All data is
synthetic and host-owned. Runtime code must not fetch market data, import
provider SDKs, call LLMs, execute broker orders, or fabricate missing evidence.

## Difference From Generic E2E Tests

Generic E2E fixtures validate broad workflow contracts. The personal regression
fixtures focus on realistic user-style portfolio situations that should remain
stable across future advisory-quality changes. They use short phrase fragments
and stable section IDs instead of exact long prose.

The flow is always:

```text
fund_analysis -> EvidenceGraph -> optional decision_support -> final report
```

`fund_analysis` remains analysis-only. `decision_support` remains the only
runtime that may produce formal `Decision` and `ExecutionLedger` artifacts.

## Blocked vs Allowed Formal Actions

v1.1 introduces positive formal-action regression cases alongside the existing
blocked/downgraded cases. This distinction is critical:

- **Blocked**: Evidence or constraints are insufficient. decision_support
  produces a passive HOLD/WAIT with reason codes explaining the blockage.
  Example: short_holding_7day_fee_sell_zh (7-day redemption fee blocker).

- **Downgraded**: User requested an active action but it was reduced to passive.
  Example: semiconductor_profit_recovery_after_rally_zh (profit protection
  concern causes downgrade from REDUCE to HOLD).

- **Allowed**: Evidence is sufficient, constraints permit the action, and
  decision_support produces an active BUY/SELL/INCREASE/REDUCE with positive
  execution_amount and evidence anchors. Example:
  semiconductor_profit_recovery_partial_reduce_allowed_zh (partial reduce
  with sufficient transaction history, no fee blocker, and risk cap).

### How to Design a Positive Formal Action Fixture Safely

1. Provide sufficient transaction history (avoid TRANSACTION_HISTORY_MISSING).
2. Ensure no redemption fee blocker (holding period > 7 days, fee = 0).
3. Ensure evidence graph has items (news, sentiment, benchmark, fee, etc.).
4. Set risk_profile.max_trade_pct and constraints.max_buy/max_sell_amount > 0.
5. Set target_trade_amount within risk caps.
6. For BUY-side: ensure cash_deployment_diagnostics.deployment_readiness is
   not "not_ready" and cash_buffer_status is not "low".
7. For BUY-side: ensure no right_side_unconfirmed or event_hype_failed blockers.
8. For SELL-side: ensure no redemption_fee_blocker.
9. Set `expected_action_outcome: "allowed"` in expected_behavior.
10. Set `expected_active_decision_count: 1` and `expected_blocked_decision_count: 0`.

## Scenario Categories

- Profit protection and principal recovery after rally.
- **Positive profit-protection partial reduce (allowed).**
- Rebound-chasing discipline after drawdown.
- Event hype failure and right-side confirmation.
- Short-holding redemption fee blockers.
- QDII/AI/S&P 500 overlap and concentration.
- Cash/bond deployment framework.
- **Positive cash deployment partial buy (allowed).**
- Low short-bond one-day yield versus cash-like alternatives.
- Oil/gas and battery loss/profit-giveback decisions.
- Dividend low-vol entry after short-term rally.
- Tactical budget discipline.
- Whole mixed-portfolio report-only review (main report regression).

## expected_behavior Contract

Each fixture has `expected_behavior` with:

- `expected_advisory_intents`
- `decision_support_called`
- `expected_report_status`
- `expected_decision_status`
- `expected_formal_source`
- decision ledger count expectations
- reason code and risk conflict fragments
- required report section IDs
- Chinese summary, direct answer, action boundary, and missing-data fragments
- no-fabrication field fragments
- `expected_no_broker_execution: true`
- `expected_action_outcome`: "allowed" | "capped" | "downgraded" | "blocked" | "passive"
- `expected_final_actions`: list of expected final action strings
- `expected_requested_actions`: list of requested action strings
- `expected_min_final_execution_amount`: minimum execution amount bound
- `expected_max_final_execution_amount`: maximum execution amount bound
- `expected_preserve_requested_action`: whether requested action must match final
- `expected_preserve_requested_amount`: whether requested amount must be preserved

Tests intentionally assert fragments, not full prose.

## Phrase Fragment Assertion Guidance

Prefer structured field assertions (section IDs, advisory_intents,
decision_status, ledger counts, reason codes, action_outcome) over phrase
locking. Reserve Chinese phrase fragments for safety-critical terms:

- 赎回费, 未满7天, 不执行券商下单, 回收本金, 不宜急着补仓,
  右侧确认, 安全垫, 不要只看一天收益

Use `flatten_report_text()` from `tests/helpers/personal_regression_runner.py`
to flatten sections for phrase checks. Phrase checks should be exact substring
for Chinese and case-insensitive for English.

## Mixed Portfolio Report-Only as Main Report Regression

`mixed_portfolio_report_only_zh` is the main personal analyst report
regression. It contains a rich synthetic portfolio with 7 positions covering
semiconductor/AI, innovation drug, QDII/US tech, battery, dividend low-vol,
oil/gas, and short-duration bond. It includes holdings overlap data, partial
NAV history, fee schedules, benchmark history, news and sentiment evidence,
and explicit cash_available with tactical budget constraints.

This fixture validates portfolio-level diagnosis, risk identification, and
report-only routing without formal decisions.

## No-Fabrication Cost Basis Rule

- Host-provided `position.total_cost` is allowed in PnL calculations.
- If transaction history is missing, `cost_basis_summary` should be
  absent/null/partial and limitations must disclose missing transaction data.
- Transaction-level cost basis must never be fabricated.
- Position-level cost from host-provided `total_cost` is not fabrication.

## Run Commands

```bash
pytest tests/personal_regression -q
python scripts/run_personal_regressions.py --pretty
python scripts/run_personal_regressions.py --json
python scripts/run_personal_regressions.py --scenario semiconductor_profit_recovery_partial_reduce_allowed_zh --pretty
```

## Shared Runner

Both `tests/personal_regression/test_personal_portfolio_regressions.py` and
`scripts/run_personal_regressions.py` use
`tests/helpers/personal_regression_runner.py` to avoid workflow logic drift.

API:
- `load_personal_regression_fixture(path)` -> dict
- `run_personal_regression_fixture(fixture, fixture_path)` -> PersonalRegressionResult
- `validate_personal_regression_result(result, expected_behavior)` -> list[dict]
- `list_personal_regression_fixtures(root)` -> list[Path]
- `flatten_report_text(report, section_ids)` -> str

## Adding New Personal Scenarios

Add a JSON fixture under `examples/personal_portfolio_regressions/`.

Use synthetic but realistic values. Include host-owned portfolio, NAV, holdings,
fees, redemption rules, benchmark, news, sentiment, risk profile, constraints,
and requested action fields only when available. Missing data should be omitted
or represented as empty input, then asserted as missing, partial, blocked, or
skipped. Never invent live price, latest news, exact fee, benchmark movement,
holdings overlap, or alternative yield.

Add stable expected fragments to `expected_behavior`. Prefer section IDs and
short Chinese phrases over full sentence snapshots. Include
`expected_action_outcome` to classify the scenario.

## Boundaries

- No live data.
- No provider SDKs.
- No network calls in core runtime.
- No broker/order execution.
- No LLM-based report generation.
- No formal `Decision` or `ExecutionLedger` from `fund_analysis`.
- No automatic decision_support call for report-only or soft-action advice.
- Active formal decisions require evidence anchors.
- Positive formal actions must not weaken safety gates for blocked scenarios.

## Quality Protection

The pack catches drift in user-facing Chinese answers and boundary behavior:
report-only scenarios must not call decision_support, fee-sensitive sells must
be blocked or downgraded, blind add/chase behavior must wait for confirmation,
overlap scenarios must explain marginal diversification, and cash deployment
must separate safety reserve from deployable capital. Positive allowed actions
must produce active decisions with valid evidence anchors and execution amounts
within risk caps.
