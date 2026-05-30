---
id: news_research
name: news-research
runtime: src.skills_runtime.news_research:NewsResearchSkill
input_schema: src.schemas.skill:SkillInput
output_schema: src.schemas.skill:SkillOutput
required_mcp_capabilities:
  - web_search
  - financial_news
produced_evidence_type: SoftEvidence
---

# News Research

## Purpose

Request host-provided news/search capability through `MCPHostAdapter` and
convert structured host results into `SoftEvidence`.

## Contract

- `id`: `news_research`
- `runtime`: `src.skills_runtime.news_research:NewsResearchSkill`
- `input_schema`: `src.schemas.skill:SkillInput`
- `output_schema`: `src.schemas.skill:SkillOutput`
- `required_mcp_capabilities`: `web_search`, `financial_news`
- `produced_evidence_type`: `SoftEvidence`
- `forbidden_behavior`: provider SDK imports, direct HTTP/network requests,
  hardcoded API keys, formal decision generation

The skill may call only `mcp_adapter.call(...)`. Provider implementation is
owned by the external host.

## Example SkillInput

```json
{
  "task_id": "task-1",
  "step_id": "news-1",
  "skill_name": "news_research",
  "payload": {"query": "fund:110011", "related_entities": ["fund:110011"]},
  "required_mcp_capabilities": ["financial_news"]
}
```

## Example SkillOutput

```json
{
  "step_id": "news-1",
  "skill_name": "news_research",
  "evidence_items": ["SoftEvidence"],
  "artifacts": {"mcp_response": {}},
  "warnings": [],
  "errors": [],
  "used_mcp_capabilities": ["financial_news"],
  "status": "OK"
}
```
