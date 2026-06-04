# Skill Input / Output Examples

This document provides JSON-like examples of `SkillInput` and `SkillOutput`
shapes for each runtime skill. External coding agents can use these as
reference when constructing skill calls.

Use `skillpack/fund-agent.skillpack.yaml` to discover runtime skill IDs. Use
hyphenated `skills/<slug>/SKILL.md` files for agent-facing policy. Do not infer
runtime IDs from folder names.

## SkillInput Base Shape

```json
{
  "task_id": "host-task-001",
  "step_id": "step-1",
  "skill_name": "fund_analysis",
  "payload": {},
  "required_mcp_capabilities": [],
  "kg_context": {},
  "evidence_context": [],
  "metadata": {}
}
```

## SkillOutput Base Shape

```json
{
  "step_id": "step-1",
  "skill_name": "fund_analysis",
  "status": "OK",
  "evidence_items": [],
  "artifacts": {},
  "warnings": [],
  "errors": [],
  "used_mcp_capabilities": []
}
```

## fund_analysis

**Input:**
```json
{
  "task_id": "host-task-001",
  "step_id": "fa-1",
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
  }
}
```

**Output:**
```json
{
  "step_id": "fa-1",
  "skill_name": "fund_analysis",
  "status": "OK",
  "evidence_items": [
    {
      "evidence_id": "abc-123",
      "confidence_weight": 1.0,
      "source_type": "portfolio_allocation_concentration",
      "direction": "positive",
      "related_entities": ["fund:110011"]
    }
  ],
  "artifacts": {
    "fund_analysis_report": {
      "fund_metrics": {},
      "portfolio_metrics": {},
      "exposures": {},
      "concentration": {},
      "risk_flags": [],
      "suggested_watchlist": [],
      "warnings": [],
      "data_completeness": {"grade": "B", "score": 0.78},
      "analysis_coverage": {"portfolio": "available", "performance": "available"},
      "report_limitations": ["Benchmark comparison unavailable"]
    },
    "portfolio_summary": {},
    "risk_flags": [],
    "suggested_rebalance_plan": {},
    "report_sections": [
      {"id": "executive_summary", "title": "Executive summary", "status": "OK", "bullets": ["..."], "data_sources": ["portfolio_summary"], "limitations": []},
      {"id": "benchmark_and_peer", "title": "Benchmark and peer", "status": "MISSING", "bullets": [], "data_sources": [], "limitations": ["No benchmark or peer data provided"]}
    ],
    "report_outline": [
      {"id": "executive_summary", "title": "Executive summary", "status": "OK"},
      {"id": "benchmark_and_peer", "title": "Benchmark and peer", "status": "MISSING"}
    ],
    "report_quality_gate": {
      "grade": "B",
      "can_publish_professional_report": true,
      "reason": "Report meets professional quality bar with adequate data completeness grade B."
    },
    "data_completeness": {"grade": "B", "score": 0.78, "available_sections": ["Portfolio Snapshot", ...], "missing_sections": ["Benchmark History", ...]},
    "analysis_coverage": {"portfolio": "available", "benchmark": "missing", "peer": "missing", ...},
    "report_limitations": ["Benchmark comparison unavailable", "Peer ranking unavailable"]
  },
  "errors": []
}
```

`report_sections` are deterministic host-display sections produced by
`compose_personal_fund_report()` in `src/tools/portfolio/report_composer.py`.
Each section has `id`, `title`, `status` (OK/PARTIAL/MISSING), `bullets`,
`data_sources`, and `limitations`. Hosts may render via
`render_report_markdown()` or replace with their own UX renderer.

`report_quality_gate` tells whether the report meets professional quality
bar (`can_publish_professional_report`) based on `data_completeness` grade.
Grade C reports are publishable with prominent limitations; grade D requires
`minimal_report` mode.

`report_outline` mirrors the section `id`/`title`/`status` in order for
host table-of-contents rendering.

Missing optional data becomes `PARTIAL` or `MISSING` sections and
corresponding `data_completeness` / `analysis_coverage` entries.
No analysis is fabricated for missing data.

Formal `BUY`/`SELL`/`HOLD` actions require `decision_support`;
`FundAnalysisSkill` does not produce `Decision` or `ExecutionLedger`.

## news_research

**Input:**
```json
{
  "task_id": "host-task-001",
  "step_id": "news-1",
  "skill_name": "news_research",
  "required_mcp_capabilities": ["web_search", "financial_news"],
  "payload": {
    "related_entities": ["fund:110011"]
  }
}
```

**Output:**
```json
{
  "step_id": "news-1",
  "skill_name": "news_research",
  "status": "OK",
  "evidence_items": [
    {
      "evidence_id": "news-abc",
      "confidence_weight": 0.75,
      "source_type": "financial_news",
      "direction": "positive",
      "related_entities": ["fund:110011"]
    }
  ],
  "used_mcp_capabilities": ["financial_news"],
  "errors": []
}
```

## sentiment_analysis

**Input:**
```json
{
  "task_id": "host-task-001",
  "step_id": "sent-1",
  "skill_name": "sentiment_analysis",
  "required_mcp_capabilities": ["social_sentiment"],
  "payload": {
    "related_entities": ["fund:110011"]
  }
}
```

**Output:**
```json
{
  "step_id": "sent-1",
  "skill_name": "sentiment_analysis",
  "status": "OK",
  "evidence_items": [
    {
      "evidence_id": "sent-abc",
      "confidence_weight": 0.6,
      "source_type": "social_sentiment",
      "direction": "neutral",
      "related_entities": ["fund:110011"]
    }
  ],
  "used_mcp_capabilities": ["social_sentiment"],
  "errors": []
}
```

## thesis_generation

**Input:**
```json
{
  "task_id": "host-task-001",
  "step_id": "thesis-1",
  "skill_name": "thesis_generation",
  "payload": {
    "evidence_items": [],
    "objective": "review fund"
  }
}
```

**Output:**
```json
{
  "step_id": "thesis-1",
  "skill_name": "thesis_generation",
  "status": "OK",
  "artifacts": {
    "thesis_draft": {}
  },
  "evidence_items": [],
  "errors": []
}
```

Note: `thesis_generation` produces `ThesisDraft` artifacts only. It is
forbidden from producing formal `Decision` objects.

## decision_support

**Input:**
```json
{
  "task_id": "host-task-001",
  "step_id": "decision-1",
  "skill_name": "decision_support",
  "payload": {
    "evidence_graph": {},
    "objective": "review fund",
    "portfolio_context": {
      "total_value": 200000,
      "cash_available": 20000
    },
    "risk_profile": {"risk_level": "moderate", "max_trade_pct": 0.1},
    "constraints": {"max_buy_amount": 10000, "min_trade_amount": 100},
    "target_trade_amount": 8000,
    "time_horizon": "1 year"
  }
}
```

**Output:**
```json
{
  "step_id": "decision-1",
  "skill_name": "decision_support",
  "status": "OK",
  "artifacts": {
    "decision": {},
    "execution_ledger": {}
  },
  "evidence_items": [],
  "errors": []
}
```

**Only `decision_support` may produce formal `Decision` and
`ExecutionLedger` artifacts.**

## Error Output Example

```json
{
  "step_id": "news-1",
  "skill_name": "news_research",
  "status": "FAILED",
  "evidence_items": [],
  "errors": [
    {
      "code": "MISSING_MCP_CAPABILITY",
      "message": "NewsResearch requires financial_news or web_search",
      "details": {"skill_name": "news_research"},
      "recoverable": false
    }
  ]
}
```

## Warnings Example

```json
{
  "step_id": "news-1",
  "skill_name": "news_research",
  "status": "PARTIAL",
  "evidence_items": [],
  "warnings": ["NewsResearch requires financial_news or web_search"],
  "errors": [
    {
      "code": "MISSING_MCP_CAPABILITY",
      "message": "NewsResearch requires financial_news or web_search",
      "details": {"skill_name": "news_research"},
      "recoverable": false
    }
  ]
}
```
