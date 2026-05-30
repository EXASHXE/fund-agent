---
id: decision_support
name: decision-support
runtime: src.skills_runtime.decision_support:DecisionSupportSkill
input_schema: src.schemas.skill:SkillInput
output_schema: src.schemas.skill:SkillOutput
required_mcp_capabilities: []
consumes:
  - EvidenceGraph
produces:
  - Decision
  - ExecutionLedger
---

# Decision Support

## Purpose

Consume a compiled `EvidenceGraph` and produce contract-enforced `Decision` and
`ExecutionLedger` artifacts for the external host.

## Contract

- `id`: `decision_support`
- `runtime`: `src.skills_runtime.decision_support:DecisionSupportSkill`
- `input_schema`: `src.schemas.skill:SkillInput`
- `output_schema`: `src.schemas.skill:SkillOutput`
- `required_mcp_capabilities`: `[]`
- `consumes`: `EvidenceGraph`
- `produces`: `Decision`, `ExecutionLedger`
- `forbidden_behavior`: provider SDK imports, direct network requests, LLM calls,
  fake evidence anchors

This is the only skill allowed to generate formal `Decision` and
`ExecutionLedger` artifacts. Active actions must anchor to real EvidenceGraph
`evidence_id` values. WAIT/HOLD may have empty anchors only when insufficient
evidence is recorded in audit text.

## Example SkillInput

```json
{
  "task_id": "task-1",
  "step_id": "decision-1",
  "skill_name": "decision_support",
  "payload": {
    "evidence_graph": {"items": {}, "edges": []},
    "objective": "review fund",
    "risk_budget": {},
    "portfolio_context": {},
    "time_horizon": "1 year"
  },
  "required_mcp_capabilities": []
}
```

## Example SkillOutput

```json
{
  "step_id": "decision-1",
  "skill_name": "decision_support",
  "evidence_items": [],
  "artifacts": {
    "decision": {},
    "execution_ledger": {},
    "decision_status": "WAIT",
    "audit_trail": ["Insufficient evidence"]
  },
  "warnings": [],
  "errors": [],
  "used_mcp_capabilities": [],
  "status": "OK"
}
```
