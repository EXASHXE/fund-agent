# Personal Portfolio Regression Pack v1

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

## Scenario Categories

- Profit protection and principal recovery after rally.
- Rebound-chasing discipline after drawdown.
- Event hype failure and right-side confirmation.
- Short-holding redemption fee blockers.
- QDII/AI/S&P 500 overlap and concentration.
- Cash/bond deployment framework.
- Low short-bond one-day yield versus cash-like alternatives.
- Oil/gas and battery loss/profit-giveback decisions.
- Dividend low-vol entry after short-term rally.
- Tactical budget discipline.
- Whole mixed-portfolio report-only review.

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

Tests intentionally assert fragments, not full prose.

## Run Commands

```bash
pytest tests/personal_regression -q
python scripts/run_personal_regressions.py --pretty
python scripts/run_personal_regressions.py --json
python scripts/run_personal_regressions.py --scenario semiconductor_profit_recovery_after_rally_zh --pretty
```

## Adding New Personal Scenarios

Add a JSON fixture under `examples/personal_portfolio_regressions/`.

Use synthetic but realistic values. Include host-owned portfolio, NAV, holdings,
fees, redemption rules, benchmark, news, sentiment, risk profile, constraints,
and requested action fields only when available. Missing data should be omitted
or represented as empty input, then asserted as missing, partial, blocked, or
skipped. Never invent live price, latest news, exact fee, benchmark movement,
holdings overlap, or alternative yield.

Add stable expected fragments to `expected_behavior`. Prefer section IDs and
short Chinese phrases over full sentence snapshots.

## Boundaries

- No live data.
- No provider SDKs.
- No network calls in core runtime.
- No broker/order execution.
- No LLM-based report generation.
- No formal `Decision` or `ExecutionLedger` from `fund_analysis`.
- No automatic decision_support call for report-only or soft-action advice.
- Active formal decisions require evidence anchors.

## Quality Protection

The pack catches drift in user-facing Chinese answers and boundary behavior:
report-only scenarios must not call decision_support, fee-sensitive sells must
be blocked or downgraded, blind add/chase behavior must wait for confirmation,
overlap scenarios must explain marginal diversification, and cash deployment
must separate safety reserve from deployable capital.
