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
`ExecutionLedger` artifacts. These snapshots include structured decision
justification fields (`decision_reason_codes`, `evidence_state`, and
`blocked_by`) for formal decision auditability. They also cover gatekeeper
reason codes such as evidence sufficiency, missing evidence, and active-to-hold
downgrades.

Fund_analysis report snapshots include stable v1 report sections for position
contribution, profit protection, benchmark divergence, right-side confirmation,
event hype failure, cash deployment, evidence status, missing data, suggested
next checks, and uncertainty notes. These are analysis/report artifacts only.

Thesis_generation golden snapshots live under `tests/golden/thesis_generation/`.
They freeze externally visible `thesis_generation` behavior. Thesis_generation
produces `ThesisDraft` artifacts only; it must not produce formal `Decision` or
`ExecutionLedger` artifacts.

Fund_analysis snapshots remain formal-decision-free. Thesis_generation
snapshots remain artifact-only.

Regenerate snapshots only after intentional review:

```bash
python scripts/update_fund_analysis_golden.py
python scripts/update_decision_support_golden.py
python scripts/update_thesis_generation_golden.py
```

Review any snapshot diff for behavior changes, accidental real data, credentials,
provider URLs or tokens, absolute local paths, and forbidden formal decision
artifacts before committing.
