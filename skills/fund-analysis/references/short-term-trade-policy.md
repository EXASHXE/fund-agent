# Short-Term Trade Budget Policy

Short-term theme trades are constrained by
`risk_profile.short_term_trade_budget_pct`.

## Policy

- Calculate the budget from total portfolio value and the host-provided
  percentage.
- Count recent short-term buys and sells when transactions are provided.
- Cap suggested short-term trade amounts to the remaining budget.
- Warn when the budget is exhausted or missing.
- Do not create a formal active trade decision from this skill.

## Host Report Language

```text
短期交易预算：本组合短期主题交易预算为总资产的 10%。在预算不足时，不应继续加仓短期主题基金；如用户仍要求执行，应进入 decision_support 做正式决策和金额校验。
```
