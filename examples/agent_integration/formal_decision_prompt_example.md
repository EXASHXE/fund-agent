# Formal Decision Prompt Example

## User Request

"帮我正式决策一下，是否需要减仓华夏成长混合"

## Host Responsibilities

1. Load portfolio data with analysis_mode: formal_trade_decision
2. Collect provider data snapshot
3. Run fund_analysis skill
4. Build evidence graph
5. Run decision_support if evidence is sufficient

## fund-agent Command

```bash
fund-agent analyze-portfolio --input portfolio.json --format markdown --output report.md
```

## Expected Output

- Analysis report
- Formal Decision (if evidence sufficient)
- ExecutionLedger
- Evidence anchor explanation
- No broker execution

## Safety Boundary

- Never place or fulfill orders
- Active trades require evidence anchors
- Do not bypass quality gate
