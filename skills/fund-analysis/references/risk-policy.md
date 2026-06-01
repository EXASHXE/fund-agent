# Fund Analysis Risk Policy

Risk analysis starts at the portfolio level and then moves to individual fund
metrics. The goal is to identify structural risk, not to force an action.

## Principles

- Analyze portfolio structure before individual fund performance.
- Check cash reserve before any buy suggestion.
- Check single-fund, theme, and industry concentration before trade
  suggestions.
- Loss does not automatically mean sell.
- Profit does not automatically mean chase or reduce.
- Drawdown matters more when paired with concentration, weak thesis, or poor
  liquidity.
- WAIT/HOLD must be explained, not used as filler.

## Concentration

Flag concentration when a position or theme exceeds host-provided risk limits.
If holdings data is missing, say industry concentration could not be assessed.

## Cash and Liquidity

Before suggesting buys, compare `cash_available` with
`liquidity_reserve_pct`, `max_trade_pct`, short-term budget, and constraints.

## Scenario Risk

Only use host-provided `market_scenario`. Do not fetch or infer market regime.
If a scenario is high-risk, show how it affects concentration, liquidity, and
short-term trades.
