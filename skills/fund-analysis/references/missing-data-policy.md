# Fund Analysis Missing Data Policy

`fund_analysis` should degrade explicitly instead of inventing data.

## Proceed With PARTIAL Analysis

Proceed when portfolio positions exist but one or more optional datasets are
missing:

- `fund_profiles`
- `nav_history`
- `holdings`
- `transactions`
- `dca_plans`
- `market_scenario`

The output should include `warnings` naming the missing dataset and affected
fund codes when possible.

## Stop With INVALID_INPUT

Return `INVALID_INPUT` when:

- `payload` is not a dictionary;
- `payload.portfolio` is missing and no compatibility `related_entities` exist;
- `payload.portfolio.positions` is missing or empty;
- positions do not include usable `fund_code` values.

## Compatibility Fallback

If only `related_entities` is provided, emit baseline HardEvidence and warn
that structured portfolio analysis was not possible.

## Host Report Language

Use direct uncertainty language:

```text
由于缺少 110011 的持仓明细，本报告无法判断其行业集中度；相关风险结论仅基于组合权重和已提供净值。
```
