# Golden Regression Snapshots

Golden snapshots protect externally visible `fund_analysis` behavior before
internal refactors. They freeze representative runtime bridge JSON envelopes and
explicit Markdown report output so a zero-behavior pipeline refactor can prove
that it changed structure only, not output semantics.

The snapshots use fake/sample fixtures only. They are not investment advice,
not real-time market data, and not real personal holdings or transaction
records. External hosts own real data fetching, provider SDK integration,
credentials, MCP providers, retries, planning, orchestration, memory, and final
UX.

Snapshots intentionally normalize volatile or non-semantic fields such as
bridge step IDs, manifest paths, runtime import paths, absolute local paths,
generated evidence IDs, and generated timestamps. They keep artifacts, evidence
claims, evidence values, related entities, confidence weights, warnings, errors,
statuses, report sections, report quality gates, data completeness, analysis
coverage, limitations, and Markdown headings intact.

Decision_support golden snapshots live under `tests/golden/decision_support/`.
They freeze externally visible `decision_support` behavior before internal
refactors. Only `decision_support` may produce formal `Decision` and
`ExecutionLedger` artifacts.

Regenerate snapshots only after intentional review:

```bash
python scripts/update_fund_analysis_golden.py
python scripts/update_decision_support_golden.py
```

Review any snapshot diff for behavior changes, accidental real data, credentials,
provider URLs or tokens, absolute local paths, and forbidden formal decision
artifacts before committing.
