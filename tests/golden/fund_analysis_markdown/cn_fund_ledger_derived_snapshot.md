# Personal fund report

## Executive summary [OK]
- Estimated portfolio value 71,350.00 across 2 position(s); cash 7,000.00.
- Data completeness grade B with score 0.767.
- Risk scan surfaced 5 flag(s) from available inputs.
- No formal decision generated; call decision-support for formal action.

## Transaction cashflow [OK]
- Total inflows: 5,300.00, total outflows: 67,030.00.
- Net cashflow: -61,730.00.
- Dividend income: 300.00.

## Portfolio snapshot [OK]
- As of 2026-03-31, total value is 71,350.00 with 7,000.00 cash.
- Largest position is SYNLED001 at 66.15% of portfolio value.
- Position detail is available for 2 fund(s).

## Reconstruction status [OK]
- Report source: reconstructed_from_ledger.
- Transactions parsed: no.
- Ledger built from transactions + current_nav: yes.
- Ledger complete: yes.
- NAV snapshot available: no.
- Confirmed portfolio with valuation: yes.

## PnL and cost basis [OK]
- Unrealized PnL is 8,350.00 (13.25%) on total cost 63,000.00.
- Position-level PnL is available for 2 fund(s).
- Transaction-derived cost basis is available for 2 fund(s).

## Position contribution [OK]
- Position contribution covers 2 fund(s).
- Largest value position: SYNLED001.
- Largest profit contributor: SYNLED001.

## Allocation and exposure [OK]
- Top fund type exposure is fund_type:equity at 66.15%.
- Top industry exposure is industry:broad_market at 48.23%.
- Top theme exposure is region:CN at 76.69%.
- Single-fund max weight is 66.15%; HHI is 0.552182.

## Risk flags [OK]
- Risk flags by severity: high=1, medium=4.

## Performance and NAV [OK]
- NAV-derived metrics are available for 2 fund(s).
- Highest total return in provided NAV history is SYNLED001 at 18.00%.

## Benchmark divergence [PARTIAL]
- Benchmark divergence reviewed 2 fund(s).
- No severe benchmark divergence was detected from provided data.

Limitations:
- Benchmark divergence check completed but no divergence was found — results are limited without NAV and benchmark history.

## Fees and redemption [OK]
- Fee schedule is available for 2 fund(s).
- Redemption rules are available for 2 fund(s).

## Manager and fund profile [PARTIAL]
- Fund profile data is present, but manager profile details were not provided.

Limitations:
- Manager tenure and manager-change analysis are unavailable.

## DCA and trade budget [OK]
- Trade budget: max buy 10,000.00, max sell 10,000.00, liquidity reserve 7,135.00.
- Short-term trade budget usage is available.
- DCA review includes 1 suggestion(s).

## Professional diagnostics [PARTIAL]
- Overlap scan found 1 overlapping holding/theme/region item(s). 
- Theme overweight scan found 1 theme(s) near or above host-supplied limit. Max: broad_market at 66.1%.
- DCA drawdown scan reviewed 1 plan(s); 0 fund(s) are under drawdown. Formal DCA changes require decision_support.
- Cash ratio is 9.8%.
- Liquidity reserve gap: 135.
- Short-term trade budget status: ok.
- Theme 'broad_market' at 66.1% exceeds limit 55.0% by 11.2%
- Cash 7000 is below 10% liquidity reserve (7135). Gap: 135.

## Profit protection [OK]
- Profit protection reviewed 2 position(s).
- High-profit watchlist contains 1 position(s).

## Right-side confirmation [OK]
- Right-side confirmation applies to 0 drawdown position(s); 0 confirmed.

## Cash deployment [OK]
- Cash-like weight 8.93%; deployment readiness ready.
- Cash accounting basis: conservative_effective_total.
- Estimated deployable cash: 0.00.

## Evidence status [PARTIAL]
- Available conclusions: portfolio has 2 identified position(s); benchmark divergence checked for 2 fund(s); profit protection reviewed for 2 position(s); right-side confirmation assessed for 2 position(s); exposure breakdown computed.
- decision_support_ready: False.
- Formal decision blockers: missing_recent_news.
- Analysis warnings: benchmark_data_missing, sentiment_missing, theme_overweight_warning.
- Missing evidence: missing_benchmark_data, missing_recent_news, missing_sentiment.

## Action watchlist [PARTIAL]
- Do not enter formal active decision until blockers clear: missing_recent_news.

Limitations:
- Suggested rebalance plan is missing.

## Missing data [PARTIAL]
- Missing data groups: missing_benchmark_data, missing_recent_news, missing_sentiment.
- missing_benchmark_data [warning] (provider_could_fetch): next data benchmark price history.
- missing_recent_news [blocker] (provider_could_fetch): next data recent fund or theme news.
- missing_sentiment [warning] (provider_could_fetch): next data sentiment snapshot for held funds or themes.

## Suggested next checks [PARTIAL]
- Next data to fetch: recent benchmark movement, recent fund news, sentiment snapshot.
- Specific data to provide:
-   missing_benchmark_data (provider_could_fetch): benchmark price history
-   missing_recent_news (provider_could_fetch): recent fund or theme news
-   missing_sentiment (provider_could_fetch): sentiment snapshot for held funds or themes

## Uncertainty note [PARTIAL]
- This conclusion is based on host-provided data and does not include live market fetching.
- No formal decision generated; call decision-support for formal action.
- Report limitations count: 1. See each section for details.

Limitations:
- Report data completeness is adequate but some optional sections are unavailable — deeper analysis may require additional data

## Data completeness and limitations [OK]
- Completeness grade B with score 0.767.
- Missing data groups: Benchmark History, Peer Group, Factor Exposures, Manager Profile, Fund Flow, Macro Events, User Investment Plan.
- Optional gaps: Benchmark History, Peer Group, Factor Exposures, Manager Profile, Fund Flow, Macro Events, User Investment Plan.
- Snapshot availability: provider_snapshot=absent, news_snapshot=absent, factor_snapshot=absent, kg_context_snapshot=absent.

Limitations:
- Report data completeness is adequate but some optional sections are unavailable — deeper analysis may require additional data

## Evidence appendix [OK]
- FundAnalysisSkill emits HardEvidence separately in SkillOutput.evidence_items.
- This composed report does not create formal decisions or execution ledgers.

## Personal portfolio health [MISSING]
- Overall status: unavailable
- Confidence: unavailable
- Transactions: none
- Valuation: unavailable
- Identity: unavailable
- Action needed: Provide portfolio_input.holdings if valuation is unavailable
- Reason codes: no_valid_fund_codes

Limitations:
- This is not a formal investment decision — no BUY/SELL/HOLD instruction.
- No broker/order execution capability.
- No auto trading.
- Estimated values are not confirmed market values.
- Partial coverage means incomplete valuation.

## Limitations

- Benchmark and peer: Benchmark data is missing; no benchmark comparison is fabricated.
- Benchmark and peer: Peer group data is missing; no peer ranking is fabricated.
- Benchmark divergence: Benchmark divergence check completed but no divergence was found — results are limited without NAV and benchmark history.
- Factor and style: Factor exposure data is missing; no style exposure is fabricated.
- Factor analysis: Factor snapshot not provided; no factor analysis is fabricated.
- Manager and fund profile: Manager tenure and manager-change analysis are unavailable.
- Event hype failure: Event hype diagnostics are missing or no host event metadata was provided.
- News and events: News snapshot not provided; no news or events are fabricated.
- Action watchlist: Suggested rebalance plan is missing.
- Uncertainty note: Report data completeness is adequate but some optional sections are unavailable — deeper analysis may require additional data
- Rebalance plan: Rebalance plan is missing; target weights or constraints may be unavailable.
- Research query plan: Research planning was not requested by the host.
- Personal portfolio health: This is not a formal investment decision — no BUY/SELL/HOLD instruction.
- Personal portfolio health: No broker/order execution capability.
- Personal portfolio health: No auto trading.
- Personal portfolio health: Estimated values are not confirmed market values.
- Personal portfolio health: Partial coverage means incomplete valuation.
