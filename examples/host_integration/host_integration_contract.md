# Host Integration Contract

This document describes the contract between fund-agent and the
external host that integrates it.

## Inputs are host-owned

All data consumed by fund-agent skills is provided by the host. The
host is responsible for:

- Collecting portfolio positions, NAV history, fund profiles
- Fetching benchmark data, fee schedules, redemption rules
- Providing news, sentiment, and web search results via MCP
- Determining the user's risk profile and constraints

## fund-agent core runtime does not fetch data

The core runtime (`src/skills_runtime/`, `src/tools/`) does not make
network calls, does not hold API keys, and does not import provider
SDKs. All data flows in through `SkillInput.payload`.

## MCP/live provider integration is host-owned

The host injects MCP provider implementations through `MCPHostAdapter`.
The `news_research` and `sentiment_analysis` skills may call
`mcp_adapter.call(...)`, but the adapter implementation is entirely
host-controlled. No skill makes direct network requests.

For dev-only fake MCP responses, see
`tools/dev/mcp_harness/normalize_mcp_responses.py`.

## decision_support only produces formal decision artifacts

Only `decision_support` may emit formal `Decision` and
`ExecutionLedger` artifacts. `fund_analysis` produces evidence,
reports, and diagnostics but must never produce formal decisions.

Active decisions (`BUY`, `SELL`, `INCREASE`, `REDUCE`) require
evidence anchors referencing real evidence IDs in the EvidenceGraph.

## broker execution is outside fund-agent

fund-agent does not contain broker APIs, order placement, or trade
execution. The `suggested_rebalance_plan` artifact is a diagnostic,
not an execution instruction. The host must not treat it as a trade
order.

## Host payload fields from MCP responses

The host converts MCP provider responses into fund-agent payload
fields:

| MCP capability | Payload field | Description |
|---|---|---|
| `financial_news` | `news_evidence` | Normalized news items |
| `web_search` | `news_evidence` | Normalized web search results |
| `social_sentiment` | `sentiment_evidence` | Normalized sentiment scores |
| `benchmark_price_history` | `benchmark_history` | NAV-style benchmark series |
| `fund_metadata_lookup` | `fund_profiles` | Fund metadata dict |
| `fund_fee_schedule` | `fee_schedules` | Fee schedule dict |
| (host-provided) | `redemption_rules` | Redemption fee rules |

See `tools/dev/mcp_harness/normalize_mcp_responses.py` for the
normalization helpers used in dev/test.
