"""Report artifact wiring for FundAnalysisSkill."""

from __future__ import annotations

from typing import Any

from src.tools.portfolio.report_composer import compose_personal_fund_report
from src.tools.portfolio.report_quality import (
    build_report_limitations,
    calculate_data_completeness,
    summarize_analysis_coverage,
)

from .input_stage import dict_or_empty


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
