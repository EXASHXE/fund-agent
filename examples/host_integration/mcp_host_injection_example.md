# MCP Host Injection Example

This document explains how an external host injects MCP provider
responses into fund-agent payload fields.

## External host owns MCP providers

The host is responsible for:

- Configuring MCP provider credentials and endpoints
- Making MCP API calls (financial_news, web_search, social_sentiment,
  benchmark_price_history, fund_metadata_lookup, fund_fee_schedule)
- Converting MCP responses into fund-agent payload fields
- Handling rate limits, retries, and error recovery

## Host converts MCP responses into payload fields

The host normalizes raw MCP responses into the payload fields that
fund-agent consumes:

| MCP capability | Normalization | Payload field |
|---|---|---|
| `financial_news` | Extract headline, date, sentiment, entities | `news_evidence` |
| `web_search` | Extract title, snippet, date | `news_evidence` |
| `social_sentiment` | Extract fund_code, sentiment, score | `sentiment_evidence` |
| `benchmark_price_history` | Pass through as NAV-style series | `benchmark_history` |
| `fund_metadata_lookup` | Pass through as fund metadata dict | `fund_profiles` |
| `fund_fee_schedule` | Pass through as fee schedule dict | `fee_schedules` |
| (host-provided) | Host assembles from internal data | `redemption_rules` |

## fund-agent core runtime consumes these fields

fund-agent core runtime consumes these payload fields; it does not
fetch them. The runtime boundary is:

- `news_research` skill calls `mcp_adapter.call("financial_news", ...)` —
  the adapter implementation is host-injected
- `sentiment_analysis` skill calls `mcp_adapter.call("social_sentiment", ...)` —
  the adapter implementation is host-injected
- `fund_analysis` skill reads `news_evidence` and `sentiment_evidence`
  from the payload dict — no MCP calls inside the skill

## Dev-only normalization helpers

For dev/test normalization of fake MCP responses, see:

```
tools/dev/mcp_harness/normalize_mcp_responses.py
```

This module provides helpers like `normalize_news_evidence()`,
`normalize_sentiment_evidence()`, `normalize_benchmark_history()`, and
`normalize_all()`. It uses fake responses from
`tools/dev/mcp_harness/fake_mcp_responses.json`.

**Core runtime must not import this module.** It is dev-only.

## Example: host injects MCP responses

```python
# Host-side code (not part of fund-agent)
from src.schemas.skill import SkillInput
from src.skills_runtime.fund_analysis import FundAnalysisSkill

# Host fetches MCP data
news_data = mcp_client.call("financial_news", query="fund:110011")
sentiment_data = mcp_client.call("social_sentiment", fund_code="110011")

# Host normalizes into payload fields
payload = {
    "portfolio": {...},
    "fund_profiles": {...},
    "nav_history": {...},
    "news_evidence": normalize_news_evidence(news_data),
    "sentiment_evidence": normalize_sentiment_evidence(sentiment_data),
}

# Host calls fund_analysis
output = FundAnalysisSkill().run(
    SkillInput(
        task_id="host-task-1",
        step_id="fund-analysis-1",
        skill_name="fund_analysis",
        payload=payload,
    )
)
```

## What NOT to do

- Do not import provider SDKs inside `src/skills_runtime/` or
  `src/tools/`.
- Do not make network calls outside `MCPHostAdapter`.
- Do not hardcode API keys or credentials in fund-agent code.
- Do not treat `suggested_rebalance_plan` as a trade execution order.
