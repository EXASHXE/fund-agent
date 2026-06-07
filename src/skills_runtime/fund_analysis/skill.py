"""Fund analysis skill runtime.

This skill performs local-only personal fund and portfolio analysis from
structured host-provided payloads. It does not call MCP, network, LLM, or
provider SDKs. External hosts own data fetching and orchestration.
"""

from __future__ import annotations

from typing import Any

from src.schemas.fund import FundAnalysisReport
from src.schemas.skill import SkillInput, SkillOutput
from src.tools.fund.metrics import calculate_fund_metrics
from src.tools.portfolio.analysis import (
    calculate_cash_ratio,
    calculate_concentration_metrics,
    calculate_industry_exposure,
    calculate_portfolio_pnl,
    calculate_position_weights,
    calculate_short_term_budget_usage,
    calculate_theme_exposure,
    calculate_trade_budget,
    detect_portfolio_risk_flags,
    review_dca_plan,
    simulate_rebalance,
    summarize_exposure,
)
from src.tools.portfolio.transaction import (
    calculate_position_cost_basis,
    detect_trading_discipline_flags,
    normalize_fund_transactions,
    reconcile_portfolio_with_transactions,
    summarize_transaction_ledger,
)
from src.tools.research.query_plan import build_research_query_plan

from .evidence_stage import (
    build_baseline_evidence,
    build_evidence_items,
    evidence_specs,
)
from .input_stage import (
    collect_fund_codes,
    dict_or_empty,
    entities_from_input,
    latest_nav_by_fund,
    missing_data_warnings,
    target_weights_from_payload,
)
from .ledger_stage import (
    build_ledger_quality_summary,
    portfolio_from_derived_snapshot,
    resolve_portfolio_context,
)
from .metrics_stage import (
    build_portfolio_summary,
    build_position_summary,
    enrich_rebalance_plan_with_positions,
    scenario_flags_from_market_scenario,
    suggested_watchlist,
)
from .optional_data_stage import (
    add_missing_optional_warnings,
    summarize_benchmark_gap,
    summarize_factor_exposures,
    summarize_fee_schedule,
    summarize_manager_profiles,
    summarize_peer_data,
    summarize_redemption_constraints,
)
from .report_stage import attach_report_artifacts
from .status_stage import (
    empty_evidence_output,
    failed_output,
    status_from_analysis,
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

        fund_profiles = dict_or_empty(payload.get("fund_profiles"))
        nav_history = dict_or_empty(payload.get("nav_history"))
        holdings = dict_or_empty(payload.get("holdings"))
        risk_profile = dict_or_empty(payload.get("risk_profile"))
        constraints = dict_or_empty(payload.get("constraints"))
        transactions = payload.get("transactions", [])
        dca_plans = payload.get("dca_plans", {})
        market_scenario = payload.get("market_scenario", {})

        # Optional host data contract fields (pass-through)
        benchmarks = payload.get("benchmarks") or {}
        benchmark_history = payload.get("benchmark_history") or {}
        peer_group = payload.get("peer_group") or {}
        factor_exposures = payload.get("factor_exposures") or {}
        manager_profiles = payload.get("manager_profiles") or {}
        fee_schedules = payload.get("fee_schedules") or {}
        redemption_rules = payload.get("redemption_rules") or {}
        research_planning = payload.get("research_planning") is True

        nav_data = latest_nav_by_fund(nav_history)
        as_of_date = portfolio.get("as_of_date", "")

        warnings = missing_data_warnings(
            fund_codes=fund_codes,
            fund_profiles=fund_profiles,
            nav_history=nav_history,
            holdings=holdings,
        )

        try:
            position_weights = calculate_position_weights(portfolio)
            concentration = calculate_concentration_metrics(positions)
            exposures = calculate_theme_exposure(
                positions,
                fund_profiles=fund_profiles,
                holdings=holdings,
            )
            cash_ratio = calculate_cash_ratio(portfolio)
            industry_exposure = calculate_industry_exposure(positions, holdings)
            fund_type_exposure = {
                key.replace("fund_type:", ""): round(value, 6)
                for key, value in exposures.items()
                if key.startswith("fund_type:")
            }
            fund_metrics = {
                fund_code: calculate_fund_metrics(nav_history[fund_code])
                for fund_code in fund_codes
                if fund_code in nav_history
            }
            metrics_for_flags = {
                "concentration": concentration,
                "fund_metrics": fund_metrics,
            }
            risk_flags = detect_portfolio_risk_flags(
                portfolio=portfolio,
                risk_profile=risk_profile,
                exposures=exposures,
                metrics=metrics_for_flags,
                industry_exposure=industry_exposure,
            )
            pnl_summary = None
            trade_budget = calculate_trade_budget(portfolio, risk_profile, constraints)
            short_term_budget = None
            dca_review = None
            if positions and any(
                isinstance(p, dict) and p.get("total_cost") is not None
                for p in positions
            ):
                pnl_summary = calculate_portfolio_pnl(positions)
            if transactions:
                short_term_budget = calculate_short_term_budget_usage(
                    positions, transactions, risk_profile, as_of_date
                )
            if dca_plans:
                dca_review = review_dca_plan(
                    dca_plans, portfolio, transactions, risk_profile
                )

            normalized_transactions = []
            ledger_summary = None
            cost_basis_summary = None
            reconciliation = None
            trading_flags: list[dict[str, Any]] = []
            scenario_flags: list[dict[str, Any]] = []
            if transactions:
                normalized_transactions, txn_warnings = normalize_fund_transactions(transactions)
                if txn_warnings:
                    warnings.extend(txn_warnings)

                # Determine as_of_date for transaction-aware tools:
                # use portfolio.as_of_date or fall back to latest transaction date.
                txn_as_of = as_of_date
                if not txn_as_of and normalized_transactions:
                    txn_dates = [t.date for t in normalized_transactions if t.date]
                    if txn_dates:
                        txn_as_of = max(txn_dates)

                ledger_summary = summarize_transaction_ledger(
                    normalized_transactions, nav_data, txn_as_of
                )
                cost_basis_summary = {
                    fund_code: cb.to_dict()
                    for fund_code, cb in calculate_position_cost_basis(
                        normalized_transactions, nav_data, txn_as_of
                    ).items()
                }
                reconciliation = reconcile_portfolio_with_transactions(
                    portfolio, ledger_summary
                )
                trading_flags = detect_trading_discipline_flags(
                    normalized_transactions, risk_profile, portfolio, txn_as_of
                )
            scenario_flags = scenario_flags_from_market_scenario(market_scenario)

            # Check for optional data dimensions host might have requested
            add_missing_optional_warnings(
                warnings, fund_codes,
                benchmarks=benchmarks,
                benchmark_history=benchmark_history,
                peer_group=peer_group,
                factor_exposures=factor_exposures,
                manager_profiles=manager_profiles,
                fee_schedules=fee_schedules,
                redemption_rules=redemption_rules,
            )

            # Research query plan (deterministic, no network)
            query_plan = None
            if research_planning:
                try:
                    themes = list(exposures.get("theme_exposure", {}).keys()) if isinstance(exposures, dict) else []
                    industries = list(industry_exposure.keys()) if isinstance(industry_exposure, dict) else []
                    query_plan = build_research_query_plan(
                        portfolio_positions=positions,
                        holdings=holdings,
                        fund_profiles=fund_profiles,
                        themes=themes[:20],
                        industries=industries[:20],
                        kg_context=skill_input.kg_context,
                    )
                except Exception:
                    pass

            # Optional data pass-through summaries
            benchmark_summary = summarize_benchmark_gap(
                fund_metrics, benchmarks, benchmark_history
            ) if (benchmarks or benchmark_history) else None
            peer_summary = summarize_peer_data(peer_group) if peer_group else None
            fee_summary = summarize_fee_schedule(fee_schedules, fund_codes) if fee_schedules else None
            redemption_summary = summarize_redemption_constraints(
                redemption_rules, fund_codes
            ) if redemption_rules else None
            factor_summary = summarize_factor_exposures(
                factor_exposures
            ) if factor_exposures else None
            manager_summary = summarize_manager_profiles(
                manager_profiles, fund_codes
            ) if manager_profiles else None

            target_weights = target_weights_from_payload(payload, positions)

            portfolio_summary = build_portfolio_summary(
                portfolio,
                fund_codes,
                position_weights,
            )

            all_risk_flags = risk_flags + trading_flags + scenario_flags
            risk_flags_refs = [f["type"] for f in all_risk_flags]
            evidence_ids = [
                f"ev:{spec['metric_name']}"
                for spec in evidence_specs(
                    skill_input=skill_input,
                    fund_codes=fund_codes,
                    portfolio_summary=portfolio_summary,
                    concentration=concentration,
                    fund_metrics=fund_metrics,
                    risk_flags=all_risk_flags,
                    rebalance_plan=None,
                    cost_basis_summary=cost_basis_summary,
                    short_term_budget=short_term_budget,
                    dca_review=dca_review,
                    market_scenario=market_scenario,
                    pnl_summary=pnl_summary,
                )
            ]
            rebalance_plan = (
                simulate_rebalance(
                    portfolio=portfolio,
                    target_weights=target_weights,
                    constraints=constraints,
                    risk_profile=risk_profile,
                    risk_flags_refs=risk_flags_refs,
                    evidence_refs=evidence_ids,
                )
                if target_weights
                else None
            )
            enrich_rebalance_plan_with_positions(rebalance_plan, positions, pnl_summary)
            report = FundAnalysisReport(
                fund_metrics=fund_metrics,
                portfolio_metrics=portfolio_summary,
                exposures=exposures,
                concentration=concentration,
                risk_flags=risk_flags + trading_flags + scenario_flags,
                suggested_watchlist=suggested_watchlist(fund_metrics, risk_flags),
                warnings=warnings,
                pnl_summary=pnl_summary,
                exposure_summary=summarize_exposure(
                    {k: v for k, v in exposures.items() if not k.startswith("fund_type:")},
                    industry_exposure,
                    {k: v for k, v in exposures.items() if k.startswith("fund_type:")},
                ),
                trade_budget=trade_budget,
                short_term_budget=short_term_budget,
                dca_review=dca_review,
                transaction_summary=ledger_summary.to_dict() if ledger_summary is not None else None,
                cost_basis_summary=cost_basis_summary,
                reconciliation=reconciliation,
                trading_flags=trading_flags,
                market_scenario=market_scenario if market_scenario else None,
            ).to_dict()
            # Augment report with new optional fields
            if benchmark_summary is not None:
                report["benchmark_summary"] = benchmark_summary
            if peer_summary is not None:
                report["peer_summary"] = peer_summary
            if fee_summary is not None:
                report["fee_summary"] = fee_summary
            if redemption_summary is not None:
                report["redemption_summary"] = redemption_summary
            if factor_summary is not None:
                report["factor_summary"] = factor_summary
            if manager_summary is not None:
                report["manager_summary"] = manager_summary
            if query_plan is not None:
                report["research_query_plan"] = query_plan
        except Exception as exc:
            return failed_output(
                skill_input,
                "INTERNAL_ERROR",
                f"FundAnalysisSkill analysis failed: {exc}",
                details={"error_type": type(exc).__name__},
            )

        artifacts: dict[str, Any] = {
            "portfolio_summary": portfolio_summary,
            "position_summary": build_position_summary(positions),
            "cost_basis_summary": cost_basis_summary if transactions else None,
            "pnl_summary": pnl_summary,
            "exposure_summary": summarize_exposure(
                {k: v for k, v in exposures.items() if not k.startswith("fund_type:")},
                industry_exposure,
                {k: v for k, v in exposures.items() if k.startswith("fund_type:")},
            ),
            "risk_flags": risk_flags + trading_flags + scenario_flags,
            "short_term_trade_budget": short_term_budget if transactions else None,
            "dca_plan_review": dca_review if dca_plans else None,
            "suggested_rebalance_plan": rebalance_plan,
            "fund_analysis_report": report,
            "warnings": warnings + list(
                reconciliation.get("warnings", [])
                if reconciliation else []
            ),
            "market_scenario_impact": market_scenario if market_scenario else None,
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
        if query_plan:
            artifacts["research_query_plan"] = query_plan

        # Optional data pass-through artifacts
        if benchmark_summary:
            artifacts["benchmark_summary"] = benchmark_summary
        if peer_summary:
            artifacts["peer_summary"] = peer_summary
        if fee_summary:
            artifacts["fee_summary"] = fee_summary
        if redemption_summary:
            artifacts["redemption_summary"] = redemption_summary
        if factor_summary:
            artifacts["factor_summary"] = factor_summary
        if manager_summary:
            artifacts["manager_summary"] = manager_summary

        data_completeness = attach_report_artifacts(
            payload=payload,
            artifacts=artifacts,
            warnings=warnings,
            report=report,
        )

        final_evidence_specs = evidence_specs(
            skill_input=skill_input,
            fund_codes=fund_codes,
            portfolio_summary=portfolio_summary,
            concentration=concentration,
            fund_metrics=fund_metrics,
            risk_flags=risk_flags + trading_flags + scenario_flags,
            rebalance_plan=rebalance_plan,
            cost_basis_summary=cost_basis_summary,
            short_term_budget=short_term_budget,
            dca_review=dca_review,
            market_scenario=market_scenario,
            pnl_summary=pnl_summary,
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
                artifacts=artifacts,
                warnings=warnings,
                errors=errors,
            )

        status = status_from_analysis(
            errors=errors,
            data_completeness=data_completeness,
            warnings=warnings,
        )
        return SkillOutput(
            step_id=skill_input.step_id,
            skill_name=skill_input.skill_name,
            evidence_items=evidence_items,
            artifacts=artifacts,
            warnings=warnings,
            errors=errors,
            status=status,
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

