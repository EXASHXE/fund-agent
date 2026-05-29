"""Pure settlement calculation tools. No IO, no network, no LLM."""

from __future__ import annotations

from datetime import date


def calculate_execution_amount(
    decision_amount: float,
    current_nav: float,
    fee_rate: float = 0.0015,
) -> dict:
    """Calculate shares from execution amount. Pure math.

    Args:
        decision_amount: Gross decision amount (e.g. 10 000 CNY).
        current_nav: Current NAV per share.
        fee_rate: Fee rate as a fraction (default 0.15 %).

    Returns:
        Dict with keys: gross_amount, fee, net_amount, shares, nav.
    """
    if current_nav <= 0:
        return {
            "gross_amount": decision_amount,
            "fee": 0.0,
            "net_amount": decision_amount,
            "shares": 0.0,
            "nav": current_nav,
        }

    fee = decision_amount * fee_rate
    net = decision_amount - fee
    shares = net / current_nav

    return {
        "gross_amount": decision_amount,
        "fee": round(fee, 4),
        "net_amount": round(net, 4),
        "shares": round(shares, 6),
        "nav": current_nav,
    }


def simulate_position_ledger(
    events: list[dict],
    nav_map: dict[str, float],
    fee_rate: float = 0.0015,
    settle_delay: int = 1,
) -> dict:
    """Simulate a position ledger from events and NAV history.

    Pure math, no IO/network/LLM. Processes BUY-type events and
    tracks cumulative shares, cost, and P&L.

    Args:
        events: List of event dicts with keys: type, date, amount.
        nav_map: Dict mapping date strings to NAV values.
        fee_rate: Fee rate as a fraction (default 0.15 %).
        settle_delay: Business days until settlement (default 1).

    Returns:
        Dict with keys: total_shares, total_cost, avg_cost_per_share,
        current_value, unrealized_pnl, realized_pnl, event_log.
    """
    total_shares = 0.0
    total_cost = 0.0
    realized_pnl = 0.0
    event_log: list[dict] = []

    for event in events:
        event_type = event.get("type", "").upper()
        event_date = event.get("date", "")
        event_amount = event.get("amount", 0.0)

        nav = nav_map.get(event_date)
        if nav is None or nav <= 0:
            event_log.append({"date": event_date, "action": event_type, "status": "SKIPPED"})
            continue

        if event_type in ("BUY", "CALIBRATE"):
            result = calculate_execution_amount(event_amount, nav, fee_rate)
            shares = result["shares"]
            total_shares += shares
            total_cost += event_amount
            event_log.append({
                "date": event_date,
                "action": event_type,
                "amount": event_amount,
                "nav": nav,
                "shares": round(shares, 6),
                "status": "CONFIRMED",
            })
        else:
            event_log.append({"date": event_date, "action": event_type, "status": "SKIPPED"})

    avg_cost = total_cost / total_shares if total_shares > 0 else 0.0
    sorted_dates = sorted(nav_map.keys())
    last_nav = nav_map[sorted_dates[-1]] if sorted_dates else 0.0
    current_value = total_shares * last_nav
    unrealized_pnl = current_value - total_cost

    return {
        "total_shares": round(total_shares, 6),
        "total_cost": round(total_cost, 2),
        "avg_cost_per_share": round(avg_cost, 4),
        "current_value": round(current_value, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "realized_pnl": round(realized_pnl, 2),
        "event_log": event_log,
    }


def _settlement_date(trade_date_str: str, settle_delay: int = 1) -> str:
    """Calculate settlement date. Uses next_business_day from calendar tools.

    Args:
        trade_date_str: ISO-format date string (``"YYYY-MM-DD"``).
        settle_delay: Number of business days to advance (default 1).

    Returns:
        ISO-format settlement date string.
    """
    from src.tools.calendar.dates import next_business_day

    d = date.fromisoformat(trade_date_str)
    for _ in range(settle_delay):
        d = next_business_day(d)
    return d.isoformat()
