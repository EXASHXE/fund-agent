"""Report artifact wiring for FundAnalysisSkill."""

from __future__ import annotations

from typing import Any

from src.schemas.fund import FundAnalysisReport
from src.tools.portfolio.analysis import summarize_exposure
from src.tools.portfolio.report_composer import compose_personal_fund_report
from src.tools.portfolio.report_quality import (
    build_report_limitations,
    calculate_data_completeness,
    summarize_analysis_coverage,
)

from .context import (
    AssembledArtifactsBundle,
    CoreMetricsBundle,
    OptionalSummariesBundle,
    PortfolioInputBundle,
)
from .input_stage import dict_or_empty
from .ledger_stage import build_ledger_quality_summary
from .metrics_stage import (
    build_position_summary,
    suggested_watchlist,
)


def assemble_analysis_report_and_artifacts(
    *,
    bundle: PortfolioInputBundle,
    metrics: CoreMetricsBundle,
    optional: OptionalSummariesBundle,
    source_of_truth: str | None,
    derived_snapshot: dict[str, Any] | None,
    reconciliation_report: dict[str, Any] | None,
    warnings: list[str],
    professional_diagnostics: dict[str, Any] | None = None,
) -> AssembledArtifactsBundle:
    report = FundAnalysisReport(
        fund_metrics=metrics.fund_metrics,
        portfolio_metrics=metrics.portfolio_summary,
        exposures=metrics.exposures,
        concentration=metrics.concentration,
        risk_flags=metrics.risk_flags + metrics.trading_flags + metrics.scenario_flags,
        suggested_watchlist=suggested_watchlist(
            metrics.fund_metrics,
            metrics.risk_flags,
        ),
        warnings=warnings,
        pnl_summary=metrics.pnl_summary,
        exposure_summary=summarize_exposure(
            {k: v for k, v in metrics.exposures.items() if not k.startswith("fund_type:")},
            metrics.industry_exposure,
            {k: v for k, v in metrics.exposures.items() if k.startswith("fund_type:")},
        ),
        trade_budget=metrics.trade_budget,
        short_term_budget=metrics.short_term_budget,
        dca_review=metrics.dca_review,
        transaction_summary=metrics.ledger_summary.to_dict() if metrics.ledger_summary is not None else None,
        cost_basis_summary=metrics.cost_basis_summary,
        reconciliation=metrics.reconciliation,
        trading_flags=metrics.trading_flags,
        market_scenario=bundle.market_scenario if bundle.market_scenario else None,
    ).to_dict()
    # Augment report with new optional fields
    if optional.benchmark_summary is not None:
        report["benchmark_summary"] = optional.benchmark_summary
    if optional.peer_summary is not None:
        report["peer_summary"] = optional.peer_summary
    if optional.fee_summary is not None:
        report["fee_summary"] = optional.fee_summary
    if optional.redemption_summary is not None:
        report["redemption_summary"] = optional.redemption_summary
    if optional.factor_summary is not None:
        report["factor_summary"] = optional.factor_summary
    if optional.manager_summary is not None:
        report["manager_summary"] = optional.manager_summary
    if optional.query_plan is not None:
        report["research_query_plan"] = optional.query_plan

    artifacts: dict[str, Any] = {
        "portfolio_summary": metrics.portfolio_summary,
        "position_summary": build_position_summary(bundle.positions),
        "cost_basis_summary": metrics.cost_basis_summary if bundle.transactions else None,
        "pnl_summary": metrics.pnl_summary,
        "exposure_summary": summarize_exposure(
            {k: v for k, v in metrics.exposures.items() if not k.startswith("fund_type:")},
            metrics.industry_exposure,
            {k: v for k, v in metrics.exposures.items() if k.startswith("fund_type:")},
        ),
        "risk_flags": metrics.risk_flags + metrics.trading_flags + metrics.scenario_flags,
        "short_term_trade_budget": metrics.short_term_budget if bundle.transactions else None,
        "dca_plan_review": metrics.dca_review if bundle.dca_plans else None,
        "suggested_rebalance_plan": metrics.rebalance_plan,
        "fund_analysis_report": report,
        "warnings": warnings + list(
            metrics.reconciliation.get("warnings", [])
            if metrics.reconciliation else []
        ),
        "market_scenario_impact": bundle.market_scenario if bundle.market_scenario else None,
    }

    # Derived portfolio / ledger artifacts
    if source_of_truth == "derived_from_transactions" and derived_snapshot:
        warnings.append(
            "portfolio was derived from transactions and current_nav; "
            "accuracy depends on input completeness"
        )
        artifacts["derived_portfolio_snapshot"] = derived_snapshot
        artifacts["ledger_cashflow_summary"] = derived_snapshot.get("cashflow_summary")
        artifacts["source_of_truth"] = "derived_from_transactions"

        artifacts["ledger_quality_summary"] = build_ledger_quality_summary(
            derived_snapshot,
            warnings,
        )

    if reconciliation_report:
        artifacts["ledger_reconciliation_report"] = reconciliation_report
        # Add reconciliation warnings
        rec_warns = reconciliation_report.get("warnings", [])
        if rec_warns:
            warnings.extend(rec_warns)

    # Query plan artifact
    if optional.query_plan:
        artifacts["research_query_plan"] = optional.query_plan

    # Optional data pass-through artifacts
    if optional.benchmark_summary:
        artifacts["benchmark_summary"] = optional.benchmark_summary
    if optional.peer_summary:
        artifacts["peer_summary"] = optional.peer_summary
    if optional.fee_summary:
        artifacts["fee_summary"] = optional.fee_summary
    if optional.redemption_summary:
        artifacts["redemption_summary"] = optional.redemption_summary
    if optional.factor_summary:
        artifacts["factor_summary"] = optional.factor_summary
    if optional.manager_summary:
        artifacts["manager_summary"] = optional.manager_summary

    # Professional diagnostics
    if professional_diagnostics:
        prof_warnings = professional_diagnostics.get("professional_warnings", [])
        if prof_warnings:
            warnings.extend(prof_warnings)
        diagnostic_keys = [
            "redemption_fee_risk",
            "overlap_diagnostics",
            "theme_overweight_diagnostics",
            "dca_drawdown_diagnostics",
            "cash_budget_diagnostics",
        ]
        for key in diagnostic_keys:
            if key in professional_diagnostics and professional_diagnostics[key] is not None:
                artifacts[key] = professional_diagnostics[key]
                report[key] = professional_diagnostics[key]
        artifacts["professional_diagnostics"] = professional_diagnostics
        report["professional_diagnostics"] = professional_diagnostics

    data_completeness = attach_report_artifacts(
        payload=bundle.payload,
        artifacts=artifacts,
        warnings=warnings,
        report=report,
    )
    return AssembledArtifactsBundle(
        report=report,
        artifacts=artifacts,
        data_completeness=data_completeness,
    )


def attach_report_artifacts(
    *,
    payload: dict[str, Any],
    artifacts: dict[str, Any],
    warnings: list[str],
    report: dict[str, Any],
) -> dict[str, Any]:
    # Data completeness, analysis coverage, and report limitations
    data_completeness = calculate_data_completeness(
        payload,
        artifacts.get("ledger_quality_summary"),
    )
    analysis_coverage = summarize_analysis_coverage(payload, artifacts)
    report_limitations_list = build_report_limitations(
        data_completeness,
        artifacts.get("ledger_quality_summary"),
    )
    report["data_completeness"] = data_completeness
    report["analysis_coverage"] = analysis_coverage
    report["report_limitations"] = report_limitations_list
    artifacts["data_completeness"] = data_completeness
    artifacts["analysis_coverage"] = analysis_coverage
    artifacts["report_limitations"] = report_limitations_list
    artifacts["warnings"] = warnings

    composed_report = compose_personal_fund_report(
        artifacts,
        warnings=warnings,
        options=dict_or_empty(payload.get("report_options")),
    )
    report_sections = composed_report["report_sections"]
    report_outline = composed_report["report_outline"]
    report_quality_gate = composed_report["quality_gate"]
    report["report_sections"] = report_sections
    report["report_outline"] = report_outline
    report["report_quality_gate"] = report_quality_gate
    artifacts["report_sections"] = report_sections
    artifacts["report_outline"] = report_outline
    artifacts["report_quality_gate"] = report_quality_gate
    return data_completeness
