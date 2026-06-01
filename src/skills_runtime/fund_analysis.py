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
from src.tools.portfolio.transaction import (
    calculate_position_cost_basis,
    detect_trading_discipline_flags,
    normalize_fund_transactions,
    reconcile_portfolio_with_transactions,
    summarize_transaction_ledger,
)


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

        if "portfolio" not in payload:
            if _has_related_entities(payload, skill_input):
                return self._run_baseline(skill_input)
            return _failed_output(
                skill_input,
                "INVALID_INPUT",
                "FundAnalysisSkill requires payload.portfolio or related_entities",
            )

        return self._run_portfolio_analysis(skill_input, payload)

    def _run_portfolio_analysis(
        self,
        skill_input: SkillInput,
        payload: dict[str, Any],
    ) -> SkillOutput:
        portfolio = payload.get("portfolio")
        if not isinstance(portfolio, dict):
            return _failed_output(
                skill_input,
                "INVALID_INPUT",
                "payload.portfolio must be a dictionary",
            )

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
                    positions, transactions, risk_profile
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
                normalized_transactions = normalize_fund_transactions(transactions)
                ledger_summary = summarize_transaction_ledger(
                    normalized_transactions, nav_data, as_of_date
                )
                cost_basis_summary = {
                    fund_code: cb.to_dict()
                    for fund_code, cb in calculate_position_cost_basis(
                        normalized_transactions, nav_data, as_of_date
                    ).items()
                }
                reconciliation = reconcile_portfolio_with_transactions(
                    portfolio, ledger_summary
                )
                trading_flags = detect_trading_discipline_flags(
                    normalized_transactions, risk_profile, portfolio
                )
            if market_scenario:
                scenario_flags.append({
                    "type": "market_scenario",
                    "severity": "high" if market_scenario.get("risk_level") == "high" else "medium",
                    "message": f"Host-provided market scenario: {market_scenario.get('name', 'unknown')}",
                    "details": {"scenario": market_scenario},
                })

            position_map = {p["fund_code"]: p for p in positions if isinstance(p, dict) and p.get("fund_code")}
            target_weights = _target_weights_from_payload(payload, positions)
            rebalance_plan = (
                simulate_rebalance(
                    portfolio=portfolio,
                    target_weights=target_weights,
                    constraints=constraints,
                    risk_profile=risk_profile,
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
            portfolio_summary = {
                "as_of_date": portfolio.get("as_of_date", ""),
                "total_value": float(portfolio.get("total_value", 0.0) or 0.0),
                "cash_available": float(portfolio.get("cash_available", 0.0) or 0.0),
                "position_count": len(fund_codes),
                "position_weights": position_weights,
            }
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
        for fund_code, pos_pnl in pnl_summary.get("positions", {}).items():
            specs.append(
                {
                    "metric_name": "position_pnl",
                    "metric_value": pos_pnl,
                    "claim": f"Position PnL computed for fund {fund_code}",
                    "related_entities": [f"fund:{fund_code}"],
                    "direction": "positive" if (pos_pnl.get("unrealized_pnl") or 0) > 0 else "negative" if (pos_pnl.get("unrealized_pnl") or 0) < 0 else "neutral",
                    "provenance": {
                        "skill_name": skill_input.skill_name,
                        "tool": "src.tools.portfolio.analysis",
                    },
                }
            )
        specs.append(
            {
                "metric_name": "portfolio_pnl",
                "metric_value": {
                    "total_cost": pnl_summary.get("total_cost"),
                    "total_value": pnl_summary.get("total_value"),
                    "unrealized_pnl": pnl_summary.get("unrealized_pnl"),
                    "unrealized_pnl_pct": pnl_summary.get("unrealized_pnl_pct"),
                },
                "claim": "Portfolio-level PnL summary computed",
                "related_entities": entities,
                "direction": "positive" if (pnl_summary.get("unrealized_pnl") or 0) > 0 else "negative" if (pnl_summary.get("unrealized_pnl") or 0) < 0 else "neutral",
                "provenance": {
                    "skill_name": skill_input.skill_name,
                    "tool": "src.tools.portfolio.analysis",
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
