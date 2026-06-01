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

This legacy/reference-only umbrella skill is retained for historical persona
and prompt material only. It is not a runtime entrypoint. New host integrations
should load `skillpack/fund-agent.skillpack.yaml` and call the manifest skills:

- `fund_analysis`
- `news_research`
- `sentiment_analysis`
- `thesis_generation`
- `decision_support`

It is not a required plugin entrypoint and does not define a runtime class.
