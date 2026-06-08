# Personal Fund Scenario Fixtures

These scenario fixtures are fake/sample data for runtime bridge testing and
host-integration examples. They are not investment advice, not real-time market data,
and not real personal holdings or transaction records.

External hosts own real data fetching, provider SDK integration, credentials,
MCP providers, retries, planning, orchestration, memory, and final UX.
`fund_analysis` outputs analysis artifacts, evidence, warnings, deterministic
report sections, and optional Markdown reports only. Formal decisions require
`decision_support`.

The golden regression snapshots for selected fixtures are documented in
[`tests/golden/README.md`](../../tests/golden/README.md) and regenerated with
[`scripts/update_fund_analysis_golden.py`](../../scripts/update_fund_analysis_golden.py).

All fixtures use the runtime bridge convenience envelope:

```json
{
  "payload": {}
}
```

## Fixtures

### `examples/scenarios/cn_fund_7d_redemption_fee.json`

Purpose: model a fake Chinese mutual fund portfolio where one recent buy is
inside a sample 7-day redemption-fee window while another holding is older than
30 days.

Important payload sections:

- `portfolio`, `transactions`, and `current_nav`
- `fund_profiles`, `nav_history`, and `holdings`
- `fee_schedules` and `redemption_rules`
- `risk_profile`, `constraints`, `dca_plans`, and `report_options`

Validation:

```bash
python scripts/run_skill.py --skill fund_analysis --input examples/scenarios/cn_fund_7d_redemption_fee.json --validate-input --pretty
```

Run:

```bash
python scripts/run_skill.py --skill fund_analysis --input examples/scenarios/cn_fund_7d_redemption_fee.json --pretty
```

Markdown report:

```bash
python scripts/run_skill.py --skill fund_analysis --input examples/scenarios/cn_fund_7d_redemption_fee.json --emit-report markdown --output /tmp/cn_fund_7d_redemption_fee.md
```

### `examples/scenarios/cn_fund_qdii_sp500_overlap.json`

Purpose: model overlap risk between fake QDII, S&P 500-style, Nasdaq-style,
and AI-themed funds using synthetic holdings and synthetic benchmark history.

Important payload sections:

- `portfolio`, `transactions`, and `current_nav`
- `fund_profiles`, `holdings`, and `nav_history`
- `benchmarks`, `benchmark_history`, and `factor_exposures`
- `constraints`, `risk_profile`, `fee_schedules`, `redemption_rules`, and
  `report_options`

Validation:

```bash
python scripts/run_skill.py --skill fund_analysis --input examples/scenarios/cn_fund_qdii_sp500_overlap.json --validate-input --pretty
```

Run:

```bash
python scripts/run_skill.py --skill fund_analysis --input examples/scenarios/cn_fund_qdii_sp500_overlap.json --pretty
```

Markdown report:

```bash
python scripts/run_skill.py --skill fund_analysis --input examples/scenarios/cn_fund_qdii_sp500_overlap.json --emit-report markdown --output /tmp/cn_fund_qdii_sp500_overlap.md
```

### `examples/scenarios/cn_fund_ai_semiconductor_overweight.json`

Purpose: model a fake portfolio overweight in AI and semiconductor exposure,
including synthetic holdings, factor exposure, and a host-supplied fake market
scenario.

Important payload sections:

- `portfolio`, `target_weights`, `transactions`, and `current_nav`
- `fund_profiles`, `holdings`, and `nav_history`
- `factor_exposures` and `market_scenario`
- `risk_profile`, `constraints`, `fee_schedules`, `redemption_rules`,
  `dca_plans`, and `report_options`

Validation:

```bash
python scripts/run_skill.py --skill fund_analysis --input examples/scenarios/cn_fund_ai_semiconductor_overweight.json --validate-input --pretty
```

Run:

```bash
python scripts/run_skill.py --skill fund_analysis --input examples/scenarios/cn_fund_ai_semiconductor_overweight.json --pretty
```

Markdown report:

```bash
python scripts/run_skill.py --skill fund_analysis --input examples/scenarios/cn_fund_ai_semiconductor_overweight.json --emit-report markdown --output /tmp/cn_fund_ai_semiconductor_overweight.md
```

### `examples/scenarios/cn_fund_dca_drawdown_review.json`

Purpose: model a fake DCA plan under a recent synthetic NAV drawdown and partial
recovery. Any formal DCA change remains a `decision_support` responsibility.

Important payload sections:

- `portfolio`, `transactions`, and `current_nav`
- `nav_history` with synthetic decline and recovery points
- `dca_plans`, `market_scenario`, `risk_profile`, and `constraints`
- `fund_profiles`, `holdings`, `fee_schedules`, `redemption_rules`, and
  `report_options`

Validation:

```bash
python scripts/run_skill.py --skill fund_analysis --input examples/scenarios/cn_fund_dca_drawdown_review.json --validate-input --pretty
```

Run:

```bash
python scripts/run_skill.py --skill fund_analysis --input examples/scenarios/cn_fund_dca_drawdown_review.json --pretty
```

Markdown report:

```bash
python scripts/run_skill.py --skill fund_analysis --input examples/scenarios/cn_fund_dca_drawdown_review.json --emit-report markdown --output /tmp/cn_fund_dca_drawdown_review.md
```

### `examples/scenarios/cn_fund_ledger_derived_snapshot.json`

Purpose: model `ledger_derived` mode, where the runtime derives a portfolio
snapshot from a synthetic transaction ledger plus `current_nav` rather than from
a direct portfolio snapshot.

Important payload sections:

- `as_of_date`, `transactions`, and `current_nav`
- `fund_profiles`, `nav_history`, and `holdings`
- `risk_profile`, `constraints`, `dca_plans`, `fee_schedules`,
  `redemption_rules`, and `report_options`

Validation:

```bash
python scripts/run_skill.py --skill fund_analysis --input examples/scenarios/cn_fund_ledger_derived_snapshot.json --validate-input --pretty
```

Run:

```bash
python scripts/run_skill.py --skill fund_analysis --input examples/scenarios/cn_fund_ledger_derived_snapshot.json --pretty
```

Markdown report:

```bash
python scripts/run_skill.py --skill fund_analysis --input examples/scenarios/cn_fund_ledger_derived_snapshot.json --emit-report markdown --output /tmp/cn_fund_ledger_derived_snapshot.md
```

## Professional Diagnostics

Certain scenarios exercise local-only, deterministic professional diagnostics
injected into `fund_analysis` report artifacts when host data supports them.
These are diagnostic artifacts only — not formal decisions and not provider
recommendations.

- **redemption_fee_risk** — Detects recent buys within short-holding fee
  windows using host-supplied `transactions`, `fee_schedules`, and
  `redemption_rules`.
  Exercised by: `cn_fund_7d_redemption_fee.json`
- **overlap_diagnostics** — Detects overlapping holdings, themes, and regions
  across multiple funds using host-supplied `holdings` and `fund_profiles`.
  Exercised by: `cn_fund_qdii_sp500_overlap.json`
- **theme_overweight_diagnostics** — Flags fund `theme` tags that exceed
  `risk_profile.max_theme_weight` or `constraints.max_single_theme_weight`.
  Exercised by: `cn_fund_ai_semiconductor_overweight.json`
- **dca_drawdown_diagnostics** — Reviews DCA plans for funds with recent NAV
  drawdowns. Uses `nav_history`, `dca_plans`, and computed `fund_metrics`.
  Exercised by: `cn_fund_dca_drawdown_review.json`
- **cash_budget_diagnostics** — Compares `cash_available` against
  `liquidity_reserve_pct` and tracks `short_term_trade_budget_pct` usage.
  May surface in any fixture with `risk_profile` and `cash_available`.
- **professional_diagnostics** — Aggregates all diagnostic results into a
  single summary artifact.

All diagnostics use host-supplied data only. They do not fetch live data, do
not call provider SDKs, and do not produce formal `Decision` / `ExecutionLedger`
artifacts. Formal actions require `decision_support`.
