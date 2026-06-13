# Report-Only Prompt Example

## User Request

"帮我分析一下基金组合，看看风险如何"

## Host Responsibilities

1. Load portfolio data from user input
2. Optionally collect provider data snapshot
3. Run fund_analysis skill

## fund-agent Command

```bash
fund-agent analyze-portfolio --input portfolio.json --format markdown --output report.md
```

## Expected Output

- Structured analysis report
- No formal trade decision
- No broker execution instructions

## Safety Boundary

- Do not call decision_support
- Do not generate trade instructions
- Missing data must be disclosed
