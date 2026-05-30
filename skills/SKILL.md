# fund-agent Skill Pack

This directory contains host-readable financial research skills. External
agents should start from `skillpack/fund-agent.skillpack.yaml`, then use these
skill documents as instructions/reference material and `src/skills_runtime` for
callable Python handlers.

## Skills

- `fund_analysis/`: local fund and quant analysis guidance
- `news_research/`: host MCP news/search research guidance
- `sentiment_analysis/`: host MCP sentiment research guidance
- `thesis_generation/`: thesis draft guidance

Formal `Decision` and `ExecutionLedger` generation is handled by
`src.skills_runtime.decision_support.DecisionSupportSkill`.
