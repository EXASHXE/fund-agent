# Report-Only Flow

## When to use

User asks: "怎么看", "分析一下", "风险如何", "是否需要观察"

## Steps

1. Load portfolio input (from `fund_portfolio_input.json` or equivalent)
2. Run `fund_analysis` skill
3. Collect artifacts: `report_sections`, `report_outline`, `report_quality_gate`
4. Optionally render markdown via `render_advisory_report_markdown()`
5. Return report to user

## What NOT to do

- Do not call `decision_support`
- Do not emit `Decision` or `ExecutionLedger`
- Do not generate trade instructions
- Do not fabricate data for missing sections

## API

```python
from src.skills_runtime.fund_analysis import FundAnalysisSkill
from src.schemas.skill import SkillInput

skill = FundAnalysisSkill()
result = skill.run(SkillInput(skill_name="fund_analysis", payload={...}))
# result.artifacts contains report_sections, report_outline, quality_gate
```
