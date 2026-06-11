"""Risk constraint conflict diagnostics for decision_support.

Produces deterministic conflict details when constraints block or cap
active actions. Does not change Decision schema. Adds artifact and
audit trail entries only.
"""
from __future__ import annotations

from typing import Any

from .action_policy import ACTIVE_ACTIONS
from .context import _dict, _float_value, _optional_float


def build_risk_constraint_conflicts(
    *,
    action: str,
    payload: dict[str, Any],
    requested_amount: float = 0.0,
    capped_amount: float = 0.0,
    cap_reasons: list[str] | None = None,
    trade_plan: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []

    if action in ACTIVE_ACTIONS:
        items.extend(_check_single_decision_conflicts(
            action=action,
            payload=payload,
            requested_amount=requested_amount,
            capped_amount=capped_amount,
            cap_reasons=cap_reasons or [],
        ))

    if trade_plan:
        items.extend(_check_trade_plan_conflicts(
            trade_plan=trade_plan,
            payload=payload,
        ))

    has_blocking = any(
        item.get("resolution") in ("reject_trade", "downgrade_to_hold")
        for item in items
    )
    has_capping = any(
        item.get("resolution") == "cap_amount"
        for item in items
    )
    blocked_count = sum(
        1 for item in items
        if item.get("resolution") in ("reject_trade", "downgrade_to_hold")
    )
    capped_count = sum(
        1 for item in items
        if item.get("resolution") == "cap_amount"
    )

    return {
        "items": items,
        "summary": {
            "has_blocking_conflict": has_blocking,
            "has_capping_conflict": has_capping,
            "blocked_trade_count": blocked_count,
            "capped_trade_count": capped_count,
        },
    }


def _check_single_decision_conflicts(
    *,
    action: str,
    payload: dict[str, Any],
    requested_amount: float,
    capped_amount: float,
    cap_reasons: list[str],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    portfolio_context = _dict(payload.get("portfolio_context"))
    risk_profile = _dict(payload.get("risk_profile"))
    constraints = _dict(payload.get("constraints"))
    total_value = _optional_float(portfolio_context.get("total_value")) or 0.0

    max_trade_pct = _optional_float(
        risk_profile.get("max_trade_pct", _dict(payload.get("risk_budget")).get("max_trade_pct"))
    )
    if max_trade_pct is not None and total_value > 0 and requested_amount > 0:
        allowed = total_value * max_trade_pct
        if requested_amount > allowed:
            items.append({
                "scope": "decision",
                "constraint": "max_trade_pct",
                "requested": requested_amount,
                "allowed": round(allowed, 2),
                "actual": capped_amount,
                "resolution": "cap_amount" if capped_amount > 0 else "downgrade_to_hold",
                "reason": f"Requested {requested_amount} exceeds max_trade_pct ({max_trade_pct}) of total_value ({total_value})",
            })

    if action in ("BUY", "INCREASE"):
        max_buy_amount = _optional_float(constraints.get("max_buy_amount"))
        if max_buy_amount is not None and requested_amount > max_buy_amount:
            items.append({
                "scope": "decision",
                "constraint": "max_buy_amount",
                "requested": requested_amount,
                "allowed": max_buy_amount,
                "actual": capped_amount,
                "resolution": "cap_amount" if capped_amount > 0 else "downgrade_to_hold",
                "reason": f"Requested {requested_amount} exceeds max_buy_amount ({max_buy_amount})",
            })

        cash_available = _optional_float(portfolio_context.get("cash_available")) or 0.0
        liquidity_reserve_pct = _optional_float(risk_profile.get("liquidity_reserve_pct")) or 0.0
        effective_cash = max(cash_available - liquidity_reserve_pct * total_value, 0.0)
        if total_value > 0 and requested_amount > effective_cash:
            items.append({
                "scope": "decision",
                "constraint": "cash_available",
                "requested": requested_amount,
                "allowed": round(effective_cash, 2),
                "actual": capped_amount,
                "resolution": "cap_amount" if effective_cash > 0 else "downgrade_to_hold",
                "reason": f"Requested {requested_amount} exceeds effective cash ({effective_cash}) after liquidity reserve",
            })

    if action in ("SELL", "REDUCE"):
        max_sell_amount = _optional_float(constraints.get("max_sell_amount"))
        if max_sell_amount is not None and requested_amount > max_sell_amount:
            items.append({
                "scope": "decision",
                "constraint": "max_sell_amount",
                "requested": requested_amount,
                "allowed": max_sell_amount,
                "actual": capped_amount,
                "resolution": "cap_amount" if capped_amount > 0 else "downgrade_to_hold",
                "reason": f"Requested {requested_amount} exceeds max_sell_amount ({max_sell_amount})",
            })

    min_trade_amount = _optional_float(constraints.get("min_trade_amount"))
    if min_trade_amount is not None and capped_amount > 0 and capped_amount < min_trade_amount:
        items.append({
            "scope": "decision",
            "constraint": "min_trade_amount",
            "requested": requested_amount,
            "allowed": 0.0,
            "actual": 0.0,
            "resolution": "reject_trade",
            "reason": f"Capped amount {capped_amount} is below min_trade_amount ({min_trade_amount})",
        })

    forbidden_actions = [
        str(item).upper() for item in constraints.get("forbidden_actions", [])
    ]
    if action in forbidden_actions:
        items.append({
            "scope": "decision",
            "constraint": "forbidden_actions",
            "requested": requested_amount,
            "allowed": 0.0,
            "actual": 0.0,
            "resolution": "reject_trade",
            "reason": f"Action {action} is in forbidden_actions list",
        })

    return items


def _check_trade_plan_conflicts(
    *,
    trade_plan: list[dict[str, Any]],
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    portfolio_context = _dict(payload.get("portfolio_context"))
    risk_profile = _dict(payload.get("risk_profile"))
    constraints = _dict(payload.get("constraints"))
    total_value = _optional_float(portfolio_context.get("total_value")) or 0.0

    for trade in trade_plan:
        if not isinstance(trade, dict):
            continue
        trade_id = str(trade.get("trade_id", trade.get("fund_code", "")))
        action = str(trade.get("action", "")).upper()
        if action not in ACTIVE_ACTIONS:
            continue

        requested = _float_value(trade.get("requested_amount"), _float_value(trade.get("amount"), 0.0))
        capped = _float_value(trade.get("amount"), 0.0)
        cap_reasons = list(trade.get("cap_reasons", []))

        if cap_reasons:
            for reason in cap_reasons:
                constraint_name = _extract_constraint_name(reason)
                items.append({
                    "scope": "trade",
                    "trade_id": trade_id,
                    "constraint": constraint_name,
                    "requested": requested,
                    "allowed": capped,
                    "actual": capped,
                    "resolution": "cap_amount" if capped > 0 and capped < requested else "downgrade_to_hold",
                    "reason": reason,
                })

        forbidden_actions = [
            str(item).upper() for item in constraints.get("forbidden_actions", [])
        ]
        if action in forbidden_actions:
            items.append({
                "scope": "trade",
                "trade_id": trade_id,
                "constraint": "forbidden_actions",
                "requested": requested,
                "allowed": 0.0,
                "actual": 0.0,
                "resolution": "reject_trade",
                "reason": f"Action {action} is forbidden for trade {trade_id}",
            })

    return items


def _extract_constraint_name(reason: str) -> str:
    reason_lower = reason.lower()
    known_constraints = [
        "max_trade_pct", "max_buy_amount", "max_sell_amount",
        "forbidden_actions", "cash_available", "min_trade_amount",
        "risk_budget", "short_term_trade_budget_pct", "liquidity_reserve_pct",
    ]
    for name in known_constraints:
        if name in reason_lower:
            return name
    return "other"
