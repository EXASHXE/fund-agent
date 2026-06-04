# Personal Fund Report Workflow

This workflow is the canonical host-side guide for the user request:

```text
分析下我的基金给出报告
```

`fund-agent` does not fetch user data or market data. The host owns data
fetching, data-fetching policy, user prompts, credentials, MCP providers, final
UX, and whether to escalate to formal decision support.

## Quick-start: end-to-end report flow

Run the reference end-to-end report flow to see the canonical report-only path:

```bash
python examples/minimal_personal_fund_report_flow.py
python examples/minimal_personal_fund_report_flow.py --output /tmp/fund-report.md
```

The flow:
1. Loads a host-provided payload.
2. Runs `FundAnalysisSkill` (deterministic, no network, no provider SDKs).
3. Produces `report_sections`, `report_outline`, `report_quality_gate`,
   `data_completeness`, `analysis_coverage`, and `report_limitations`.
4. Renders a Markdown report via `render_report_markdown()`.
5. Stops — no formal decisions are produced.

For formal action, use `minimal_personal_fund_report_with_decision_handoff.py`
which adds `DecisionSupportSkill` when `--with-decision` is passed.

```bash
python examples/minimal_personal_fund_report_with_decision_handoff.py
python examples/minimal_personal_fund_report_with_decision_handoff.py --with-decision
```

Note: `DecisionSupportSkill` requires evidence-anchored active decisions
(BUY/SELL/INCREASE/REDUCE) or defaults to WAIT/HOLD when evidence is
insufficient.

Portfolio can be provided directly via `portfolio.positions` or derived from
`transactions` + `current_nav` + `as_of_date`. The derived portfolio snapshot is
deterministic (weighted-average cost basis) but depends on input completeness.
Realized PnL is weighted-average and limited; if incomplete, the skill outputs
a warning and `null` rather than overclaiming.

Research query plan is only a plan; the host decides whether to call
news/sentiment skills. New capabilities (benchmarks, peers, managers, fees,
redemption rules, macro events, market calendar, etc.) are host-owned
contracts, not built-in providers. `fund-agent` still does not fetch NAV,
news, sentiment, or fund profiles directly.

## 1. User request

A user asking `分析下我的基金给出报告` is asking for an analysis report, not
automatically for executable trade advice. Hosts should default to a report-only
flow and escalate to `decision_support` only when the user asks for actionable
buy, sell, increase, reduce, wait, or hold guidance.

## 2. Objective interpretation

Default objective:

```json
{
  "objective": "portfolio_review",
  "formal_decision": false
}
```

Do not assume the user wants executable trade decisions. A report request should
normally stop after `FundAnalysisSkill` unless the user asks what to buy, sell,
increase, reduce, wait on, or hold.

## 3. Data collection checklist

Collect as much of the following from the host data layer as available:

- `portfolio`
- `transactions`
- `current_nav`
- `fund_profiles`
- `nav_history`
- `holdings`
- `dca_plans`
- `risk_profile`
- `constraints`
- `benchmark_history`
- `peer_group`
- `factor_exposures`
- `manager_profiles`
- `fee_schedules`
- `redemption_rules`
- `fund_flow`
- `macro_events`
- `user_investment_plan`
- `market_scenario` (if a stress or drawdown view is in scope)

If portfolio positions exist but optional data is missing, proceed with
`PARTIAL` analysis and label the missing data in warnings.

If `portfolio.positions` is missing but `transactions` + `current_nav` +
`as_of_date` exist, `fund_analysis` will deterministically derive a position
snapshot from the transaction ledger. The derived snapshot emits
`derived_portfolio_snapshot` and `ledger_cashflow_summary` artifacts.

## 4. Required vs optional data

Required data groups for a professional personal report:

- portfolio snapshot via `portfolio.positions`, or a derived snapshot from
  `transactions` + `current_nav` + `as_of_date`
- current value or `current_nav` sufficient to value positions
- `fund_profiles`
- `nav_history`
- `holdings`
- `risk_profile`
- `constraints`

Optional data groups that improve analysis quality:

- `benchmark_history`
- `peer_group`
- `factor_exposures`
- `manager_profiles`
- `fee_schedules`
- `redemption_rules`
- `fund_flow`
- `macro_events`
- `user_investment_plan`

Missing portfolio or a derivable snapshot is critical and returns
`INVALID_INPUT`. Missing `risk_profile` or `constraints` does not necessarily
fail the skill, but it lowers `data_completeness` and adds limitations.
Missing `nav_history` or `holdings` lowers the grade and marks performance or
holding sections `PARTIAL`/`MISSING`. If only `related_entities` is supplied,
use the baseline `HardEvidence` compatibility path and warn that structured
portfolio analysis was not possible.

## 5. When to ask the user for missing data

Ask before running when:

- there are no positions;
- fund codes are missing;
- current values are missing;
- the user asks for exact PnL but costs or transactions are absent;
- the user asks for formal trade advice but risk limits are missing.

## 6. When to proceed with PARTIAL analysis

Proceed with `PARTIAL` when:

- positions and current values exist;
- optional NAV history, holdings, transactions, DCA plans, or market scenario
  are missing;
- the host can clearly label missing data in warnings.

Emit explicit `warnings` for every missing optional data category. Do not
fabricate missing data.

## 7. Minimal payload

```json
{
  "portfolio": {
    "as_of_date": "2026-06-01",
    "total_value": 200000,
    "cash_available": 20000,
    "positions": [
      {
        "fund_code": "110011",
        "fund_name": "Example Fund",
        "current_value": 60000,
        "total_cost": 58000,
        "target_weight": 0.25,
        "tags": ["broad_market"]
      }
    ]
  },
  "risk_profile": {
    "risk_level": "moderate",
    "max_single_fund_weight": 0.2,
    "max_theme_weight": 0.35,
    "max_trade_pct": 0.1,
    "liquidity_reserve_pct": 0.1,
    "short_term_trade_budget_pct": 0.1
  },
  "constraints": {
    "min_trade_amount": 100,
    "forbidden_actions": []
  }
}
```

## 8. Expanded payload

```json
{
  "portfolio": {},
  "transactions": [],
  "fund_profiles": {
    "110011": {"fund_code": "110011", "name": "Example Fund", "fund_type": "equity"}
  },
  "nav_history": {
    "110011": [
      {"date": "2025-06-01", "nav": 1.0},
      {"date": "2026-06-01", "nav": 1.2}
    ]
  },
  "holdings": {
    "110011": [
      {"name": "A", "weight": 0.08, "industry": "technology", "region": "CN"}
    ]
  },
  "dca_plans": {
    "110011": {"monthly_amount": 1000}
  },
  "risk_profile": {},
  "constraints": {},
  "market_scenario": {
    "name": "host_supplied_drawdown",
    "risk_level": "high",
    "description": "Host-provided market scenario"
  }
}
```

## 9. Calling FundAnalysisSkill

```python
from src.schemas.skill import SkillInput
from src.skills_runtime.fund_analysis import FundAnalysisSkill

fund_output = FundAnalysisSkill().run(
    SkillInput(
        task_id="host-task-1",
        step_id="fund-analysis-1",
        skill_name="fund_analysis",
        payload=payload,
    )
)
```

`FundAnalysisSkill` emits artifacts plus `HardEvidence`. It may emit warnings
or `PARTIAL` status when optional data is missing.

## 10. Generating a report without formal decisions

If `formal_decision=false`, the host writes the final report directly from:

- `fund_output.artifacts["report_sections"]`
- `fund_output.artifacts["report_outline"]`
- `fund_output.artifacts["report_quality_gate"]`
- `fund_output.artifacts["portfolio_summary"]`
- `fund_output.artifacts["exposure_summary"]`
- `fund_output.artifacts["risk_flags"]`
- `fund_output.artifacts["fund_analysis_report"]`
- `fund_output.artifacts["suggested_rebalance_plan"]`
- `fund_output.artifacts["data_completeness"]`
- `fund_output.artifacts["analysis_coverage"]`
- `fund_output.artifacts["report_limitations"]`
- `fund_output.evidence_items`
- `fund_output.warnings`

`report_sections` are deterministic and host-displayable. Missing optional data
appears as `PARTIAL` or `MISSING` sections with limitations rather than
fabricated analysis. `report_quality_gate` says whether the artifact set is
publishable as a professional report.

Do not turn `suggested_rebalance_plan` into executable advice by itself. The
host should label it as a suggested plan, not a decision.

## 11. When to escalate to DecisionSupportSkill

Escalate when the user asks:

- `现在该买什么？`
- `要不要卖？`
- `帮我给出买卖操作`
- `加仓还是减仓？`
- `给我正式决策`

Do not escalate for a plain report request unless the host policy requires it.

## 12. Calling DecisionSupportSkill

If the user asks for actionable trade advice:

1. Compile an `EvidenceGraph`.
2. Extract `suggested_rebalance_plan`.
3. Call `DecisionSupportSkill`.
4. Use returned `Decision` and `ExecutionLedger`.

```python
from src.tools.evidence.validators import compile_evidence_graph
from src.skills_runtime.decision_support import DecisionSupportSkill

compile_result = compile_evidence_graph(fund_output.evidence_items)
trade_plan = fund_output.artifacts.get("suggested_rebalance_plan", {})

decision_output = DecisionSupportSkill().run(
    SkillInput(
        task_id="host-task-1",
        step_id="decision-1",
        skill_name="decision_support",
        payload={
            "evidence_graph": compile_result.graph.to_dict(),
            "trade_plan": trade_plan,
            "portfolio_context": payload["portfolio"],
            "risk_profile": payload.get("risk_profile", {}),
            "constraints": payload.get("constraints", {}),
            "objective": "personal portfolio trade decision",
        },
    )
)
```

`DecisionSupportSkill` is the only skill allowed to emit formal `Decision` or
`ExecutionLedger` objects.

## 13. Report section template

Use `fund_output.artifacts["report_sections"]` as the canonical structured
outline:

1. `executive_summary`
2. `portfolio_snapshot`
3. `pnl_and_cost_basis`
4. `allocation_and_exposure`
5. `risk_flags`
6. `performance_and_nav`
7. `benchmark_and_peer`
8. `factor_and_style`
9. `fees_and_redemption`
10. `manager_and_fund_profile`
11. `dca_and_trade_budget`
12. `rebalance_plan`
13. `research_query_plan`
14. `data_completeness_and_limitations`
15. `evidence_appendix`

Each section has `id`, `title`, `status`, `bullets`, `data_sources`, and
`limitations`. Hosts may render these sections directly or adapt them to their
UX, but should preserve `PARTIAL` and `MISSING` statuses.

## 14. Warning and uncertainty language

Use concrete, bounded wording:

```text
由于缺少部分基金持仓明细，行业集中度分析为 PARTIAL；本报告不会据此生成正式买卖决策。
```

```text
当前建议先观察，不是因为亏损本身，而是因为缺少能支持加仓或卖出的交易级证据。
```

```text
市场情景来自主机提供的数据，fund-agent 未自行抓取或推断市场状态。
```

## 14.5. Report quality and data completeness

The skill now produces `data_completeness` (score 0.0-1.0 and grade A-D),
`analysis_coverage` (per-section availability), `report_limitations`
(concise user-facing caveats), `report_sections`, and `report_quality_gate`.
Use these to set reader expectations:

- Grade **A**: near-complete input — all required + most optional data present.
- Grade **B**: all required data present, some optional missing — adequate.
- Grade **C**: usable report with important limitations; keep limitations
  prominent.
- Grade **D**: insufficient for a professional report unless the host
  explicitly requested minimal report mode and core portfolio data exists.

`report_quality_gate.can_publish_professional_report` is true for grade A/B,
true for grade C with prominent limitations, and false for grade D unless
minimal report mode is requested. Formal actions still require
`DecisionSupportSkill`.

In the report, include:

```text
数据完整性评级: B (评分 0.78)
缺失数据: 无费率数据、无同类基金排名
分析覆盖: 组合=可用, 业绩=可用, 持仓=可用, 基准=缺失, 同业=缺失
```

If `redemption_summary` warns about lockup funds, elevate that warning to the
executive summary. If `fee_summary` flags high-fee funds, suggest cost review.

```text
⚠️ 赎回限制: 基金 110011 持有不足30天需支付0.5%赎回费
⚠️ 费率提醒: 基金 110011 综合费率2.15%高于同类均值
```

## 15. Evidence appendix guidance

The evidence appendix is what makes the report auditable. For every claim in
sections 1-14, the host should attach:

- the `HardEvidence` or `SoftEvidence` ID(s) that justify the claim;
- the source artifact (for example `portfolio_summary`, `exposure_summary`,
  `risk_flags`, `suggested_rebalance_plan`) the claim was derived from;
- any `warnings` that downgrade the claim to `PARTIAL`.

Format guidance:

- one row per claim, with the artifact name, evidence IDs, and any caveat;
- group rows by report section so the reader can trace each section back to
  its evidence;
- if a claim has no evidence ID, mark it as an observation, not a fact;
- if a `WAIT`/`HOLD` is recommended, list the missing evidence IDs and the
  trigger that would change the recommendation.

`fund-agent` does not produce the appendix formatting — the host renders it
from `SkillOutput.evidence_items`, `artifacts`, and `warnings`.
