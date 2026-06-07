"""Shared context structures for the fund analysis runtime pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.schemas.skill import SkillOutput


@dataclass(frozen=True)
class FundAnalysisContext:
    """Resolved input context passed from input/ledger stages into analysis."""

    payload: dict[str, Any]
    source_of_truth: str | None = None
    derived_snapshot: dict[str, Any] | None = None
    reconciliation_report: dict[str, Any] | None = None
    baseline_only: bool = False


@dataclass(frozen=True)
class StageResult:
    """Small result wrapper for stages that may short-circuit with SkillOutput."""

    context: FundAnalysisContext | None = None
    output: SkillOutput | None = None


@dataclass(frozen=True)
class PortfolioInputBundle:
    """Normalized host payload fields used by downstream analysis stages."""

    payload: dict[str, Any]
    portfolio: dict[str, Any]
    positions: list[dict[str, Any]]
    fund_codes: list[str]
    fund_profiles: dict[str, Any]
    nav_history: dict[str, Any]
    holdings: dict[str, Any]
    risk_profile: dict[str, Any]
    constraints: dict[str, Any]
    transactions: Any
    dca_plans: Any
    market_scenario: Any
    benchmarks: Any
    benchmark_history: Any
    peer_group: Any
    factor_exposures: Any
    manager_profiles: Any
    fee_schedules: Any
    redemption_rules: Any
    research_planning: bool
    nav_data: dict[str, float]
    as_of_date: Any


@dataclass(frozen=True)
class CoreMetricsBundle:
    """Core deterministic metrics computed from normalized portfolio inputs."""

    position_weights: dict[str, Any]
    concentration: dict[str, Any]
    exposures: dict[str, Any]
    cash_ratio: Any
    industry_exposure: dict[str, Any]
    fund_type_exposure: dict[str, Any]
    fund_metrics: dict[str, Any]
    risk_flags: list[dict[str, Any]]
    pnl_summary: dict[str, Any] | None
    trade_budget: dict[str, Any] | None
    short_term_budget: dict[str, Any] | None
    dca_review: dict[str, Any] | None
    normalized_transactions: list[Any]
    ledger_summary: Any
    cost_basis_summary: dict[str, Any] | None
    reconciliation: dict[str, Any] | None
    trading_flags: list[dict[str, Any]]
    scenario_flags: list[dict[str, Any]]
    portfolio_summary: dict[str, Any]
    rebalance_plan: dict[str, Any] | None


@dataclass(frozen=True)
class OptionalSummariesBundle:
    """Optional host-supplied summaries and deterministic query planning output."""

    benchmark_summary: dict[str, Any] | None = None
    peer_summary: dict[str, Any] | None = None
    fee_summary: dict[str, Any] | None = None
    redemption_summary: dict[str, Any] | None = None
    factor_summary: dict[str, Any] | None = None
    manager_summary: dict[str, Any] | None = None
    query_plan: dict[str, Any] | None = None


@dataclass(frozen=True)
class AssembledArtifactsBundle:
    """Final report and artifact payloads before evidence/status assembly."""

    report: dict[str, Any]
    artifacts: dict[str, Any]
    data_completeness: dict[str, Any]
