# Personal fund report

## Executive summary [OK]
- Portfolio value 150,000.00 across 4 position(s); cash 5,000.00.
- Data completeness grade B with score 0.800.
- Risk scan surfaced 7 flag(s) from available inputs.
- No formal decision generated; call decision-support for formal action.

## Portfolio snapshot [OK]
- As of 2026-03-31, total value is 150,000.00 with 5,000.00 cash.
- Largest position is SYNAI001 at 46.67% of portfolio value.
- Position detail is available for 4 fund(s).

## PnL and cost basis [OK]
- Unrealized PnL is 7,000.00 (5.07%) on total cost 138,000.00.
- Position-level PnL is available for 4 fund(s).
- Transaction-derived cost basis is available for 4 fund(s).

## Position contribution [OK]
- Position contribution covers 4 fund(s).
- Largest value position: SYNAI001.
- Largest profit contributor: SYNAI001.
- Largest loss contributor: SYNAI002.

## Allocation and exposure [OK]
- Top fund type exposure is fund_type:equity at 48.28%.
- Top industry exposure is industry:ai_semiconductor at 15.28%.
- Top theme exposure is region:CN at 45.00%.
- Single-fund max weight is 48.28%; HHI is 0.353151.

## Risk flags [OK]
- Risk flags by severity: high=2, low=1, medium=4.

## Performance and NAV [OK]
- NAV-derived metrics are available for 4 fund(s).
- Highest total return in provided NAV history is SYNAI001 at 40.00%.

## Benchmark and peer [MISSING]
- No section content available from provided artifacts.

Limitations:
- Benchmark data is missing; no benchmark comparison is fabricated.
- Peer group data is missing; no peer ranking is fabricated.

## Benchmark divergence [OK]
- Benchmark divergence reviewed 4 fund(s).
- No severe benchmark divergence was detected from provided data.

## Factor and style [OK]
- Host-provided factor dimensions: ai_theme, duration, semiconductor_beta.
- Fund SYNAI001 has high ai_theme exposure (0.88)
- Fund SYNAI002 has high ai_theme exposure (0.70)
- Fund SYNAI001 has high semiconductor_beta exposure (0.82)
- Fund SYNAI002 has high semiconductor_beta exposure (0.90)

## Fees and redemption [OK]
- Fee schedule is available for 4 fund(s).
- Redemption rules are available for 4 fund(s).

## Manager and fund profile [PARTIAL]
- Fund profile data is present, but manager profile details were not provided.

Limitations:
- Manager tenure and manager-change analysis are unavailable.

## DCA and trade budget [OK]
- Trade budget: max buy 8,000.00, max sell 12,000.00, liquidity reserve 15,000.00.
- Short-term trade budget usage is available.
- DCA review includes 1 suggestion(s).

## Professional diagnostics [PARTIAL]
- Overlap scan found 2 overlapping holding/theme/region item(s). Highest: Sample Advanced Chip A.
- Theme overweight scan found 2 theme(s) near or above host-supplied limit. Max: ai_semiconductor at 46.7%.
- DCA drawdown scan reviewed 1 plan(s); 1 fund(s) are under drawdown. Formal DCA changes require decision_support.
- Cash ratio is 3.3%.
- Liquidity reserve gap: 10,000.
- Short-term trade budget status: ok.
- Theme 'ai_semiconductor' at 46.7% exceeds limit 35.0% by 11.7%
- Fund SYNAI001 has max drawdown 11.3%. DCA may benefit from buying at lower NAV, but review risk tolerance.
- Cash 5000 is below 10% liquidity reserve (15000). Gap: 10000.

## Profit protection [OK]
- Profit protection reviewed 4 position(s).

## Right-side confirmation [OK]
- Right-side confirmation applies to 3 drawdown position(s); 0 confirmed.
- Fresh NAV, benchmark, news, or sentiment evidence is needed before action.

## Event hype failure [MISSING]
- No section content available from provided artifacts.

Limitations:
- Event hype diagnostics are missing or no host event metadata was provided.

## Cash deployment [OK]
- Cash-like weight 3.33%; deployment readiness not_ready.
- Cash accounting basis: conservative_effective_total.
- Estimated deployable cash: 0.00.

## Evidence status [PARTIAL]
- decision_support_ready: False.
- Formal decision blockers: cash_deployment_not_ready, missing_recent_news.
- Analysis warnings: benchmark_data_missing, cash_deployment_not_ready, right_side_unconfirmed, sentiment_missing, theme_overweight_warning.
- Missing evidence: missing_benchmark_data, missing_recent_news, missing_sentiment.

## Action watchlist [OK]
- Action watchlist contains 4 simulated trade leg(s).
- Formal action requires decision_support; this section is analysis-only.
- Do not enter formal active decision until blockers clear: cash_deployment_not_ready, missing_recent_news.

## Missing data [PARTIAL]
- Missing data groups: missing_benchmark_data, missing_recent_news, missing_sentiment.
- missing_benchmark_data: next data benchmark price history.
- missing_recent_news: next data recent fund or theme news.
- missing_sentiment: next data sentiment snapshot for held funds or themes.

## Suggested next checks [PARTIAL]
- Next data to fetch: recent benchmark movement, recent fund news, sentiment snapshot, benchmark price history, recent news evidence, target asset evidence.

## Uncertainty note [PARTIAL]
- This conclusion is based on host-provided data and does not include live market fetching.
- No formal decision generated; call decision-support for formal action.
- Report limitations count: 1.

Limitations:
- Report data completeness is adequate but some optional sections are unavailable — deeper analysis may require additional data

## Rebalance plan [OK]
- Rebalance simulation produced 4 trade leg(s) with total trade amount 32,500.00.
- Synthetic max_single_theme_weight included as host context.
- FundAnalysisSkill analysis remains artifact/report only.

## Research query plan [MISSING]
- No section content available from provided artifacts.

Limitations:
- Research planning was not requested by the host.

## Data completeness and limitations [OK]
- Completeness grade B with score 0.800.
- Missing data groups: Benchmark History, Peer Group, Manager Profile, Fund Flow, Macro Events, User Investment Plan.
- Optional gaps: Benchmark History, Peer Group, Manager Profile, Fund Flow, Macro Events, User Investment Plan.

Limitations:
- Report data completeness is adequate but some optional sections are unavailable — deeper analysis may require additional data

## Evidence appendix [OK]
- FundAnalysisSkill emits HardEvidence separately in SkillOutput.evidence_items.
- This composed report does not create formal decisions or execution ledgers.

## Limitations

- Benchmark and peer: Benchmark data is missing; no benchmark comparison is fabricated.
- Benchmark and peer: Peer group data is missing; no peer ranking is fabricated.
- Manager and fund profile: Manager tenure and manager-change analysis are unavailable.
- Event hype failure: Event hype diagnostics are missing or no host event metadata was provided.
- Uncertainty note: Report data completeness is adequate but some optional sections are unavailable — deeper analysis may require additional data
- Research query plan: Research planning was not requested by the host.
