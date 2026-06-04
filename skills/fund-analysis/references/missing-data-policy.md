# Fund Analysis Missing Data Policy

`fund_analysis` should degrade explicitly instead of inventing data.

## Proceed With PARTIAL Analysis

Proceed when a usable portfolio snapshot exists but one or more required
analytical datasets are partial, or optional datasets are missing.

Required report data groups:

- portfolio snapshot or derived portfolio snapshot
- current value or `current_nav` sufficient to value positions
- `fund_profiles`
- `nav_history`
- `holdings`
- `risk_profile`
- `constraints`

Optional report data groups:

- `benchmark_history`
- `peer_group`
- `factor_exposures`
- `manager_profiles`
- `fee_schedules`
- `redemption_rules`
- `fund_flow`
- `macro_events`
- `user_investment_plan`

The output should include `warnings` naming the missing dataset and affected
fund codes when possible.

The skill computes a formal `data_completeness` score (0.0-1.0) and grade
(A-D) via `calculate_data_completeness()`. Grades C and D automatically
trigger `PARTIAL` status. Required sections (portfolio snapshot, current NAV,
fund profiles, NAV history, holdings, risk profile, constraints) are weighted
more heavily than optional sections (benchmark history, peer group, factor
exposures, manager profiles, fee schedules, redemption rules, fund flow, macro
events, user investment plan).

Grade A requires all required groups and most optional groups. Grade B requires
all required groups with optional gaps. Grade C means the report is usable but
important analytical sections are partial. Grade D means insufficient data for
a professional report. Missing portfolio data is critical. Missing
`risk_profile` or `constraints` lowers the grade and adds limitations but does
not necessarily fail. Derived portfolios count as available, but unresolved or
invalid transaction events lower completeness.

`analysis_coverage` provides a per-section availability summary (available,
partial, derived, missing). `report_limitations` provides concise user-facing
caveats based on completeness and ledger quality. `report_sections` and
`report_quality_gate` provide deterministic host-displayable sections and a
publishability gate.

## Stop With INVALID_INPUT

Return `INVALID_INPUT` when:

- `payload` is not a dictionary;
- `payload.portfolio` is missing and no compatibility `related_entities` exist;
- `payload.portfolio.positions` is missing or empty and the skill cannot derive
  a snapshot from `transactions` + `current_nav`;
- positions do not include usable `fund_code` values.

## Compatibility Fallback

If only `related_entities` is provided, emit baseline HardEvidence and warn
that structured portfolio analysis was not possible.

## Host Report Language

Use direct uncertainty language, surfaced through `data_completeness` grade:

```text
数据完整性评级: B (评分 0.78) — 缺失费率数据和同类排名，报告分析范围受限。
```

```text
数据完整性评级: D (评分 0.35) — 关键数据缺失；基金公司对账单/交易记录为权威数据源。
```

```text
由于缺少 110011 的持仓明细，本报告无法判断其行业集中度；相关风险结论仅基于组合权重和已提供净值。
```

When optional data is absent, use section status language:

```text
benchmark_and_peer: MISSING — 未提供基准或同业数据，本报告不生成基准超额收益或同业排名。
```

Formal actions still require `DecisionSupportSkill`; `fund_analysis` report
sections do not emit `Decision` or `ExecutionLedger`.
