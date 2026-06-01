# Decision Contract Reference

This skill produces `Decision` and `ExecutionLedger` according to
`docs/contracts/decision-contract.v2.md`.

## Decision Fields

- `decision_id`
- `action`
- `execution_amount`
- `rationale_anchor`
- `trigger_conditions`
- `invalidating_conditions`
- `time_horizon`
- `risk_budget`
- `audit_trail`
- `version`
- `created_at`

## ExecutionLedger Fields

- `ledger_id`
- `version`
- `generated_at`
- `decisions`

## Contract Rules

- Only `decision_support` emits formal `Decision` or `ExecutionLedger`.
- Active decisions require real EvidenceGraph anchors.
- WAIT/HOLD may be used when evidence is insufficient, but must explain why.
- Outputs must be JSON-serializable.
