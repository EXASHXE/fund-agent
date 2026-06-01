"""Pure personal portfolio analysis helpers."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from src.schemas.fund import (
    PortfolioPosition,
    PortfolioSnapshot,
    RebalanceConstraint,
    UserRiskProfile,
)


def calculate_position_weights(portfolio_snapshot: Any) -> dict[str, float]:
    """Return current position weights keyed by fund_code."""
    snapshot = _snapshot_from_payload(portfolio_snapshot)
    if snapshot is None or snapshot.total_value <= 0:
        return {}

    return {
        position.fund_code: round(position.current_value / snapshot.total_value, 6)
        for position in snapshot.positions
    }


def calculate_theme_exposure(
    positions: Any,
    fund_profiles: dict[str, Any] | None = None,
    holdings: dict[str, Any] | None = None,
) -> dict[str, float]:
    """Aggregate tag, holding industry, region, and asset-type exposure."""
    position_list = _positions_from_payload(positions)
    total_value = sum(max(position.current_value, 0.0) for position in position_list)
    if total_value <= 0:
        return {}

    exposures: defaultdict[str, float] = defaultdict(float)
    holdings = holdings or {}
    fund_profiles = fund_profiles or {}

    for position in position_list:
        position_weight = position.current_value / total_value
        fund_holdings = holdings.get(position.fund_code) or []
        if fund_holdings:
            for holding in fund_holdings:
                for key in _holding_exposure_keys(holding):
                    exposures[key] += position_weight * _holding_weight(holding)
        else:
            for tag in position.tags:
                if tag:
                    exposures[f"tag:{tag}"] += position_weight

        profile = fund_profiles.get(position.fund_code) or {}
        fund_type = profile.get("fund_type")
        if fund_type:
            exposures[f"fund_type:{fund_type}"] += position_weight

    return {
        key: round(value, 6)
        for key, value in sorted(exposures.items())
        if value > 0
    }


def calculate_concentration_metrics(
    positions: Any,
    top_n: int = 3,
) -> dict[str, Any]:
    """Calculate single-fund, HHI, top-N, and duplicate tag concentration."""
    position_list = _positions_from_payload(positions)
    total_value = sum(max(position.current_value, 0.0) for position in position_list)
    if total_value <= 0:
        return {
            "position_count": len(position_list),
            "single_fund_max_weight": 0.0,
            "max_fund_code": None,
            "hhi": 0.0,
            "top_n": top_n,
            "top_n_concentration": 0.0,
            "duplicate_tags": [],
        }

    weights = {
        position.fund_code: position.current_value / total_value
        for position in position_list
    }
    max_fund_code = max(weights, key=weights.get) if weights else None
    sorted_weights = sorted(weights.values(), reverse=True)
    tag_counts = Counter(
        tag
        for position in position_list
        for tag in position.tags
        if tag
    )

    return {
        "position_count": len(position_list),
        "single_fund_max_weight": round(max(sorted_weights, default=0.0), 6),
        "max_fund_code": max_fund_code,
        "hhi": round(sum(weight * weight for weight in weights.values()), 6),
        "top_n": top_n,
        "top_n_concentration": round(sum(sorted_weights[:top_n]), 6),
        "duplicate_tags": sorted(
            tag
            for tag, count in tag_counts.items()
            if count >= 2
        ),
    }


def detect_portfolio_risk_flags(
    portfolio: Any,
    risk_profile: Any,
    exposures: dict[str, float] | None,
    metrics: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Detect deterministic portfolio risk flags."""
    snapshot = _snapshot_from_payload(portfolio)
    profile = _risk_profile_from_payload(risk_profile)
    exposures = exposures or {}
    metrics = metrics or {}
    flags: list[dict[str, Any]] = []

    concentration = metrics.get("concentration", metrics)
    max_weight = float(concentration.get("single_fund_max_weight", 0.0) or 0.0)
    if max_weight > profile.max_single_fund_weight:
        flags.append(
            _flag(
                "overweight_single_fund",
                "single fund weight exceeds risk profile limit",
                "high",
                value=max_weight,
                limit=profile.max_single_fund_weight,
                fund_code=concentration.get("max_fund_code"),
            )
        )

    for theme, value in sorted(exposures.items()):
        if value > profile.max_theme_weight:
            flags.append(
                _flag(
                    "overweight_theme",
                    "theme exposure exceeds risk profile limit",
                    "medium",
                    value=value,
                    limit=profile.max_theme_weight,
                    theme=theme,
                )
            )

    if snapshot is not None and snapshot.total_value > 0:
        cash_pct = snapshot.cash_available / snapshot.total_value
        if cash_pct < profile.liquidity_reserve_pct:
            flags.append(
                _flag(
                    "insufficient_cash_reserve",
                    "cash reserve is below liquidity reserve target",
                    "medium",
                    value=round(cash_pct, 6),
                    limit=profile.liquidity_reserve_pct,
                )
            )

        pending_pct = (
            sum(max(position.pending_amount, 0.0) for position in snapshot.positions)
            / snapshot.total_value
        )
        if pending_pct > profile.short_term_trade_budget_pct:
            flags.append(
                _flag(
                    "excessive_short_term_trading_budget",
                    "pending trade amount exceeds short-term trading budget",
                    "medium",
                    value=round(pending_pct, 6),
                    limit=profile.short_term_trade_budget_pct,
                )
            )

    fund_metrics = metrics.get("fund_metrics", {})
    drawdown_limit = _drawdown_limit(profile.risk_level)
    for fund_code, fund_metric in fund_metrics.items():
        drawdown = float(fund_metric.get("max_drawdown", 0.0) or 0.0)
        if drawdown > drawdown_limit:
            flags.append(
                _flag(
                    "high_drawdown_fund",
                    "fund max drawdown exceeds risk-level threshold",
                    "medium",
                    value=drawdown,
                    limit=drawdown_limit,
                    fund_code=fund_code,
                )
            )

    for tag in concentration.get("duplicate_tags", []):
        flags.append(
            _flag(
                "duplicate_exposure",
                "multiple funds share the same exposure tag",
                "low",
                tag=tag,
            )
        )

    return flags


def simulate_rebalance(
    portfolio: Any,
    target_weights: dict[str, float],
    constraints: Any = None,
    risk_profile: Any = None,
) -> dict[str, Any]:
    """Simulate a pure rebalance plan without creating Decision objects."""
    snapshot = _snapshot_from_payload(portfolio)
    if snapshot is None or snapshot.total_value <= 0:
        return {"suggested_trade_plan": [], "warnings": ["invalid portfolio"]}

    constraint = _constraint_from_payload(constraints)
    profile = _risk_profile_from_payload(risk_profile)
    current_weights = calculate_position_weights(snapshot)
    position_map = {position.fund_code: position for position in snapshot.positions}
    max_trade_amount = snapshot.total_value * profile.max_trade_pct
    trades: list[dict[str, Any]] = []
    warnings: list[str] = []

    for fund_code, target_weight in sorted(target_weights.items()):
        current_value = position_map.get(
            fund_code,
            PortfolioPosition(fund_code, fund_code, 0.0, 0.0),
        ).current_value
        target_value = snapshot.total_value * float(target_weight)
        delta = target_value - current_value
        action = "BUY" if delta > 0 else "SELL"
        amount = abs(delta)

        if amount < constraint.min_trade_amount:
            continue
        if action in constraint.forbidden_actions:
            warnings.append(f"{action} forbidden for {fund_code}")
            continue

        cap = max_trade_amount
        if action == "BUY":
            cap = min(cap, snapshot.cash_available)
            if constraint.max_buy_amount is not None:
                cap = min(cap, constraint.max_buy_amount)
        else:
            cap = min(cap, current_value)
            if constraint.max_sell_amount is not None:
                cap = min(cap, constraint.max_sell_amount)

        trade_amount = min(amount, cap)
        if trade_amount < constraint.min_trade_amount:
            warnings.append(f"trade below minimum after constraints for {fund_code}")
            continue

        trades.append(
            {
                "fund_code": fund_code,
                "action": action,
                "amount": round(trade_amount, 2),
                "requested_amount": round(amount, 2),
                "current_weight": current_weights.get(fund_code, 0.0),
                "target_weight": round(float(target_weight), 6),
                "capped": trade_amount < amount,
            }
        )

    return {
        "suggested_trade_plan": trades,
        "warnings": warnings + list(constraint.notes),
        "total_trade_amount": round(sum(item["amount"] for item in trades), 2),
    }


def _snapshot_from_payload(payload: Any) -> PortfolioSnapshot | None:
    if isinstance(payload, PortfolioSnapshot):
        return payload
    if not isinstance(payload, dict):
        return None

    positions = _positions_from_payload(payload.get("positions", []))
    total_value = _float(payload.get("total_value"))
    if total_value <= 0:
        total_value = sum(max(position.current_value, 0.0) for position in positions)

    return PortfolioSnapshot(
        as_of_date=str(payload.get("as_of_date", "")),
        total_value=total_value,
        cash_available=_float(payload.get("cash_available")),
        positions=positions,
    )


def _positions_from_payload(payload: Any) -> list[PortfolioPosition]:
    if isinstance(payload, PortfolioSnapshot):
        return payload.positions
    if isinstance(payload, dict) and "positions" in payload:
        payload = payload.get("positions", [])
    if not isinstance(payload, list):
        return []

    positions: list[PortfolioPosition] = []
    for item in payload:
        if isinstance(item, PortfolioPosition):
            positions.append(item)
        elif isinstance(item, dict):
            fund_code = item.get("fund_code")
            fund_name = item.get("fund_name", item.get("name", fund_code))
            if not fund_code or fund_name is None:
                continue
            positions.append(
                PortfolioPosition(
                    fund_code=str(fund_code),
                    fund_name=str(fund_name),
                    current_value=_float(item.get("current_value")),
                    total_cost=_float(item.get("total_cost")),
                    shares=_optional_float(item.get("shares")),
                    pending_amount=_float(item.get("pending_amount")),
                    target_weight=_optional_float(item.get("target_weight")),
                    tags=[str(tag) for tag in item.get("tags", [])],
                )
            )
    return positions


def _risk_profile_from_payload(payload: Any) -> UserRiskProfile:
    if isinstance(payload, UserRiskProfile):
        return payload
    if not isinstance(payload, dict):
        return UserRiskProfile()
    return UserRiskProfile(
        risk_level=payload.get("risk_level", "moderate"),
        max_single_fund_weight=_float(
            payload.get("max_single_fund_weight"),
            default=0.2,
        ),
        max_theme_weight=_float(payload.get("max_theme_weight"), default=0.35),
        max_trade_pct=_float(payload.get("max_trade_pct"), default=0.1),
        liquidity_reserve_pct=_float(
            payload.get("liquidity_reserve_pct"),
            default=0.1,
        ),
        short_term_trade_budget_pct=_float(
            payload.get("short_term_trade_budget_pct"),
            default=0.1,
        ),
    )


def _constraint_from_payload(payload: Any) -> RebalanceConstraint:
    if isinstance(payload, RebalanceConstraint):
        return payload
    if not isinstance(payload, dict):
        return RebalanceConstraint()
    return RebalanceConstraint(
        max_buy_amount=_optional_float(payload.get("max_buy_amount")),
        max_sell_amount=_optional_float(payload.get("max_sell_amount")),
        min_trade_amount=_float(payload.get("min_trade_amount")),
        forbidden_actions=[str(item) for item in payload.get("forbidden_actions", [])],
        notes=[str(item) for item in payload.get("notes", [])],
    )


def _holding_exposure_keys(holding: Any) -> list[str]:
    if not isinstance(holding, dict):
        return []
    keys: list[str] = []
    for field, prefix in (
        ("industry", "industry"),
        ("region", "region"),
        ("asset_type", "asset_type"),
    ):
        value = holding.get(field)
        if value:
            keys.append(f"{prefix}:{value}")
    return keys


def _holding_weight(holding: Any) -> float:
    if not isinstance(holding, dict):
        return 0.0
    weight = _float(holding.get("weight"))
    if weight > 1:
        weight = weight / 100.0
    return max(weight, 0.0)


def _drawdown_limit(risk_level: str) -> float:
    return {
        "conservative": 0.15,
        "moderate": 0.25,
        "aggressive": 0.35,
    }.get(risk_level, 0.25)


def _flag(
    flag_type: str,
    message: str,
    severity: str,
    **details: Any,
) -> dict[str, Any]:
    return {
        "type": flag_type,
        "severity": severity,
        "message": message,
        "details": details,
    }


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
