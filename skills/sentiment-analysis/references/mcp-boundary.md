# Sentiment Analysis MCP Boundary

This skill requires a host-injected `social_sentiment` MCP capability.

## Required MCP capability

- `social_sentiment` — provides social media sentiment data for funds, themes, or markets

## Host responsibilities

The host must:
1. Implement the `social_sentiment` MCP capability
2. Inject the MCP adapter via `SkillInput.required_mcp_capabilities`
3. Own all API keys, credentials, and rate limiting

## Skill responsibilities

The skill:
1. Calls `mcp_adapter.call("social_sentiment", ...)` with structured query parameters
2. Converts raw MCP responses into `SoftEvidence` items
3. Never makes direct network requests or imports provider SDKs

## Data contract

Input: fund codes, themes, or market identifiers
Output: `SoftEvidence` items with sentiment scores, source timestamps, and related entities
