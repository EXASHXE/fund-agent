# Fund Analysis Input Contract v1

**Version:** 1.0
**Contract ID:** `fund-analysis-input.v1`
**Runtime ID:** `fund_analysis`
**Markdown skill slug:** `fund-analysis`
**Machine-readable contract:** `skillpack/input-contracts.yaml`

This document defines the stable host-facing input contract for
`FundAnalysisSkill`. It is a practical runtime bridge and host integration
contract, not a provider integration specification.

## Scope

`fund_analysis` consumes host-supplied portfolio, ledger, NAV, holdings,
benchmark, peer, fee, manager, market scenario, research planning, risk
profile, constraints, and DCA data.

`fund-agent` does not fetch NAV, holdings, benchmark, peer, fee, manager, news,
sentiment, market, macro, or calendar data by itself. The external host owns
data fetching, credentials, provider SDKs, retries, memory, orchestration, and
final UX.

Validation is structural and host-assistive. It is not a guarantee of investment
correctness, data freshness, report publishability, or decision quality.
Validation is not a guarantee of investment correctness.

## Accepted Envelope Shapes

| Shape | Required fields | Notes |
|---|---|---|
| `full_skill_input` | `task_id`, `step_id`, `skill_name`, `payload`, `kg_context`, `required_mcp_capabilities`, `evidence_context`, `metadata` | Full `SkillInput`-shaped envelope with host-supplied payload. `mcp_responses` may be supplied for runtime bridge testing. |
| `payload_only` | `payload` | Convenience envelope; the bridge fills `task_id`, `step_id`, and `skill_name`. `mcp_responses` may be supplied for runtime bridge testing. |

`fund_analysis` has no required MCP capability. Any `mcp_responses` block is
runtime-bridge test data only.

## Minimum Valid Input Modes

| Mode | Required fields | Valid when | Notes |
|---|---|---|---|
| `portfolio_snapshot` | `payload.portfolio`, `payload.portfolio.positions[]`, `payload.portfolio.positions[].fund_code` | `portfolio.positions` has at least one usable `fund_code`. | Recommended per position: `current_value`, `shares`, `current_nav`, `total_cost`. |
| `ledger_derived` | `payload.transactions[]`, `payload.current_nav`, `payload.as_of_date or payload.portfolio.as_of_date` | Transactions and `current_nav` are non-empty and `as_of_date` is present. | Derives a portfolio snapshot from transactions and current NAV. |
| `related_entities_baseline` | `payload.related_entities[] or kg_context.fund_codes[]` | Related entities are present but structured portfolio/ledger data is absent. | Degraded baseline-only mode. Structured portfolio analysis, PnL, weights, and report sections are not possible. |

## Recommended Fields

Missing recommended fields appear in `missing_recommended` and produce warnings.
They do not hard-fail validation by themselves.

| Field | Description | Missing behavior |
|---|---|---|
| `risk_profile` | User risk profile and risk tolerance. | warning |
| `constraints` | User constraints such as caps, liquidity needs, or no-buy/no-sell rules. | warning |
| `fund_profiles` | Host-supplied fund profile data keyed by fund code. | warning |
| `nav_history` | Host-supplied historical NAV points keyed by fund code. | warning |
| `holdings` | Host-supplied fund holdings or constituents keyed by fund code. | warning |
| `transactions` | Host-supplied transaction ledger for cost basis, PnL, and derived snapshots. | warning |
| `dca_plans` | Host-supplied DCA plan data for deterministic plan review. | warning |

## Optional Fields

Optional fields depend on host-supplied data. Missing optional fields populate
`missing_optional` and may produce limitations, `PARTIAL` analysis, or skipped
optional sections. Missing optional data must not be fabricated.

| Field | Description | Missing behavior |
|---|---|---|
| `benchmarks` | Fund or portfolio benchmark mapping. | omit optional analysis |
| `benchmark_history` | Host-supplied benchmark return or value history. | omit optional analysis |
| `peer_group` | Host-supplied peer group data for relative comparison. | omit optional analysis |
| `factor_exposures` | Host-supplied factor or style exposure data. | omit optional analysis |
| `manager_profiles` | Host-supplied fund manager profile data. | omit optional analysis |
| `fee_schedules` | Host-supplied fee schedule data. | omit optional analysis |
| `redemption_rules` | Host-supplied redemption and lockup rule data. | omit optional analysis |
| `market_scenario` | Host-supplied market scenario data for deterministic scenario impact analysis. | omit optional analysis |
| `report_options` | Host-supplied report composition options. | use defaults |
| `research_planning` | Host-supplied research planning context for deterministic query plan generation. | omit optional analysis |

## Host Data Capability Mapping

These capability names mirror `skillpack/capabilities.yaml`. The payload field
mapping is governed by `skillpack/input-contracts.yaml` and powers
`--explain-input` plus structural capability coverage in `--validate-input`.

| Host capability | Payload fields |
|---|---|
| `portfolio_snapshot` | `portfolio` |
| `fund_profile` | `fund_profiles`, `fund_profile` |
| `fund_nav_history` | `nav_history` |
| `fund_holdings` | `holdings` |
| `fund_transactions` | `transactions` |
| `fund_fee_schedule` | `fee_schedules`, `fee_schedule` |
| `fund_benchmark` | `benchmarks`, `benchmark`, `fund_benchmark` |
| `benchmark_history` | `benchmark_history` |
| `fund_peer_group` | `peer_group`, `peer_groups` |
| `fund_manager_profile` | `manager_profiles`, `manager_profile` |
| `fund_flow` | `fund_flows`, `fund_flow` |
| `index_constituents` | `index_constituents` |
| `macro_events` | `macro_events`, `market_scenario` |
| `market_calendar` | `market_calendar` |
| `user_investment_plan` | `investment_plan`, `user_investment_plan` |

## Validation Severity

| Severity | Meaning |
|---|---|
| `OK` | Structural minimum is met and no validation warnings downgrade the input. |
| `PARTIAL` | A degraded mode is used or warnings such as missing `current_value` limit useful analysis. |
| `INVALID` | No minimum input mode is satisfied, or a ledger-derived input is missing `as_of_date`. |

Specific validation behavior:

- `portfolio_snapshot` is valid when there is at least one usable
  `payload.portfolio.positions[].fund_code`.
- `ledger_derived` is valid when `transactions`, `current_nav`, and
  `as_of_date` are present.
- `related_entities_baseline` is `valid=true` but `severity=PARTIAL`.
- `transactions + current_nav` without `as_of_date` is `INVALID`.
- Empty payload is `INVALID`.
- Missing `current_value` warns and may produce `PARTIAL`; it is not a hard
  failure.
- Missing recommended fields produce warnings and `missing_recommended`, not
  hard errors.
- Missing optional fields populate `missing_optional` and do not hard-fail.

## Degradation Policy

Missing optional data should produce `PARTIAL` analysis, warnings,
`report_limitations`, or skipped sections. `fund-agent` must not fabricate
missing host-owned data.

Missing usable `portfolio.positions`, `transactions + current_nav + as_of_date`,
and `related_entities` baseline is `INVALID_INPUT`.

The host owns all NAV, holdings, benchmark, peer, fee, manager, market
scenario, news, sentiment, macro, and calendar data.

## Decision Boundary

`fund_analysis` may produce analysis artifacts, warnings, report sections,
report outline, report quality gate, and suggested plans.

`fund_analysis` MUST NOT produce formal `Decision` or `ExecutionLedger`
artifacts. Formal action decisions belong to `decision_support`.

## Related Contracts

- [`fund-analysis-artifacts.v1.md`](./fund-analysis-artifacts.v1.md)
- [`report-output-contract.v1.md`](./report-output-contract.v1.md)
- `skillpack/input-contracts.yaml`
- `skillpack/artifact-contracts.yaml`
