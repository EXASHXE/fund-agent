"""Evidence generation helpers for FundAnalysisSkill."""

from __future__ import annotations

from typing import Any

from src.schemas.skill import SkillError, SkillInput
from src.tools.evidence.builders import build_hard_evidence_from_metric

MAX_POSITION_EVIDENCE = 5


def evidence_specs(
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
            "direction": direction_from_concentration(concentration),
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
                "direction": direction_from_fund_metrics(metrics),
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
        top_pnl_positions = top_n_pnl_positions(pnl_summary, MAX_POSITION_EVIDENCE)
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


def build_evidence_items(
    skill_input: SkillInput,
    specs: list[dict[str, Any]],
) -> tuple[list[Any], list[dict[str, Any]]]:
    evidence_items = []
    errors: list[dict[str, Any]] = []
    for spec in specs:
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
    return evidence_items, errors


def build_baseline_evidence(
    skill_input: SkillInput,
    entities: list[str],
) -> tuple[list[Any], list[dict[str, Any]]]:
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
    return evidence_items, errors


def direction_from_concentration(concentration: dict[str, Any]) -> str:
    hhi = float(concentration.get("hhi", 0.0) or 0.0)
    max_weight = float(concentration.get("single_fund_max_weight", 0.0) or 0.0)
    if max_weight > 0.3 or hhi > 0.25:
        return "negative"
    if max_weight < 0.2 and hhi < 0.15:
        return "positive"
    return "neutral"


def direction_from_fund_metrics(metrics: dict[str, Any]) -> str:
    total_return = float(metrics.get("total_return", 0.0) or 0.0)
    max_drawdown = float(metrics.get("max_drawdown", 0.0) or 0.0)
    if max_drawdown > 0.25:
        return "negative"
    if total_return > 0.05:
        return "positive"
    if total_return < -0.05:
        return "negative"
    return "neutral"


def top_n_pnl_positions(pnl_summary: dict[str, Any], n: int) -> list[dict[str, Any]]:
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
