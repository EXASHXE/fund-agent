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
    calculate_concentration_metrics,
    calculate_position_weights,
    calculate_theme_exposure,
    detect_portfolio_risk_flags,
    simulate_rebalance,
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
                risk_flags=risk_flags,
                suggested_watchlist=_suggested_watchlist(fund_metrics, risk_flags),
                warnings=warnings,
            ).to_dict()
        except Exception as exc:
            return _failed_output(
                skill_input,
                "INTERNAL_ERROR",
                f"FundAnalysisSkill analysis failed: {exc}",
                details={"error_type": type(exc).__name__},
            )

        artifacts: dict[str, Any] = {
            "fund_analysis_report": report,
            "portfolio_summary": portfolio_summary,
            "risk_flags": risk_flags,
        }
        if rebalance_plan is not None:
            artifacts["suggested_rebalance_plan"] = rebalance_plan

        evidence_items = []
        errors: list[dict[str, Any]] = []
        evidence_specs = _evidence_specs(
            skill_input=skill_input,
            fund_codes=fund_codes,
            portfolio_summary=portfolio_summary,
            concentration=concentration,
            fund_metrics=fund_metrics,
            risk_flags=risk_flags,
            rebalance_plan=rebalance_plan,
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
