# Formal Decision Flow

## When to use

User asks: "今天卖出/买入/减仓/加仓多少", "正式决策", "给交易计划"

## Prerequisites

- Evidence graph must have sufficient evidence
- Active trades require evidence anchors
- `analysis_mode` must be `formal_trade_decision`

## Steps

1. Run `fund_analysis` skill first
2. Build evidence graph from artifacts
3. Run `decision_support` with evidence graph
4. Collect `Decision` and `ExecutionLedger`
5. Render markdown if requested
6. Return decision artifacts to user

## What NOT to do

- Do not place or fulfill orders
- Do not call broker APIs
- Do not fabricate evidence
- Do not bypass quality gate

## API

```python
from src.skills_runtime.decision_support import DecisionSupportSkill
from src.schemas.skill import SkillInput

skill = DecisionSupportSkill()
result = skill.run(SkillInput(task_id="t1", step_id="1", skill_name="decision_support", payload={...}))
# result.artifacts contains Decision, ExecutionLedger
```
