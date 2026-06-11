# Tools Inventory

This document classifies every `src/tools/` subdirectory and its relationship
to the public skillpack tool registry (`skillpack/tools.yaml`) and the
skillpack manifest (`skillpack/fund-agent.skillpack.yaml`).

## Provider/Network Boundary

Provider SDKs and network calls belong to the **external host / MCP provider**.
`fund-agent` does not fetch provider data itself. The only boundary for
host-provided data is `src/tools/adapters/mcp.py:MCPHostAdapter`.

## Registry Consistency Policy

- `skillpack/tools.yaml` is the canonical tool registry.
- `skillpack/fund-agent.skillpack.yaml` tools section lists host-callable import paths.
- Every public registered tool must appear in **both** tools.yaml and the manifest.
- Internal deterministic helpers may live under `src/tools/` but must not appear in the manifest.
- Registry consistency is enforced by `tests/skillpack/test_tools_registry_consistency.py`.
- Provider SDKs and network calls belong to the external host / MCP provider boundary.

## Current Drift Status: no unclassified drift.

All tools declared in the manifest have corresponding tools.yaml entries.
All public tools.yaml entries (except `MCPHostAdapter` which is an adapter contract)
appear in the manifest.

## Directory Classification

### `src/tools/adapters/` — MCP adapter boundary

| File | Classification | Registered in tools.yaml | Notes |
|---|---|---|---|
| `mcp.py` | public registered tool | Yes (`MCPHostAdapter`) | Host capability boundary; concrete provider networking belongs to the external host |
| `__init__.py` | internal | No | Package init |

### `src/tools/evidence/` — Evidence construction helpers

| File | Classification | Registered in tools.yaml | Notes |
|---|---|---|---|
| `validators.py` | public registered tool | Yes (`compile_evidence_graph`) | Full evidence pipeline validation |
| `review.py` | public registered tool | Yes (`review_evidence_graph`) | Optional evidence review helper |
| `builders.py` | public registered tool | Yes (`build_hard_evidence_from_metric`, `build_soft_evidence_from_mcp_result`) | Evidence factory functions |
| `__init__.py` | internal | No | Package init |

### `src/tools/fund/` — Fund metric tools

| File | Classification | Registered in tools.yaml | Notes |
|---|---|---|---|
| `metrics.py` | public registered tool | Yes (`normalize_nav_history`, `calculate_returns_from_nav`, `calculate_fund_metrics`, `calculate_period_return`, `calculate_rolling_drawdown`) | Pure fund NAV/metrics computation |
| `__init__.py` | internal | No | Package init |

### `src/tools/portfolio/` — Portfolio analysis tools

| File | Classification | Registered in tools.yaml | Notes |
|---|---|---|---|
| `analysis.py` | public registered tool | Yes (`calculate_position_weights`, `calculate_theme_exposure`, `calculate_concentration_metrics`, `detect_portfolio_risk_flags`, `simulate_rebalance`, `calculate_position_pnl`, `calculate_portfolio_pnl`, `calculate_trade_budget`, `review_dca_plan`, `rank_trade_plan`) | Portfolio analysis and simulation |
| `transaction.py` | public registered tool | Yes (`normalize_fund_transactions`, `calculate_position_cost_basis`, `summarize_transaction_ledger`) | Transaction normalization and cost basis |
| `ledger_snapshot.py` | public registered tool | Yes (`normalize_transaction_events`, `build_position_snapshot_from_transactions`, `reconcile_snapshot_with_portfolio`, `calculate_realized_unrealized_pnl`, `apply_settlement_rules`) | Ledger snapshot construction and reconciliation |
| `builder.py` | internal deterministic helper | No | Portfolio construction helper |
| `report_composer.py` | internal deterministic helper | No | Deterministic report section assembly |
| `report_quality.py` | internal deterministic helper | No | Report quality gate |
| `__init__.py` | internal | No | Package init |

### `src/tools/quant/` — Quantitative metric tools

| File | Classification | Registered in tools.yaml | Notes |
|---|---|---|---|
| `metrics.py` | public registered tool | Yes (`calculate_sharpe`, `calculate_sortino`, `calculate_max_drawdown`, `calculate_volatility`, `calculate_hhi`) | Pure quantitative computations |
| `__init__.py` | internal | No | Package init |

### `src/tools/ledger/` — Ledger simulation tools

| File | Classification | Registered in tools.yaml | Notes |
|---|---|---|---|
| `settlement.py` | public registered tool | Yes (`simulate_position_ledger`) | Pure ledger settlement simulation |
| `dca.py` | public registered tool | Yes (`simulate_dca_plan`) | Pure DCA simulation |
| `__init__.py` | internal | No | Package init |

### `src/tools/research/` — Research planning tools

| File | Classification | Registered in tools.yaml | Notes |
|---|---|---|---|
| `query_plan.py` | public registered tool | Yes (`build_research_query_plan`) | Research query plan builder |
| `__init__.py` | internal | No | Package init |

### `src/tools/calendar/` — Calendar/date helpers

| File | Classification | Registered in tools.yaml | Notes |
|---|---|---|---|
| `dates.py` | internal deterministic helper | No | Date/calendar utilities used by runtime skills |
| `__init__.py` | internal | No | Package init |

### `src/tools/factors/` — Factor analysis helpers

| File | Classification | Registered in tools.yaml | Notes |
|---|---|---|---|
| `builder.py` | internal deterministic helper | No | Factor exposure builder used by fund_analysis |
| `__init__.py` | internal | No | Package init |

### `src/tools/math/` — Math utilities

| File | Classification | Registered in tools.yaml | Notes |
|---|---|---|---|
| `calc.py` | internal deterministic helper | No | General math utilities |
| `xirr.py` | internal deterministic helper | No | XIRR calculation helper |
| `__init__.py` | internal | No | Package init |

### `src/tools/risk/` — Risk metric helpers

| File | Classification | Registered in tools.yaml | Notes |
|---|---|---|---|
| `metrics.py` | internal deterministic helper | No | Risk metric computation used by portfolio analysis |
| `__init__.py` | internal | No | Package init |

### `src/tools/scoring/` — Scoring helpers

| File | Classification | Registered in tools.yaml | Notes |
|---|---|---|---|
| `helpers.py` | internal deterministic helper | No | Scoring utility functions |
| `__init__.py` | internal | No | Package init |

### `src/tools/evidence_tools.py` — Standalone evidence tools

| File | Classification | Registered in tools.yaml | Notes |
|---|---|---|---|
| `evidence_tools.py` | internal deterministic helper | No | Standalone evidence utility module |

### `src/tools/registry.py` — Tool registry

| File | Classification | Registered in tools.yaml | Notes |
|---|---|---|---|
| `registry.py` | internal runtime infrastructure | No | Generic ToolRegistry class; not auto-populated from tools.yaml |

### `src/tools/workflow/` — Workflow-level bridge tools

| File | Classification | Registered in tools.yaml | Notes |
|---|---|---|---|
| `final_report.py` | internal deterministic helper | No | Composes final advisory workflow report from fund_analysis and decision_support outputs |
| `__init__.py` | internal | No | Package init; re-exports from src.skills_runtime.workflow |

## Classification Legend

| Classification | Meaning |
|---|---|
| public registered tool | Declared in tools.yaml and manifest; host-callable |
| internal deterministic helper | Used by runtime skills; not declared in public registry |
| MCP adapter boundary | Host capability boundary; no provider SDK imports |
| evidence construction helper | Builds HardEvidence/SoftEvidence from local or MCP data |
| internal runtime infrastructure | Runtime support code; not a host-callable tool |
