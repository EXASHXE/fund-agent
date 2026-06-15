# News Research Input Contract

## Required fields

- `related_entities` (list[str]): Fund codes, themes, or market identifiers to research
- OR `fund_codes` (list[str]) in `kg_context`: Alternative entity specification

## Optional fields

- `time_range` (str): Time range for news search (e.g., "7d", "30d")
- `query` (str): Free-text search query
- `categories` (list[str]): News categories to filter

## MCP requirements

- `web_search` capability: General web search
- `financial_news` capability: Structured financial news feeds

At least one of these capabilities must be available.

## Output

Produces `SoftEvidence` items with news headlines, summaries, timestamps, and source attribution.
