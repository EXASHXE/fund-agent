# Personal Fund Report Workflow

This workflow is the canonical host-side guide for the user request:

```text
分析下我的基金给出报告
```

`fund-agent` does not fetch user data or market data. The host owns data
fetching, data-fetching policy, user prompts, credentials, MCP providers, final
UX, and whether to escalate to formal decision support.

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
- `fund_profiles`
- `nav_history`
- `holdings`
- `dca_plans`
- `risk_profile`
- `constraints`
- `market_scenario` (if a stress or drawdown view is in scope)

If portfolio positions exist but optional data is missing, proceed with
`PARTIAL` analysis and label the missing data in warnings.

## 4. Required vs optional data

Required to produce any portfolio analysis:

- `portfolio.as_of_date`
- `portfolio.total_value`
- `portfolio.cash_available`
- `portfolio.positions[]` with `fund_code` and `current_value`
- `risk_profile` with concentration, liquidity, and trade budget limits
- `constraints` such as minimum trade amount and forbidden actions

Optional (improves analysis quality but not strictly required):

- `fund_profiles` for fund type, benchmark, manager, and tags
- `nav_history` for deterministic risk-return metrics
- `holdings` for theme, industry, region, and security exposure
- `transactions` for cost basis, cashflow, and trading discipline analysis
- `dca_plans` for recurring investment review
- `market_scenario` supplied by the host (never fetched by `fund-agent`)

If required data is absent, return `INVALID_INPUT`. If only `related_entities`
is supplied, use the baseline `HardEvidence` compatibility path and warn that
structured portfolio analysis was not possible.

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

- `fund_output.artifacts["portfolio_summary"]`
- `fund_output.artifacts["exposure_summary"]`
- `fund_output.artifacts["risk_flags"]`
- `fund_output.artifacts["fund_analysis_report"]`
- `fund_output.artifacts["suggested_rebalance_plan"]`
- `fund_output.evidence_items`
- `fund_output.warnings`

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

1. Executive summary
2. Portfolio overview
3. Position table
4. Cost and PnL summary
5. Fund type allocation
6. Theme exposure
7. Industry exposure
8. Cash ratio
9. Fund metrics
10. Risk flags
11. DCA review
12. Short-term budget review
13. Suggested rebalance plan
14. WAIT/HOLD/BUY/SELL explanation
15. Data gaps and warnings
16. Evidence appendix

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
