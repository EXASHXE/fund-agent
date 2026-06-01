# fund-agent Skill Pack

This directory contains host-readable financial research skills. `fund-agent`
is Markdown-first at the skill layer: `SKILL.md` files define agent-facing
workflow, policy, constraints, and report style, while `src/` remains the
deterministic runtime, schema, and tool layer.

External agents should start from `skillpack/fund-agent.skillpack.yaml`, then
read `skills/README.md` and the relevant `skills/<slug>/SKILL.md` file for
usage policy. Do not infer callable runtime skill IDs from folder names.

## Skills (Superpowers-compatible collection)

- **Primary / default:** `fund-analysis` (runtime ID `fund_analysis`).
  Start here for ordinary portfolio and fund report requests.
- **Supporting:** `decision-support`, `news-research`, `sentiment-analysis`,
  `thesis-generation` (runtime IDs `decision_support`, `news_research`,
  `sentiment_analysis`, `thesis_generation`).

Formal `Decision` and `ExecutionLedger` generation is handled by
`src.skills_runtime.decision_support.DecisionSupportSkill`, and only by
that skill. No other skill may produce a formal `Decision`.

The legacy `fund-analyst` persona material is archived under
`docs/archive/fund-analyst/`; it is not installed, not discovered, and
not a runtime entrypoint.
