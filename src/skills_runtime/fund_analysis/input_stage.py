"""Input normalization helpers for FundAnalysisSkill."""

from __future__ import annotations

from typing import Any

from src.schemas.skill import SkillInput

from .context import PortfolioInputBundle


def dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def is_number(value: Any) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def collect_fund_codes(positions: list[dict[str, Any]]) -> list[str]:
    return [
        str(position.get("fund_code"))
        for position in positions
        if isinstance(position, dict) and position.get("fund_code")
    ]


def latest_nav_by_fund(nav_history: dict[str, Any]) -> dict[str, float]:
    nav_data: dict[str, float] = {}
    for fund_code, nav_points in nav_history.items():
        if isinstance(nav_points, list) and nav_points:
            latest = max(nav_points, key=lambda x: x.get("date", ""))
            if isinstance(latest, dict) and latest.get("nav") is not None:
                nav_data[fund_code] = float(latest["nav"])
    return nav_data


def build_portfolio_input_bundle(
    *,
    payload: dict[str, Any],
    portfolio: dict[str, Any],
    positions: list[dict[str, Any]],
    fund_codes: list[str],
) -> PortfolioInputBundle:
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

    return PortfolioInputBundle(
        payload=payload,
        portfolio=portfolio,
        positions=positions,
        fund_codes=fund_codes,
        fund_profiles=fund_profiles,
        nav_history=nav_history,
        holdings=holdings,
        risk_profile=risk_profile,
        constraints=constraints,
        transactions=transactions,
        dca_plans=dca_plans,
        market_scenario=market_scenario,
        benchmarks=benchmarks,
        benchmark_history=benchmark_history,
        peer_group=peer_group,
        factor_exposures=factor_exposures,
        manager_profiles=manager_profiles,
        fee_schedules=fee_schedules,
        redemption_rules=redemption_rules,
        research_planning=research_planning,
        nav_data=nav_data,
        as_of_date=as_of_date,
    )


def target_weights_from_payload(
    payload: dict[str, Any],
    positions: list[dict[str, Any]],
) -> dict[str, float]:
    raw = payload.get("target_weights")
    if isinstance(raw, dict):
        return {
            str(fund_code): float(weight)
            for fund_code, weight in raw.items()
            if is_number(weight)
        }

    targets: dict[str, float] = {}
    for position in positions:
        if not isinstance(position, dict):
            continue
        fund_code = position.get("fund_code")
        target_weight = position.get("target_weight")
        if fund_code and is_number(target_weight):
            targets[str(fund_code)] = float(target_weight)
    return targets


def missing_data_warnings(
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


def entities_from_input(skill_input: SkillInput) -> list[str]:
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


def has_related_entities(payload: dict[str, Any], skill_input: SkillInput) -> bool:
    if isinstance(payload.get("related_entities"), list) and payload["related_entities"]:
        return True
    return bool(skill_input.kg_context.get("fund_codes"))
