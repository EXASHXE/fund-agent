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

Produce local quantitative fund evidence such as risk baseline, exposure
summary, and simple metric artifacts.

## Contract

- `id`: `fund_analysis`
- `runtime`: `src.skills_runtime.fund_analysis:FundAnalysisSkill`
- `input_schema`: `src.schemas.skill:SkillInput`
- `output_schema`: `src.schemas.skill:SkillOutput`
- `required_mcp_capabilities`: `[]`
- `produced_evidence_type`: `HardEvidence`
- `forbidden_behavior`: network requests, LLM calls, provider SDK imports,
  formal decision generation

## Example SkillInput

```json
{
  "task_id": "task-1",
  "step_id": "fund-analysis-1",
  "skill_name": "fund_analysis",
  "payload": {"related_entities": ["fund:110011"]},
  "kg_context": {"fund_codes": ["110011"]},
  "required_mcp_capabilities": []
}
```

## Example SkillOutput

```json
{
  "step_id": "fund-analysis-1",
  "skill_name": "fund_analysis",
  "evidence_items": ["HardEvidence"],
  "artifacts": {},
  "warnings": [],
  "errors": [],
  "used_mcp_capabilities": [],
  "status": "OK"
}
```
