---
id: sentiment_analysis
name: sentiment-analysis
runtime: src.skills_runtime.sentiment_analysis:SentimentAnalysisSkill
input_schema: src.schemas.skill:SkillInput
output_schema: src.schemas.skill:SkillOutput
required_mcp_capabilities:
  - social_sentiment
produced_evidence_type: SoftEvidence
role: supporting
---

# Sentiment Analysis (supporting skill)

`sentiment-analysis` is a **supporting skill** in the
`fund-agent` Superpowers-compatible skill collection. It should be
loaded only when the user wants sentiment-backed `SoftEvidence`, and
only when the host has an MCP provider wired for `social_sentiment`.
For ordinary portfolio and fund report requests, start with the
primary skill `fund-analysis` and stop there.

`sentiment-analysis` itself maps to the Python runtime ID
`sentiment_analysis` declared in
`skillpack/fund-agent.skillpack.yaml`. The agent-facing skill name is
the hyphenated slug `sentiment-analysis`; the underscore
`sentiment_analysis` is the runtime ID only.

The host owns the sentiment MCP provider, network access, and any
API credentials. This skill **must not** make direct network calls,
import provider SDKs, or treat sentiment as deterministic evidence.
It produces soft evidence only — **no formal `Decision` or
`ExecutionLedger`**.

## Purpose

Use `sentiment_analysis` to request host-provided social or market sentiment
signals through `MCPHostAdapter` and convert structured signals into
`SoftEvidence`.

## When to use

- The host has a `social_sentiment` MCP capability.
- The user asks about market mood, social chatter, or crowd risk.
- Sentiment should supplement HardEvidence and news evidence.

**`sentiment-analysis` is not required for ordinary `fund-analysis`
flows.** Load it only when sentiment context is needed.

## When not to use

- Do not use it for deterministic fund metrics or portfolio math.
- Do not use it as a substitute for holdings, NAV, or transaction data.
- Do not use it to make formal trade decisions.
- Do not use it without host-owned MCP capability.
- Do not use it as the only input to a formal `Decision`. Combine it
  with `HardEvidence` from `fund-analysis` and any `SoftEvidence`
  from `news-research` first.

## Host responsibilities

The host owns provider selection, credentials, network access, query scope,
entity mapping, bot/spam filtering, retry policy, and final UX. The skill only
uses the host-injected `MCPHostAdapter`.

## MCP capabilities required

- `social_sentiment`

## Inputs

Runtime skill ID: `sentiment_analysis`.
Runtime: `src.skills_runtime.sentiment_analysis:SentimentAnalysisSkill`.

Expected payload fields include:

- `related_entities`
- `query`
- `fund_codes`
- host-defined sentiment filters

## Outputs

- `SoftEvidence` items
- `artifacts.mcp_response`
- `used_mcp_capabilities`
- `warnings`
- `errors`

## Missing-data policy

If `social_sentiment` is unavailable, return `MISSING_MCP_CAPABILITY`. If the
adapter call fails, return `MCP_CALL_FAILED`. If signals are absent or too weak,
return `PARTIAL` or `EMPTY_RESULT`; do not invent sentiment.

## Forbidden behavior

This skill must never make direct network calls, import provider SDKs, hardcode
API keys, call LLMs, produce formal `Decision` or `ExecutionLedger`, or treat
sentiment as deterministic evidence.

## How it composes with other skills

Use sentiment as a soft overlay after `fund_analysis` has established portfolio
facts. Combine with `news_research` for source context and compile both into an
`EvidenceGraph` before `decision_support`.

## Minimal example

```json
{
  "task_id": "task-1",
  "step_id": "sentiment-1",
  "skill_name": "sentiment_analysis",
  "payload": {"related_entities": ["fund:110011"]},
  "required_mcp_capabilities": ["social_sentiment"]
}
```

See `references/signal-quality-policy.md`.
