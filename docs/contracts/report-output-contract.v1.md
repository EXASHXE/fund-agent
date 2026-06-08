# Report Output Contract v1

**Version:** 1.0
**Effective:** v0.4.8
**Scope:** Determines the stable shape of FundAnalysisSkill report composer output.

For the broader `fund_analysis` artifact key contract, see
[`fund-analysis-artifacts.v1.md`](./fund-analysis-artifacts.v1.md) and the
machine-readable catalog at `skillpack/artifact-contracts.yaml`.

## 1. `report_sections`

The `report_sections` list is produced by `compose_personal_fund_report()` in
`src/tools/portfolio/report_composer.py`. It is deterministic, JSON-serializable,
and host-viewable. Hosts may replace the UX renderer but must preserve the
section identities, ordering, status semantics, and no-fabrication policy.

### 1.1 Section identity and ordering

Sections are ordered. The canonical order is defined by `SECTION_ORDER`:

1. `executive_summary` — Executive summary
2. `portfolio_snapshot` — Portfolio snapshot
3. `pnl_and_cost_basis` — PnL and cost basis
4. `allocation_and_exposure` — Allocation and exposure
5. `risk_flags` — Risk flags
6. `performance_and_nav` — Performance and NAV
7. `benchmark_and_peer` — Benchmark and peer
8. `factor_and_style` — Factor and style
9. `fees_and_redemption` — Fees and redemption
10. `manager_and_fund_profile` — Manager and fund profile
11. `dca_and_trade_budget` — DCA and trade budget
12. `professional_diagnostics` — Professional diagnostics
13. `rebalance_plan` — Rebalance plan
14. `research_query_plan` — Research query plan
15. `data_completeness_and_limitations` — Data completeness and limitations
16. `evidence_appendix` — Evidence appendix

The ordering is stable. No section may be omitted; MISSING sections are
represented with `status: "MISSING"` and an empty `bullets` list.

### 1.2 Required keys per section

Every section dict MUST include:

| Key | Type | Description |
|-----|------|-------------|
| `id` | string | Section identifier from `SECTION_ORDER` |
| `title` | string | Human-readable section title |
| `status` | string | One of `OK`, `PARTIAL`, `MISSING` |
| `bullets` | list of string | Deterministic bullet points |
| `data_sources` | list of string | Artifact/evidence names that informed the section |
| `limitations` | list of string | Why the section is PARTIAL or MISSING, or empty if OK |

### 1.3 Status enum

- `OK` — Section has sufficient data; all bullets are directly sourced from
  host-provided data and deterministic computation.
- `PARTIAL` — Some data is available but incomplete; bullets list what IS
  known; `limitations` explain what IS missing.
- `MISSING` — No host-provided data exists for this section. `bullets` is
  empty. `limitations` states the missing data.

### 1.4 No-fabrication policy

- Bullets MUST be deterministic strings derived from artifacts.
- No section may fabricate absent facts, rankings, comparisons, or predictions.
- If optional host data is missing, the section MUST be PARTIAL or MISSING.
- Benchmark comparisons, peer rankings, factor decompositions, fee analyses,
  and manager assessments are only present when the host provides the
  corresponding data payload.

  The `professional_diagnostics` section summarizes host-data-only diagnostic
  artifacts (redemption_fee_risk, overlap_diagnostics,
  theme_overweight_diagnostics, dca_drawdown_diagnostics, cash_budget_diagnostics)
  produced by local deterministic rules. It is not a formal decision section.
  Formal Decision / ExecutionLedger artifacts remain `decision_support`-only.

---

## 2. `report_outline`

The `report_outline` is a subset of `report_sections` — a list of
`{id, title, status}` dicts in the same order. It provides a table-of-contents
for host UX without exposing full section detail.

```json
[
  {"id": "executive_summary", "title": "Executive summary", "status": "OK"},
  ...
]
```

---

## 3. `report_quality_gate`

Produced by `_build_quality_gate()` from `data_completeness`, section statuses,
and compose options.

### 3.1 Keys

| Key | Type | Description |
|-----|------|-------------|
| `grade` | string | A, B, C, or D |
| `can_publish_professional_report` | boolean | Whether the report meets professional quality bar |
| `reason` | string | Human-readable explanation of the gate decision |

### 3.2 Grade semantics

| Grade | Publishable | Condition |
|-------|-------------|-----------|
| A | true | data_completeness grade A |
| B | true | data_completeness grade B |
| C | true (with prominent limitations) | data_completeness grade C |
| D | false (unless `minimal_report` option is true) | data_completeness grade D |

Grade D reports are not publishable as professional reports unless the
`minimal_report` compose option is set to `true` AND core portfolio data
exists (portfolio snapshot present).

---

## 4. Markdown rendering

`render_report_markdown(report_sections)` produces a deterministic Markdown
string from `report_sections`.

- All section titles are rendered as `##` headings.
- `PARTIAL` sections include a `[PARTIAL]` annotation.
- `MISSING` sections include a `[MISSING]` annotation.
- When any section is PARTIAL or MISSING, a **Limitations** footer is appended
  listing the limitation text from each affected section.
- The Markdown MUST NOT contain `Decision`, `ExecutionLedger`, `BUY`, `SELL`,
  or `HOLD` as formal action directives.

Hosts may replace the Markdown renderer with their own UX. Hosts must preserve
the no-fabrication policy and limitations display.

---

## 5. Decision boundary

- `report_sections` may contain analysis artifacts and suggested rebalance
  plan summaries. These are **analysis**, not formal decisions.
- `report_sections` MUST NOT contain formal `Decision` or `ExecutionLedger`
  artifacts.
- The `rebalance_plan` section may describe a suggested plan but it is
  labeled as a suggestion, not an executable order.
- Formal `BUY`/`SELL`/`INCREASE`/`REDUCE`/`HOLD` actions REQUIRE
  `DecisionSupportSkill` and its structured decision justification contract.
- `FundAnalysisSkill` output includes `report_sections` but never `decision`
  or `execution_ledger`.

---

## 6. Integration with FundAnalysisSkill

`FundAnalysisSkill._run_portfolio_analysis()` calls `compose_personal_fund_report()`
and includes the result in `SkillOutput.artifacts`:

```json
{
  "artifacts": {
    "report_sections": [...],
    "report_outline": [...],
    "report_quality_gate": {...},
    "data_completeness": {...},
    "analysis_coverage": {...},
    "report_limitations": [...],
    "fund_analysis_report": {...},
    ...
  }
}
```

`report_sections`, `report_outline`, and `report_quality_gate` are top-level
artifacts. `data_completeness`, `analysis_coverage`, and `report_limitations`
are also present in `fund_analysis_report`.

---

## 7. Stability guarantees

- Section IDs and ordering are stable within this contract version.
- Required keys per section are stable.
- Status semantics are stable.
- New optional sections may be appended to the end of `SECTION_ORDER` without
  a contract version bump.
- Adding new keys to existing sections (e.g., a `charts` key for future visual
  data) is backward-compatible and does not require a contract bump.
- Removing or reordering existing sections, or changing the `status` enum,
  requires a contract version bump.
