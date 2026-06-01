# Decision Support Examples

## Active Trade With Valid Anchors

```json
{
  "skill_name": "decision_support",
  "payload": {
    "evidence_graph": {
      "items": {
        "ev:portfolio_risk_flags": {"evidence_id": "ev:portfolio_risk_flags"}
      },
      "edges": []
    },
    "trade_plan": {
      "suggested_trade_plan": [
        {
          "trade_id": "110011_REDUCE_0",
          "fund_code": "110011",
          "action": "REDUCE",
          "requested_amount": 5000,
          "evidence_refs": ["ev:portfolio_risk_flags"]
        }
      ]
    },
    "portfolio_context": {"total_value": 200000, "cash_available": 20000},
    "risk_profile": {"max_trade_pct": 0.1},
    "constraints": {"min_trade_amount": 100}
  }
}
```

## Downgrade Missing Anchors

When `evidence_refs` are absent or do not resolve in the graph, the runtime
should return HOLD or WAIT:

```json
{
  "action": "HOLD",
  "execution_amount": 0,
  "rationale_anchor": [],
  "audit_trail": [
    "Insufficient evidence: evidence_refs and risk_flags_refs contained no valid evidence IDs"
  ]
}
```
