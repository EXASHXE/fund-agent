# Fund Analysis Report Template

Hosts may adapt this template to their final UX. Keep claims tied to artifacts,
warnings, or evidence IDs. `fund_analysis` now emits structured
`report_sections`; hosts can render them directly.

## Structured section contract

Each section has this JSON-serializable shape:

```json
{
  "id": "executive_summary",
  "title": "Executive summary",
  "status": "OK",
  "bullets": [],
  "data_sources": [],
  "limitations": []
}
```

Statuses are `OK`, `PARTIAL`, or `MISSING`. Missing data must appear as
`PARTIAL`/`MISSING` sections and limitations, not fabricated analysis.

## Canonical sections

1. `executive_summary`
2. `portfolio_snapshot`
3. `pnl_and_cost_basis`
4. `position_contribution`
5. `allocation_and_exposure`
6. `risk_flags`
7. `performance_and_nav`
8. `benchmark_and_peer`
9. `benchmark_divergence`
10. `factor_and_style`
11. `fees_and_redemption`
12. `manager_and_fund_profile`
13. `dca_and_trade_budget`
14. `professional_diagnostics`
15. `profit_protection`
16. `right_side_confirmation`
17. `event_hype_failure`
18. `cash_deployment`
19. `evidence_status`
20. `action_watchlist`
21. `missing_data`
22. `suggested_next_checks`
23. `uncertainty_note`
24. `rebalance_plan`
25. `research_query_plan`
26. `data_completeness_and_limitations`
27. `evidence_appendix`

## Section guidance

### Executive summary

Summarize portfolio value, position count, major risk flags, data completeness
grade, and whether a formal decision was generated. For report-only output,
state that no formal decision was generated and the host must call
`decision_support` for formal action.

### Portfolio snapshot

Use `portfolio_summary` and `position_summary`. Show as-of date, total value,
cash, position count, and largest position. Do not infer missing position names
or values.

### PnL and cost basis

Use `pnl_summary` and `cost_basis_summary`. If transaction-level cost basis is
absent, say so; do not infer broker cost basis.

### Position contribution

Use `position_contribution` artifact. Shows each position's contribution to
portfolio return and risk.

### Allocation and exposure

Use `exposure_summary` and concentration metrics. If holdings are missing, keep
holding-derived exposure `PARTIAL` or `MISSING`.

### Risk flags

Use only `risk_flags` emitted by the skill. Missing `risk_profile` or
`constraints` should be surfaced as limitations.

### Performance and NAV

Use host-provided `nav_history` through `fund_metrics`. If NAV history is
missing, mark the section `MISSING` or `PARTIAL`.

### Benchmark and peer

Use `benchmark_summary` and `peer_summary`. Do not fabricate benchmark
comparisons, rankings, percentiles, categories, or attribution.

### Benchmark divergence

Use `benchmark_divergence_diagnostics` artifact. Flags funds diverging
significantly from their benchmarks.

### Factor and style

Use `factor_summary`. Do not infer style exposure from fund names or tags when
host-provided factor data is absent.

### Fees and redemption

Use `fee_summary` and `redemption_summary`. Do not invent fee schedules,
lockups, redemption fees, or suspension status.

### Manager and fund profile

Use `manager_summary` and fund profile availability. Do not invent manager
stability, tenure, or change-risk conclusions.

### DCA and trade budget

Use `trade_budget`, `short_term_trade_budget`, and `dca_plan_review`. If DCA
inputs are absent, state that DCA review is unavailable.

### Professional diagnostics

Use `professional_diagnostics` artifact. Aggregates overlap, theme overweight,
DCA drawdown, and cash budget diagnostics.

### Profit protection

Use `profit_protection_diagnostics` artifact. Identifies positions with
significant unrealized gains that may need protection.

### Right-side confirmation

Use `right_side_confirmation_diagnostics` artifact. Confirms whether recent
price action supports current positions.

### Event hype failure

Use `event_hype_failure_diagnostics` artifact. Flags funds where recent events
may have created unsustainable hype.

### Cash deployment

Use `cash_deployment_diagnostics` artifact. Analyzes cash allocation efficiency
and deployment opportunities.

### Evidence status

Summarizes evidence item coverage and quality for the analysis.

### Action watchlist

Lists positions or funds that may need attention based on analysis results.

### Missing data

Enumerates data gaps that affected the analysis.

### Suggested next checks

Recommends additional data or analysis the host could provide.

### Uncertainty note

Documents key uncertainties and assumptions in the analysis.

### Rebalance plan

Present `suggested_rebalance_plan` as analysis only. It is not executable
advice unless `DecisionSupportSkill` produced formal decisions.

### Research query plan

Use `research_query_plan` only when `research_planning` was requested. The host
decides whether to call news or sentiment skills.

### Data completeness and limitations

Include `data_completeness`, `analysis_coverage`, `report_limitations`, and
`report_quality_gate`. `report_quality_gate` tells the host whether the report
is publishable as a professional report.

### Evidence appendix

List artifact names and evidence IDs, for example:

```text
Evidence appendix:
- ev:portfolio_allocation_concentration
- ev:fund_risk_return_metrics
- ev:portfolio_risk_flags
```

The host renders appendix formatting from `SkillOutput.evidence_items`,
`artifacts`, and `warnings`.
