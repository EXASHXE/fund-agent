"""Deterministic report-quality and data-completeness helpers for FundAnalysisSkill.

These helpers are pure and host-data-driven. They do not call providers,
fetch data, or depend on LLM layers. All outputs are JSON-serializable.
"""

from __future__ import annotations

from typing import Any

# ── required vs optional sections ────────────────────────────────────────────

_REQUIRED_SECTIONS: tuple[str, ...] = (
    "portfolio_snapshot",
    "current_nav",
    "fund_profiles",
    "nav_history",
    "holdings",
    "risk_profile",
    "constraints",
)

_OPTIONAL_SECTIONS: tuple[str, ...] = (
    "benchmark_history",
    "peer_group",
    "factor_exposures",
    "manager_profile",
    "fee_schedule",
    "redemption_rules",
    "fund_flow",
    "macro_events",
    "user_investment_plan",
)

_SECTION_LABELS: dict[str, str] = {
    "portfolio_snapshot": "Portfolio Snapshot",
    "current_nav": "Current Value Or Nav",
    "fund_profiles": "Fund Profiles",
    "nav_history": "Nav History",
    "holdings": "Holdings",
    "risk_profile": "Risk Profile",
    "constraints": "Constraints",
    "benchmark_history": "Benchmark History",
    "peer_group": "Peer Group",
    "factor_exposures": "Factor Exposures",
    "manager_profile": "Manager Profile",
    "fee_schedule": "Fee Schedule",
    "redemption_rules": "Redemption Rules",
    "fund_flow": "Fund Flow",
    "macro_events": "Macro Events",
    "user_investment_plan": "User Investment Plan",
}

_MOST_OPTIONAL_COUNT = 6


def _section_label(key: str) -> str:
    return _SECTION_LABELS.get(key, key.replace("_", " ").title())


# ── data completeness ────────────────────────────────────────────────────────


def calculate_data_completeness(
    payload: dict[str, Any],
    ledger_quality_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate how complete the host-provided payload is for a personal fund report.

    Returns a dict with *score* (0.0--1.0), *grade* ("A"--"D"),
    available / missing / optional missing section lists, and a
    human-readable *limitations* list.
    """

    portfolio = payload.get("portfolio") or {}
    direct_positions = _positions_from_portfolio(portfolio)
    has_direct_portfolio = bool(direct_positions)
    has_derived_portfolio = _has_derived_portfolio_inputs(payload) or _has_derived_snapshot(payload)
    has_portfolio = has_direct_portfolio or has_derived_portfolio

    has_nav = _has_position_valuation(portfolio, direct_positions) or _has_current_nav(payload)

    checks: dict[str, bool] = {
        "portfolio_snapshot": has_portfolio,
        "current_nav": has_nav,
        "fund_profiles": _has_non_empty_dict(payload.get("fund_profiles")),
        "nav_history": _has_non_empty_series_map(payload.get("nav_history")),
        "holdings": _has_non_empty_series_map(payload.get("holdings")),
        "risk_profile": _has_non_empty_dict(payload.get("risk_profile")),
        "constraints": _has_non_empty_dict(payload.get("constraints")),
    }

    optional_checks: dict[str, bool] = {
        "benchmark_history": _has_non_empty_dict(payload.get("benchmark_history")),
        "peer_group": _has_non_empty_dict(payload.get("peer_group")),
        "factor_exposures": _has_non_empty_dict(payload.get("factor_exposures")),
        "manager_profile": _has_non_empty_dict(payload.get("manager_profiles")),
        "fee_schedule": _has_non_empty_dict(payload.get("fee_schedules")),
        "redemption_rules": _has_non_empty_dict(payload.get("redemption_rules")),
        "fund_flow": _has_non_empty_dict(payload.get("fund_flow")),
        "macro_events": bool(
            payload.get("macro_events")
            and isinstance(payload["macro_events"], (list, dict))
            and len(payload["macro_events"]) > 0
        ),
        "user_investment_plan": _has_non_empty_dict(payload.get("user_investment_plan")),
    }

    available_required = [key for key, ok in checks.items() if ok]
    missing_required = [key for key in _REQUIRED_SECTIONS if not checks[key]]
    available_optional = [key for key in _OPTIONAL_SECTIONS if optional_checks[key]]
    missing_optional = [key for key in _OPTIONAL_SECTIONS if not optional_checks[key]]

    critical_missing = [
        key for key in missing_required
        if key in {"portfolio_snapshot", "current_nav"}
    ]

    # Weighted score: required sections are essential (70%), optional are bonus (30%)
    required_weight = 0.70
    optional_weight = 0.30
    req_ratio = sum(1.0 for key in _REQUIRED_SECTIONS if checks[key]) / len(_REQUIRED_SECTIONS)
    opt_ratio = (
        sum(1.0 for key in _OPTIONAL_SECTIONS if optional_checks[key]) / len(_OPTIONAL_SECTIONS)
        if _OPTIONAL_SECTIONS else 1.0
    )
    score = req_ratio * required_weight + opt_ratio * optional_weight

    grade = _grade_from_checks(
        checks=checks,
        optional_checks=optional_checks,
        missing_required=missing_required,
    )

    ledger_issue_count = _ledger_issue_count(ledger_quality_summary)
    if ledger_issue_count:
        score = max(0.0, score - min(0.20, 0.05 * ledger_issue_count))
        grade = _lower_grade(grade)

    score = round(score, 3)

    limitations: list[str] = []
    if not has_portfolio:
        limitations.append(
            "No usable portfolio snapshot or derivable transaction snapshot was provided"
        )
    if not has_nav:
        limitations.append(
            "Current value or current NAV is missing — positions cannot be reliably valued"
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
    if ledger_issue_count:
        limitations.append(
            "Derived portfolio uses an incomplete transaction ledger — unresolved "
            "or invalid events lower report completeness"
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


def _positions_from_portfolio(portfolio: Any) -> list[dict[str, Any]]:
    if not isinstance(portfolio, dict):
        return []
    positions = portfolio.get("positions")
    if not isinstance(positions, list):
        return []
    return [
        position for position in positions
        if isinstance(position, dict) and position.get("fund_code")
    ]


def _has_derived_portfolio_inputs(payload: dict[str, Any]) -> bool:
    return bool(
        isinstance(payload.get("transactions"), list)
        and len(payload["transactions"]) > 0
        and _has_current_nav(payload)
    )


def _has_derived_snapshot(payload: dict[str, Any]) -> bool:
    snapshot = payload.get("derived_portfolio_snapshot")
    if not isinstance(snapshot, dict):
        return False
    return bool(_positions_from_portfolio(snapshot))


def _has_current_nav(payload: dict[str, Any]) -> bool:
    current_nav = payload.get("current_nav")
    if not isinstance(current_nav, dict):
        return False
    for key, value in current_nav.items():
        if str(key).startswith("_"):
            continue
        if _is_positive_number(value):
            return True
    return False


def _has_position_valuation(
    portfolio: Any,
    positions: list[dict[str, Any]],
) -> bool:
    if not isinstance(portfolio, dict):
        return False
    if _is_positive_number(portfolio.get("total_value")):
        return True
    return any(_is_positive_number(position.get("current_value")) for position in positions)


def _has_non_empty_dict(value: Any) -> bool:
    return isinstance(value, dict) and len(value) > 0


def _has_non_empty_series_map(value: Any) -> bool:
    if not isinstance(value, dict) or not value:
        return False
    for series in value.values():
        if isinstance(series, list) and len(series) > 0:
            return True
        if isinstance(series, dict) and len(series) > 0:
            return True
    return False


def _is_positive_number(value: Any) -> bool:
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def _grade_from_checks(
    *,
    checks: dict[str, bool],
    optional_checks: dict[str, bool],
    missing_required: list[str],
) -> str:
    if not checks["portfolio_snapshot"] or not checks["current_nav"]:
        return "D"
    if not missing_required:
        optional_available = sum(1 for key in _OPTIONAL_SECTIONS if optional_checks[key])
        return "A" if optional_available >= _MOST_OPTIONAL_COUNT else "B"
    if len(missing_required) <= 3:
        return "C"
    return "D"


def _ledger_issue_count(ledger_quality_summary: dict[str, Any] | None) -> int:
    if not ledger_quality_summary:
        return 0
    invalid = _safe_int(ledger_quality_summary.get("invalid_events_count", 0))
    unresolved = _safe_int(ledger_quality_summary.get("unresolved_events_count", 0))
    return max(0, invalid) + max(0, unresolved)


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _lower_grade(grade: str) -> str:
    order = ["A", "B", "C", "D"]
    try:
        idx = order.index(str(grade))
    except ValueError:
        return "D"
    return order[min(idx + 1, len(order) - 1)]


# ── analysis coverage ────────────────────────────────────────────────────────


def summarize_analysis_coverage(
    payload: dict[str, Any],
    artifacts: dict[str, Any],
) -> dict[str, Any]:
    """Summarise which analysis dimensions are covered given host data and
    already-produced artifacts."""

    completeness = calculate_data_completeness(
        payload,
        artifacts.get("ledger_quality_summary")
        if isinstance(artifacts.get("ledger_quality_summary"), dict)
        else None,
    )

    missing_sections = set(completeness.get("missing_sections", []))
    has_portfolio = _section_label("portfolio_snapshot") not in missing_sections
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
    nav_available = _section_label("nav_history") not in missing_sections
    perf_available = bool(artifacts.get("portfolio_summary"))
    if perf_available and nav_available:
        performance_status = "available"
    elif perf_available:
        performance_status = "partial"
    else:
        performance_status = "missing"

    # Holdings
    holdings_available = _section_label("holdings") not in missing_sections
    if holdings_available:
        holdings_status = "available"
    elif artifacts.get("exposure_summary"):
        holdings_status = "partial"
    else:
        holdings_status = "missing"

    # Optional sections
    def _optional_status(key: str) -> str:
        return "missing" if _section_label(key) in completeness["optional_missing"] else "available"

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

    limitations: list[str] = []
    for item in completeness.get("limitations", []):
        if isinstance(item, str) and item not in limitations:
            limitations.append(item)

    # Ledger-quality limitations
    if ledger_quality:
        for lim in ledger_quality.get("limitations", []):
            if isinstance(lim, str) and lim not in limitations:
                limitations.append(lim)
        if (
            not ledger_quality.get("is_complete", True)
            and not ledger_quality.get("limitations")
        ):
            item = (
                "Transaction ledger is incomplete — derived positions may differ "
                "from broker statements"
            )
            if item not in limitations:
                limitations.append(item)

    # Missing data warnings
    if missing_data:
        for item in missing_data:
            if isinstance(item, str) and item not in limitations:
                limitations.append(item)

    # Grade-based general statement
    grade = completeness.get("grade", "D")
    if grade in ("C", "D"):
        item = (
            f"Report data completeness grade is {grade} — key sections are "
            f"missing; broker/fund statements remain the authoritative source"
        )
        if item not in limitations:
            limitations.append(item)
    elif grade == "B":
        item = (
            "Report data completeness is adequate but some optional sections are "
            "unavailable — deeper analysis may require additional data"
        )
        if item not in limitations:
            limitations.append(item)

    return limitations
