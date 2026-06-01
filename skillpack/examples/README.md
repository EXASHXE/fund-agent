# Skillpack Examples

These files are host-facing examples for external coding agents. They
demonstrate the expected `SkillInput` and `SkillOutput` shapes for each
runtime skill.

## Example Files

| File | Purpose |
|---|---|
| `fund_analysis_input.json` | Portfolio review input for `FundAnalysisSkill` |
| `news_research_input.json` | Input for `NewsResearchSkill` (includes mock MCP payload) |
| `sentiment_analysis_input.json` | Input for `SentimentAnalysisSkill` |
| `decision_support_input.json` | Input for `DecisionSupportSkill` (includes evidence_graph) |
| `decision_support_output.json` | Expected output from `DecisionSupportSkill` |
| `host_minimal_news_to_decision.json` | Orchestration flow: news → evidence → decision |

## How To Use Each Example

1. Load the JSON file.
2. Construct a `SkillInput` from the data.
3. Call the corresponding runtime skill with `skill.run(skill_input)`.
4. Collect `SkillOutput.evidence_items` and `artifacts`.
5. For the full flow, compile evidence with `compile_evidence_graph` and
   then call `DecisionSupportSkill`.

## Constraints

- Examples do NOT require real network access.
- Examples do NOT require ResearchOS (`src.core.research_os`).
- Examples use `InMemoryMCPHostAdapter` or mock payload for MCP data.

## Reference

See `examples/minimal_host_news_to_decision.py` and
`examples/minimal_host_portfolio_review.py` for working Python demos.
