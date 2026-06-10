# Personal fund report

## Executive summary [OK]
- Portfolio value 100,000.00 across 3 position(s); cash 12,000.00.
- Data completeness grade B with score 0.767.
- Risk scan surfaced 7 flag(s) from available inputs.
- No formal decision generated; call decision-support for formal action.

## Portfolio snapshot [OK]
- As of 2026-03-31, total value is 100,000.00 with 12,000.00 cash.
- Largest position is SYNDCA001 at 45.00% of portfolio value.
- Position detail is available for 3 fund(s).

## PnL and cost basis [OK]
- Unrealized PnL is -9,000.00 (-9.28%) on total cost 97,000.00.
- Position-level PnL is available for 3 fund(s).
- Transaction-derived cost basis is available for 3 fund(s).

## Position contribution [OK]
- Position contribution covers 3 fund(s).
- Largest value position: SYNDCA001.
- Largest loss contributor: SYNDCA001.

## Allocation and exposure [OK]
- Top fund type exposure is fund_type:equity at 51.14%.
- Top industry exposure is industry:broad_market at 48.58%.
- Top theme exposure is region:CN at 85.00%.
- Single-fund max weight is 51.14%; HHI is 0.399535.

## Risk flags [OK]
- Risk flags by severity: high=1, medium=6.

## Performance and NAV [OK]
- NAV-derived metrics are available for 3 fund(s).
- Highest total return in provided NAV history is SYNMM001 at 0.00%.

## Benchmark and peer [MISSING]
- No section content available from provided artifacts.

Limitations:
- Benchmark data is missing; no benchmark comparison is fabricated.
- Peer group data is missing; no peer ranking is fabricated.

## Benchmark divergence [OK]
- Benchmark divergence reviewed 3 fund(s).
- No severe benchmark divergence was detected from provided data.

## Factor and style [MISSING]
- No section content available from provided artifacts.

Limitations:
- Factor exposure data is missing; no style exposure is fabricated.

## Fees and redemption [OK]
- Fee schedule is available for 3 fund(s).
- Redemption rules are available for 3 fund(s).

## Manager and fund profile [PARTIAL]
- Fund profile data is present, but manager profile details were not provided.

Limitations:
- Manager tenure and manager-change analysis are unavailable.

## DCA and trade budget [OK]
- Trade budget: max buy 6,000.00, max sell 10,000.00, liquidity reserve 12,000.00.
- Short-term trade budget usage is available.
- DCA review includes 1 suggestion(s).

## Professional diagnostics [PARTIAL]
- Overlap scan found 1 overlapping holding/theme/region item(s). 
- Theme overweight scan found 1 theme(s) near or above host-supplied limit. Max: broad_market at 45.0%.
- DCA drawdown scan reviewed 1 plan(s); 1 fund(s) are under drawdown. Formal DCA changes require decision_support.
- Cash ratio is 12.0%.
- Short-term trade budget status: ok.
- Fund SYNDCA001 has max drawdown 29.2%. DCA may benefit from buying at lower NAV, but review risk tolerance.

## Profit protection [OK]
- Profit protection reviewed 3 position(s).

## Right-side confirmation [OK]
- Right-side confirmation applies to 2 drawdown position(s); 0 confirmed.
- Fresh NAV, benchmark, news, or sentiment evidence is needed before action.

## Event hype failure [MISSING]
- No section content available from provided artifacts.

Limitations:
- Event hype diagnostics are missing or no host event metadata was provided.

## Cash deployment [OK]
- Cash-like weight 12.00%; deployment readiness ready.
- Cash accounting basis: conservative_effective_total.
- Estimated deployable cash: 0.00.

## Evidence status [PARTIAL]
- decision_support_ready: False.
- Formal decision blockers: missing_recent_news.
- Analysis warnings: benchmark_data_missing, right_side_unconfirmed, sentiment_missing, theme_overweight_warning.
- Missing evidence: missing_benchmark_data, missing_recent_news, missing_sentiment.

## Action watchlist [OK]
- Action watchlist contains 2 simulated trade leg(s).
- Formal action requires decision_support; this section is analysis-only.
- Do not enter formal active decision until blockers clear: missing_recent_news.

## Missing data [PARTIAL]
- Missing data groups: missing_benchmark_data, missing_recent_news, missing_sentiment.
- missing_benchmark_data: next data benchmark price history.
- missing_recent_news: next data recent fund or theme news.
- missing_sentiment: next data sentiment snapshot for held funds or themes.

## Suggested next checks [PARTIAL]
- Next data to fetch: recent benchmark movement, recent fund news, sentiment snapshot, benchmark price history, recent news evidence.

## Uncertainty note [PARTIAL]
- This conclusion is based on host-provided data and does not include live market fetching.
- No formal decision generated; call decision-support for formal action.
- Report limitations count: 1.

Limitations:
- Report data completeness is adequate but some optional sections are unavailable — deeper analysis may require additional data

## Rebalance plan [OK]
- Rebalance simulation produced 2 trade leg(s) with total trade amount 16,000.00.
- Sample review checks DCA plan pressure against concentration limits.
- Formal DCA changes require decision_support.

## Research query plan [MISSING]
- No section content available from provided artifacts.

Limitations:
- Research planning was not requested by the host.

## Data completeness and limitations [OK]
- Completeness grade B with score 0.767.
- Missing data groups: Benchmark History, Peer Group, Factor Exposures, Manager Profile, Fund Flow, Macro Events, User Investment Plan.
- Optional gaps: Benchmark History, Peer Group, Factor Exposures, Manager Profile, Fund Flow, Macro Events, User Investment Plan.

Limitations:
- Report data completeness is adequate but some optional sections are unavailable — deeper analysis may require additional data

## Evidence appendix [OK]
- FundAnalysisSkill emits HardEvidence separately in SkillOutput.evidence_items.
- This composed report does not create formal decisions or execution ledgers.

## Limitations

- Benchmark and peer: Benchmark data is missing; no benchmark comparison is fabricated.
- Benchmark and peer: Peer group data is missing; no peer ranking is fabricated.
- Factor and style: Factor exposure data is missing; no style exposure is fabricated.
- Manager and fund profile: Manager tenure and manager-change analysis are unavailable.
- Event hype failure: Event hype diagnostics are missing or no host event metadata was provided.
- Uncertainty note: Report data completeness is adequate but some optional sections are unavailable — deeper analysis may require additional data
- Research query plan: Research planning was not requested by the host.
