# Tools Inventory

This document classifies every `src/tools/` subdirectory and its relationship
to the public skillpack tool registry (`skillpack/tools.yaml`) and the
skillpack manifest (`skillpack/fund-agent.skillpack.yaml`).

## Provider/Network Boundary

Provider SDKs and network calls belong to the **external host / MCP provider**.
`fund-agent` does not fetch provider data itself. The only boundary for
host-provided data is `src/tools/adapters/mcp.py:MCPHostAdapter`.

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
| `metrics.py` | public registered tool | Yes (`normalize_nav_history`, `calculate_returns_from_nav`, `calculate_fund_metrics`) | Pure fund NAV/metrics computation |
| `__init__.py` | internal | No | Package init |

Also referenced in manifest but not in tools.yaml:
- `calculate_period_return` — listed in manifest tools, implemented in `metrics.py`
- `calculate_rolling_drawdown` — listed in manifest tools, implemented in `metrics.py`

Classification: **public registered tool** (manifest-declared, needs tools.yaml entry).

### `src/tools/portfolio/` — Portfolio analysis tools

| File | Classification | Registered in tools.yaml | Notes |
|---|---|---|---|
| `analysis.py` | public registered tool | Yes (partial) | Some functions in tools.yaml, others in manifest only |
| `builder.py` | internal deterministic helper | No | Portfolio construction helper |
| `report_composer.py` | internal deterministic helper | No | Deterministic report section assembly |
| `report_quality.py` | internal deterministic helper | No | Report quality gate |
| `transaction.py` | public registered tool | In manifest only | Transaction normalization/cost basis/summary |
| `ledger_snapshot.py` | public registered tool | In manifest only | Ledger snapshot construction and reconciliation |
| `__init__.py` | internal | No | Package init |

Functions in `analysis.py` declared in manifest but not tools.yaml:
- `calculate_position_pnl`, `calculate_portfolio_pnl`, `calculate_trade_budget`
- `review_dca_plan`, `rank_trade_plan`

Classification: **public registered tool** (manifest-declared, needs tools.yaml entry).

### `src/tools/quant/` — Quantitative metric tools

| File | Classification | Registered in tools.yaml | Notes |
|---|---|---|---|
| `metrics.py` | public registered tool | Yes (`calculate_sharpe`, `calculate_sortino`, `calculate_max_drawdown`, `calculate_volatility`, `calculate_hhi`) | Pure quantitative computations |
| `__init__.py` | internal | No | Package init |

Quant tools are in tools.yaml but NOT in the manifest tools list.
Classification: **public registered tool** (tools.yaml-declared).

### `src/tools/ledger/` — Ledger simulation tools

| File | Classification | Registered in tools.yaml | Notes |
|---|---|---|---|
| `settlement.py` | public registered tool | Yes (`simulate_position_ledger`) | Pure ledger settlement simulation |
| `dca.py` | public registered tool | Yes (`simulate_dca_plan`) | Pure DCA simulation |
| `__init__.py` | internal | No | Package init |

Ledger tools are in tools.yaml but NOT in the manifest tools list.
Classification: **public registered tool** (tools.yaml-declared).

### `src/tools/research/` — Research planning tools

| File | Classification | Registered in tools.yaml | Notes |
|---|---|---|---|
| `query_plan.py` | public registered tool | In manifest only | Research query plan builder |
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

## Drift Summary

### Manifest tools not in tools.yaml (16 entries)

These are declared in `skillpack/fund-agent.skillpack.yaml` tools section but
have no corresponding entry in `skillpack/tools.yaml`:

1. `src.tools.fund.metrics:calculate_period_return`
2. `src.tools.fund.metrics:calculate_rolling_drawdown`
3. `src.tools.portfolio.analysis:calculate_position_pnl`
4. `src.tools.portfolio.analysis:calculate_portfolio_pnl`
5. `src.tools.portfolio.analysis:calculate_trade_budget`
6. `src.tools.portfolio.analysis:review_dca_plan`
7. `src.tools.portfolio.analysis:rank_trade_plan`
8. `src.tools.portfolio.transaction:normalize_fund_transactions`
9. `src.tools.portfolio.transaction:calculate_position_cost_basis`
10. `src.tools.portfolio.transaction:summarize_transaction_ledger`
11. `src.tools.portfolio.ledger_snapshot:normalize_transaction_events`
12. `src.tools.portfolio.ledger_snapshot:build_position_snapshot_from_transactions`
13. `src.tools.portfolio.ledger_snapshot:reconcile_snapshot_with_portfolio`
14. `src.tools.portfolio.ledger_snapshot:calculate_realized_unrealized_pnl`
15. `src.tools.portfolio.ledger_snapshot:apply_settlement_rules`
16. `src.tools.research.query_plan:build_research_query_plan`

These are **public registered tools** that need tools.yaml entries for
consistency.

### tools.yaml entries not in manifest (7 entries)

These are declared in `skillpack/tools.yaml` but not in the manifest tools list:

1. `calculate_sharpe`
2. `calculate_sortino`
3. `calculate_max_drawdown`
4. `calculate_volatility`
5. `calculate_hhi`
6. `simulate_position_ledger`
7. `simulate_dca_plan`

These are **public registered tools** that may need manifest inclusion if
intended as host-callable skillpack tools, or classification as
internal/experimental if not.

## Classification Legend

| Classification | Meaning |
|---|---|
| public registered tool | Declared in tools.yaml and/or manifest; host-callable |
| internal deterministic helper | Used by runtime skills; not declared in public registry |
| MCP adapter boundary | Host capability boundary; no provider SDK imports |
| evidence construction helper | Builds HardEvidence/SoftEvidence from local or MCP data |
| test-only helper | Used only in test code |
| archive/delete candidate | Appears stale or unused (requires proof before deletion) |
