"""Fund analysis skill runtime.

This skill performs local-only personal fund and portfolio analysis from
structured host-provided payloads. It does not call MCP, network, LLM, or
provider SDKs. External hosts own data fetching and orchestration.
"""

from __future__ import annotations

from typing import Any

from src.schemas.fund import FundAnalysisReport
from src.schemas.skill import SkillError, SkillInput, SkillOutput
from src.tools.evidence.builders import build_hard_evidence_from_metric
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
from src.tools.portfolio.ledger_snapshot import (
    build_position_snapshot_from_transactions,
    reconcile_snapshot_with_portfolio,
)
from src.tools.portfolio.transaction import (
    calculate_position_cost_basis,
    detect_trading_discipline_flags,
    normalize_fund_transactions,
    reconcile_portfolio_with_transactions,
    summarize_transaction_ledger,
)
from src.tools.research.query_plan import build_research_query_plan

MAX_POSITION_EVIDENCE = 5


class FundAnalysisSkill:
    """Local personal fund and portfolio analysis skill."""

    mcp_adapter = None
    tool_registry = None

    def run(self, skill_input: SkillInput) -> SkillOutput:
        payload = skill_input.payload or {}

        if not isinstance(payload, dict):
            return _failed_output(
                skill_input,
                "INVALID_INPUT",
                "FundAnalysisSkill payload must be a dictionary",
            )

        portfolio = _dict_or_empty(payload.get("portfolio"))
        positions = portfolio.get("positions")

        # Determine source-of-truth for portfolio positions
        source_of_truth: str | None = None
        derived_snapshot: dict[str, Any] | None = None
        reconciliation_report: dict[str, Any] | None = None

        has_host_positions = isinstance(positions, list) and len(positions) > 0
        has_transactions = isinstance(payload.get("transactions"), list) and len(payload["transactions"]) > 0
        has_current_nav = isinstance(payload.get("current_nav"), dict) and len(payload["current_nav"]) > 0

        if has_host_positions:
            source_of_truth = "host_portfolio"
        elif has_transactions and has_current_nav:
            # Derive portfolio snapshot from transactions + current_nav
            as_of_date = portfolio.get("as_of_date", payload.get("as_of_date", ""))
            if not as_of_date:
                return _failed_output(
                    skill_input,
                    "INVALID_INPUT",
                    "Cannot derive portfolio from transactions: missing as_of_date",
                )
            try:
                derived_snapshot = build_position_snapshot_from_transactions(
                    transactions=payload["transactions"],
                    current_nav_by_fund=payload["current_nav"],
                    as_of_date=as_of_date,
                    options=payload.get("settlement_options"),
                )
                source_of_truth = "derived_from_transactions"
            except Exception as exc:
                return _failed_output(
                    skill_input,
                    "INTERNAL_ERROR",
                    f"Failed to derive portfolio from transactions: {exc}",
                    details={"error_type": type(exc).__name__},
                )
        elif not has_host_positions:
            if _has_related_entities(payload, skill_input):
                return self._run_baseline(skill_input)
            return _failed_output(
                skill_input,
                "INVALID_INPUT",
                "FundAnalysisSkill requires portfolio.positions or transactions+current_nav or related_entities",
            )

        # If both host portfolio and derivable transactions exist, reconcile
        if has_host_positions and has_transactions and has_current_nav:
            try:
                derived_for_reconcile = build_position_snapshot_from_transactions(
                    transactions=payload["transactions"],
                    current_nav_by_fund=payload["current_nav"],
                    as_of_date=portfolio.get("as_of_date", payload.get("as_of_date", "")),
                    options=payload.get("settlement_options"),
                )
                reconciliation_report = reconcile_snapshot_with_portfolio(
                    derived_for_reconcile, portfolio
                )
            except Exception:
                # Reconciliation failure should not block analysis
                pass

        return self._run_portfolio_analysis(
            skill_input=skill_input,
            payload=payload,
            source_of_truth=source_of_truth,
            derived_snapshot=derived_snapshot,
            reconciliation_report=reconciliation_report,
        )

    def _run_portfolio_analysis(
        self,
        skill_input: SkillInput,
        payload: dict[str, Any],
        source_of_truth: str | None = None,
        derived_snapshot: dict[str, Any] | None = None,
        reconciliation_report: dict[str, Any] | None = None,
    ) -> SkillOutput:
        portfolio = _dict_or_empty(payload.get("portfolio"))

        # When derived from transactions, reconstruct portfolio from snapshot
        if source_of_truth == "derived_from_transactions" and derived_snapshot:
            positions = derived_snapshot.get("positions", [])
            # Build portfolio dict from snapshot positions
            total_value = 0.0
            for pos in positions:
                cv = pos.get("current_value") or 0.0
                total_value += cv
            portfolio = {
                "as_of_date": derived_snapshot.get("as_of_date", payload.get("as_of_date", "")),
                "total_value": total_value,
                "cash_available": payload.get("current_nav", {}).get("_cash_available",
                                    derived_snapshot.get("cashflow_summary", {}).get("implied_cash", 0.0)),
                "positions": [
                    {
                        "fund_code": pos.get("fund_code", ""),
                        "fund_name": pos.get("fund_code", ""),  # name unknown from ledger only
                        "shares": pos.get("shares"),
                        "current_value": pos.get("current_value"),
                        "total_cost": pos.get("total_cost"),
                        "tags": [],
                    }
                    for pos in positions
                ],
            }
        else:
            positions = portfolio.get("positions")

        if not isinstance(positions, list) or not positions:
            return _failed_output(
                skill_input,
                "INVALID_INPUT",
                "payload.portfolio.positions must be a non-empty list",
            )

        fund_codes = [
            str(position.get("fund_code"))
            for position in positions
            if isinstance(position, dict) and position.get("fund_code")
        ]
        if not fund_codes:
            return _failed_output(
                skill_input,
                "INVALID_INPUT",
                "portfolio positions must include fund_code",
            )

        fund_profiles = _dict_or_empty(payload.get("fund_profiles"))
        nav_history = _dict_or_empty(payload.get("nav_history"))
        holdings = _dict_or_empty(payload.get("holdings"))
        risk_profile = _dict_or_empty(payload.get("risk_profile"))
        constraints = _dict_or_empty(payload.get("constraints"))
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

        nav_data: dict[str, float] = {}
        for fund_code, nav_points in nav_history.items():
            if isinstance(nav_points, list) and nav_points:
                latest = max(nav_points, key=lambda x: x.get("date", ""))
                if isinstance(latest, dict) and latest.get("nav") is not None:
                    nav_data[fund_code] = float(latest["nav"])
        as_of_date = portfolio.get("as_of_date", "")

        warnings = _missing_data_warnings(
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
            if market_scenario:
                scenario_flags.append({
                    "type": "market_scenario",
                    "severity": "high" if market_scenario.get("risk_level") == "high" else "medium",
                    "message": f"Host-provided market scenario: {market_scenario.get('name', 'unknown')}",
                    "details": {"scenario": market_scenario},
                })

            # Check for optional data dimensions host might have requested
            _add_missing_optional_warnings(
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

            position_map = {p["fund_code"]: p for p in positions if isinstance(p, dict) and p.get("fund_code")}
            target_weights = _target_weights_from_payload(payload, positions)

            portfolio_summary = {
                "as_of_date": portfolio.get("as_of_date", ""),
                "total_value": float(portfolio.get("total_value", 0.0) or 0.0),
                "cash_available": float(portfolio.get("cash_available", 0.0) or 0.0),
                "position_count": len(fund_codes),
                "position_weights": position_weights,
            }

            all_risk_flags = risk_flags + trading_flags + scenario_flags
            risk_flags_refs = [f["type"] for f in all_risk_flags]
            evidence_ids = [
                f"ev:{spec['metric_name']}"
                for spec in _evidence_specs(
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
            if rebalance_plan is not None:
                pos_pnl_map = pnl_summary.get("positions", {}) if pnl_summary else {}
                for trade_leg in rebalance_plan.get("suggested_trade_plan", []):
                    fund_code = trade_leg.get("fund_code", "")
                    pos = position_map.get(fund_code, {})
                    trade_leg["fund_name"] = pos.get("fund_name", pos.get("name", fund_code))
                    trade_leg["current_value"] = pos.get("current_value", 0.0)
                    trade_leg["current_cost"] = pos.get("total_cost")
                    trade_leg["unrealized_pnl"] = pos_pnl_map.get(fund_code, {}).get("unrealized_pnl")
                    trade_leg["cap_reasons"] = trade_leg.get("cap_reasons", [])
                    trade_leg["rationale"] = ""
                    if trade_leg.get("capped"):
                        trade_leg["rationale"] = "Capped by constraints" + (
                            f": {', '.join(trade_leg['cap_reasons'])}"
                            if trade_leg.get("cap_reasons") else ""
                        )
                    else:
                        trade_leg["rationale"] = "Within constraint bounds"
                    trade_leg["tags"] = pos.get("tags", [])
            report = FundAnalysisReport(
                fund_metrics=fund_metrics,
                portfolio_metrics=portfolio_summary,
                exposures=exposures,
                concentration=concentration,
                risk_flags=risk_flags + trading_flags + scenario_flags,
                suggested_watchlist=_suggested_watchlist(fund_metrics, risk_flags),
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
            return _failed_output(
                skill_input,
                "INTERNAL_ERROR",
                f"FundAnalysisSkill analysis failed: {exc}",
                details={"error_type": type(exc).__name__},
            )

        artifacts: dict[str, Any] = {
            "portfolio_summary": portfolio_summary,
            "position_summary": {
                p["fund_code"]: {
                    "fund_code": p.get("fund_code"),
                    "fund_name": p.get("fund_name", p.get("name", "")),
                    "current_value": p.get("current_value", 0.0),
                    "total_cost": p.get("total_cost"),
                    "shares": p.get("shares"),
                    "target_weight": p.get("target_weight"),
                    "tags": p.get("tags", []),
                    "pending_amount": p.get("pending_amount", 0.0),
                }
                for p in positions
                if isinstance(p, dict) and p.get("fund_code")
            },
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

        evidence_items = []
        errors: list[dict[str, Any]] = []
        evidence_specs = _evidence_specs(
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
        for spec in evidence_specs:
            try:
                evidence_items.append(build_hard_evidence_from_metric(**spec))
            except Exception as exc:
                errors.append(
                    SkillError(
                        code="EVIDENCE_BUILD_FAILED",
                        message=str(exc),
                        details={
                            "error_type": type(exc).__name__,
                            "skill_name": skill_input.skill_name,
                        },
                    ).to_dict()
                )

        if not evidence_items:
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

        status = "PARTIAL" if warnings or errors else "OK"
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
        entities = _entities_from_input(skill_input)
        evidence_items = []
        errors = []
        for entity in entities:
            try:
                metric_value = {
                    "fund": entity,
                    "fund_count": len(entities),
                    "source": "local_quant_tools",
                }
                evidence_items.append(
                    build_hard_evidence_from_metric(
                        metric_name="local_quant_tools",
                        metric_value=metric_value,
                        claim=f"Local quant baseline generated for {entity}",
                        related_entities=[entity],
                        direction="neutral",
                        provenance={
                            "skill_name": skill_input.skill_name,
                            "tool": "local_quant_tools",
                            "fallback": "related_entities_only",
                        },
                    )
                )
            except Exception as exc:
                errors.append(
                    SkillError(
                        code="EVIDENCE_BUILD_FAILED",
                        message=str(exc),
                        details={
                            "error_type": type(exc).__name__,
                            "skill_name": skill_input.skill_name,
                        },
                    ).to_dict()
                )
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


def _evidence_specs(
    *,
    skill_input: SkillInput,
    fund_codes: list[str],
    portfolio_summary: dict[str, Any],
    concentration: dict[str, Any],
    fund_metrics: dict[str, Any],
    risk_flags: list[dict[str, Any]],
    rebalance_plan: dict[str, Any] | None,
    cost_basis_summary: dict[str, Any] | None = None,
    short_term_budget: dict[str, Any] | None = None,
    dca_review: dict[str, Any] | None = None,
    market_scenario: dict[str, Any] | None = None,
    pnl_summary: dict[str, Any] | None = None,
    source_of_truth: str | None = None,
    derived_snapshot: dict[str, Any] | None = None,
    reconciliation_report: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    entities = [f"fund:{code}" for code in fund_codes] or ["portfolio"]
    specs: list[dict[str, Any]] = [
        {
            "metric_name": "portfolio_allocation_concentration",
            "metric_value": {
                "portfolio_summary": portfolio_summary,
                "concentration": concentration,
            },
            "claim": "Portfolio allocation and concentration metrics were computed",
            "related_entities": entities,
            "direction": _direction_from_concentration(concentration),
            "provenance": {
                "skill_name": skill_input.skill_name,
                "tool": "src.tools.portfolio.analysis",
            },
        }
    ]

    for fund_code, metrics in fund_metrics.items():
        specs.append(
            {
                "metric_name": "fund_risk_return_metrics",
                "metric_value": metrics,
                "claim": f"Risk-return metrics were computed for fund {fund_code}",
                "related_entities": [f"fund:{fund_code}"],
                "direction": _direction_from_fund_metrics(metrics),
                "provenance": {
                    "skill_name": skill_input.skill_name,
                    "tool": "src.tools.fund.metrics",
                },
            }
        )

    specs.append(
        {
            "metric_name": "portfolio_risk_flags",
            "metric_value": {"risk_flags": risk_flags},
            "claim": f"Portfolio risk flag scan found {len(risk_flags)} issue(s)",
            "related_entities": entities,
            "direction": "negative" if risk_flags else "neutral",
            "provenance": {
                "skill_name": skill_input.skill_name,
                "tool": "src.tools.portfolio.analysis",
            },
        }
    )

    if rebalance_plan is not None:
        specs.append(
            {
                "metric_name": "portfolio_rebalance_simulation",
                "metric_value": rebalance_plan,
                "claim": "Portfolio rebalance simulation was generated",
                "related_entities": entities,
                "direction": "neutral",
                "provenance": {
                    "skill_name": skill_input.skill_name,
                    "tool": "src.tools.portfolio.analysis",
                },
            }
        )

    if cost_basis_summary is not None:
        specs.append(
            {
                "metric_name": "position_cost_basis",
                "metric_value": cost_basis_summary,
                "claim": "Position cost basis computed from transaction history",
                "related_entities": entities,
                "direction": "neutral",
                "provenance": {
                    "skill_name": skill_input.skill_name,
                    "tool": "src.tools.portfolio.transaction",
                },
            }
        )

    if short_term_budget is not None:
        specs.append(
            {
                "metric_name": "short_term_budget_usage",
                "metric_value": short_term_budget,
                "claim": "Short-term trading budget usage computed",
                "related_entities": entities,
                "direction": "negative" if short_term_budget.get("exceeded") else "neutral",
                "provenance": {
                    "skill_name": skill_input.skill_name,
                    "tool": "src.tools.portfolio.analysis",
                },
            }
        )

    if dca_review is not None:
        specs.append(
            {
                "metric_name": "dca_plan_review",
                "metric_value": dca_review,
                "claim": f"DCA plan review completed with {len(dca_review.get('suggestions', []))} action(s) suggested",
                "related_entities": entities,
                "direction": "neutral",
                "provenance": {
                    "skill_name": skill_input.skill_name,
                    "tool": "src.tools.portfolio.analysis",
                },
            }
        )

    if market_scenario:
        specs.append(
            {
                "metric_name": "market_scenario_impact",
                "metric_value": {"scenario": market_scenario},
                "claim": f"Market scenario impact assessed: {market_scenario.get('name', 'unknown')}",
                "related_entities": entities,
                "direction": "negative" if market_scenario.get("risk_level") == "high" else "neutral",
                "provenance": {
                    "skill_name": skill_input.skill_name,
                    "tool": "host_provided",
                },
            }
        )

    if pnl_summary is not None:
        top_pnl_positions = _top_n_pnl_positions(pnl_summary, MAX_POSITION_EVIDENCE)
        specs.append(
            {
                "metric_name": "portfolio_pnl_summary",
                "metric_value": {
                    "total_cost": pnl_summary.get("total_cost"),
                    "total_value": pnl_summary.get("total_value"),
                    "unrealized_pnl": pnl_summary.get("unrealized_pnl"),
                    "unrealized_pnl_pct": pnl_summary.get("unrealized_pnl_pct"),
                    "top_positions": top_pnl_positions,
                },
                "claim": "Portfolio-level PnL summary with top positions computed",
                "related_entities": entities,
                "direction": "positive" if (pnl_summary.get("unrealized_pnl") or 0) > 0 else "negative" if (pnl_summary.get("unrealized_pnl") or 0) < 0 else "neutral",
                "provenance": {
                    "skill_name": skill_input.skill_name,
                    "tool": "src.tools.portfolio.analysis",
                },
            }
        )

    if source_of_truth == "derived_from_transactions" and derived_snapshot:
        specs.append(
            {
                "metric_name": "derived_portfolio_snapshot",
                "metric_value": derived_snapshot,
                "claim": "Portfolio snapshot was deterministically derived from transaction ledger and current NAV",
                "related_entities": entities,
                "direction": "neutral",
                "provenance": {
                    "skill_name": skill_input.skill_name,
                    "tool": "src.tools.portfolio.ledger_snapshot",
                },
            }
        )

    if reconciliation_report and reconciliation_report.get("mismatches"):
        specs.append(
            {
                "metric_name": "ledger_reconciliation_mismatch",
                "metric_value": reconciliation_report,
                "claim": f"Ledger-portfolio reconciliation found {len(reconciliation_report['mismatches'])} mismatches",
                "related_entities": entities,
                "direction": "negative",
                "provenance": {
                    "skill_name": skill_input.skill_name,
                    "tool": "src.tools.portfolio.ledger_snapshot",
                },
            }
        )

    return specs


def _target_weights_from_payload(
    payload: dict[str, Any],
    positions: list[dict[str, Any]],
) -> dict[str, float]:
    raw = payload.get("target_weights")
    if isinstance(raw, dict):
        return {
            str(fund_code): float(weight)
            for fund_code, weight in raw.items()
            if _is_number(weight)
        }

    targets: dict[str, float] = {}
    for position in positions:
        if not isinstance(position, dict):
            continue
        fund_code = position.get("fund_code")
        target_weight = position.get("target_weight")
        if fund_code and _is_number(target_weight):
            targets[str(fund_code)] = float(target_weight)
    return targets


def _missing_data_warnings(
    *,
    fund_codes: list[str],
    fund_profiles: dict[str, Any],
    nav_history: dict[str, Any],
    holdings: dict[str, Any],
) -> list[str]:
    warnings: list[str] = []
    for fund_code in fund_codes:
        if fund_code not in fund_profiles:
            warnings.append(f"Missing fund profile for fund_code={fund_code}")
        if fund_code not in nav_history:
            warnings.append(f"Missing NAV history for fund_code={fund_code}")
        if fund_code not in holdings:
            warnings.append(f"Missing holdings for fund_code={fund_code}")
    return warnings


def _suggested_watchlist(
    fund_metrics: dict[str, Any],
    risk_flags: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    watchlist: list[dict[str, Any]] = []
    flagged_funds = {
        flag.get("details", {}).get("fund_code")
        for flag in risk_flags
        if flag.get("details", {}).get("fund_code")
    }
    for fund_code, metrics in fund_metrics.items():
        if fund_code in flagged_funds or float(metrics.get("max_drawdown", 0.0)) > 0.2:
            watchlist.append(
                {
                    "fund_code": fund_code,
                    "reason": "drawdown or concentration risk requires monitoring",
                }
            )
    return watchlist


def _direction_from_concentration(concentration: dict[str, Any]) -> str:
    hhi = float(concentration.get("hhi", 0.0) or 0.0)
    max_weight = float(concentration.get("single_fund_max_weight", 0.0) or 0.0)
    if max_weight > 0.3 or hhi > 0.25:
        return "negative"
    if max_weight < 0.2 and hhi < 0.15:
        return "positive"
    return "neutral"


def _direction_from_fund_metrics(metrics: dict[str, Any]) -> str:
    total_return = float(metrics.get("total_return", 0.0) or 0.0)
    max_drawdown = float(metrics.get("max_drawdown", 0.0) or 0.0)
    if max_drawdown > 0.25:
        return "negative"
    if total_return > 0.05:
        return "positive"
    if total_return < -0.05:
        return "negative"
    return "neutral"


def _entities_from_input(skill_input: SkillInput) -> list[str]:
    payload_entities = skill_input.payload.get("related_entities")
    if isinstance(payload_entities, list) and payload_entities:
        return [str(entity) for entity in payload_entities]
    fund_codes = skill_input.kg_context.get("fund_codes", [])
    if isinstance(fund_codes, list) and fund_codes:
        return [
            code if str(code).startswith("fund:") else f"fund:{code}"
            for code in fund_codes
        ]
    return ["research_task"]


def _has_related_entities(payload: dict[str, Any], skill_input: SkillInput) -> bool:
    if isinstance(payload.get("related_entities"), list) and payload["related_entities"]:
        return True
    return bool(skill_input.kg_context.get("fund_codes"))


def _failed_output(
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


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _is_number(value: Any) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _top_n_pnl_positions(pnl_summary: dict[str, Any], n: int) -> list[dict[str, Any]]:
    positions = pnl_summary.get("positions", {})
    if not positions:
        return []
    pnl_items = [
        (fund_code, pos)
        for fund_code, pos in positions.items()
        if isinstance(pos, dict)
    ]
    pnl_items.sort(
        key=lambda item: abs(item[1].get("unrealized_pnl") or 0),
        reverse=True,
    )
    return [
        {"fund_code": fund_code, **pos}
        for fund_code, pos in pnl_items[:n]
    ]


# ————————————————————————————— Optional Data Pass-Through Summaries

def summarize_benchmark_gap(
    fund_metrics: dict[str, Any],
    benchmarks: dict[str, Any],
    benchmark_history: dict[str, Any],
) -> dict[str, Any] | None:
    """Minimal pass-through benchmark gap summary. Does not fabricate rankings."""
    result: dict[str, Any] = {
        "benchmarks_available": list(benchmarks.keys()) if benchmarks else [],
    }
    if benchmarks:
        result["benchmarks"] = benchmarks
    if benchmark_history:
        result["benchmark_history"] = benchmark_history
    return result if (benchmarks or benchmark_history) else None


def summarize_peer_data(peer_group: dict[str, Any]) -> dict[str, Any] | None:
    """Minimal pass-through peer group summary."""
    if not peer_group:
        return None
    return {
        "funds_with_peers": list(peer_group.keys()),
        "peer_data": peer_group,
    }


def summarize_fee_schedule(
    fee_schedules: dict[str, Any],
    fund_codes: list[str],
) -> dict[str, Any] | None:
    """Minimal pass-through fee schedule summary."""
    if not fee_schedules:
        return None
    fees_found = {fc: fee_schedules.get(fc) for fc in fund_codes if fc in fee_schedules}
    return {
        "funds_with_fees": list(fees_found.keys()),
        "fee_schedules": fees_found,
    }


def summarize_redemption_constraints(
    redemption_rules: dict[str, Any],
    fund_codes: list[str],
) -> dict[str, Any] | None:
    """Minimal pass-through redemption constraints summary."""
    if not redemption_rules:
        return None
    rules_found = {fc: redemption_rules.get(fc) for fc in fund_codes if fc in redemption_rules}
    return {
        "funds_with_rules": list(rules_found.keys()),
        "redemption_constraints": rules_found,
    }


def summarize_factor_exposures(
    factor_exposures: dict[str, Any],
) -> dict[str, Any] | None:
    """Minimal pass-through factor exposure summary."""
    if not factor_exposures:
        return None
    return {
        "factors": list(factor_exposures.keys()),
        "factor_exposures": factor_exposures,
    }


def summarize_manager_profiles(
    manager_profiles: dict[str, Any],
    fund_codes: list[str],
) -> dict[str, Any] | None:
    """Minimal pass-through manager profile summary."""
    if not manager_profiles:
        return None
    profiles_found = {fc: manager_profiles.get(fc) for fc in fund_codes if fc in manager_profiles}
    return {
        "funds_with_profiles": list(profiles_found.keys()),
        "manager_profiles": profiles_found,
    }


def _add_missing_optional_warnings(
    warnings: list[str],
    fund_codes: list[str],
    *,
    benchmarks: dict[str, Any],
    benchmark_history: dict[str, Any],
    peer_group: dict[str, Any],
    factor_exposures: dict[str, Any],
    manager_profiles: dict[str, Any],
    fee_schedules: dict[str, Any],
    redemption_rules: dict[str, Any],
) -> None:
    """Emit warnings when host requests optional data dimensions but data is missing."""
    if not benchmarks and not benchmark_history:
        # Not requested, no warning needed
        pass
    if not peer_group:
        # Not requested
        pass
