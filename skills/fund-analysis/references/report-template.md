# Fund Analysis Report Template

Hosts may adapt this template to their final UX. Keep claims tied to artifacts,
warnings, or evidence IDs.

## 1. Executive summary

Summarize the portfolio state, main risk flags, whether the analysis is full or
partial, and whether formal decisions were requested.

Chinese example:

```text
本次分析基于你提供的持仓、净值、交易和风险约束。组合目前主要风险是单只基金占比偏高、权益主题集中度偏高，以及现金缓冲需要在买入前优先确认。本报告仅为组合分析；如需正式买卖决策，需要进入 decision_support。
```

## 2. Portfolio overview

Include total value, cash available, cash ratio, position count, and as-of date.

## 3. Position table

Show fund code, name, current value, weight, cost, PnL, target weight, and tags.

## 4. Cost and PnL summary

Explain total cost, current value, unrealized PnL, and position-level PnL.
Avoid automatic sell language for losses and automatic chase language for gains.

## 5. Fund type allocation

Summarize equity, bond, mixed, QDII, cash, or other fund type exposure.

## 6. Theme exposure

Show theme, region, and style exposures when available.

## 7. Industry exposure

Show industry concentration from holdings when supplied.

## 8. Cash ratio

State whether cash reserve is enough before any buy suggestion.

## 9. Fund metrics

Use host-provided NAV history to summarize return, volatility, drawdown,
momentum, Sharpe, Sortino, and risk-adjusted score when available.

## 10. Risk flags

List concentration, theme, industry, liquidity, drawdown, trading discipline,
DCA, and host-provided market scenario flags.

Chinese example:

```text
风险提示：110011 单只基金权重超过风险约束；权益类基金整体占比偏高；如果继续加仓，应先确认现金缓冲和短期交易预算。
```

## 11. DCA review

State whether each DCA plan should continue, pause, or be reviewed, and why.
Tie the explanation to long-term thesis, cashflow, concentration, and drawdown.

## 12. Short-term budget review

Show `short_term_trade_budget`, used amount, remaining amount, and whether the
budget is exceeded.

## 13. Suggested rebalance plan

Present as analysis unless `decision_support` has produced formal decisions.
Include capped amount and cap reasons.

## 14. WAIT/HOLD/BUY/SELL explanation

Use formal action words only when they come from `decision_support`. If the
host is writing an analysis-only report, phrase as:

```text
暂不形成正式买卖结论。当前更适合先观察/补充数据，因为...
```

For formal WAIT/HOLD, include why not buy, why not sell, missing evidence,
trigger to change, and invalidating conditions.

## 15. Data gaps and warnings

List missing profiles, NAV history, holdings, transactions, DCA plans, market
scenario, or reconciliation mismatches.

## 16. Evidence appendix

Include artifact names and evidence IDs, for example:

```text
证据附录：
- ev:portfolio_allocation_concentration
- ev:fund_risk_return_metrics
- ev:portfolio_risk_flags
```
