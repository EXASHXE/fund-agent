"""Amount derivation, capping, and risk budget helpers."""

from __future__ import annotations

from typing import Any

from .action_policy import ACTIVE_ACTIONS, PASSIVE_ACTIONS, _risk_level
from .context import _dict, _float_value, _optional_float


def _derive_execution_amount(
    action: str,
    payload: dict[str, Any],
) -> tuple[float, str]:
    if action in PASSIVE_ACTIONS:
        return 0.0, "passive action does not require execution amount"

    constraints = _dict(payload.get("constraints"))
    forbidden = {str(item).upper() for item in constraints.get("forbidden_actions", [])}
    if action in forbidden:
        return 0.0, f"{action} is forbidden by constraints"

    portfolio_context = _dict(payload.get("portfolio_context"))
    risk_profile = _dict(payload.get("risk_profile"))
    risk_budget = _dict(payload.get("risk_budget"))
    target_amount = _optional_float(payload.get("target_trade_amount"))
    has_budget_context = any(
        (
            portfolio_context,
            risk_profile,
            risk_budget,
            constraints,
            target_amount is not None,
        )
    )

    if not has_budget_context:
        return 10000.0, "default amount used because no portfolio budget context was provided"

    caps: list[float] = []
    total_value = _optional_float(portfolio_context.get("total_value"))
    max_trade_pct = _optional_float(
        risk_profile.get("max_trade_pct", risk_budget.get("max_trade_pct"))
    )
    if total_value is not None and max_trade_pct is not None:
        caps.append(total_value * max_trade_pct)

    if action in {"BUY", "INCREASE"}:
        cash_available = _optional_float(portfolio_context.get("cash_available"))
        if cash_available is not None:
            caps.append(cash_available)
        max_buy_amount = _optional_float(constraints.get("max_buy_amount"))
        if max_buy_amount is not None:
            caps.append(max_buy_amount)
    else:
        max_sell_amount = _optional_float(constraints.get("max_sell_amount"))
        if max_sell_amount is not None:
            caps.append(max_sell_amount)

    positive_caps = [cap for cap in caps if cap > 0]
    if target_amount is not None and target_amount > 0:
        amount = min([target_amount] + positive_caps) if positive_caps else target_amount
    elif positive_caps:
        amount = min(positive_caps)
    else:
        return 0.0, "missing usable trade budget cap"

    min_trade_amount = _optional_float(constraints.get("min_trade_amount")) or 0.0
    if amount < min_trade_amount:
        return 0.0, "derived execution amount is below min_trade_amount"

    return round(amount, 2), "execution amount derived from portfolio risk constraints"


def _calculate_risk_budget(payload: dict[str, Any], action: str) -> float:
    risk_budget = _dict(payload.get("risk_budget"))
    explicit = _optional_float(risk_budget.get("risk_budget"))
    if explicit is not None and explicit > 0:
        return explicit

    risk_map = {
        "conservative": 0.02,
        "moderate": 0.05,
        "aggressive": 0.10,
    }
    base = risk_map.get(_risk_level(payload.get("risk_profile")), 0.05)
    return 0.01 if action in PASSIVE_ACTIONS else base


def _validate_trade_amount(
    *,
    trade: dict[str, Any],
    portfolio_context: dict[str, Any],
    risk_profile: dict[str, Any],
    constraints: dict[str, Any],
    is_short_term: bool = False,
) -> tuple[float, list[str], bool]:
    """Validate and cap a trade amount against portfolio constraints.

    Returns (capped_amount, cap_reasons, is_valid).
    """
    action = str(trade.get("action", "")).upper()
    requested_amount = _float_value(trade.get("amount"), _float_value(trade.get("requested_amount"), 0.0))

    if requested_amount <= 0:
        return (0.0, ["amount is zero or negative"], False)

    total_value = _float_value(portfolio_context.get("total_value"), 0.0)
    max_trade_pct = _float_value(risk_profile.get("max_trade_pct"), 0.1)
    liquidity_reserve_pct = _float_value(risk_profile.get("liquidity_reserve_pct"), 0.1)
    max_trade_amount = total_value * max_trade_pct if total_value > 0 else float("inf")

    caps: list[tuple[float, str]] = [(max_trade_amount, f"max_trade_pct ({max_trade_pct})")]

    if action in ("BUY", "INCREASE"):
        cash_available = _float_value(portfolio_context.get("cash_available"), 0.0)
        effective_cash = max(cash_available - liquidity_reserve_pct * total_value, 0.0)
        if total_value > 0:
            caps.append((effective_cash, f"liquidity_reserve_pct ({liquidity_reserve_pct})"))
        max_buy_amount = _optional_float(constraints.get("max_buy_amount"))
        if max_buy_amount is not None and max_buy_amount > 0:
            caps.append((max_buy_amount, f"max_buy_amount ({max_buy_amount})"))

        if is_short_term:
            short_term_budget_pct = _float_value(
                risk_profile.get("short_term_trade_budget_pct"), 0.1
            )
            short_term_budget = total_value * short_term_budget_pct
            if total_value > 0:
                caps.append((short_term_budget, f"short_term_trade_budget_pct ({short_term_budget_pct})"))
    else:
        current_value = _float_value(trade.get("current_value"), 0.0)
        if current_value > 0:
            caps.append((current_value, "current position value"))
        max_sell_amount = _optional_float(constraints.get("max_sell_amount"))
        if max_sell_amount is not None and max_sell_amount > 0:
            caps.append((max_sell_amount, f"max_sell_amount ({max_sell_amount})"))

    caps.sort(key=lambda x: x[0])
    bounding_cap, bound_reason = caps[0]
    capped_amount = min(requested_amount, bounding_cap)

    cap_reasons: list[str] = []
    if capped_amount < requested_amount:
        cap_reasons.append(bound_reason)

    min_trade_amount = _float_value(constraints.get("min_trade_amount"), 0.0)
    if capped_amount < min_trade_amount:
        cap_reasons.append(f"below min_trade_amount ({min_trade_amount})")
        return (0.0, cap_reasons, False)

    return (round(capped_amount, 2), cap_reasons, True)
