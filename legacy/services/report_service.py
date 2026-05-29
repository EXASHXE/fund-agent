"""Report evidence, rendering, and validation service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.core.contracts import (
    build_report_evidence,
    load_agent_decisions,
    write_report_evidence,
)


@dataclass(frozen=True)
class ReportResult:
    evidence_path: str
    report_path: str
    markdown: str
    evidence: dict[str, Any]
    agent_decisions: dict[str, Any] | None


def load_decisions_for_run(
    path,
    report_date,
    scores=None,
    news_data=None,
    recommendation_candidates=None,
):
    """Load and validate Agent decisions for the current report date."""
    return load_agent_decisions(
        path,
        report_date,
        scores=scores,
        news_data=news_data,
        recommendation_candidates=recommendation_candidates,
    )


def render_analysis_report(
    *,
    output_path: str,
    report_date,
    analyzer,
    scores,
    correlations,
    stress_results,
    holdings_data,
    news_data,
    recommendations,
    recommendation_status,
    unscores,
    workflow_context,
    inter_recommendation_correlations=None,
    agent_decisions=None,
    holding_count: int = 0,
) -> ReportResult:
    """Build evidence, render report markdown, post-process, validate, and write files."""
    from legacy.output.report import generate_report
    from legacy.output.validator import post_process_report, validate_final_report

    evidence = build_report_evidence(
        report_date,
        scores,
        holdings_data,
        news_data,
        correlations,
        stress_results,
        (workflow_context or {}).get("portfolio_risk_matrix", {}),
        recommendations=recommendations,
        recommendation_status=recommendation_status,
        workflow_context=workflow_context,
    )
    evidence_path = write_report_evidence(output_path, evidence)

    markdown = generate_report(
        analyzer,
        scores,
        correlations,
        stress_results,
        holdings_data=holdings_data,
        news_data=news_data,
        recommendations=recommendations,
        recommendation_status=recommendation_status,
        unscores=unscores,
        workflow_context=workflow_context,
        inter_recommendation_correlations=inter_recommendation_correlations,
        agent_decisions=agent_decisions,
    )
    markdown = post_process_report(markdown, scores)
    if agent_decisions:
        validate_final_report(markdown, report_date.isoformat(), holding_count)

    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(markdown)

    return ReportResult(
        evidence_path=evidence_path,
        report_path=output_path,
        markdown=markdown,
        evidence=evidence,
        agent_decisions=agent_decisions,
    )
