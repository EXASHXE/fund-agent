# Personal Portfolio Regression Fixtures

Synthetic zh-CN personal mutual-fund scenarios for deterministic advisory
quality regression. These fixtures do not contain private user data, live market
data, provider output, broker execution data, or LLM-generated reports.

| scenario_id | theme | user question | report-only/formal | key risk | expected decision |
| ----------- | ----- | ------------- | ------------------ | -------- | ----------------- |
| `semiconductor_profit_recovery_after_rally_zh` | Semiconductor profit protection | 半导体前面已经盈利很多，最近反弹又涨了，我要不要减仓把本金拿回来？ | Formal | Profit protection and evidence conflict | BLOCKED formal reduce, partial-trim framing |
| `semiconductor_chase_after_two_day_rebound_zh` | Semiconductor rebound chase | 半导体大跌后连续两天上涨，今天预计还会涨3%-4%，我前面已经卖了一部分，现在要不要追回？ | Report-only | Emotional chase after rebound | NO_FORMAL_DECISION |
| `innovation_drug_7day_drawdown_after_event_zh` | Innovation drug event drawdown | 创新药7天跌了10%，ASCO利好不涨反跌，现在怎么办，要不要补仓？ | Report-only | Event hype failure and weak right-side confirmation | NO_FORMAL_DECISION |
| `short_holding_7day_fee_sell_zh` | Short-holding fee sell | 这只基金还没满7天，但我想今天卖出，可以吗？ | Formal | 7-day redemption fee blocker | BLOCKED sell |
| `qdii_ai_overlap_vs_sp500_zh` | QDII/AI vs S&P 500 overlap | 我已经有两只华宝QDII/AI基金了，再买标普500是不是重合度很高，收益会不会不明显？ | Report-only | Holdings overlap and marginal diversification | NO_FORMAL_DECISION |
| `cash_bond_allocation_where_to_deploy_zh` | Cash/bond deployment | 现在现金和债券仓位比较高，AI涨太多不好追，其他都在跌，资金到底该投去哪？ | Report-only | Reserve vs deployable cash | NO_FORMAL_DECISION |
| `bond_fund_low_yield_vs_cash_zh` | Short bond low one-day yield | 我买的短债收益太低，12000一天才0.21，还不如余额宝，要不要换？ | Report-only | Overreacting to one-day income | NO_FORMAL_DECISION |
| `oil_gas_loss_position_rebalance_zh` | Oil/gas loss review | 油气基金亏了快12%，要不要清仓或者调仓？ | Formal | Loss-driven full exit and missing transaction evidence | BLOCKED sell |
| `battery_profit_evaporating_stop_or_hold_zh` | Battery profit evaporation | 电池基金的收益快跌没了，要不要清仓？ | Formal | Profit giveback and evidence conflict | BLOCKED sell |
| `dividend_low_vol_entry_after_rally_zh` | Dividend low-vol entry | 红利低波这两天涨了不少，现在买是不是追高？ | Report-only | Defensive-style chase risk | NO_FORMAL_DECISION |
| `short_term_tactical_budget_limit_zh` | Tactical budget discipline | 我想拿10%以内资金做短线热点打枪，消费电子最多5%，怎么控制？ | Report-only | 10% tactical / 5% theme cap | NO_FORMAL_DECISION |
| `mixed_portfolio_report_only_zh` | Whole portfolio report | 帮我整体看一下现在基金组合，哪些风险最大，下一步重点看什么？ | Report-only | Concentration, overlap, loss contributors, cash buffer | NO_FORMAL_DECISION |
