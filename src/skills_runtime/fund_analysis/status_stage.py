"""Status and failure-output helpers for FundAnalysisSkill."""

from __future__ import annotations

from typing import Any

from src.schemas.skill import SkillError, SkillInput, SkillOutput

from .context import AssembledArtifactsBundle, CoreMetricsBundle, PortfolioInputBundle
from .evidence_stage import build_evidence_items, evidence_specs


def failed_output(
    skill_input: SkillInput,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> SkillOutput:
    return SkillOutput(
        step_id=skill_input.step_id,
        skill_name=skill_input.skill_name,
        errors=[
            SkillError(
                code=code,
                message=message,
                details={
                    "skill_name": skill_input.skill_name,
                    **(details or {}),
                },
                recoverable=code not in {"INVALID_INPUT"},
            ).to_dict()
        ],
        warnings=[message],
        status="FAILED",
    )


def empty_evidence_output(
    skill_input: SkillInput,
    *,
    artifacts: dict[str, Any],
    warnings: list[str],
    errors: list[dict[str, Any]],
) -> SkillOutput:
    return SkillOutput(
        step_id=skill_input.step_id,
        skill_name=skill_input.skill_name,
        artifacts=artifacts,
        warnings=warnings,
        errors=errors
        or [
            SkillError(
                code="EMPTY_RESULT",
                message="FundAnalysisSkill produced no evidence",
                details={"skill_name": skill_input.skill_name},
            ).to_dict()
        ],
        status="FAILED",
    )


def status_from_analysis(
    *,
    errors: list[dict[str, Any]],
    data_completeness: dict[str, Any],
    warnings: list[str],
) -> str:
    # Enhanced status semantics:
    # OK    — enough data for a coherent portfolio report, no errors
    # PARTIAL — derived ledger unresolved, optional data requested but missing,
    #           stale data, or non-critical warnings exist
    # FAILED — no usable positions (caught earlier), no evidence produced
    if errors:
        status = "PARTIAL"
    elif data_completeness["grade"] in ("C", "D"):
        status = "PARTIAL"
        if "Report data completeness grade is" not in " ".join(warnings):
            warnings.append(
                f"Report data completeness grade is {data_completeness['grade']} "
                f"(score {data_completeness['score']:.2f})"
            )
    elif warnings:
        status = "PARTIAL"
    else:
        status = "OK"
    return status


def build_final_skill_output(
    *,
    skill_input: SkillInput,
    bundle: PortfolioInputBundle,
    metrics: CoreMetricsBundle,
    artifacts_bundle: AssembledArtifactsBundle,
    source_of_truth: str | None,
    derived_snapshot: dict[str, Any] | None,
    reconciliation_report: dict[str, Any] | None,
    warnings: list[str],
) -> SkillOutput:
    final_evidence_specs = evidence_specs(
        skill_input=skill_input,
        fund_codes=bundle.fund_codes,
        portfolio_summary=metrics.portfolio_summary,
        concentration=metrics.concentration,
        fund_metrics=metrics.fund_metrics,
        risk_flags=metrics.risk_flags + metrics.trading_flags + metrics.scenario_flags,
        rebalance_plan=metrics.rebalance_plan,
        cost_basis_summary=metrics.cost_basis_summary,
        short_term_budget=metrics.short_term_budget,
        dca_review=metrics.dca_review,
        market_scenario=bundle.market_scenario,
        pnl_summary=metrics.pnl_summary,
        source_of_truth=source_of_truth,
        derived_snapshot=derived_snapshot,
        reconciliation_report=reconciliation_report,
    )
    evidence_items, errors = build_evidence_items(
        skill_input,
        final_evidence_specs,
    )

    if not evidence_items:
        return empty_evidence_output(
            skill_input,
            artifacts=artifacts_bundle.artifacts,
            warnings=warnings,
            errors=errors,
        )

    status = status_from_analysis(
        errors=errors,
        data_completeness=artifacts_bundle.data_completeness,
        warnings=warnings,
    )
    return SkillOutput(
        step_id=skill_input.step_id,
        skill_name=skill_input.skill_name,
        evidence_items=evidence_items,
        artifacts=artifacts_bundle.artifacts,
        warnings=warnings,
        errors=errors,
        status=status,
    )
