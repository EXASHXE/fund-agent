---
id: fund_analysis
name: fund-analysis
runtime: src.skills_runtime.fund_analysis:FundAnalysisSkill
input_schema: src.schemas.skill:SkillInput
output_schema: src.schemas.skill:SkillOutput
required_mcp_capabilities: []
produced_evidence_type: HardEvidence
---

# Fund Analysis

## Purpose

Analyze host-provided personal fund and portfolio data. The skill computes
local NAV risk-return metrics, position weights, concentration, theme exposure,
risk flags, and an optional rebalance simulation. It emits HardEvidence and
plain artifacts only.

## Contract

- `id`: `fund_analysis`
- `runtime`: `src.skills_runtime.fund_analysis:FundAnalysisSkill`
- `input_schema`: `src.schemas.skill:SkillInput`
- `output_schema`: `src.schemas.skill:SkillOutput`
- `required_mcp_capabilities`: `[]`
- `produced_evidence_type`: `HardEvidence`
- `forbidden_behavior`: network requests, LLM calls, provider SDK imports,
  formal decision generation

The host owns data fetching. Provide portfolio positions, fund profiles,
NAV history, holdings, risk profile, and constraints in `payload`. Missing
fund-level data produces `PARTIAL` with explicit warnings by fund code.

## Example SkillInput

```json
{
  "task_id": "task-1",
  "step_id": "fund-analysis-1",
  "skill_name": "fund_analysis",
  "payload": {
    "portfolio": {
      "as_of_date": "2026-06-01",
      "total_value": 200000,
      "cash_available": 20000,
      "positions": [
        {
          "fund_code": "110011",
          "fund_name": "Example Fund",
          "current_value": 30000,
          "total_cost": 32000,
          "shares": 12345.67,
          "target_weight": 0.12,
          "tags": ["healthcare", "active"]
        }
      ]
    },
    "fund_profiles": {
      "110011": {
        "fund_code": "110011",
        "name": "Example Fund",
        "fund_type": "active",
        "manager": "Manager",
        "benchmark": "Benchmark"
      }
    },
    "nav_history": {
      "110011": [
        {"date": "2025-06-01", "nav": 1.0},
        {"date": "2026-06-01", "nav": 1.2}
      ]
    },
    "holdings": {
      "110011": [
        {"name": "A", "weight": 0.08, "industry": "pharma", "region": "CN"}
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
  },
  "kg_context": {},
  "required_mcp_capabilities": []
}
```

## Example SkillOutput

```json
{
  "step_id": "fund-analysis-1",
  "skill_name": "fund_analysis",
  "evidence_items": ["HardEvidence"],
  "artifacts": {
    "fund_analysis_report": {},
    "portfolio_summary": {},
    "risk_flags": [],
    "suggested_rebalance_plan": {}
  },
  "warnings": [],
  "errors": [],
  "used_mcp_capabilities": [],
  "status": "OK"
}
```

## Personal Portfolio Mode

When the payload includes expanded personal portfolio data, `fund_analysis` runs
in full portfolio mode. The expanded payload shape accepts:

- `transactions` — list of `FundTransaction` objects (buy, sell, dividend, fee, transfer)
- `dca_plans` — recurring DCA (dollar-cost averaging) subscriptions per fund
- `cost_basis` — per-position `PositionCostBasis` with weighted-average cost
- `market_scenario` — optional stress/sensitivity scenarios (e.g. ±10% NAV shock)
- `risk_profile` / `constraints` — user risk preferences and rebalance limits

New artifacts produced in personal portfolio mode:

| Artifact | Source | Description |
|---|---|---|
| `portfolio_summary` | analysis tools | Position weights, PnL by fund, total PnL, concentration |
| `cost_basis_summary` | transaction tools | Weighted-average cost per position, unrealized PnL |
| `trade_budget` | analysis tools | Max trade amount, short-term budget remaining |
| `dca_review` | analysis tools | DCA plan health, recent discipline flags |
| `trade_plan` | rank_trade_plan | Ranked multi-leg trade proposals with rationale |
| `risk_flags` | detection | Concentration, drawdown, discipline, liquidity flags |
| `fund_analysis_report` | aggregator | Composite report merging all above artifacts |

Compatibility fallback: payloads with only `related_entities` still produce
baseline HardEvidence and include a warning that structured portfolio analysis
was not possible.
