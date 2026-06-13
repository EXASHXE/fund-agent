# Changelog

## Unreleased

### Fixed

- Stabilized provider adapter tests so default pytest does not require live AkShare/network/env.
- Added `live_provider` / `adapter_live` test markers with explicit opt-in via `FUND_AGENT_RUN_LIVE_PROVIDER_TESTS` env var.
- Added live provider adapter test file (`tests/host_data/test_live_provider_adapters.py`) — skipped by default.
- Clarified live provider smoke tests as opt-in with CI warning in adapter README.

### Safety

- Core runtime remains no-network and no-provider-SDK.
- Live provider smoke remains outside core runtime and opt-in.
- No broker/order execution behavior added.

## [0.9.0] — 2026-06-13

### Added

- **Public `fund_agent.*` facade** — top-level package with stable import paths
  for workflow, regression, quality, providers, reporting, runtime, version, and
  cli. `fund_agent.*` is the preferred public API.
- **Unified `fund-agent` CLI** — single entry point with subcommands: `doctor`,
  `run-skill`, `regressions`, `provider-smoke`, `audit`. Old console scripts
  (`fund-agent-run-skill`, `fund-agent-doctor`) remain compatible.
- **Personal portfolio regression pack** — scenario-based regression fixtures
  covering report-only, formal decision, mixed portfolio, and zh-CN flows.
- **Advisory quality gate** — deterministic evaluation of advisory outputs,
  including forbidden execution field checks and SOFT_ACTION_ADVICE boundary.
- **Deterministic workflow trace** — `WorkflowTrace` for recording and
  reproducing advisory workflow steps.
- **Provider contract layer** — `ProviderCredentialSpec`, `ProviderCredentials`,
  `ProviderRegistry`, `ProviderConfig`, `ProviderResult`, `ProviderCapability`,
  credential resolution from config/env, and `providers.example.yaml`.
- **Optional AkShare / Eastmoney / Xueqiu host adapter prototypes** — under
  `examples/host_data_adapters/` as reference implementations only.
- **News MCP/API key policy** — keys are host-owned; core never handles them.
- **Audit scripts** — `audit_project_structure.py`, `audit_dead_code.py`,
  `audit_public_api.py`, `audit_docs_links.py`, `run_all_audits.py`.
- **v0.9.0 readiness checklist** — `docs/release/v0.9.0-readiness-checklist.md`.
- **KnowledgeGraph enum-safe queries** — `KGEdgeType` comparison in graph layer.
- **`knowledge_graph_summary` artifact** — optional fund_analysis enrichment
  when holdings data supports KnowledgeGraph construction.
- **`evidence_anchor_diagnostics` artifact** — decision_support explainability.
- **`risk_constraint_conflicts` artifact** — decision_support constraint
  blocking details with cap/downgrade reasons.
- **`ledger_summary` field in ExecutionLedger** — deterministic summary of
  decisions, execution amounts, and action counts.
- **Expanded MCP harness** — dev-only fake MCP responses for all 6 capability
  types. No network, no API keys, no provider SDKs.

### Changed

- **README rewritten for pre-0.9 clarity** — removed ResearchOS/autonomous-agent-loop/LangGraph references.
- **Docs aligned around host-owned live data and no-core-network boundary** —
  17 overclaims fixed across install, design, and contract docs.
- **Report-only vs formal decision boundary clarified** — `SOFT_ACTION_ADVICE`
  alone does not force `decision_support`.
- **`src.fund_agent.*` kept as compatibility/internal path** — `fund_agent.*`
  documented as preferred public API.
- **Install docs updated to v0.9.0** — version pinning and clone examples
  reference v0.9.0.

### Safety / Boundaries

- Core runtime remains **no-network** — no provider SDK imports, no API calls.
- **No broker/order execution** — no trade placement, no order fields in
  workflow outputs.
- `fund_analysis` remains **analysis/report only** — never emits formal
  `Decision` or `ExecutionLedger`.
- `decision_support` remains the **only formal Decision / ExecutionLedger
  runtime**.
- `suggested_rebalance_plan` remains **analysis-only** — not a trade
  instruction.
- Provider adapters remain **optional host examples** — not core dependencies.
- Credentials loaded from **config/env only** — no secrets committed.
- News MCP/API keys are **host-owned** — core never handles them.

### Known Limitations

- Eastmoney adapter is **prototype**, not a production connector.
- Xueqiu adapter is **prototype**, not a production connector.
- AkShare adapter coverage is **partial**.
- **No live data fetching** in core runtime.
- **No autonomous trading**.
- **No broker execution**.
- **Not v1.0.0 stable API** yet — pre-launch baseline.

## [1.1.0] — 2026-06-11

### Added

- **KnowledgeGraph enum-safe queries** — `src/graph/queries.py` now uses
  `KGEdgeType` enum comparison instead of raw string comparison, preventing
  typos and ensuring edge-type safety across the graph layer.
- **`knowledge_graph_summary` artifact** — optional `fund_analysis` artifact
  emitted when holdings data supports KnowledgeGraph construction. Provides
  KG-derived context summarizing entity relationships, sector/theme links,
  and cross-fund overlap patterns. Emits `enabled=false` with `limitations`
  when data is insufficient; hosts always receive the artifact for
  host-friendliness. No requirement to have KG data for normal reports.
- **`evidence_anchor_diagnostics` artifact** — `decision_support` artifact
  that explains anchor validity and coverage per decision and per trade.
  Surfaces which evidence IDs were used, which were missing or weak, and the
  resulting anchor coverage ratio. Includes `trade_plan_has_active_actions`
  and `trade_plan_requires_anchor` top-level fields when trade_plan is
  present, avoiding misleading single-action diagnostics for multi-trade
  plans.
- **`risk_constraint_conflicts` artifact** — `decision_support` artifact
  that explains budget/constraint blocking with cap/downgrade details.
  Surfaces which constraints conflicted, the original requested vs capped
  execution amount, and the downgrade reason. Trade plan path now consumes
  validated trades with `cap_reasons` and `requested_amount` for accurate
  conflict reporting.
- **`ledger_summary` field in ExecutionLedger** — `ExecutionLedger.to_dict()`
  now includes a `ledger_summary` field providing a deterministic summary of
  all decisions, total execution amounts, passive/active action counts,
  blocked_by_counts, and reason_code_counts.
- **9 new user flow fixtures** — expanded scenario-specific user flow
  assertions covering KnowledgeGraph context, evidence anchor diagnostics,
  risk constraint conflicts, ledger summary validation, and an
  all-data-sufficient decision-ready scenario.
- **Expanded MCP harness** — dev-only MCP harness (`tools/dev/mcp_harness/`)
  now handles all 6 MCP→fund_analysis mappings: `financial_news`→
  `news_evidence`, `web_search`→`news_evidence`, `social_sentiment`→
  `sentiment_evidence`, `benchmark_price_history`→`benchmark_history`,
  `fund_metadata_lookup`→`fund_profiles`, `fund_fee_schedule`→
  `fee_schedules`/`redemption_rules`. No network, no API keys, no provider
  SDKs, no core runtime imports.

### Changed

- **`queries.py` now uses `KGEdgeType` enum comparison** — all edge-type
  checks in `src/graph/queries.py` compare against `KGEdgeType` enum members
  instead of raw strings, improving type safety and preventing silent
  mismatches.
- **`ExecutionLedger.to_dict()` includes `ledger_summary`** — the serialized
  ledger output now contains a `ledger_summary` field with deterministic
  counts and totals.
- **MCP harness handles all 6 capability types** — the fake MCP harness
  normalizes responses for all six capability types with priority-based
  fallback, enabling complete integration testing without live providers.
- **Single-decision `requested_amount` derived from payload** —
  `DecisionSupportSkill._run_single_decision_path` now derives the original
  requested amount from `payload.requested_amount` → `target_trade_amount` →
  `execution_amount` → `decision.execution_amount`, so
  `risk_constraint_conflicts` accurately reports the original requested
  amount vs the capped/final amount.
- **Trade plan `risk_constraint_conflicts` uses validated trades** —
  `_run_trade_plan_path` now passes `validated_trades` (with `cap_reasons`
  and `requested_amount`) instead of raw `trades` to both
  `build_evidence_anchor_diagnostics` and `build_risk_constraint_conflicts`.
- **`knowledge_graph_summary` emits `enabled=false` with limitations** —
  when positions exist but holdings data is empty or insufficient, the
  artifact now consistently emits `enabled=false` with a `limitations` list
  rather than `enabled=true` with empty stock nodes.

### Honesty

- No live provider integration was added. All MCP responses remain fake/dev-only.
- No broker/order execution exists.
- MCP live mode is documented but not implemented in v1.1.
- `fund_analysis` still does not emit formal `Decision` or `ExecutionLedger`.
- KnowledgeGraph context is optional and does not affect report output when
  holdings data is insufficient.
- `risk_budget` as a standalone constraint in `_check_single_decision_conflicts`
  is deferred; it is handled via `BUDGET_BLOCKED` evidence_state in the
  decision stage.

## [1.0.0-rc]

### Added

- **Evidence state constants module** — `src/skills_runtime/decision_support/evidence_states.py`
  provides named constants and helper functions for evidence_state semantics
  (ANCHORED, INSUFFICIENT_EVIDENCE, CRITIC_BLOCKED, CONSTRAINT_BLOCKED,
  BUDGET_BLOCKED, DOWNGRADED) with `describe_evidence_state()` documentation.
- **zh-CN report localization improvements** — additional bullet localizations
  for right-side confirmation, event hype failure, cash deployment, research
  query plan, rebalance plan, and professional diagnostics sections in
  `report_composer.py`.
- **Host integration examples** — `examples/host_integration/` with three new
  examples: `minimal_fund_analysis_runtime_call.py`,
  `minimal_decision_support_call.py`, and `full_personal_fund_workflow.json`.
- **Dev-only MCP harness** — `tools/dev/mcp_harness/` with fake MCP responses,
  normalization utilities, and README. Fake mode only; live mode is env-gated
  and not implemented in v1.
- **MCP harness integration test** — `tests/integration/test_mcp_harness_fake_mode.py`
  validates fake responses normalize correctly and can be used by fund_analysis.
- **Scenario-specific user flow assertions** — semiconductor profit protection,
  innovation drug drawdown, bond cash allocation, mixed portfolio rebalance,
  and energy loss position scenario-specific tests in
  `tests/integration/test_user_flow_scenarios.py`.
- **v1 release readiness doc** — `docs/v1-release-readiness.md` with full
  checklist, non-goals, deferred items, and validation commands.
- **MCP live testing doc** — `docs/mcp-live-testing.md` documents dev-only
  harness usage and rules.

### Changed

- **Weak test assertions hardened** — replaced bare `assert x is not None`
  with `assert isinstance(x, dict)` and structural checks in
  `test_fund_analysis_professional_diagnostics.py`,
  `test_fund_analysis_phase3.py`, `test_ledger_tools.py`, and
  `test_runtime_skill_surface.py`.
- **README updated** — added v1 artifacts table, data boundary section,
  test gates, and release readiness status.
- **Trade plan gatekeeper** — already implemented: `_decision_from_trade`
  calls `evaluate_gatekeeper` and applies downgrades with reason_codes,
  blocked_by, evidence_state, trigger_conditions, invalidating_conditions,
  and audit_trail.

### Honesty

- No live-data fetching was added to core runtime.
- No broker/order execution exists.
- OpenCode plugin does not launch Python runtime.
- fund_analysis does not emit formal Decision or ExecutionLedger.
- MCP live mode is documented but not implemented in v1.

## 0.4.9-dev-end-to-end-personal-fund-flow

### Added

- **End-to-end report flow** — `examples/minimal_personal_fund_report_flow.py`
  demonstrates the canonical report-only path: host data →
  `FundAnalysisSkill` → `report_sections` → `render_report_markdown()`.
  Supports `--output` for Markdown file output. No network, no provider SDKs,
  no formal decisions.
- **Decision handoff example** — `examples/minimal_personal_fund_report_with_decision_handoff.py`
  extends the report flow with optional `DecisionSupportSkill` handoff via
  `--with-decision`. Clearly separates analysis output from formal decisions.
- **Integration tests** — `tests/integration/test_personal_fund_report_flow.py`
  (8 tests): deterministic output, required section titles, no Decision/
  ExecutionLedger in markdown, data_completeness/coverage/gate present.
- **Example tests** — `tests/examples/test_personal_report_flow_examples.py`
  (6 tests): no-network validation, `--output` file writing, invalid-input
  handling, decision handoff semantics.
- **Doc consistency tests** — `tests/docs/test_personal_report_flow_docs.py`
  (6 tests): docs mention report-only flow, decision handoff, report_sections,
  and do not overclaim OpenCode plugin capabilities.

### Changed

- `scripts/check_examples.py` — validates both new flow scripts as demos (6 total).
- `docs/workflows/personal-fund-report.md` — added quick-start end-to-end
  flow section with CLI examples.
- `AGENTS.md` — added end-to-end report flow examples to Minimal Example
  section.

## 0.4.8

### Release Summary

**Host-owned data capability catalog** — 15 capability contracts in
`skillpack/capabilities.yaml` defining the host-data interface for fund
profiles, NAV history, holdings, transactions, fees, benchmarks, peer
groups, manager profiles, fund flows, macro events, and more.

**Portfolio ledger snapshot core** — `src/tools/portfolio/ledger_snapshot.py`
provides deterministic transaction-to-position-snapshot tools including
event normalization, settlement rules, PnL calculation, and
portfolio-ledger reconciliation. Weighted-average cost basis is default.

**Derived portfolio mode** — `FundAnalysisSkill` accepts
`transactions` + `current_nav` + `as_of_date` as an alternative to
`portfolio.positions`. Automatic reconciliation when both exist.

**Runtime bridge CLI** — `scripts/run_skill.py` provides a thin,
host-invoked JSON CLI bridge: skill listing, capability discovery, skill
execution with JSON stdin/stdout. No server, no daemon, no provider SDKs.

**Dependency boundary cleanup** — `requirements.txt` minimal (`pyyaml` only);
provider SDKs moved to `requirements-legacy.txt`. Default install does not
pull Tavily, Finnhub, Exa, Firecrawl, Reddit, AkShare, OpenAI, Anthropic,
or LangChain.

**Report quality core** — `src/tools/portfolio/report_quality.py`:
`calculate_data_completeness()` (score 0-1, grade A-D),
`summarize_analysis_coverage()` (per-section availability),
`build_report_limitations()` (user-facing caveats). All deterministic.

**Deterministic report composer** — `src/tools/portfolio/report_composer.py`:
`compose_personal_fund_report()` produces 15 ordered `report_sections`
with `id/title/status/bullets/data_sources/limitations`, `report_outline`,
and `report_quality_gate`. `render_report_markdown()` for default UX.

**Enhanced optional summaries** — Benchmark comparison, peer ranking
extraction, fee schedule analysis, redemption constraint warnings, factor
concentration detection, manager change-risk flags. All host-data-driven;
no rankings or comparisons fabricated.

**Report output contract v1** — `docs/contracts/report-output-contract.v1.md`
defines the stable shape of report composer output, status semantics,
Markdown rendering contract, and decision boundary.

**Documentation and consistency** — 22 doc consistency tests, AGENTS.md
cleanup (removed duplicate, added report contract pointers), stale doc
wording fixed (host-compatibility, runtime-bridge design), skill-io-examples
updated with full report composer output shape.

### Detailed changelog

## 0.4.8-dev-data-contract-and-portfolio-ledger-core (development)

### Added

- **Host-owned data capability catalog** — 15 new host-owned capability
  contracts defined in `skillpack/capabilities.yaml`:
  `fund_profile`, `fund_nav_history`, `fund_holdings`,
  `fund_transactions`, `fund_fee_schedule`, `fund_benchmark`,
  `benchmark_history`, `fund_peer_group`, `fund_manager_profile`,
  `fund_flow`, `index_constituents`, `macro_events`,
  `market_calendar`, `portfolio_snapshot`, `user_investment_plan`.
  Each includes purpose, required_by, input/output shape, missing
  behavior, and canned test examples. All are host-owned; fund-agent
  does not fetch them directly.
- **Portfolio ledger snapshot core** — `src/tools/portfolio/ledger_snapshot.py`
  provides deterministic transaction-to-position-snapshot tools:
  `normalize_transaction_events`, `build_position_snapshot_from_transactions`,
  `reconcile_snapshot_with_portfolio`, `calculate_realized_unrealized_pnl`,
  `apply_settlement_rules`. No network calls, all JSON-serializable.
  Weighted-average cost basis is the default.
- **Derived portfolio mode** — `FundAnalysisSkill` now accepts
  `transactions` + `current_nav` + `as_of_date` as an alternative to
  `portfolio.positions`. When both exist, a ledger-portfolio reconciliation
  runs automatically. New artifacts: `derived_portfolio_snapshot`,
  `ledger_cashflow_summary`, `ledger_reconciliation_report`.
- **Research query planning** — `src/tools/research/query_plan.py`
  provides `build_research_query_plan` for deterministic query planning
  from portfolio positions, holdings, themes, and industries. Sets
  `research_planning: true` in the payload to trigger. No network calls
  or provider imports. Outputs include news_queries, sentiment_queries,
  entities, themes, industries, and required_capabilities.
- **Optional data pass-through** — Benchmarks, peer groups, factor
  exposures, manager profiles, fee schedules, and redemption rules are
  accepted as optional host-provided payload fields and passed through
  to the fund_analysis_report. Minimal summarization helpers included
  (`summarize_benchmark_gap`, `summarize_fee_schedule`, etc.).
- **New runtime bridge examples**:
  `examples/runtime_bridge_ledger_snapshot_input.json` (derived mode),
  `examples/runtime_bridge_research_query_plan_input.json` (query planning).
- **Tests**: 27 ledger_snapshot tests, 10 query_plan tests, 8 derived
  portfolio tests, 6 runtime bridge tests for new examples, 10 data
  capability documentation consistency tests.

### Changed

- FundAnalysisSkill `run()` restructured to support three portfolio modes:
  host-provided, derived-from-transactions, and hybrid with reconciliation.
- Evidence specs now include `derived_portfolio_snapshot` and
  `ledger_reconciliation_mismatch` when applicable.
- `skillpack/fund-agent.skillpack.yaml` tools section includes new
  ledger snapshot and query plan tools.

### Ledger and Capability Hardening (v0.4.8-dev)

- **Formalized transaction event semantics** with explicit policies:
  TRANSFER_OUT has no realized PnL (use SELL if needed),
  TRANSFER_IN is not a cashflow event, FEE is a realized expense (not
  capitalized), BUY/SELL with amount-only is marked unresolved.
- **Invalid event quarantine**: unknown actions marked `valid=false`
  and skipped in PnL calculation; unresolved events tracked in output.
- **Snapshot sanity**: negative shares/cost clamped with warnings.
- **Reconciliation hardening**: configurable tolerances
  (`shares_tolerance`, `value_tolerance`), mismatch severity field
  (`ok`, `low`, `medium`, `high`).
- **Capability discovery**: `--list-capabilities` and
  `--describe-capability NAME` added to runtime bridge CLI.
  Outputs JSON only, reads `skillpack/capabilities.yaml`.
- **Query plan improvements**: deduplication, sorting by value/weight
  descending, `per_fund_holding_limit`, `query_budget_summary` with
  dropped counts, deterministic prioritization.
- **Cashflow hardening**: TRANSFER_IN/TRANSFER_OUT no longer counted
  as cashflow events (position movements only).
- **Documentation**: transaction semantics added to input-contract.md,
  capability discovery documented in runtime-bridge-cli.md.

### Report Quality and Completeness (v0.4.8-dev)

- **Report quality core** — `src/tools/portfolio/report_quality.py`:
  `calculate_data_completeness()` (score 0.0-1.0, grade A-D),
  `summarize_analysis_coverage()` (per-section availability),
  `build_report_limitations()` (user-facing caveats). All deterministic,
  no network, no provider SDKs.
- **Enhanced FundAnalysisSkill report artifact** — `fund_analysis_report`
  and artifacts now include `data_completeness`, `analysis_coverage`,
  and `report_limitations`. Optional summary functions enhanced:
  benchmark comparison, peer ranking extraction, fee schedule analysis,
  redemption constraint warnings, factor concentration detection,
  manager change-risk flags. All optional summaries are host-data-driven;
  no rankings, comparisons, or attributions are fabricated.
- **Enhanced status semantics** — `OK` only when data completeness is
  grade A or B and no errors; `PARTIAL` when grade C/D, derived ledger
  has unresolved events, or optional data requested but missing.
  Warning categories: MISSING_DATA, LEDGER_PARTIAL, OPTIONAL_ANALYSIS_UNAVAILABLE.
- **New example**: `examples/runtime_bridge_personal_report_quality_input.json`
  — complete payload with all optional data sections for full report quality
  demonstration.
- **Tests**: 16 report quality tool tests, 12 skill integration tests,
  5 runtime bridge example tests.
- **Documentation**: Report quality sections added to plugin-api.md,
  personal-fund-report.md, host-integration.md, runtime-bridge-cli.md,
  and all skill reference docs (SKILL.md, input-contract.md,
  report-template.md, missing-data-policy.md).

### Report Quality Hardening and Composer (v0.4.8-dev)

- **Hardened completeness semantics** — `calculate_data_completeness()`
  now uses explicit required and optional report data groups, distinguishes
  current value / current NAV availability, treats missing portfolio data as
  critical, lowers grade for incomplete derived ledgers, and keeps output order
  deterministic.
- **Deterministic personal report composer** —
  `src/tools/portfolio/report_composer.py` adds
  `compose_personal_fund_report()` and `render_report_markdown()`. The composer
  turns existing `FundAnalysisSkill` artifacts into 15 structured
  host-displayable sections plus `report_outline` and `report_quality_gate`.
  It is JSON-serializable and does not call providers, network, LLMs, or
  decision support.
- **FundAnalysisSkill integration** — `fund_analysis_report` and top-level
  artifacts now include `report_sections`, `report_outline`, and
  `report_quality_gate` alongside `data_completeness`, `analysis_coverage`,
  and `report_limitations`.
- **No-fabrication hardening** — optional benchmark, peer, manager, fee,
  redemption, and factor summaries surface only host-provided facts. Missing
  optional data produces `PARTIAL`/`MISSING` report sections and limitations,
  not invented comparisons, rankings, manager stability, fees, or liquidity
  facts.

### Report Contract and Doc Consistency (v0.4.8-dev)

- **Report output contract** — `docs/contracts/report-output-contract.v1.md`
  defines the stable shape of `report_sections`, `report_outline`,
  `report_quality_gate`, Markdown rendering, decision boundary, and
  stability guarantees.
- **Contract tests** — `tests/contracts/test_report_output_contract_v1.py`
  (19 tests) asserts section IDs/order, required keys, status enum,
  outline mirroring, quality gate shape, Markdown rendering, JSON
  serialization, and decision boundary.
- **Stale doc cleanup** — Updated `AGENTS.md` (removed duplicate line,
  added report contract pointers, fixed stale version tags, corrected
  runtime bridge status), `docs/host-compatibility.md` (removed v0.4.6
  stale references, corrected runtime bridge availability),
  `docs/design/runtime-bridge.md` (all v0.4.7-dev → v0.4.8-dev),
  `docs/skill-io-examples.md` (full report composer output shape with
  report_sections/outline/gate/completeness/coverage/limitations).
- **Doc consistency tests** — 22 new tests across
  `test_skill_io_examples_current.py`, `test_agent_docs_current.py`,
  `test_host_compatibility_current.py`.

## 0.4.7-dev-runtime-bridge-hardening

### Changed

- Runtime bridge MCP resolution now unions the manifest
  `requires_mcp` declaration with the host's
  `SkillInput.required_mcp_capabilities` to compute the
  **effective required MCP set**. Skills like `news_research` and
  `sentiment_analysis` no longer silently lose their manifest
  requirements when the host passes a convenience `{"payload":
  {...}}` envelope without `required_mcp_capabilities`.
- Bridge output envelope metadata now always includes
  `required_mcp_capabilities` and `missing_mcp_capabilities`,
  even when the skill has no MCP requirements. The keys are
  always present so hosts can rely on them.
- `_emit_envelope` returns exit code **2** whenever the
  `JSON_SERIALIZATION_FAILED` fallback fires, even if the
  original envelope had `ok=true`. A non-serializable output is
  a bridge-level failure regardless of skill intent.
- Bridge-level error code `MISSING_MCP_CAPABILITY` is now
  included in `BRIDGE_ERROR_CODES` and downgrades `ok` to
  `false` whenever at least one required MCP capability is
  missing — including cases where the embedded skill returned
  `FAILED` with its own `MISSING_MCP_CAPABILITY` error.
- `opencode.plugin.js` top-of-file comments are now
  version-neutral; the runtime version constant
  `PLUGIN_VERSION` remains the single source of truth.

### Added

- `tests/runtime_bridge/test_runtime_bridge_mcp_capabilities.py`
  — 8 tests covering: manifest requires_mcp surfacing for
  `news_research` and `sentiment_analysis`, canned MCP
  round-trip, convenience input without `required_mcp_capabilities`
  still respecting manifest requirements, host-added
  capabilities extending the union, no-synthetic-missing for
  `fund_analysis`, and `JSON_SERIALIZATION_FAILED` exit code 2
  semantics.
- `tests/runtime_bridge/test_runtime_bridge_output_contract.py`
  — 7 golden-ish contract tests for the bridge envelope shape,
  metadata keys, and the no-traceback-on-stdout property.
- `tests/docs/test_runtime_bridge_doc_consistency.py` — 6
  doc consistency tests for the runtime bridge CLI doc and
  the install matrix (`docs/install/runtime-bridge-cli.md`,
  `.opencode/INSTALL.md`, `docs/install/opencode.md`).

### Documented

- `docs/install/runtime-bridge-cli.md` now has an explicit
  "Install (source checkout only)" section. The runtime bridge
  is **git-clone-only** in v0.4.7-dev; the npm package
  (Mode A: plugin + skill docs) does **not** ship
  `scripts/run_skill.py`, `src/skillpack/run_skill.py`, or the
  runtime bridge examples.
- `docs/release-checklist.md` adds a "v0.4.7-dev hardening
  additions" subsection.
- `docs/design/runtime-bridge.md` reframes the "Why the
  runtime bridge is still future" section to acknowledge the
  thin CLI bridge is shipped and only the **deeper** bridge
  is still future.
- `CHANGELOG.md` adds this section.

## 0.4.7-dev-runtime-bridge-cli

### Added

- `src/skillpack/run_skill.py` — runtime bridge module. A thin local
  JSON-in / JSON-out Python shim over the existing manifest runtime
  skills. Resolves runtime classes from
  `skillpack/fund-agent.skillpack.yaml` via
  `src.skillpack.loader.resolve_runtime`. Does not import provider
  SDKs, does not call the network, does not run an agent loop, and
  does not become a daemon or server. For skills that require MCP,
  the bridge accepts an in-memory `mcp_responses` block in the
  input JSON; it never spawns subprocesses for handlers. The host
  owns the actual provider calls.
- `scripts/run_skill.py` — thin CLI wrapper that delegates to
  `src.skillpack.run_skill`. Supports:
  - `python scripts/run_skill.py --skill fund_analysis --input payload.json`
  - `python scripts/run_skill.py --skill fund_analysis --input - < payload.json`
  - `python scripts/run_skill.py --skill fund_analysis --input payload.json --output output.json`
  - `python scripts/run_skill.py --skill fund_analysis --input payload.json --pretty`
  - `python scripts/run_skill.py --list-skills`
  - `python scripts/run_skill.py --manifest path/to/manifest.yaml --list-skills`
  Stdout is JSON only. Diagnostics go to stderr. Exit code 0 means
  the bridge itself succeeded; the embedded skill status is
  reported in the JSON envelope. Bridge-level error codes:
  `INVALID_INPUT`, `UNKNOWN_SKILL`, `RUNTIME_LOAD_FAILED`,
  `SKILL_RUN_FAILED`, `JSON_SERIALIZATION_FAILED`,
  `MISSING_MCP_CAPABILITY`.
- `examples/runtime_bridge_fund_analysis_input.json` — minimal
  convenience input for `fund_analysis`.
- `examples/runtime_bridge_decision_support_input.json` — minimal
  convenience input for `decision_support` with a one-evidence
  graph fixture.
- `examples/minimal_runtime_bridge_fund_analysis.py` — minimal
  host demo that spawns the bridge CLI from Python and parses the
  JSON envelope.
- `docs/install/runtime-bridge-cli.md` — install / usage guide for
  the runtime bridge CLI, including the JSON-in / JSON-out
  contract, MCP boundary behavior, and the relationship to the
  existing manifest, plugin, and design doc.
- `tests/runtime_bridge/test_run_skill_cli.py` — 11 CLI tests
  covering `--list-skills`, fund_analysis happy path, `--output`,
  `--pretty`, invalid JSON, unknown skill, and stdout-is-JSON-only.
- `tests/runtime_bridge/test_runtime_bridge_manifest_resolution.py`
  — 7 tests covering manifest resolution, hyphen-slug convenience,
  underscore runtime_id, no-legacy-imports, and
  no-provider-SDK-imports.
- `tests/runtime_bridge/test_runtime_bridge_no_network.py` — 5
  tests guarding the no-network contract: no provider SDKs, no
  `requests` / `httpx` / `urllib.request`, no subprocess, no
  `opencode.plugin.js` reference, and a live end-to-end
  invocation that must not touch the network.
- `tests/runtime_bridge/test_runtime_bridge_decision_support.py`
  — 5 tests covering DecisionSupportSkill via the bridge:
  minimal evidence graph, JSON-serializable output, deterministic
  mode, hyphen slug, and stdin input.
- `tests/runtime_bridge/test_runtime_bridge_examples.py` — 6
  tests pinning the documented example commands and
  `examples/minimal_runtime_bridge_fund_analysis.py`.

### Changed

- `VERSION`, `pyproject.toml`, `skillpack/fund-agent.skillpack.yaml`,
  `package.json`, and `opencode.plugin.js` `PLUGIN_VERSION` bumped
  to `0.4.7-dev` (the v0.4.6 tag is preserved at the v0.4.6
  commit; this is post-tag development).
- `scripts/check_examples.py` adds the runtime bridge example
  inputs to its validation pass and registers
  `examples/minimal_runtime_bridge_fund_analysis.py` as a demo
  script.
- `pyproject.toml` `testpaths` includes `tests/runtime_bridge` so
  the new test directory is part of the default gate.
- `tests/install/test_npm_pack_contents.py` and
  `tests/install/test_opencode_plugin_skeleton.py` now read the
  canonical `VERSION` file at test time rather than pinning a
  literal version string. The contract — "the npm pack version
  equals the canonical VERSION" — is preserved; the test is now
  forward-compatible with dev tags.
- `tests/install/test_install_docs_no_overclaim.py` and
  `tests/install/test_no_node_dependency_bloat.py` version
  references updated to be version-neutral or current.
- `docs/design/runtime-bridge.md` is now positioned as the
  "deeper" / future runtime-bridge design (subprocess handlers,
  OpenCode plugin tool wrapper). The thin CLI shipped in
  v0.4.7-dev is the implementation of a subset of the full design.
- `docs/release-checklist.md` adds a v0.4.7 section.

### Honesty

- The runtime bridge is a **thin CLI shim**, not an agent loop, not
  a server, not a daemon, not a planner, not a provider
  integration.
- The bridge **does not fetch data**. For MCP-requiring skills, the
  bridge returns a clear PARTIAL/FAILED envelope explaining the
  host-owned MCP requirement when no `mcp_responses` block is
  supplied.
- The bridge **does not import provider SDKs** (Tavily, Finnhub,
  Exa, Firecrawl, Reddit, AkShare, OpenAI, Anthropic, LangChain).
- The bridge **does not shell out to OpenCode**, does not call
  `opencode.plugin.js`, and does not import `@opencode-ai/plugin`.
- The bridge is **host-agnostic**; it does not know whether the
  caller is OpenCode, Codex, Claude Code, OpenClaw, Hermes, or a
  custom CLI.
- The bridge **does not change the existing Python runtime**. It
  resolves runtime classes from the manifest and calls them via
  their existing `run(skill_input)` API.
- Only `decision_support` may produce formal `Decision` and
  `ExecutionLedger` artifacts; the bridge does not relax this.
- `opencode.plugin.js` still does **not** call Python, does **not**
  spawn subprocesses, does **not** fetch data, and does **not** run
  providers. The plugin and the bridge are independent surfaces.
- No new fund metrics, no new portfolio tools, no new schemas, no
  new runtime contracts, no new MCP providers, no autonomous loop.
- All v0.4.6 install-packaging-smoke items still pass.

## 0.4.6-install-packaging-smoke

### Added

- `tests/install/test_npm_pack_contents.py` — 6 assertions that
  `npm pack --dry-run --json` produces a tarball containing the
  five canonical `skills/<slug>/SKILL.md` files and the three
  install docs, and does **not** contain `legacy/`,
  `docs/archive/fund-analyst/`, `tests/`, `scripts/` (Mode B
  helper), `.opencode/INSTALL.md`, `__pycache__/`, `*.pyc`, or
  `__init__.py` (stale Python leftovers in `skills/`). Skipped if
  `npm` is not on the test host.
- `tests/install/test_opencode_native_install_tree.py` — 6
  assertions that simulate a fresh project-local install. The
  test creates `<project>/.opencode/skills/`, runs the sync
  helper, and asserts: the install tree contains exactly the five
  canonical skills, each `SKILL.md` has a YAML frontmatter with
  `name: <slug>` and a non-empty `description`, `references/` is
  copied where the source has it, no underscore runtime dirs are
  written, no archived `fund-analyst` is written, no
  `__pycache__/` / `*.pyc` / `__init__.py` files are written, the
  marker file lists exactly the five canonical skills, `--clean`
  removes only the generated skills (user-authored files are
  preserved), and the install is idempotent.
- `tests/install/test_opencode_plugin_runtime_smoke.py` — 11
  assertions that exercise the OpenCode plugin's helper functions
  through a dynamic-import test harness: `node --check` succeeds,
  the plugin is dynamically importable, `listSkills()` returns
  `primary_skill == "fund-analysis"`, exactly four
  `supporting_skills`, and a `skills` array of length 5,
  `readSkillDoc` accepts `fund-analysis` and rejects
  `fund_analysis`, `decision_support`, `fund-analyst`, and
  `../README.md` (path-traversal), `runtimeHint` accepts both
  `fund-analysis` and `fund_analysis`, and the startup log does
  not classify `fund-analysis` as a supporting skill.
- `tests/docs/test_install_mode_consistency.py` — cross-doc
  consistency assertions for the install docs. Both
  `.opencode/INSTALL.md` and `docs/install/opencode.md` must
  mention Mode A / Mode B / Mode C, must say Mode C is a future
  runtime bridge, must say the plugin does not shell out to
  Python, must say the Mode B sync helper is a plain file copy,
  must mention `fund-analysis` as primary and the four supporting
  slugs explicitly, and must not contain `skills//SKILL.md`
  placeholders or claim the npm package is published.
- `description:` field in the YAML frontmatter of all five
  canonical `skills/<slug>/SKILL.md` files. Each description is a
  single-quoted, non-empty scalar that captures the skill's
  role, MCP requirements (if any), and produced artifacts. This
  satisfies the OpenCode Agent Skills frontmatter contract that
  requires a `description` for native skill discovery.

### Changed

- `package.json` `files` field is now an explicit whitelist with
  negation patterns: includes `opencode.plugin.js`, `skillpack/`,
  `skills/`, and `docs/install/`; excludes `__pycache__/`,
  `*.pyc`, `*.pyo`, and `__init__.py` from the `skills/`
  subtree. The resulting `npm pack` tarball is a clean
  Mode-A-only install surface (plugin + skill docs + install
  docs) with no Python build artifacts, no tests, no archive
  material, and no Mode B helper. Verified by
  `tests/install/test_npm_pack_contents.py`.
- `.opencode/INSTALL.md` and `docs/install/opencode.md` updated to
  document three install modes consistently: **Mode A** (the
  plugin, Mode A only, npm-shipped), **Mode B** (native Agent
  Skills sync via `scripts/install_opencode_skills.py`,
  git-clone-only), and **Mode C** (future runtime bridge, design
  only). `.opencode/INSTALL.md` adds an explicit
  "Install modes (Mode A / Mode B / Mode C)" section and a
  "Package contents — npm vs git" section that states the npm
  package is Mode A only and the Mode B helper is
  git-clone-only.
- `docs/install/codex.md` and `docs/install/manual-host.md` and
  `docs/install/opencode.md` version references updated from
  `v0.4.4` / `v0.4.5` to `v0.4.6`.
- `docs/design/runtime-bridge.md` version references updated
  from `v0.4.5` to `v0.4.6` (the design is still not
  implemented).
- `VERSION`, `pyproject.toml`, `skillpack/fund-agent.skillpack.yaml`,
  `package.json`, and `opencode.plugin.js` `PLUGIN_VERSION` all
  advanced to `0.4.6`.
- `tests/install/test_opencode_plugin_skeleton.py`
  `PLUGIN_VERSION` assertion bumped to `0.4.6`.
- `tests/install/test_install_docs_no_overclaim.py`
  runtime-bridge design doc assertion now accepts `v0.4.4`,
  `v0.4.5`, or `v0.4.6` in the doc text (forward-compatible; the
  contract — "runtime bridge is not implemented in the current
  release" — is unchanged).
- `docs/release-checklist.md` adds a "v0.4.6 Install Packaging
  Smoke" section.

### Honesty

- The v0.4.6 milestone is **purely about install packaging and
  the install-side smoke test surface**. No new domain features,
  no new schemas, no new providers, no new tools, no new
  Python runtime bridge.
- The npm package is **declared but not yet published**. The
  install still works end-to-end via the project-local symlink
  path. The npm convenience install is a future milestone.
- The npm package is **Mode A only**. A user who installs the
  npm package and also wants Mode B (native `Agent Skills`
  directory copy) must run `scripts/install_opencode_skills.py`
  from a git clone of the repo, not from the npm package. This
  split is intentional and is documented in
  `.opencode/INSTALL.md` and `docs/install/opencode.md`.
- No provider SDKs, no LLM clients, no autonomous loop, no
  autonomous agent loop, no runtime bridge, no database, no server, no
  autonomous agent runtime.
- All v0.4.5 install-hardening items (Mode A vs Mode B vs Mode C
  docs, plugin startup log primary / supporting distinction,
  sync helper safety) are still in place and still pass.

## 0.4.5-native-skill-install-hardening

### Added

- `.gitattributes` enforcing LF line endings for `*.sh`, `*.yml`,
  `*.yaml`, `*.toml`, `*.json`, `*.js`, `*.py`, `*.md`, with `text=auto`
  as the default. This is a regression guard for the v0.4.4 zip
  extraction issue where `scripts/check_plugin_gate.sh` shipped with
  CRLF line endings even though the git index was LF.
- `scripts/install_opencode_skills.py` — Mode B of the OpenCode
  install. Copies the five canonical hyphenated skill directories
  from `skills/` into `.opencode/skills/<slug>/SKILL.md` so OpenCode's
  native `Agent Skills` discovery sees the same five skills as the
  plugin. Supports `--dry-run`, `--target <path>`, and `--clean`
  (which only removes the skills this script wrote, identified by
  the marker file `.opencode/skills/.fund-agent-generated.json`).
  Does not edit `opencode.json`, does not start a subprocess, does
  not install the Python runtime, and does not call any network.
- `tests/ci/test_line_endings.py` — file-level CRLF guard for
  `scripts/check_plugin_gate.sh`, `.github/workflows/*.yml`,
  `opencode.plugin.js`, canonical `skills/<slug>/SKILL.md`, and
  canonical `skills/<slug>/references/*.md`. The test does not
  depend on git and catches CRLF even if the renormalize step is
  bypassed.
- `tests/install/test_opencode_native_skill_sync.py` — 12 tests
  covering dry-run output, apply output, copied `SKILL.md`
  frontmatter, references preservation, refusal to copy
  `fund-analyst` and underscore runtime IDs, marker file behavior,
  and `--clean` safety.
- Four new tests in `tests/install/test_opencode_skill_surface.py`
  guarding the startup log primary / supporting distinction: the
  log message text must not list `fund-analysis` under
  `supporting skills:`, the structured `extra` payload must split
  primary from supporting, and `listSkills().supporting_skills`
  must equal exactly the four canonical supporting slugs.

### Changed

- `opencode.plugin.js` startup log message now correctly splits
  the primary skill from the four supporting skills. v0.4.4 had a
  bug where the message joined all five slugs into the
  `supporting skills:` clause; v0.4.5 filters by `role ===
  "supporting"` and asserts the distinction via tests. The plugin
  exports a new `buildStartupLogMessage()` helper for testability.
- `.opencode/INSTALL.md` and `docs/install/opencode.md` updated to
  use the corrected startup log example and to document three
  install modes: Mode A (plugin metadata + doc-reader, current
  target), Mode B (native `Agent Skills` install via the sync
  helper, optional), and Mode C (future runtime bridge, design
  only). The docs now distinguish OpenCode **plugins** (the JS
  module loaded via `opencode.json`) from OpenCode **Agent Skills**
  (`SKILL.md` directories under `.opencode/skills/<slug>/`).
- `docs/install/opencode.md` and `.opencode/INSTALL.md` version
  pinning examples updated to `v0.4.5`.
- `docs/design/runtime-bridge.md` updated to reference v0.4.5
  (the design is still not implemented).
- `VERSION`, `pyproject.toml`, `skillpack/fund-agent.skillpack.yaml`,
  `package.json`, and `opencode.plugin.js` `PLUGIN_VERSION` all
  advanced to `0.4.5`.
- `tests/install/test_opencode_plugin_skeleton.py` PLUGIN_VERSION
  assertion bumped to `0.4.5`.
- `tests/install/test_install_docs_no_overclaim.py` runtime-bridge
  design doc assertion accepts `v0.4.4` or `v0.4.5` (forward-
  compatible; the contract — "runtime bridge is not implemented in
  the current release" — is unchanged).
- `scripts/install_opencode_skills.py` is executable
  (`chmod +x`).

### Honesty

- Mode A is **plugin metadata + doc-reader only**; it does not
  invoke the Python runtime and does not call any network.
- Mode B is a **plain file copy**; it does not start a subprocess,
  does not edit `opencode.json`, does not install the Python
  runtime, and does not call any network. The marker file is the
  only state it writes outside the copied skill files.
- Mode C is **design only**, not implemented in v0.4.5.
- No provider SDKs, no LLM clients, no autonomous loop, no
  autonomous agent loop, no new fund metrics, no new schemas, no new
  portfolio tools, no new providers, no runtime bridge, no
  database, no server, no autonomous agent runtime.
- No runtime / domain feature changes. The v0.4.5 milestone is
  purely about install-surface hardening and OpenCode install
  honesty (Mode A vs Mode B).

## 0.4.4-superpowers-compatible-skill-surface

### Changed

- Skill surface is now a **Superpowers-compatible composable
  Markdown collection**: one hyphenated `skills/<slug>/SKILL.md`
  directory per skill, with the directory name matching the
  frontmatter `name` field.
- `fund-analysis` is the **primary / default skill**. For ordinary
  user requests like `分析下我的基金给出报告`, load `fund-analysis`
  first. It alone is sufficient for a report-only flow.
- `decision-support`, `news-research`, `sentiment-analysis`, and
  `thesis-generation` are **supporting skills**. They are loaded
  only when the subtask description matches the supporting skill
  and only after the primary skill (or equivalent evidence) is in
  scope. `decision-support` remains the only skill that may produce
  a formal `Decision` / `ExecutionLedger`.
- `skills/fund-analysis/SKILL.md` now has a "Default entrypoint"
  section and a "When to load supporting skills" table.
- Each supporting `SKILL.md` has a "supporting skill" preamble that
  states the policy: `decision-support` is only for actionable trade
  decisions after an `EvidenceGraph` exists, `news-research` and
  `sentiment-analysis` are host/MCP-backed evidence skills with no
  direct provider SDK calls, and `thesis-generation` produces a
  `thesis_draft` artifact only and must not produce formal decisions.
- Python runtime IDs remain underscore names in the manifest and
  Python (`fund_analysis`, `decision_support`, `news_research`,
  `sentiment_analysis`, `thesis_generation`). External hosts should
  pass the underscore runtime ID to `fund_agent_runtime_hint` and to
  `SkillInput(skill_name=...)`.

### Removed

- Underscore skill directories deleted: `skills/fund_analysis/`,
  `skills/news_research/`, `skills/sentiment_analysis/`,
  `skills/thesis_generation/`. They are not part of the
  v0.4.4+ surface and are not exposed by the OpenCode plugin.
- Legacy persona directory `skills/fund-analyst/` moved to
  `docs/archive/fund-analyst/`. It is archived legacy reference
  material, not a runtime skill, not installed, and not discovered.
- `tests/skills/test_skill_classes.py` removed (it tested the
  legacy underscore skill classes that have been removed).

### Plugin

- The OpenCode plugin now exposes the **five hyphenated Markdown
  doc slugs** as agent-facing skill names: `fund-analysis` (primary)
  + `decision-support`, `news-research`, `sentiment-analysis`,
  `thesis-generation` (supporting).
- `fund_agent_skills` returns `primary_skill`, `supporting_skills`,
  and per-skill `role` metadata.
- `fund_agent_skill_doc` accepts **hyphenated slugs only** and
  rejects underscore skill slugs and the archived `fund-analyst`
  persona.
- `fund_agent_runtime_hint` accepts either a hyphenated agent-facing
  slug **or** an underscore Python runtime ID; both resolve to the
  same Python runtime class path.
- `VERSION`, `pyproject.toml`, `skillpack/fund-agent.skillpack.yaml`,
  and `package.json` all advanced to `0.4.4`.

### Honesty

- No provider SDKs, no LLM clients, no autonomous loop, no
  subprocess spawn, no autonomous agent loop. The host-agnostic architecture
  constraints are preserved.
- No runtime / domain feature changes. The new milestone is purely
  about the agent-facing skill surface and the install surface.

## 0.4.3-installable-skillpack

### Added

- OpenCode project-local plugin install: `package.json` at the repo
  root + `opencode.plugin.js` plugin entrypoint + `.opencode/INSTALL.md`
  + `docs/install/opencode.md`. The plugin is a metadata + doc reader
  only; it registers `fund_agent_skills`, `fund_agent_skill_doc`, and
  `fund_agent_runtime_hint` tools and does not run an autonomous loop.
- Manual / Python host install documented at
  `docs/install/manual-host.md`. The canonical install path for any
  Python host.
- Codex install (manual / light) at `docs/install/codex.md`. No
  OMO-style installer in v0.4.3.
- Future runtime bridge design at `docs/design/runtime-bridge.md`.
  Document-only, not implemented.
- New `tests/install/` package with 55 installability tests covering
  `package.json` metadata, the OpenCode plugin skeleton (syntax +
  no-network + no-provider-SDK invariants), install docs honesty, and
  manifest-runtime-id-to-doc-slug mapping consistency.

### Changed

- `VERSION`, `pyproject.toml`, `skillpack/fund-agent.skillpack.yaml`,
  and `package.json` all advanced to `0.4.3`.
- `scripts/check_plugin_gate.sh` now runs `tests/install` after the
  install smoke suite.
- `pyproject.toml` `tool.pytest.ini_options.testpaths` includes
  `tests/install`.
- `tests/docs/test_skill_doc_quality.py` canonical-docs list now
  includes the new install docs and runtime-bridge design doc.

### Honesty

- The OpenCode install is **metadata + docs only**. The Python runtime
  is host-driven; the plugin does not invoke skills or fetch data.
- The runtime bridge is **not** in v0.4.3. The design is documented for
  a future milestone.
- No provider SDKs, no LLM clients, no autonomous loop. The
  host-agnostic architecture constraints are preserved.

## 0.4.2-skill-md-first

### Added
- Markdown-first skill architecture documentation under `skills/README.md`
- Canonical hyphenated SKILL.md workflow guides for all manifest skills
- Fund analysis policy references for inputs, reports, risk, missing data, DCA,
  short-term trade budgets, market scenarios, and examples
- Decision support references for evidence anchors, WAIT/HOLD, execution amount
  caps, deterministic mode, contracts, and examples
- Host workflow guide for `分析下我的基金给出报告`
- Documentation policy tests for skill docs and directory naming

### Changed
- Project docs now state that the manifest is the discovery entrypoint and
  `skills/<slug>/SKILL.md` is the agent-facing policy layer
- Underscore `skills/` directories are documented as compatibility-only
- `fund-analyst` is explicitly marked legacy/reference-only

## 0.4.1-personal-portfolio-advisor-core

### Added
- Extended portfolio analysis tools (PnL, cost_basis, DCA review, trade budget)
- Transaction/cost basis schemas and tools (weighted-average cost basis)
- Fund NAV extended metrics (period returns, momentum, risk-adjusted score)
- Multi-leg trade plan generation with deterministic ranking
- 5 realistic personal portfolio example JSON payloads
- 38 new tests across tools, skills, and integration
- docs/host-compatibility.md host compatibility matrix

### Changed
- FundAnalysisSkill extended for personal portfolio analysis with transactions/DCA/market_scenario
- DecisionSupportSkill extended for multi-trade decision making from trade_plan
- Portfolio analysis API stabilized with 14 public functions
- Fund metrics produce per-period returns and risk-adjusted scores

## 0.4.0.dev0

### Added

- Personal portfolio domain schemas in `src.schemas.fund`
- Pure fund NAV metric tools in `src.tools.fund.metrics`
- Pure portfolio analysis tools in `src.tools.portfolio.analysis`
- Structured portfolio review support in `FundAnalysisSkill`
- `examples/minimal_host_portfolio_review.py`
- Domain core tests for fund metrics, portfolio analysis, and portfolio review integration

### Changed

- `DecisionSupportSkill` derives active trade amounts from host-provided
  portfolio context, risk profile, constraints, and target trade amount when
  those are available.
- Skillpack version advanced to `0.4.0.dev0`.

## 0.3.0-skillpack-rc

### Added

- `AGENTS.md` — coding agent integration guide
- `examples/minimal_host_news_to_decision.py` — self-contained host integration demo
- `skillpack/examples/README.md` — host-facing examples documentation
- `docs/skill-io-examples.md` — JSON-like SkillInput/SkillOutput reference
- `docs/plugin-api.md` — full plugin API reference for external agents
- `docs/archive/legacy-system.md` — historical module documentation
- `docs/release-checklist.md` — release verification checklist
- `docs/CONTRACT_FREEZE.md` — frozen contracts for rc
- `VERSION` — canonical version file
- `CHANGELOG.md` — this file
- `scripts/check_plugin_gate.sh` — plugin health gate script
- `.github/workflows/plugin-ci.yml` — CI workflow
- `tests/integration/test_external_host_smoke.py` — external host integration smoke
- `tests/integration/test_minimal_host_demo.py` — minimal host demo test
- `tests/skillpack/test_version_consistency.py` — version consistency tests
- `tests/contracts/test_contract_freeze_docs.py` — contract freeze validation
- `tests/skillpack/test_project_metadata.py` — project metadata sanity tests

### Changed

- Repository is now a host-agnostic Skill Pack / Agent Plugin
- ResearchOS is not required; optional reference only
- External host owns orchestration, MCP provider injection, and retry policy
- `README.md` rewritten for Host-Agnostic Skill Pack narrative
- `legacy/README.md` reduced to pointer to `v0.1.0-skillpack-alpha`

### Removed

- Legacy code removed from mainline (analysis, news, output, strategy, workflows, etc.)
- `tests/deprecated` removed
- Low-value legacy dirs removed (ui, routes, services, agents, forecast)

### Fixed

- Architecture boundary tests enforce no legacy imports
- Skillpack manifest does not require ResearchOS
- DecisionSupportSkill is the only formal Decision producer

### Compatibility

- Old legacy implementation available at `v0.1.0-skillpack-alpha`
  ```bash
  git checkout v0.1.0-skillpack-alpha
  ```
- Skillpack schema is `skillpack.v1`

### Known Limitations

- No real MCP providers bundled
- No provider SDKs bundled (Tavily, Finnhub, Exa, Firecrawl, Reddit)
- fund-agent is not a production autonomous agent runtime
- MCP providers must be injected by the external host
