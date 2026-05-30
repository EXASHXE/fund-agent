---
id: fund_analyst_legacy
name: fund-analyst
runtime: none
input_schema: none
output_schema: none
required_mcp_capabilities: []
produced_artifact: legacy_reference
---

# fund-analyst Legacy Reference

This legacy umbrella skill is retained for reference material only. New host
integrations should load `skillpack/fund-agent.skillpack.yaml` and call the
manifest skills:

- `fund_analysis`
- `news_research`
- `sentiment_analysis`
- `thesis_generation`
- `decision_support`

It is not a required plugin entrypoint and does not define a runtime class.
