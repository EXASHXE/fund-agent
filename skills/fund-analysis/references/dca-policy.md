# DCA Review Policy

DCA review should evaluate whether recurring investment still fits the user's
portfolio, not whether the latest return is positive.

## Inputs

- `dca_plans`
- portfolio weights
- transaction history
- cashflow context when host-provided
- risk profile and concentration limits
- drawdown and NAV metrics when available

## Review Rules

- Continue DCA when concentration is acceptable, thesis remains intact, and
  cashflow supports the plan.
- Pause or reduce DCA when the fund is already overweight, the theme is
  overweight, or cash reserve is insufficient.
- Review DCA when drawdown is large but thesis and concentration data are
  incomplete.
- Do not pause DCA solely because a position is temporarily losing money.

## Report Language

```text
定投建议：110011 当前权重已超过单只基金限制，继续定投会放大集中度风险。建议先暂停或降低定投金额，并在补充长期持有理由后再评估。
```
