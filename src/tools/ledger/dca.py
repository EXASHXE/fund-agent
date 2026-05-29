"""Pure DCA simulation tools. No IO, no network, no LLM."""

from __future__ import annotations

from datetime import date


def simulate_dca_plan(
    monthly_amount: float,
    nav_history: dict[str, float],
    start_date: str,
    end_date: str,
    fee_rate: float = 0.0015,
) -> dict:
    """Simulate dollar-cost averaging plan. Pure math, deterministic.

    Invests *monthly_amount* on each day in the range, using the nearest
    available NAV date on or after the target date.  Deducts *fee_rate*
    from each investment via :func:`calculate_execution_amount`.

    Args:
        monthly_amount: Gross amount to invest each month.
        nav_history: Dict mapping ISO date strings to NAV values.
        start_date: ISO-format start date (``"YYYY-MM-DD"``).
        end_date: ISO-format end date (inclusive).
        fee_rate: Fee rate as a fraction (default 0.0015 = 0.15 %).

    Returns:
        Dict with keys: total_invested, total_shares, avg_cost_per_share,
        final_value, total_return_pct, monthly_details (list of per-investment
        dicts with date, nav, shares_bought, amount).

        All fields are zeroed out when *nav_history* is empty.
    """
    from src.tools.ledger.settlement import calculate_execution_amount

    if not nav_history:
        return {
            "total_invested": 0.0,
            "total_shares": 0.0,
            "avg_cost_per_share": 0.0,
            "final_value": 0.0,
            "total_return_pct": 0.0,
            "monthly_details": [],
        }

    total_invested = 0.0
    total_shares = 0.0
    monthly_details: list[dict] = []

    sorted_dates = sorted(nav_history.keys())
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)

    current = start
    while current <= end:
        current_str = current.isoformat()

        # Find nearest nav date on or after the current date
        nav = None
        for d in sorted_dates:
            if d >= current_str:
                nav = nav_history[d]
                break
        if nav is None and sorted_dates:
            nav = nav_history[sorted_dates[-1]]

        if nav and nav > 0:
            result = calculate_execution_amount(monthly_amount, nav, fee_rate)
            total_invested += monthly_amount
            total_shares += result["shares"]
            monthly_details.append({
                "date": current_str,
                "nav": nav,
                "shares_bought": result["shares"],
                "amount": monthly_amount,
            })

        # Advance to the same day in the next month
        if current.month == 12:
            current = date(current.year + 1, 1, current.day)
        else:
            try:
                current = date(current.year, current.month + 1, current.day)
            except ValueError:
                # Handle days that don't exist in the target month (e.g. Jan 31 → Feb)
                current = date(current.year, current.month + 1, 1)

    avg_cost = total_invested / total_shares if total_shares > 0 else 0.0
    last_nav = nav_history[sorted_dates[-1]] if sorted_dates else 0.0
    final_value = total_shares * last_nav
    total_return_pct = (
        ((final_value - total_invested) / total_invested * 100)
        if total_invested > 0
        else 0.0
    )

    return {
        "total_invested": round(total_invested, 2),
        "total_shares": round(total_shares, 6),
        "avg_cost_per_share": round(avg_cost, 4),
        "final_value": round(final_value, 2),
        "total_return_pct": round(total_return_pct, 2),
        "monthly_details": monthly_details,
    }
