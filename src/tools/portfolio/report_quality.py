"""Deterministic report-quality and data-completeness helpers for FundAnalysisSkill.

These helpers are pure and host-data-driven. They do not call providers,
fetch data, or depend on LLM layers. All outputs are JSON-serializable.
"""

from __future__ import annotations

from typing import Any

# ── required vs optional sections ────────────────────────────────────────────

_REQUIRED_SECTIONS: list[str] = [
    "portfolio_snapshot",
    "current_nav",
    "fund_profiles",
    "nav_history",
    "holdings",
    "risk_profile",
    "constraints",
]

_OPTIONAL_SECTIONS: list[str] = [
    "benchmark_history",
    "peer_group",
    "factor_exposures",
    "manager_profile",
    "fee_schedule",
    "redemption_rules",
    "fund_flow",
    "macro_events",
    "user_investment_plan",
]


def _section_label(key: str) -> str:
    return key.replace("_", " ").title()


# ── data completeness ────────────────────────────────────────────────────────


def calculate_data_completeness(payload: dict[str, Any]) -> dict[str, Any]:
    """Evaluate how complete the host-provided payload is for a personal fund report.

    Returns a dict with *score* (0.0--1.0), *grade* ("A"--"D"),
    available / missing / optional missing section lists, and a
    human-readable *limitations* list.
    """

    portfolio = payload.get("portfolio") or {}
    has_direct_portfolio = bool(
        isinstance(portfolio, dict)
        and isinstance(portfolio.get("positions"), list)
        and len(portfolio["positions"]) > 0
    )
    has_derived_portfolio = bool(
        isinstance(payload.get("transactions"), list)
        and len(payload["transactions"]) > 0
        and isinstance(payload.get("current_nav"), dict)
        and len(payload["current_nav"]) > 0
    )
    has_portfolio = has_direct_portfolio or has_derived_portfolio

    has_nav = bool(
        isinstance(payload.get("current_nav"), dict)
        and len(payload["current_nav"]) > 0
        or (
            isinstance(portfolio, dict)
            and isinstance(portfolio.get("total_value"), (int, float))
            and portfolio["total_value"] > 0
        )
    )

    checks: dict[str, bool] = {
        "portfolio_snapshot": has_portfolio,
        "current_nav": has_nav,
        "fund_profiles": bool(
            payload.get("fund_profiles")
            and isinstance(payload["fund_profiles"], dict)
            and len(payload["fund_profiles"]) > 0
        ),
        "nav_history": bool(
            payload.get("nav_history")
            and isinstance(payload["nav_history"], dict)
            and len(payload["nav_history"]) > 0
        ),
        "holdings": bool(
            payload.get("holdings")
            and isinstance(payload["holdings"], dict)
            and len(payload["holdings"]) > 0
        ),
        "risk_profile": bool(
            payload.get("risk_profile")
            and isinstance(payload["risk_profile"], dict)
            and len(payload["risk_profile"]) > 0
        ),
        "constraints": bool(
            payload.get("constraints")
            and isinstance(payload["constraints"], dict)
            and len(payload["constraints"]) > 0
        ),
    }

    optional_checks: dict[str, bool] = {
        "benchmark_history": bool(
            payload.get("benchmark_history")
            and isinstance(payload["benchmark_history"], dict)
            and len(payload["benchmark_history"]) > 0
        ),
        "peer_group": bool(
            payload.get("peer_group")
            and isinstance(payload["peer_group"], dict)
            and len(payload["peer_group"]) > 0
        ),
        "factor_exposures": bool(
            payload.get("factor_exposures")
            and isinstance(payload["factor_exposures"], dict)
            and len(payload["factor_exposures"]) > 0
        ),
        "manager_profile": bool(
            payload.get("manager_profiles")
            and isinstance(payload["manager_profiles"], dict)
            and len(payload["manager_profiles"]) > 0
        ),
        "fee_schedule": bool(
            payload.get("fee_schedules")
            and isinstance(payload["fee_schedules"], dict)
            and len(payload["fee_schedules"]) > 0
        ),
        "redemption_rules": bool(
            payload.get("redemption_rules")
            and isinstance(payload["redemption_rules"], dict)
            and len(payload["redemption_rules"]) > 0
        ),
        "fund_flow": bool(
            payload.get("fund_flow")
            and isinstance(payload["fund_flow"], dict)
            and len(payload["fund_flow"]) > 0
        ),
        "macro_events": bool(
            payload.get("macro_events")
            and isinstance(payload["macro_events"], (list, dict))
            and len(payload["macro_events"]) > 0
        ),
        "user_investment_plan": bool(
            payload.get("user_investment_plan")
            and isinstance(payload["user_investment_plan"], dict)
            and len(payload["user_investment_plan"]) > 0
        ),
    }

    available_required = [key for key, ok in checks.items() if ok]
    missing_required = [key for key in _REQUIRED_SECTIONS if not checks[key]]
    available_optional = [key for key in _OPTIONAL_SECTIONS if optional_checks[key]]
    missing_optional = [key for key in _OPTIONAL_SECTIONS if not optional_checks[key]]

    critical_missing = [key for key in missing_required if key in {"portfolio_snapshot", "current_nav", "fund_profiles"}]

    # Weighted score: required sections are essential (70%), optional are bonus (30%)
    required_weight = 0.70
    optional_weight = 0.30
    req_ratio = sum(1.0 for key in _REQUIRED_SECTIONS if checks[key]) / len(_REQUIRED_SECTIONS)
    opt_ratio = (
        sum(1.0 for key in _OPTIONAL_SECTIONS if optional_checks[key]) / len(_OPTIONAL_SECTIONS)
        if _OPTIONAL_SECTIONS else 1.0
    )
    score = round(req_ratio * required_weight + opt_ratio * optional_weight, 3)

    # Grade based primarily on required completeness
    if req_ratio >= 1.0 and opt_ratio >= 0.67:
        grade = "A"
    elif req_ratio >= 1.0:
        grade = "B"
    elif req_ratio >= 0.6:
        grade = "C"
    else:
        grade = "D"

    limitations: list[str] = []
    if not has_portfolio:
        limitations.append(
            "No portfolio positions available — report is based on host-provided "
            "fund profiles / transactions only"
        )
    if not checks["fund_profiles"]:
        limitations.append(
            "Fund profile data is missing — fund type, manager, and benchmark "
            "information will be unavailable"
        )
    if not checks["nav_history"]:
        limitations.append(
            "NAV history is missing — performance metrics (returns, drawdowns) "
            "cannot be computed"
        )
    if not checks["holdings"]:
        limitations.append(
            "Holdings data is missing — exposure and concentration analysis "
            "will be limited"
        )
    if not checks["risk_profile"]:
        limitations.append(
            "Risk profile is missing — using default moderate risk assumptions"
        )
    if not checks["constraints"]:
        limitations.append(
            "Trade constraints are missing — rebalance suggestions may not "
            "respect account-level limits"
        )

    return {
        "score": score,
        "grade": grade,
        "available_sections": [
            _section_label(key) for key in available_required + available_optional
        ],
        "missing_sections": [
            _section_label(key) for key in missing_required + missing_optional
        ],
        "critical_missing": [_section_label(key) for key in critical_missing],
        "optional_missing": [_section_label(key) for key in missing_optional],
        "limitations": limitations,
    }


# ── analysis coverage ────────────────────────────────────────────────────────


def summarize_analysis_coverage(
    payload: dict[str, Any],
    artifacts: dict[str, Any],
) -> dict[str, Any]:
    """Summarise which analysis dimensions are covered given host data and
    already-produced artifacts."""

    completeness = calculate_data_completeness(payload)

    has_portfolio = "portfolio_snapshot" not in completeness["missing_sections"]
    derived = artifacts.get("source_of_truth") == "derived_from_transactions"

    # Portfolio
    if has_portfolio and derived:
        portfolio_status = "derived"
    elif has_portfolio:
        portfolio_status = "available"
    else:
        portfolio_status = "missing"

    # Ledger
    ledger_quality = artifacts.get("ledger_quality_summary", {})
    if ledger_quality:
        if ledger_quality.get("is_complete"):
            ledger_status = "complete"
        elif ledger_quality.get("unresolved_events_count", 0) > 0 or ledger_quality.get(
            "invalid_events_count", 0
        ) > 0:
            ledger_status = "partial"
        else:
            ledger_status = "complete"
    elif derived:
        ledger_status = "partial"
    elif has_portfolio:
        ledger_status = "available" if artifacts.get("transaction_summary") else "missing"
    else:
        ledger_status = "missing"

    # Performance
    nav_available = "Nav History" not in completeness["missing_sections"]
    perf_available = bool(artifacts.get("portfolio_summary"))
    if perf_available and nav_available:
        performance_status = "available"
    elif perf_available:
        performance_status = "partial"
    else:
        performance_status = "missing"

    # Holdings
    holdings_available = "Holdings" not in completeness["missing_sections"]
    if holdings_available:
        holdings_status = "available"
    elif artifacts.get("exposure_summary"):
        holdings_status = "partial"
    else:
        holdings_status = "missing"

    # Optional sections
    def _optional_status(key: str) -> str:
        return (
            "missing"
            if _section_label(key) in completeness["optional_missing"]
            else "available"
        )

    benchmark_status = _optional_status("benchmark_history")
    peer_status = _optional_status("peer_group")
    factor_status = _optional_status("factor_exposures")
    fees_status = _optional_status("fee_schedule")
    redemption_status = _optional_status("redemption_rules")

    # Research plan
    research_available = bool(artifacts.get("research_query_plan"))
    research_requested = payload.get("research_planning") is True
    if research_available:
        research_plan_status = "available"
    elif research_requested:
        research_plan_status = "missing_inputs"
    else:
        research_plan_status = "not_requested"

    return {
        "portfolio": portfolio_status,
        "ledger": ledger_status,
        "performance": performance_status,
        "holdings": holdings_status,
        "benchmark": benchmark_status,
        "peer": peer_status,
        "factor": factor_status,
        "fees": fees_status,
        "redemption": redemption_status,
        "research_plan": research_plan_status,
    }


# ── report limitations ───────────────────────────────────────────────────────


def build_report_limitations(
    completeness: dict[str, Any],
    ledger_quality: dict[str, Any] | None = None,
    missing_data: list[str] | None = None,
) -> list[str]:
    """Build a concise, user-facing limitations list from completeness and
    ledger-quality signals."""

    limitations: list[str] = list(completeness.get("limitations", []))

    # Ledger-quality limitations
    if ledger_quality:
        for lim in ledger_quality.get("limitations", []):
            if isinstance(lim, str):
                limitations.append(lim)
        if (
            not ledger_quality.get("is_complete", True)
            and not ledger_quality.get("limitations")
        ):
            limitations.append(
                "Transaction ledger is incomplete — derived positions may differ "
                "from broker statements"
            )

    # Missing data warnings
    if missing_data:
        for item in missing_data:
            if isinstance(item, str) and item not in limitations:
                limitations.append(item)

    # Grade-based general statement
    grade = completeness.get("grade", "D")
    if grade in ("C", "D"):
        limitations.append(
            f"Report data completeness grade is {grade} — key sections are "
            f"missing; broker/fund statements remain the authoritative source"
        )
    elif grade == "B":
        limitations.append(
            "Report data completeness is adequate but some optional sections are "
            "unavailable — deeper analysis may require additional data"
        )

    # Derived portfolio warning
    if "derived" in str(limitations).lower():
        pass  # already covered
    derived_marker = "[derived]"
    if any(derived_marker in lim for lim in limitations):
        pass

    return limitations
