# fund-agent Skill Pack

This directory contains host-readable financial research skills. `fund-agent`
is Markdown-first at the skill layer: `SKILL.md` files define agent-facing
workflow, policy, constraints, and report style, while `src/` remains the
deterministic runtime, schema, and tool layer.

External agents should start from `skillpack/fund-agent.skillpack.yaml`, then
read `skills/README.md` and the relevant `skills/<slug>/SKILL.md` file for
usage policy. Do not infer callable runtime skill IDs from folder names.

## Skills

- `fund_analysis` runtime ID, `fund-analysis/` Markdown docs
- `news_research` runtime ID, `news-research/` Markdown docs
- `sentiment_analysis` runtime ID, `sentiment-analysis/` Markdown docs
- `thesis_generation` runtime ID, `thesis-generation/` Markdown docs
- `decision_support` runtime ID, `decision-support/` Markdown docs

Formal `Decision` and `ExecutionLedger` generation is handled by
`src.skills_runtime.decision_support.DecisionSupportSkill`.

`fund-analyst/` is legacy/reference-only persona material, not a runtime
entrypoint.
