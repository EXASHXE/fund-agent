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

Use `news_research` to request host-provided news or web search data through
`MCPHostAdapter` and convert structured host results into `SoftEvidence`.

## When to use

- The host needs recent or historical news evidence related to funds,
  holdings, themes, managers, or macro topics.
- The host has an MCP adapter with `financial_news` or `web_search`.
- A later `EvidenceGraph` or `decision_support` step needs news-backed
  `SoftEvidence`.

## When not to use

- Do not use it for deterministic NAV, PnL, or portfolio math.
- Do not use it for social sentiment-only signals.
- Do not use it to produce formal `Decision` or `ExecutionLedger` artifacts.
- Do not use it without a host-injected MCP adapter.

## Host responsibilities

The host owns query formulation, provider selection, credentials, network
access, rate limits, source filtering, retry policy, and final report UX. The
host supplies `MCPHostAdapter`; the skill may only call `mcp_adapter.call(...)`.

## MCP capabilities required

- `financial_news`
- `web_search`

At least one compatible capability must be available through the host adapter.

## Inputs

Runtime skill ID: `news_research`.
Runtime: `src.skills_runtime.news_research:NewsResearchSkill`.

Expected payload fields include:

- `query`
- `related_entities`
- `fund_codes`
- `holdings`
- host-defined search filters

## Outputs

- `SoftEvidence` items
- `artifacts.mcp_response`
- `used_mcp_capabilities`
- `warnings`
- `errors`

## Missing-data policy

If no compatible MCP capability exists, return `MISSING_MCP_CAPABILITY`. If the
MCP call fails, return `MCP_CALL_FAILED`. If the call succeeds but yields no
usable items, return `EMPTY_RESULT` or `PARTIAL` with errors. Do not invent
news items or timestamps.

## Forbidden behavior

This skill must never make direct network calls, import provider SDKs, hardcode
API keys, call LLMs, produce formal `Decision` or `ExecutionLedger`, or bypass
`MCPHostAdapter`.

## How it composes with other skills

Use `news_research` before `compile_evidence_graph` when news should influence
a thesis or decision. Combine with `sentiment_analysis` for softer market
signals, with `fund_analysis` for deterministic portfolio facts, and with
`decision_support` only after evidence is compiled.

## Minimal example

```json
{
  "task_id": "task-1",
  "step_id": "news-1",
  "skill_name": "news_research",
  "payload": {"query": "fund:110011", "related_entities": ["fund:110011"]},
  "required_mcp_capabilities": ["financial_news"]
}
```

See `references/source-quality-policy.md` and `references/mcp-boundary.md`.
