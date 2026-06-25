"""Fund analysis skill runtime.

This skill performs local-only personal fund and portfolio analysis from
structured host-provided payloads. It does not call MCP, network, LLM, or
provider SDKs. External hosts own data fetching and orchestration.
"""

from __future__ import annotations

from typing import Any

from src.schemas.skill import SkillInput, SkillOutput
from src.skills_runtime.base import BaseSkillRuntime
from src.tools.portfolio.ledger_snapshot import compute_transaction_cashflow_summary

from .benchmark_rules import compute_benchmark_divergence_diagnostics
from .cash_deployment_rules import compute_cash_deployment_diagnostics
from .contribution_stage import compute_position_contribution
from .diagnostics_stage import (
    compute_diagnostics,
)
from .event_rules import compute_event_hype_failure_diagnostics
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
from .knowledge_graph_stage import build_knowledge_graph_summary
from .ledger_stage import (
    build_transactions_only_portfolio,
    portfolio_from_derived_snapshot,
    resolve_portfolio_context,
)
from .metrics_stage import compute_core_metrics
from .optional_data_stage import build_optional_summaries
from .planning_stage import build_analysis_plan
from .profit_protection_rules import compute_profit_protection_diagnostics
from .report_stage import assemble_analysis_report_and_artifacts
from .right_side_rules import compute_right_side_confirmation_diagnostics
from .status_stage import (
    build_final_skill_output,
    failed_output,
)


class FundAnalysisSkill(BaseSkillRuntime):
    """Local personal fund and portfolio analysis skill."""

    def run(self, skill_input: SkillInput) -> SkillOutput:
        payload = skill_input.payload or {}

        if not isinstance(payload, dict):
            return failed_output(
                skill_input,
                "INVALID_INPUT",
                "FundAnalysisSkill payload must be a dictionary",
            )

        # Runtime guard: warn when used directly for personal portfolio analysis
        # without canonical provenance (personal-run pipeline).
        warnings_list: list[str] = []
        if _looks_like_personal_portfolio(payload):
            provenance = payload.get("_provenance", {})
            if not isinstance(provenance, dict) or provenance.get("source") != "personal_run":
                warnings_list.append(
                    "non_canonical_personal_analysis_entrypoint: "
                    "FundAnalysisSkill was called directly for personal portfolio analysis. "
                    "Use bin/fund-agent-personal-run and agent_context for canonical analysis. "
                    "This output is not canonical for personal portfolio analysis."
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
            entrypoint_warnings=warnings_list,
        )

    def _run_portfolio_analysis(
        self,
        skill_input: SkillInput,
        payload: dict[str, Any],
        source_of_truth: str | None = None,
        derived_snapshot: dict[str, Any] | None = None,
        reconciliation_report: dict[str, Any] | None = None,
        entrypoint_warnings: list[str] | None = None,
    ) -> SkillOutput:
        portfolio = dict_or_empty(payload.get("portfolio"))

        # When derived from transactions, reconstruct portfolio from snapshot
        if source_of_truth == "derived_from_transactions" and derived_snapshot:
            positions = derived_snapshot.get("positions", [])
            portfolio = portfolio_from_derived_snapshot(payload, derived_snapshot)
        elif source_of_truth == "transactions_only":
            # Transactions exist but no current_nav — cashflow-only mode
            as_of_date = portfolio.get("as_of_date", payload.get("as_of_date", ""))
            cashflow_summary = compute_transaction_cashflow_summary(
                transactions=payload.get("transactions", []),
                as_of_date=as_of_date,
                options=payload.get("settlement_options"),
            )
            portfolio = build_transactions_only_portfolio(payload, cashflow_summary)
            positions = portfolio.get("positions", [])
        else:
            positions = portfolio.get("positions")

        if not isinstance(positions, list) or not positions:
            if source_of_truth == "transactions_only":
                # transactions_only may produce no positions if all transactions are invalid
                # but we still want to produce a cashflow-only report
                pass
            else:
                return failed_output(
                    skill_input,
                    "INVALID_INPUT",
                    "payload.portfolio.positions must be a non-empty list",
                )

        fund_codes = collect_fund_codes(positions)
        if not fund_codes and source_of_truth != "transactions_only":
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
        if entrypoint_warnings:
            warnings.extend(entrypoint_warnings)

        try:
            metrics = compute_core_metrics(bundle, warnings, skill_input)
            optional = build_optional_summaries(
                bundle,
                metrics,
                skill_input,
                warnings,
            )
            professional_diagnostics = compute_diagnostics(
                bundle,
                metrics,
                warnings,
            )
            position_contribution = compute_position_contribution(
                bundle, metrics,
            )
            profit_protection = compute_profit_protection_diagnostics(
                bundle, metrics,
            )
            benchmark_divergence = compute_benchmark_divergence_diagnostics(
                bundle, metrics,
            )
            right_side_confirmation = compute_right_side_confirmation_diagnostics(
                bundle, metrics,
            )
            event_hype_failure = compute_event_hype_failure_diagnostics(
                bundle, metrics,
            )
            cash_deployment = compute_cash_deployment_diagnostics(
                bundle, metrics,
            )
            try:
                knowledge_graph_summary = build_knowledge_graph_summary(
                    positions=positions,
                    fund_profiles=bundle.fund_profiles,
                    holdings=bundle.holdings,
                    events=payload.get("events", payload.get("catalyst_events")),
                )
            except Exception:
                knowledge_graph_summary = None
            plan_result = build_analysis_plan(
                bundle=bundle,
                metrics=metrics,
                optional=optional,
                diagnostics=professional_diagnostics,
                warnings=warnings,
                user_goal=payload.get("user_goal") or payload.get("user_question"),
                benchmark_divergence=benchmark_divergence,
                right_side_confirmation=right_side_confirmation,
                event_hype_failure=event_hype_failure,
                cash_deployment=cash_deployment,
            )
            artifacts_bundle = assemble_analysis_report_and_artifacts(
                bundle=bundle,
                metrics=metrics,
                optional=optional,
                source_of_truth=source_of_truth,
                derived_snapshot=derived_snapshot,
                reconciliation_report=reconciliation_report,
                warnings=warnings,
                professional_diagnostics=professional_diagnostics,
                plan_result=plan_result,
                position_contribution=position_contribution,
                profit_protection=profit_protection,
                benchmark_divergence=benchmark_divergence,
                right_side_confirmation=right_side_confirmation,
                event_hype_failure=event_hype_failure,
                cash_deployment=cash_deployment,
                knowledge_graph_summary=knowledge_graph_summary,
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


def _looks_like_personal_portfolio(payload: dict[str, Any]) -> bool:
    """Heuristic: does this payload look like a personal portfolio analysis?

    Detects patterns common in personal portfolio inputs:
    - Has portfolio.positions with fund_code + invested_amount/total_cost
    - Has transactions list
    - Missing _provenance.source == "personal_run"

    This is a heuristic guard, not a strict gate. It warns but does not block.
    """
    portfolio = payload.get("portfolio")
    if not isinstance(portfolio, dict):
        return False
    positions = portfolio.get("positions")
    if not isinstance(positions, list) or len(positions) < 1:
        return False
    # Check for personal-portfolio-style fields
    has_invested = any(
        isinstance(p, dict) and (p.get("invested_amount") is not None or p.get("total_cost") is not None)
        for p in positions
    )
    has_transactions = isinstance(payload.get("transactions"), list)
    return has_invested or has_transactions
