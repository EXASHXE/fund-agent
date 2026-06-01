# Fund Analysis Input Contract

This reference describes host-provided payloads for runtime skill ID
`fund_analysis`. The host owns data fetching and must pass JSON-serializable
data in `SkillInput.payload`.

## Minimal Structured Payload

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
        "current_value": 30000,
        "total_cost": 32000,
        "shares": 12345.67,
        "target_weight": 0.12,
        "tags": ["healthcare", "active"]
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

## Expanded Payload

```json
{
  "portfolio": {},
  "fund_profiles": {
    "110011": {
      "fund_code": "110011",
      "name": "Example Fund",
      "fund_type": "equity",
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
      {"name": "A", "weight": 0.08, "industry": "technology", "region": "CN"}
    ]
  },
  "transactions": [],
  "dca_plans": {},
  "market_scenario": {
    "name": "host_supplied_drawdown",
    "risk_level": "high",
    "description": "Host-provided scenario text"
  },
  "risk_profile": {},
  "constraints": {}
}
```

## Field Guidance

- `portfolio.positions[].target_weight` enables `suggested_rebalance_plan`.
- `transactions` enables transaction ledger, cost basis, reconciliation, and
  short-term budget usage.
- `dca_plans` enables DCA review.
- `holdings` improves theme, industry, and region exposure.
- `market_scenario` must be supplied by the host and must not be invented by
  `fund-agent`.

## Compatibility Fallback

Payloads with only `related_entities` can produce baseline HardEvidence for
legacy callers. Hosts should prefer structured portfolio payloads for reports.
