# Execution Amount Policy

`decision_support` validates active trade amounts against host-provided
portfolio and risk context.

## Caps

Execution amount may be capped by:

- `portfolio_context.cash_available` for buys;
- current position value for sells or reductions;
- `risk_profile.max_trade_pct`;
- `risk_profile.short_term_trade_budget_pct` for short-term trades;
- `constraints.max_buy_amount`;
- `constraints.max_sell_amount`;
- `constraints.min_trade_amount`;
- `payload.target_trade_amount`;
- trade `requested_amount`;
- `constraints.forbidden_actions`.

## Downgrade Rule

If a safe positive execution amount cannot be derived for an active action,
return WAIT or HOLD with an audit note instead of inventing an amount.

## Reporting

Hosts should surface capped amounts and cap reasons in the final report.
