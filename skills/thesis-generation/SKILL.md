---
id: thesis_generation
name: thesis-generation
runtime: src.skills_runtime.thesis_generation:ThesisGenerationSkill
input_schema: src.schemas.skill:SkillInput
output_schema: src.schemas.skill:SkillOutput
required_mcp_capabilities: []
produced_artifact: thesis_draft
forbidden_behavior:
  - formal_decision_generation
---

# Thesis Generation

## Purpose

Create a `thesis_draft` artifact from host-provided context and evidence IDs.
This skill does not produce formal investment decisions.

## Contract

- `id`: `thesis_generation`
- `runtime`: `src.skills_runtime.thesis_generation:ThesisGenerationSkill`
- `input_schema`: `src.schemas.skill:SkillInput`
- `output_schema`: `src.schemas.skill:SkillOutput`
- `required_mcp_capabilities`: `[]`
- `produced_artifact`: `thesis_draft`
- `forbidden_behavior`: `formal_decision_generation`, provider SDK imports,
  direct network requests

Formal `Decision` and `ExecutionLedger` artifacts must be produced by
`decision_support` only.

## Example SkillInput

```json
{
  "task_id": "task-1",
  "step_id": "thesis-1",
  "skill_name": "thesis_generation",
  "payload": {},
  "evidence_context": ["ev-1", "ev-2"],
  "required_mcp_capabilities": []
}
```

## Example SkillOutput

```json
{
  "step_id": "thesis-1",
  "skill_name": "thesis_generation",
  "evidence_items": [],
  "artifacts": {"thesis_draft": {"task_id": "task-1"}},
  "warnings": [],
  "errors": [],
  "used_mcp_capabilities": [],
  "status": "OK"
}
```
