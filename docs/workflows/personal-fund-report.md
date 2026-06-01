# Personal Fund Report Workflow

This workflow covers the user request:

```text
分析下我的基金给出报告
```

`fund-agent` does not fetch user data or market data. The host owns data
fetching, data-fetching policy, user prompts, credentials, MCP providers, final
UX, and whether to escalate to formal decision support.

## 1. Interpret Objective

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

## 2. Collect Data

Data requirements checklist:

- `portfolio`
- `transactions`
- `fund_profiles`
- `nav_history`
- `holdings`
- `dca_plans`
- `risk_profile`
- `constraints`
- `market_scenario` if applicable

Ask the user or host data layer for missing required data. Proceed with PARTIAL
analysis when portfolio positions exist but optional data is missing.

## 3. Example Minimal Payload

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

## 4. Example Expanded Payload

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

## 5. Call FundAnalysisSkill

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

## 6. Generate Report Without Formal Decision

If `formal_decision=false`, the host writes the final report directly from:

- `fund_output.artifacts["portfolio_summary"]`
- `fund_output.artifacts["exposure_summary"]`
- `fund_output.artifacts["risk_flags"]`
- `fund_output.artifacts["fund_analysis_report"]`
- `fund_output.artifacts["suggested_rebalance_plan"]`
- `fund_output.evidence_items`
- `fund_output.warnings`

## 7. Escalate For Actionable Trade Advice

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

## 8. Report Section Template

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

## 9. When To Ask The User For Missing Data

Ask before running when:

- there are no positions;
- fund codes are missing;
- current values are missing;
- the user asks for exact PnL but costs or transactions are absent;
- the user asks for formal trade advice but risk limits are missing.

## 10. When To Proceed With PARTIAL Analysis

Proceed when:

- positions and current values exist;
- optional NAV history, holdings, transactions, DCA plans, or market scenario
  are missing;
- the host can clearly label missing data in warnings.

## 11. When To Escalate To decision_support

Escalate when the user asks:

- `现在该买什么？`
- `要不要卖？`
- `帮我给出买卖操作`
- `加仓还是减仓？`
- `给我正式决策`

Do not escalate for a plain report request unless the host policy requires it.

## 12. Warning And Uncertainty Language

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
