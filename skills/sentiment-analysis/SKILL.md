---
id: sentiment_analysis
name: sentiment-analysis
runtime: src.skills_runtime.sentiment_analysis:SentimentAnalysisSkill
input_schema: src.schemas.skill:SkillInput
output_schema: src.schemas.skill:SkillOutput
required_mcp_capabilities:
  - social_sentiment
produced_evidence_type: SoftEvidence
---

# Sentiment Analysis

## Purpose

Request host-provided sentiment capability through `MCPHostAdapter` and convert
structured sentiment signals into `SoftEvidence`.

## Contract

- `id`: `sentiment_analysis`
- `runtime`: `src.skills_runtime.sentiment_analysis:SentimentAnalysisSkill`
- `input_schema`: `src.schemas.skill:SkillInput`
- `output_schema`: `src.schemas.skill:SkillOutput`
- `required_mcp_capabilities`: `social_sentiment`
- `produced_evidence_type`: `SoftEvidence`
- `forbidden_behavior`: provider SDK imports, direct HTTP/network requests,
  hardcoded API keys, formal decision generation

## Example SkillInput

```json
{
  "task_id": "task-1",
  "step_id": "sentiment-1",
  "skill_name": "sentiment_analysis",
  "payload": {"related_entities": ["fund:110011"]},
  "required_mcp_capabilities": ["social_sentiment"]
}
```

## Example SkillOutput

```json
{
  "step_id": "sentiment-1",
  "skill_name": "sentiment_analysis",
  "evidence_items": ["SoftEvidence"],
  "artifacts": {"mcp_response": {}},
  "warnings": [],
  "errors": [],
  "used_mcp_capabilities": ["social_sentiment"],
  "status": "OK"
}
```
