# Personal fund report

## Executive summary [OK]
- Portfolio value 500,000.00 across 3 position(s); cash 50,000.00.
- Data completeness grade A with score 0.967.
- Risk scan surfaced no flags from available inputs.
- No formal decision generated; call decision-support for formal action.

## Portfolio snapshot [OK]
- As of 2026-06-01, total value is 500,000.00 with 50,000.00 cash.
- Largest position is 110011 at 40.00% of portfolio value.
- Position detail is available for 3 fund(s).

## PnL and cost basis [OK]
- Unrealized PnL is 30,000.00 (7.14%) on total cost 420,000.00.
- Position-level PnL is available for 3 fund(s).

Limitations:
- Transaction-level cost-basis summary is absent; PnL uses provided position cost fields.

## Position contribution [OK]
- Position contribution covers 3 fund(s).
- Largest value position: 110011.
- Largest profit contributor: 110011.

## Allocation and exposure [OK]
- Top fund type exposure is fund_type:equity at 44.44%.
- Top industry exposure is industry:govt at 5.56%.
- Top theme exposure is region:CN at 19.53%.
- Single-fund max weight is 44.44%; HHI is 0.381728.

## Risk flags [OK]
- No risk flags were generated from available inputs.

## Performance and NAV [OK]
- NAV-derived metrics are available for 3 fund(s).
- Highest total return in provided NAV history is 110011 at 43.00%.

## Benchmark and peer [OK]
- Benchmark gap comparison is available for 6 fund-benchmark pair(s).
- Peer ranking data is available for 3 fund(s).

## Benchmark divergence [OK]
- Benchmark divergence reviewed 3 fund(s).
- No severe benchmark divergence was detected from provided data.

## Factor and style [OK]
- Host-provided factor dimensions: momentum, quality, size, value.
- Fund 110011 has high size exposure (0.60)

## Fees and redemption [OK]
- Fee schedule is available for 3 fund(s).
- Redemption rules are available for 3 fund(s).

## Manager and fund profile [OK]
- Manager profile is available for 3 fund(s).
- Fund(s) 330033 have elevated manager-change risk or short manager tenure

## DCA and trade budget [PARTIAL]
- Trade budget: max buy 100,000.00, max sell 100,000.00, liquidity reserve 50,000.00.

Limitations:
- DCA plan review is absent; host did not provide DCA inputs.

## Professional diagnostics [OK]
- Cash ratio is 10.0%.
- Short-term trade budget status: ok.

## Profit protection [OK]
- Profit protection reviewed 3 position(s).

## Right-side confirmation [OK]
- Right-side confirmation applies to 0 drawdown position(s); 0 confirmed.

## Event hype failure [MISSING]
- No section content available from provided artifacts.

Limitations:
- Event hype diagnostics are missing or no host event metadata was provided.

## Cash deployment [OK]
- Cash-like weight 10.00%; deployment readiness ready.
- Cash accounting basis: conservative_effective_total.
- Estimated deployable cash: 0.00.

## Evidence status [PARTIAL]
- decision_support_ready: False.
- Formal decision blockers: missing_recent_news.
- Analysis warnings: sentiment_missing, transaction_history_incomplete.
- Missing evidence: missing_recent_news, missing_sentiment, missing_transaction_history.

## Action watchlist [OK]
- Action watchlist contains 0 simulated trade leg(s).
- Formal action requires decision_support; this section is analysis-only.
- Do not enter formal active decision until blockers clear: missing_recent_news.

## Missing data [PARTIAL]
- Missing data groups: missing_recent_news, missing_sentiment, missing_transaction_history.
- missing_transaction_history: next data transaction ledger with BUY/SELL/DIVIDEND/FEE events.
- missing_recent_news: next data recent fund or theme news.
- missing_sentiment: next data sentiment snapshot for held funds or themes.

## Suggested next checks [PARTIAL]
- Next data to fetch: recent fund news, sentiment snapshot, transaction history, recent benchmark movement.

## Uncertainty note [OK]
- This conclusion is based on host-provided data and does not include live market fetching.
- No formal decision generated; call decision-support for formal action.

## Rebalance plan [OK]
- Rebalance simulation produced 0 trade leg(s) with total trade amount 0.00.
- No single fund > 45%
- Cash reserve >= 10%

## Research query plan [OK]
- Research query plan includes 22 news query(ies) and 3 sentiment query(ies).

## Data completeness and limitations [OK]
- Completeness grade A with score 0.967.
- Missing data groups: Fund Flow.
- Optional gaps: Fund Flow.

## Evidence appendix [OK]
- FundAnalysisSkill emits HardEvidence separately in SkillOutput.evidence_items.
- This composed report does not create formal decisions or execution ledgers.

## Limitations

- DCA and trade budget: DCA plan review is absent; host did not provide DCA inputs.
- Event hype failure: Event hype diagnostics are missing or no host event metadata was provided.
