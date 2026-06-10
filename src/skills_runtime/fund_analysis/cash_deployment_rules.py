"""Cash deployment diagnostics for FundAnalysisSkill.

Deterministic, local-only assessment of cash-like allocation, deployment
readiness, and missing evidence. Does NOT fetch data, call providers,
use LLMs, or make formal decisions. Only provides readiness and
missing data; never recommends specific buys or outputs formal ADD/BUY.
"""

from __future__ import annotations

from typing import Any

from .context import CoreMetricsBundle, PortfolioInputBundle


CASH_LOW_THRESHOLD = 0.05
CASH_HIGH_THRESHOLD = 0.30

CASH_LIKE_KEYWORDS = {
    "cash", "money_market", "short_bond", "money market", "short bond",
    "货币", "短债", "现金", "货币基金", "短债基金",
}

CASH_LIKE_FUND_TYPES = {"cash", "money_market", "short_bond"}


def compute_cash_deployment_diagnostics(
    bundle: PortfolioInputBundle,
    metrics: CoreMetricsBundle,
) -> dict[str, Any]:
    total_value = float(bundle.portfolio.get("total_value", 0) or 0)
    cash_available = float(bundle.portfolio.get("cash_available", 0) or 0)
    fund_profiles = bundle.fund_profiles or {}
    risk_profile = bundle.risk_profile or {}
    constraints = bundle.constraints or {}
    notes: list[str] = []
    recommended_next_data: list[str] = []

    cash_like_value = cash_available
    bucket_items: list[dict[str, Any]] = []

    cash_bucket_value = cash_available
    money_market_value = 0.0
    short_bond_value = 0.0
    bond_value = 0.0
    equity_value = 0.0

    for pos in bundle.positions:
        if not isinstance(pos, dict) or not pos.get("fund_code"):
            continue
        fund_code = str(pos["fund_code"])
        current_value = float(pos.get("current_value", 0) or 0)
        profile = fund_profiles.get(fund_code, {}) if isinstance(fund_profiles, dict) else {}
        fund_type = str(profile.get("fund_type", "")).lower() if isinstance(profile, dict) else ""
        theme = str(profile.get("theme", "")).lower() if isinstance(profile, dict) else ""
        tags = pos.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]

        bucket = _classify_bucket(fund_type, theme, tags)
        liquidity_hint = _classify_liquidity(bucket)
        weight = round(current_value / total_value, 6) if total_value > 0 else 0.0

        bucket_items.append({
            "bucket": bucket,
            "value": current_value,
            "weight": weight,
            "liquidity_hint": liquidity_hint,
        })

        if bucket == "cash":
            cash_bucket_value += current_value
        elif bucket == "money_market":
            money_market_value += current_value
        elif bucket == "short_bond":
            short_bond_value += current_value
        elif bucket == "bond":
            bond_value += current_value
        elif bucket == "equity":
            equity_value += current_value

    cash_like_value = cash_available + money_market_value + short_bond_value
    cash_like_weight = round(cash_like_value / total_value, 6) if total_value > 0 else 0.0

    cash_buffer_status = _classify_cash_buffer(cash_like_weight)
    risk_budget_status = _classify_risk_budget(risk_profile, constraints)
    deployment_readiness = _classify_deployment_readiness(
        cash_buffer_status, risk_budget_status, risk_profile, constraints, notes,
    )

    if deployment_readiness in ("not_ready", "unknown"):
        if not risk_profile:
            recommended_next_data.append("user risk preference")
        if not constraints:
            recommended_next_data.append("liquidity needs and planned holding period")
        recommended_next_data.append("target asset evidence")

    estimated_deployable_cash = 0.0
    if cash_like_weight > CASH_HIGH_THRESHOLD and total_value > 0:
        estimated_deployable_cash = round(cash_like_value - total_value * CASH_HIGH_THRESHOLD, 2)

    return {
        "summary": {
            "cash_like_value": round(cash_like_value, 2),
            "cash_like_weight": cash_like_weight,
            "estimated_deployable_cash": estimated_deployable_cash,
            "cash_buffer_status": cash_buffer_status,
            "deployment_readiness": deployment_readiness,
            "risk_budget_status": risk_budget_status,
            "notes": notes,
        },
        "items": bucket_items,
        "recommended_next_data": recommended_next_data,
    }


def _classify_bucket(fund_type: str, theme: str, tags: list[str]) -> str:
    if fund_type in CASH_LIKE_FUND_TYPES:
        if fund_type == "cash" or fund_type == "money_market":
            return "money_market"
        return "short_bond"
    if fund_type == "bond":
        return "bond"
    if fund_type in ("equity", "index", "active", "QDII"):
        return "equity"

    tag_set = {str(t).lower() for t in tags}
    tag_set.add(theme)
    if tag_set & CASH_LIKE_KEYWORDS:
        if "cash" in tag_set or "货币" in tag_set or "money_market" in tag_set:
            return "money_market"
        return "short_bond"

    return "unknown"


def _classify_liquidity(bucket: str) -> str:
    if bucket in ("cash", "money_market", "short_bond"):
        return "high"
    if bucket == "bond":
        return "medium"
    if bucket == "equity":
        return "medium"
    return "unknown"


def _classify_cash_buffer(cash_like_weight: float) -> str:
    if cash_like_weight < CASH_LOW_THRESHOLD:
        return "low"
    if cash_like_weight > CASH_HIGH_THRESHOLD:
        return "high"
    return "adequate"


def _classify_risk_budget(
    risk_profile: dict[str, Any],
    constraints: dict[str, Any],
) -> str:
    if not risk_profile and not constraints:
        return "unknown"
    max_theme = risk_profile.get("max_theme_weight") or constraints.get("max_theme_weight")
    if max_theme is not None:
        try:
            _ = float(max_theme)
            return "available"
        except (TypeError, ValueError):
            pass
    if risk_profile.get("risk_level"):
        return "available"
    return "constrained"


def _classify_deployment_readiness(
    cash_buffer_status: str,
    risk_budget_status: str,
    risk_profile: dict[str, Any],
    constraints: dict[str, Any],
    notes: list[str],
) -> str:
    if cash_buffer_status == "low":
        notes.append("cash buffer is low; deployment not appropriate")
        return "not_ready"
    if not risk_profile and not constraints:
        notes.append("missing risk preference and constraints; cannot assess deployment readiness")
        return "unknown"
    if risk_budget_status == "unknown":
        notes.append("risk budget unknown; deployment readiness uncertain")
        return "unknown"
    if cash_buffer_status in ("high", "adequate") and risk_budget_status in ("available", "constrained"):
        if risk_budget_status == "constrained":
            notes.append("risk budget constrained; partial deployment may be possible")
            return "partial"
        return "ready"
    return "not_ready"
