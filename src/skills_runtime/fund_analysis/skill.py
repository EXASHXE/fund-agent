"""Fund analysis skill runtime.

This skill performs local-only personal fund and portfolio analysis from
structured host-provided payloads. It does not call MCP, network, LLM, or
provider SDKs. External hosts own data fetching and orchestration.
"""

from __future__ import annotations

from typing import Any

from src.schemas.skill import SkillInput, SkillOutput

from .evidence_stage import (
    build_baseline_evidence,
)
from .input_stage import (
    build_portfolio_input_bundle,
    collect_fund_codes,
    dict_or_empty,
    entities_from_input,
    missing_data_warnings,
)
from .ledger_stage import (
    portfolio_from_derived_snapshot,
    resolve_portfolio_context,
)
from .metrics_stage import compute_core_metrics
from .optional_data_stage import build_optional_summaries
from .report_stage import assemble_analysis_report_and_artifacts
from .status_stage import (
    build_final_skill_output,
    failed_output,
)


class FundAnalysisSkill:
    """Local personal fund and portfolio analysis skill."""

    mcp_adapter = None
    tool_registry = None

    def run(self, skill_input: SkillInput) -> SkillOutput:
        payload = skill_input.payload or {}

        if not isinstance(payload, dict):
            return failed_output(
                skill_input,
                "INVALID_INPUT",
                "FundAnalysisSkill payload must be a dictionary",
            )

        stage_result = resolve_portfolio_context(skill_input, payload)
        if stage_result.output is not None:
            return stage_result.output
        context = stage_result.context
        if context is None:
            return failed_output(
                skill_input,
                "INTERNAL_ERROR",
                "FundAnalysisSkill failed to resolve portfolio context",
            )
        if context.baseline_only:
            return self._run_baseline(skill_input)

        return self._run_portfolio_analysis(
            skill_input=skill_input,
            payload=payload,
            source_of_truth=context.source_of_truth,
            derived_snapshot=context.derived_snapshot,
            reconciliation_report=context.reconciliation_report,
        )

    def _run_portfolio_analysis(
        self,
        skill_input: SkillInput,
        payload: dict[str, Any],
        source_of_truth: str | None = None,
        derived_snapshot: dict[str, Any] | None = None,
        reconciliation_report: dict[str, Any] | None = None,
    ) -> SkillOutput:
        portfolio = dict_or_empty(payload.get("portfolio"))

        # When derived from transactions, reconstruct portfolio from snapshot
        if source_of_truth == "derived_from_transactions" and derived_snapshot:
            positions = derived_snapshot.get("positions", [])
            portfolio = portfolio_from_derived_snapshot(payload, derived_snapshot)
        else:
            positions = portfolio.get("positions")

        if not isinstance(positions, list) or not positions:
            return failed_output(
                skill_input,
                "INVALID_INPUT",
                "payload.portfolio.positions must be a non-empty list",
            )

        fund_codes = collect_fund_codes(positions)
        if not fund_codes:
            return failed_output(
                skill_input,
                "INVALID_INPUT",
                "portfolio positions must include fund_code",
            )

        bundle = build_portfolio_input_bundle(
            payload=payload,
            portfolio=portfolio,
            positions=positions,
            fund_codes=fund_codes,
        )
        warnings = missing_data_warnings(
            fund_codes=bundle.fund_codes,
            fund_profiles=bundle.fund_profiles,
            nav_history=bundle.nav_history,
            holdings=bundle.holdings,
        )

        try:
            metrics = compute_core_metrics(bundle, warnings, skill_input)
            optional = build_optional_summaries(
                bundle,
                metrics,
                skill_input,
                warnings,
            )
            artifacts_bundle = assemble_analysis_report_and_artifacts(
                bundle=bundle,
                metrics=metrics,
                optional=optional,
                source_of_truth=source_of_truth,
                derived_snapshot=derived_snapshot,
                reconciliation_report=reconciliation_report,
                warnings=warnings,
            )
        except Exception as exc:
            return failed_output(
                skill_input,
                "INTERNAL_ERROR",
                f"FundAnalysisSkill analysis failed: {exc}",
                details={"error_type": type(exc).__name__},
            )

        return build_final_skill_output(
            skill_input=skill_input,
            bundle=bundle,
            metrics=metrics,
            artifacts_bundle=artifacts_bundle,
            source_of_truth=source_of_truth,
            derived_snapshot=derived_snapshot,
            reconciliation_report=reconciliation_report,
            warnings=warnings,
        )

    def _run_baseline(self, skill_input: SkillInput) -> SkillOutput:
        entities = entities_from_input(skill_input)
        evidence_items, errors = build_baseline_evidence(skill_input, entities)
        return SkillOutput(
            step_id=skill_input.step_id,
            skill_name=skill_input.skill_name,
            evidence_items=evidence_items,
            errors=errors,
            warnings=[
                "FundAnalysisSkill received only related_entities; "
                "produced baseline evidence only."
            ],
            status="OK" if evidence_items and not errors else "FAILED",
        )
