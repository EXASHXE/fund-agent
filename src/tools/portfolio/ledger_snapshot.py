"""Deterministic portfolio ledger -> position snapshot core.

No network calls, no provider SDKs, no IO beyond dataclass/JSON serialization.
Weighted-average cost basis is the default. FIFO/LIFO are out of scope.

All outputs are JSON-serializable via dict/list/number/str/None.
"""

from __future__ import annotations

import warnings as _warnings
from dataclasses import asdict, dataclass, field
from datetime import date as date_type
from typing import Any


# ———————————————————————————————————————————————— Valid actions

_VALID_ACTIONS = frozenset({
    "BUY", "SELL", "DIVIDEND", "FEE",
    "TRANSFER_IN", "TRANSFER_OUT", "CALIBRATE",
})

_BUY_ACTIONS = frozenset({"BUY", "TRANSFER_IN"})
_SELL_ACTIONS = frozenset({"SELL", "TRANSFER_OUT"})


# ———————————————————————————————————————————————— Normalize

def normalize_transaction_events(
    raw: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Normalize and validate raw transaction events.

    Accepts either 'action' or 'type' as the action field.
    Returns (normalized_events, warnings).

    Does NOT perform network calls, IO, or provider lookups.
    """
    normalized: list[dict[str, Any]] = []
    warnings: list[str] = []

    if not isinstance(raw, list):
        return normalized, ["normalize_transaction_events: raw must be a list"]

    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            warnings.append(f"transaction[{idx}]: not a dict, skipped")
            continue

        event = dict(item)

        # Normalize action/type to 'action'
        if "action" not in event and "type" in event:
            event["action"] = event.pop("type")

        action = event.get("action", "")
        if action not in _VALID_ACTIONS:
            warnings.append(
                f"transaction[{idx}]: unknown action '{action}', "
                f"expected one of {sorted(_VALID_ACTIONS)}; keeping as-is"
            )
            # Keep it but mark for downstream handling
            normalized.append(event)
            continue

        # Ensure required fields exist
        for field_name in ("fund_code", "date"):
            if field_name not in event:
                warnings.append(
                    f"transaction[{idx}]: missing '{field_name}' for action '{action}'"
                )

        # Normalize numeric fields
        for num_field in ("amount", "shares", "nav"):
            if num_field in event and event[num_field] is not None:
                try:
                    event[num_field] = float(event[num_field])
                except (TypeError, ValueError):
                    warnings.append(
                        f"transaction[{idx}]: could not convert '{num_field}' "
                        f"to float: {event.get(num_field)!r}"
                    )
                    event[num_field] = None

        # Enforce non-negative amount/shares for buys
        if action in _BUY_ACTIONS:
            for nf in ("amount", "shares"):
                if nf in event and event[nf] is not None and event[nf] < 0:
                    warnings.append(
                        f"transaction[{idx}]: negative {nf} for {action}, clamped to 0"
                    )
                    event[nf] = 0.0

        normalized.append(event)

    return normalized, warnings


# ———————————————————————————————————————————————— Cost basis helper

def _weighted_average_cost(
    total_cost: float,
    total_shares: float,
) -> float | None:
    if total_shares <= 0:
        return None
    return total_cost / total_shares


# ———————————————————————————————————————————————— Settlement rules

def apply_settlement_rules(
    transactions: list[dict[str, Any]],
    as_of_date: str,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply minimal deterministic settlement (T+ confirmation) rules.

    Args:
        transactions: Normalized transaction events.
        as_of_date: The as-of date (YYYY-MM-DD).
        options: Optional config (settlement_lag_days, include_pending).

    Returns:
        {
            "confirmed": [...],        # transactions settled by as_of_date
            "pending": [...],           # transactions not yet settled
            "adjusted_as_of_date": str,
            "warnings": [...],
        }
    """
    opts = options or {}
    lag_days = int(opts.get("settlement_lag_days", 3))
    include_pending = bool(opts.get("include_pending", False))

    warnings: list[str] = []
    confirmed: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []

    try:
        as_of = date_type.fromisoformat(as_of_date)
    except (ValueError, TypeError):
        warnings.append(f"apply_settlement_rules: invalid as_of_date '{as_of_date}'")
        return {
            "confirmed": list(transactions),
            "pending": [],
            "adjusted_as_of_date": as_of_date,
            "warnings": warnings,
        }

    for txn in transactions:
        txn_date_str = txn.get("date", "")
        try:
            txn_date = date_type.fromisoformat(txn_date_str)
        except (ValueError, TypeError):
            # Cannot determine settlement status, treat as confirmed
            confirmed.append(txn)
            continue

        settlement_date = date_type.fromordinal(
            txn_date.toordinal() + lag_days
        )

        if settlement_date <= as_of:
            confirmed.append(txn)
        else:
            if include_pending:
                confirmed.append(txn)  # include but warn
                warnings.append(
                    f"txn {txn.get('fund_code','?')} {txn_date_str} "
                    f"settles {settlement_date.isoformat()} (after {as_of_date})"
                )
            else:
                pending.append(txn)

    return {
        "confirmed": confirmed,
        "pending": pending,
        "adjusted_as_of_date": as_of_date,
        "warnings": warnings,
    }


# ———————————————————————————————————————————————— Realized / Unrealized PnL

def calculate_realized_unrealized_pnl(
    transactions: list[dict[str, Any]],
    current_nav_by_fund: dict[str, float],
) -> dict[str, Any]:
    """Calculate realized and unrealized PnL using weighted-average cost basis.

    Args:
        transactions: Normalized transaction events in chronological order.
        current_nav_by_fund: {fund_code: current_nav}.

    Returns:
        {
            "positions": [{fund_code, shares, total_cost, avg_cost_nav,
                           current_nav, current_value, unrealized_pnl,
                           unrealized_pnl_pct, realized_pnl, warnings}],
            "overall": {total_cost, current_value, unrealized_pnl, realized_pnl},
            "warnings": [...],
        }
    """
    # Accumulate per fund
    funds: dict[str, dict[str, Any]] = {}
    overall_realized_pnl = 0.0
    warnings: list[str] = []

    for txn in transactions:
        fund_code = txn.get("fund_code", "")
        if not fund_code:
            continue

        action = txn.get("action", "")
        amount = txn.get("amount")
        shares = txn.get("shares")
        nav = txn.get("nav")

        if fund_code not in funds:
            funds[fund_code] = {
                "fund_code": fund_code,
                "total_shares": 0.0,
                "total_cost": 0.0,
                "realized_pnl": 0.0,
                "fund_warnings": [],
            }

        f = funds[fund_code]

        if action in _BUY_ACTIONS:
            if amount is not None and amount > 0:
                f["total_cost"] += amount
            if shares is not None and shares > 0:
                f["total_shares"] += shares
            elif amount is not None and nav is not None and nav > 0 and shares is None:
                # Infer shares from amount and nav
                inferred = amount / nav
                f["total_shares"] += inferred

        elif action in _SELL_ACTIONS:
            sell_shares = shares if shares is not None else 0.0
            sell_amount = amount if amount is not None else 0.0

            if sell_shares <= 0 and sell_amount > 0 and nav is not None and nav > 0:
                # Infer shares from amount and nav when only amount provided
                sell_shares = sell_amount / nav

            if sell_shares > f["total_shares"]:
                warnings.append(
                    f"{fund_code}: SELL of {sell_shares} shares exceeds "
                    f"holdings of {f['total_shares']} shares; clamping sell to "
                    f"available shares"
                )
                f["fund_warnings"].append("SELL_EXCEEDS_SHARES_CLAMPED")
                sell_shares = f["total_shares"]

            if sell_shares > 0 and f["total_shares"] > 0:
                # Weighted-average cost of sold portion
                avg_cost = _weighted_average_cost(f["total_cost"], f["total_shares"])
                cost_of_sold = avg_cost * sell_shares if avg_cost is not None else 0.0
                realized = sell_amount - cost_of_sold
                f["realized_pnl"] += realized
                overall_realized_pnl += realized

                # Reduce holdings proportionally
                cost_reduction = (
                    f["total_cost"] * sell_shares / f["total_shares"]
                )
                f["total_cost"] -= cost_reduction
                f["total_shares"] -= sell_shares

        elif action == "DIVIDEND":
            # Dividend increases cash but doesn't change shares/cost basis
            # Record as realized income (cash received)
            if amount is not None and amount > 0:
                f["realized_pnl"] += amount
                overall_realized_pnl += amount

        elif action == "FEE":
            # Fees reduce realized PnL, don't affect shares
            if amount is not None and amount > 0:
                f["realized_pnl"] -= amount
                overall_realized_pnl -= amount

        elif action == "CALIBRATE":
            # CALIBRATE overrides position data
            if amount is not None:
                f["total_cost"] = amount
            if shares is not None and shares > 0:
                f["total_shares"] = shares
            # Reset realized PnL on calibrate unless host carries it forward
            if txn.get("reset_realized_pnl", True):
                f["realized_pnl"] = 0.0

    # Calculate unrealized PnL per fund
    positions: list[dict[str, Any]] = []
    overall_cost = 0.0
    overall_value = 0.0

    for fund_code in sorted(funds):
        f = funds[fund_code]
        total_shares = f["total_shares"]
        total_cost = f["total_cost"]
        realized = f["realized_pnl"]
        fund_warnings = f["fund_warnings"]

        avg_cost_nav = _weighted_average_cost(total_cost, total_shares)

        current_nav = current_nav_by_fund.get(fund_code)
        current_value = None
        unrealized_pnl = None
        unrealized_pnl_pct = None

        if current_nav is None or current_nav <= 0:
            fund_warnings.append("MISSING_NAV_OMIT_CURRENT_VALUE")
            warnings.append(
                f"{fund_code}: missing or invalid current NAV; current_value "
                f"and unrealized_pnl omitted"
            )
        elif total_shares <= 0:
            fund_warnings.append("ZERO_SHARES_OMIT_VALUE")
            warnings.append(
                f"{fund_code}: zero shares; current_value and unrealized_pnl omitted"
            )
        else:
            current_value = total_shares * current_nav
            overall_value += current_value
            unrealized_pnl = current_value - total_cost
            unrealized_pnl_pct = (
                unrealized_pnl / total_cost if total_cost > 0 else None
            )

        overall_cost += total_cost

        positions.append({
            "fund_code": fund_code,
            "shares": round(total_shares, 8),
            "current_nav": current_nav,
            "current_value": round(current_value, 2) if current_value is not None else None,
            "total_cost": round(total_cost, 2),
            "average_cost_nav": round(avg_cost_nav, 8) if avg_cost_nav is not None else None,
            "unrealized_pnl": round(unrealized_pnl, 2) if unrealized_pnl is not None else None,
            "unrealized_pnl_pct": round(unrealized_pnl_pct, 6) if unrealized_pnl_pct is not None else None,
            "realized_pnl": round(realized, 2) if realized else None,
            "warnings": fund_warnings,
        })

    return {
        "positions": positions,
        "overall": {
            "total_cost": round(overall_cost, 2),
            "current_value": round(overall_value, 2) if overall_value > 0 else None,
            "unrealized_pnl": round(overall_value - overall_cost, 2) if overall_value > 0 else None,
            "realized_pnl": round(overall_realized_pnl, 2),
        },
        "warnings": warnings,
    }


# ———————————————————————————————————————————————— Position snapshot from transactions

def build_position_snapshot_from_transactions(
    transactions: list[dict[str, Any]],
    current_nav_by_fund: dict[str, float],
    as_of_date: str,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a position snapshot deterministically from a transaction ledger.

    Args:
        transactions: Raw transaction events (will be normalized).
        current_nav_by_fund: {fund_code: current_nav} for current value calc.
        as_of_date: The as-of date (YYYY-MM-DD). Only transactions on or
                    before this date (respecting settlement) are included.
        options: Optional config:
            - settlement_lag_days (int): days for T+ settlement. Default 3.
            - include_pending (bool): include pending settlements. Default False.
            - cash_available (float): host-provided cash balance.
            - initial_cash (float): starting cash for cashflow calc.

    Returns:
        {
            "as_of_date": "2026-06-01",
            "positions": [{fund_code, shares, current_nav, current_value,
                           total_cost, avg_cost_nav, unrealized_pnl,
                           unrealized_pnl_pct, realized_pnl, warnings}],
            "cashflow_summary": {total_inflows, total_outflows, net_cashflow,
                                 dividend_income, fee_expense},
            "warnings": [...],
        }
    """
    opts = options or {}
    all_warnings: list[str] = []

    # Normalize transactions
    normalized, norm_warnings = normalize_transaction_events(transactions)
    all_warnings.extend(norm_warnings)

    if not normalized:
        return {
            "as_of_date": as_of_date,
            "positions": [],
            "cashflow_summary": {
                "total_inflows": 0.0,
                "total_outflows": 0.0,
                "net_cashflow": 0.0,
                "dividend_income": 0.0,
                "fee_expense": 0.0,
            },
            "warnings": all_warnings,
        }

    # Apply settlement rules
    settlement = apply_settlement_rules(normalized, as_of_date, options=opts)
    confirmed = settlement.get("confirmed", [])
    all_warnings.extend(settlement.get("warnings", []))

    if not confirmed:
        all_warnings.append("no confirmed transactions in settlement window")

    # Calculate PnL from confirmed transactions
    pnl_result = calculate_realized_unrealized_pnl(confirmed, current_nav_by_fund)
    all_warnings.extend(pnl_result.get("warnings", []))

    # Build cashflow summary (from all normalized, not just confirmed)
    total_inflows = 0.0
    total_outflows = 0.0
    dividend_income = 0.0
    fee_expense = 0.0

    for txn in normalized:
        action = txn.get("action", "")
        amount = txn.get("amount", 0.0) or 0.0
        # For BUY-type, exclude TRANSFER_IN from inflows for cashflow
        # (TRANSFER_IN is a position movement, not new cash)
        if action in ("BUY",):
            total_outflows += amount
        elif action in ("SELL",):
            total_inflows += amount
        elif action == "DIVIDEND":
            dividend_income += amount
            total_inflows += amount
        elif action == "FEE":
            fee_expense += amount
            total_outflows += amount
        elif action == "TRANSFER_IN":
            total_inflows += amount
        elif action == "TRANSFER_OUT":
            total_outflows += amount
        # CALIBRATE has no cashflow impact

    initial_cash = opts.get("initial_cash", 0.0)
    net_cashflow = total_inflows - total_outflows
    implied_cash = initial_cash + net_cashflow

    return {
        "as_of_date": as_of_date,
        "positions": pnl_result["positions"],
        "pnl_overall": pnl_result["overall"],
        "cashflow_summary": {
            "total_inflows": round(total_inflows, 2),
            "total_outflows": round(total_outflows, 2),
            "net_cashflow": round(net_cashflow, 2),
            "dividend_income": round(dividend_income, 2),
            "fee_expense": round(fee_expense, 2),
            "initial_cash": round(initial_cash, 2),
            "implied_cash": round(implied_cash, 2),
        },
        "settlement": {
            "confirmed_count": len(confirmed),
            "pending_count": len(settlement.get("pending", [])),
            "lag_days": opts.get("settlement_lag_days", 3),
            "include_pending": opts.get("include_pending", False),
        },
        "warnings": all_warnings,
    }


# ———————————————————————————————————————————————— Reconciliation

def reconcile_snapshot_with_portfolio(
    snapshot: dict[str, Any],
    portfolio: dict[str, Any],
) -> dict[str, Any]:
    """Compare a host-provided portfolio.positions with a ledger-derived snapshot.

    Does NOT throw for mismatches. Returns a reconciliation report with
    mismatches listed as warnings.

    Args:
        snapshot: Output of build_position_snapshot_from_transactions.
        portfolio: Host-provided portfolio dict with 'positions' list.

    Returns:
        {
            "matched": true/false,
            "comparisons": [{fund_code, snapshot_value, portfolio_value,
                              delta, delta_pct, matched}],
            "mismatches": [{fund_code, reason, snapshot_value, portfolio_value}],
            "warnings": [...],
        }
    """
    warnings: list[str] = []
    mismatch_warnings: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []
    all_matched = True

    snap_positions = {p["fund_code"]: p for p in snapshot.get("positions", [])}
    port_positions = {p.get("fund_code", ""): p for p in portfolio.get("positions", [])
                      if p.get("fund_code")}

    # Check each snapshot fund against portfolio
    for fund_code, snap_pos in snap_positions.items():
        port_pos = port_positions.get(fund_code)

        if port_pos is None:
            mismatch_warnings.append({
                "fund_code": fund_code,
                "reason": "MISSING_IN_PORTFOLIO",
                "snapshot_shares": snap_pos.get("shares"),
                "snapshot_value": snap_pos.get("current_value"),
                "portfolio_shares": None,
                "portfolio_value": None,
            })
            warnings.append(
                f"{fund_code}: in ledger-derived snapshot but missing from "
                f"host portfolio"
            )
            all_matched = False
            comparisons.append({
                "fund_code": fund_code,
                "snapshot_shares": snap_pos.get("shares"),
                "portfolio_shares": None,
                "shares_delta": None,
                "snapshot_value": snap_pos.get("current_value"),
                "portfolio_value": None,
                "value_delta": None,
                "matched": False,
            })
            continue

        snap_shares = snap_pos.get("shares", 0.0) or 0.0
        port_shares = port_pos.get("shares", 0.0) or 0.0
        snap_value = snap_pos.get("current_value")
        port_value = port_pos.get("current_value")

        shares_delta = snap_shares - port_shares
        shares_tolerance = 0.01  # 1 share cent tolerance

        if abs(shares_delta) > shares_tolerance:
            mismatch_warnings.append({
                "fund_code": fund_code,
                "reason": "SHARES_MISMATCH",
                "snapshot_shares": snap_shares,
                "portfolio_shares": port_shares,
                "delta": round(shares_delta, 8),
            })
            warnings.append(
                f"{fund_code}: shares mismatch — snapshot={snap_shares:.4f}, "
                f"portfolio={port_shares:.4f}, delta={shares_delta:.4f}"
            )
            all_matched = False

        comp = {
            "fund_code": fund_code,
            "snapshot_shares": snap_shares,
            "portfolio_shares": port_shares,
            "shares_delta": round(shares_delta, 8),
            "snapshot_value": snap_value,
            "portfolio_value": port_value,
            "value_delta": (
                round((snap_value - port_value), 2)
                if snap_value is not None and port_value is not None
                else None
            ),
            "matched": abs(shares_delta) <= shares_tolerance,
        }
        comparisons.append(comp)

    # Check for portfolio funds not in snapshot
    for fund_code in port_positions:
        if fund_code not in snap_positions:
            port_pos = port_positions[fund_code]
            mismatch_warnings.append({
                "fund_code": fund_code,
                "reason": "MISSING_IN_SNAPSHOT",
                "snapshot_shares": None,
                "snapshot_value": None,
                "portfolio_shares": port_pos.get("shares"),
                "portfolio_value": port_pos.get("current_value"),
            })
            warnings.append(
                f"{fund_code}: in host portfolio but missing from ledger-derived snapshot"
            )
            all_matched = False
            comparisons.append({
                "fund_code": fund_code,
                "snapshot_shares": None,
                "portfolio_shares": port_pos.get("shares"),
                "shares_delta": None,
                "snapshot_value": None,
                "portfolio_value": port_pos.get("current_value"),
                "value_delta": None,
                "matched": False,
            })

    return {
        "matched": all_matched,
        "comparisons": comparisons,
        "mismatches": mismatch_warnings,
        "warnings": warnings,
    }
