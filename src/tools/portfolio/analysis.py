"""Pure personal portfolio analysis helpers."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
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
    industry_exposure: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Detect deterministic portfolio risk flags."""
    snapshot = _snapshot_from_payload(portfolio)
    profile = _risk_profile_from_payload(risk_profile)
    exposures = exposures or {}
    metrics = metrics or {}
    industry_exposure = industry_exposure or {}
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

    for industry_key, value in sorted(industry_exposure.items()):
        if value > profile.max_industry_weight:
            industry_name = industry_key.replace("industry:", "")
            flags.append(
                _flag(
                    "overweight_industry",
                    "industry exposure exceeds risk profile limit",
                    "medium",
                    current_value=value,
                    limit=profile.max_industry_weight,
                    affected_entities=[industry_name],
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
    risk_flags_refs: list[str] | None = None,
    evidence_refs: list[str] | None = None,
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
    evidence_refs = evidence_refs or []
    risk_flags_refs = risk_flags_refs or []

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

        idx = len(trades)
        pos = position_map.get(fund_code, PortfolioPosition(fund_code, fund_code, 0.0, 0.0))
        trades.append(
            {
                "trade_id": f"{fund_code}_{action}_{idx}",
                "fund_code": fund_code,
                "fund_name": pos.fund_name,
                "action": action,
                "amount": round(trade_amount, 2),
                "requested_amount": round(amount, 2),
                "current_weight": current_weights.get(fund_code, 0.0),
                "target_weight": round(float(target_weight), 6),
                "current_value": round(current_value, 2),
                "current_cost": round(pos.total_cost, 2),
                "unrealized_pnl": round(current_value - pos.total_cost, 2),
                "capped": trade_amount < amount,
                "cap_reasons": _build_cap_reasons(trade_amount, amount, action, snapshot, constraint, profile),
                "rationale": "rebalance to target weight",
                "tags": list(pos.tags),
                "evidence_refs": list(evidence_refs),
                "risk_flags_refs": list(risk_flags_refs),
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
        max_industry_weight=_float(payload.get("max_industry_weight"), default=0.30),
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


def _build_cap_reasons(
    trade_amount: float,
    requested_amount: float,
    action: str,
    snapshot: PortfolioSnapshot,
    constraint: RebalanceConstraint,
    profile: UserRiskProfile,
) -> list[str]:
    reasons: list[str] = []
    if trade_amount >= requested_amount:
        return reasons
    max_trade = snapshot.total_value * profile.max_trade_pct
    if trade_amount == max_trade:
        reasons.append(f"capped by max_trade_pct ({profile.max_trade_pct})")
    if action in ("BUY", "INCREASE"):
        cash_available = snapshot.cash_available
        if trade_amount == cash_available:
            reasons.append(f"capped by cash_available ({cash_available})")
        effective_cash = cash_available - profile.liquidity_reserve_pct * snapshot.total_value
        if trade_amount == max(effective_cash, 0):
            reasons.append(f"capped by liquidity_reserve_pct ({profile.liquidity_reserve_pct})")
        max_buy = constraint.max_buy_amount
        if max_buy is not None and trade_amount == max_buy:
            reasons.append(f"capped by max_buy_amount ({max_buy})")
    else:
        max_sell = constraint.max_sell_amount
        if max_sell is not None and trade_amount == max_sell:
            reasons.append(f"capped by max_sell_amount ({max_sell})")
    if not reasons:
        reasons.append("capped by constraints")
    return reasons


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


def _date(value: Any) -> str:
    if isinstance(value, (date,)):
        return value.isoformat()
    return str(value or "")


# ——————————————————————————————————————————————————————————————————————————————
# Extended portfolio analysis (v0.4.1)
# ——————————————————————————————————————————————————————————————————————————————

def calculate_industry_exposure(
    positions: Any,
    holdings: dict[str, Any] | None = None,
) -> dict[str, float]:
    """Aggregate industry exposure from position holdings."""
    position_list = _positions_from_payload(positions)
    total_value = sum(max(p.current_value, 0.0) for p in position_list)
    if total_value <= 0:
        return {}
    holdings = holdings or {}
    exposures: defaultdict[str, float] = defaultdict(float)
    for pos in position_list:
        w = pos.current_value / total_value
        for h in holdings.get(pos.fund_code, []):
            if isinstance(h, dict) and h.get("industry"):
                exposures[f"industry:{h['industry']}"] += w * _holding_weight(h)
    return {k: round(v, 6) for k, v in sorted(exposures.items()) if v > 0}


def calculate_cash_ratio(portfolio: Any) -> float:
    """Return cash_available / total_value."""
    snapshot = _snapshot_from_payload(portfolio)
    if snapshot is None or snapshot.total_value <= 0:
        return 0.0
    return round(snapshot.cash_available / snapshot.total_value, 6)


def calculate_position_pnl(positions: Any) -> dict[str, dict[str, float]]:
    """Return per-position unrealized PnL when total_cost is available."""
    position_list = _positions_from_payload(positions)
    result: dict[str, dict[str, float]] = {}
    for pos in position_list:
        pnl = pos.current_value - pos.total_cost if pos.total_cost else None
        pnl_pct = (pnl / pos.total_cost) if pnl is not None and pos.total_cost > 0 else None
        result[pos.fund_code] = {
            "current_value": round(pos.current_value, 2),
            "total_cost": round(pos.total_cost, 2) if pos.total_cost else 0.0,
            "unrealized_pnl": round(pnl, 2) if pnl is not None else None,
            "unrealized_pnl_pct": round(pnl_pct, 6) if pnl_pct is not None else None,
        }
    return result


def calculate_portfolio_pnl(positions: Any) -> dict[str, Any]:
    """Aggregate portfolio-level PnL summary."""
    per_position = calculate_position_pnl(positions)
    total_cost = sum(p["total_cost"] for p in per_position.values())
    total_value = sum(p["current_value"] for p in per_position.values())
    pnl = total_value - total_cost if total_cost > 0 else 0.0
    pnl_pct = round(pnl / total_cost, 6) if total_cost > 0 else 0.0
    return {
        "total_cost": round(total_cost, 2),
        "total_value": round(total_value, 2),
        "unrealized_pnl": round(pnl, 2),
        "unrealized_pnl_pct": pnl_pct,
        "positions": per_position,
    }


def calculate_trade_budget(
    portfolio: Any,
    risk_profile: Any,
    constraints: Any = None,
) -> dict[str, Any]:
    """Calculate available trade budget and short-term trade budget."""
    snapshot = _snapshot_from_payload(portfolio)
    profile = _risk_profile_from_payload(risk_profile)
    constraint = _constraint_from_payload(constraints)
    if snapshot is None or snapshot.total_value <= 0:
        return {"total_value": 0, "max_trade_amount": 0, "short_term_budget": 0, "cash_available": 0}
    max_trade = snapshot.total_value * profile.max_trade_pct
    short_term_budget = snapshot.total_value * profile.short_term_trade_budget_pct
    return {
        "total_value": round(snapshot.total_value, 2),
        "cash_available": round(snapshot.cash_available, 2),
        "max_trade_amount": round(max_trade, 2),
        "short_term_budget": round(short_term_budget, 2),
        "liquidity_reserve": round(snapshot.total_value * profile.liquidity_reserve_pct, 2),
        "max_buy_amount": constraint.max_buy_amount,
        "max_sell_amount": constraint.max_sell_amount,
        "min_trade_amount": constraint.min_trade_amount,
    }


def calculate_short_term_budget_usage(
    positions: Any,
    transactions: list[dict[str, Any]] | None,
    risk_profile: Any,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    """Estimate short-term trading budget usage from recent transactions."""
    profile = _risk_profile_from_payload(risk_profile)
    position_list = _positions_from_payload(positions)
    total_value = sum(max(p.current_value, 0.0) for p in position_list)
    budget = total_value * profile.short_term_trade_budget_pct
    transactions = transactions or []

    if as_of_date is None:
        return {
            "short_term_budget": round(budget, 2),
            "used": 0.0,
            "remaining": round(budget, 2),
            "usage_pct": 0.0,
            "exceeded": False,
            "recent_buys": 0.0,
            "recent_sells": 0.0,
            "warning": "as_of_date not provided; date-sensitive checks skipped",
        }

    recent_buys = sum(
        abs(_float(t.get("amount", 0))) for t in transactions
        if str(t.get("action", t.get("type", ""))).upper() in ("BUY",) and _is_recent(t, 30, as_of_date)
    )
    recent_sells = sum(
        abs(_float(t.get("amount", 0))) for t in transactions
        if str(t.get("action", t.get("type", ""))).upper() in ("SELL",) and _is_recent(t, 30, as_of_date)
    )
    used = recent_buys + recent_sells
    return {
        "short_term_budget": round(budget, 2),
        "used": round(used, 2),
        "remaining": round(max(budget - used, 0), 2),
        "usage_pct": round(used / budget, 6) if budget > 0 else 0.0,
        "exceeded": used > budget,
        "recent_buys": round(recent_buys, 2),
        "recent_sells": round(recent_sells, 2),
    }


def review_dca_plan(
    dca_plans: dict[str, Any] | None,
    portfolio: Any,
    transactions: dict[str, Any] | None,
    risk_profile: Any,
) -> dict[str, Any]:
    """Review DCA plans against portfolio concentration and budget."""
    dca_plans = dca_plans or {}
    snapshot = _snapshot_from_payload(portfolio)
    profile = _risk_profile_from_payload(risk_profile)
    results: list[dict[str, Any]] = []
    warnings: list[str] = []
    if snapshot is None or snapshot.total_value <= 0:
        return {"plans": results, "warnings": ["invalid portfolio for DCA review"], "suggestions": []}

    for plan_id, plan in dca_plans.items():
        if not isinstance(plan, dict):
            continue
        fund_code = plan.get("fund_code", "")
        monthly = _float(plan.get("monthly_amount", 0))
        annual = monthly * 12
        weight = 0.0
        for pos in snapshot.positions:
            if pos.fund_code == fund_code:
                weight = pos.current_value / snapshot.total_value
                break
        exceeded = weight + annual / snapshot.total_value > profile.max_single_fund_weight if annual > 0 else False
        item = {
            "plan_id": plan_id,
            "fund_code": fund_code,
            "monthly_amount": round(monthly, 2),
            "annual_amount": round(annual, 2),
            "current_weight": round(weight, 6),
            "exceeds_limit": exceeded,
            "suggestion": "CONTINUE",
        }
        if exceeded:
            item["suggestion"] = "PAUSE" if weight > profile.max_single_fund_weight else "REDUCE"
            warnings.append(f"DCA plan {plan_id} for {fund_code} exceeds concentration limit")
        results.append(item)

    suggestions = [r for r in results if r["suggestion"] in ("PAUSE", "REDUCE")]
    return {"plans": results, "warnings": warnings, "suggestions": suggestions}


def apply_trade_constraints(
    trade_plan: list[dict[str, Any]],
    portfolio: Any,
    constraints: Any,
    risk_profile: Any,
) -> list[dict[str, Any]]:
    """Filter and cap trade legs against host-provided constraints."""
    snapshot = _snapshot_from_payload(portfolio)
    constraint = _constraint_from_payload(constraints)
    profile = _risk_profile_from_payload(risk_profile)
    if snapshot is None:
        return []

    current_weights = calculate_position_weights(snapshot)
    position_map = {p.fund_code: p for p in snapshot.positions}
    max_trade = snapshot.total_value * profile.max_trade_pct
    short_term_budget = snapshot.total_value * profile.short_term_trade_budget_pct
    used_budget = 0.0
    result: list[dict[str, Any]] = []

    for trade in trade_plan:
        if not isinstance(trade, dict):
            continue
        fund_code = trade.get("fund_code", "")
        action = str(trade.get("action", "")).upper()
        amount = _float(trade.get("amount", trade.get("requested_amount", 0)))
        target_weight = trade.get("target_weight")

        cap_reasons: list[str] = []
        capped = False

        if action in constraint.forbidden_actions:
            cap_reasons.append(f"action {action} forbidden")
            capped = True
            amount = 0.0

        if amount < constraint.min_trade_amount:
            continue

        cap = max_trade
        if action in ("BUY", "INCREASE"):
            effective_cash = snapshot.cash_available - profile.liquidity_reserve_pct * snapshot.total_value
            cap = min(cap, max(effective_cash, 0))
            if constraint.max_buy_amount is not None:
                cap = min(cap, constraint.max_buy_amount)
            budget_remaining = short_term_budget - used_budget
            if budget_remaining < amount:
                cap = min(cap, max(budget_remaining, 0))
                cap_reasons.append("short-term budget exceeded")
                capped = True
        else:
            current_val = position_map.get(fund_code, PortfolioPosition(fund_code, "", 0, 0)).current_value
            cap = min(cap, current_val)
            if constraint.max_sell_amount is not None:
                cap = min(cap, constraint.max_sell_amount)

        trade_amount = min(amount, cap)
        if trade_amount < constraint.min_trade_amount:
            continue

        used_budget += trade_amount
        was_capped = trade_amount < amount or capped
        result.append({
            **trade,
            "amount": round(trade_amount, 2),
            "requested_amount": round(amount, 2),
            "capped": was_capped,
            "cap_reasons": cap_reasons,
            "current_weight": current_weights.get(fund_code, 0.0),
            "rationale": trade.get("rationale") or (
                "constraint-capped rebalance" if was_capped else "rebalance to target weight"
            ),
            "evidence_refs": trade.get("evidence_refs", []),
            "risk_flags_refs": trade.get("risk_flags_refs", []),
        })

    return result


def summarize_exposure(
    theme_exposure: dict[str, float],
    industry_exposure: dict[str, float] | None,
    fund_type_exposure: dict[str, float] | None,
) -> dict[str, Any]:
    """Consolidate exposure maps into a structured summary."""
    return {
        "theme_exposure": theme_exposure or {},
        "industry_exposure": industry_exposure or {},
        "fund_type_exposure": fund_type_exposure or {},
    }


def rank_trade_plan(
    trades: list[dict[str, Any]],
    risk_flags: list[dict[str, Any]],
    fund_metrics: dict[str, Any] | None = None,
    cost_basis: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Deterministic trade ranking: risk-reduction first, respect constraints."""
    fund_metrics = fund_metrics or {}
    cost_basis = cost_basis or {}
    risk_fund_codes = {f.get("details", {}).get("fund_code", "") for f in risk_flags if "fund_code" in f.get("details", {})}
    overweight_themes = {f.get("details", {}).get("theme", "") for f in risk_flags if f.get("type") == "overweight_theme"}

    def rank(trade: dict) -> tuple[int, int, float]:
        code = trade.get("fund_code", "")
        action = str(trade.get("action", "")).upper()
        priority = 0 if (action in ("SELL", "REDUCE") and code in risk_fund_codes) else 1
        if priority != 0:
            priority = 1 if action in ("SELL", "REDUCE") else 2
        if priority == 2 and code in risk_fund_codes:
            priority = 3
        amount = float(trade.get("amount", 0))
        return (priority, 0 if action in ("SELL", "REDUCE") else 1, -amount)

    ranked = sorted(trades, key=rank)
    annotated = []
    for i, t in enumerate(ranked):
        trade = dict(t)
        trade["rank"] = i + 1
        priority, _, _ = rank(trade)
        trade["priority"] = "risk_reduction" if priority == 0 else "constraint_reduction" if priority == 1 else "rebalance" if priority == 2 else "avoid"
        annotated.append(trade)
    return annotated


def _is_recent(transaction: dict[str, Any], days: int, as_of_date: str = "") -> bool:
    """Check if a transaction is within N days of as_of_date (best-effort).

    When as_of_date is empty, the check is skipped (returns True).
    """
    tx_date = transaction.get("date", transaction.get("trade_date", ""))
    if not tx_date:
        return False
    if not as_of_date:
        return False
    try:
        from datetime import date, timedelta
        d = date.fromisoformat(str(tx_date)[:10])
        ref = date.fromisoformat(str(as_of_date)[:10])
        return (ref - d).days <= days
    except (ValueError, TypeError):
        return False
