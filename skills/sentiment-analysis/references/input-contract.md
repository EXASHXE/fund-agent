# Sentiment Analysis Input Contract

## Required fields

- `related_entities` (list[str]): Fund codes, themes, or market identifiers for sentiment analysis
- OR `fund_codes` (list[str]) in `kg_context`: Alternative entity specification

## Optional fields

- `time_range` (str): Time range for sentiment analysis (e.g., "7d", "30d")
- `sources` (list[str]): Social platforms to analyze (e.g., ["reddit", "twitter"])

## MCP requirements

- `social_sentiment` capability: Social media sentiment data

This capability must be available for the skill to produce results.

## Output

Produces `SoftEvidence` items with sentiment scores, confidence levels, and source attribution.
