"""Unified XIRR implementation via Newton's method.

Phase 1.3: Single canonical xirr() replacing the duplicate implementations
that were in calc.py (calc_xirr from holdings.py, _calc_xirr from calculator.py).

Pure Newton's method — no IO, no network, no LLM.
"""

from __future__ import annotations

from datetime import date


def xirr(
    cashflows: list[tuple[date, float]],
    current_value: float,
    current_date: date | None = None,
    guess: float = 0.1,
) -> float:
    """Annualized XIRR via Newton's method (pure, no scipy).

    Solves for *r* such that the net present value of all cashflows plus
    the terminal current_value is zero:

        NPV = sum(cf_i / (1+r)^(t_i/365)) = 0

    where *t_i* is the number of days from the first cashflow.

    Args:
        cashflows: List of ``(date, amount)`` tuples.
            Negative amounts = money invested (outflow).
            Positive amounts = dividends / returns (inflow).
        current_value: Current market value of the investment (positive = asset).
        current_date: Date of the current_value.  ``None`` → ``date.today()``.
        guess: Initial Newton guess (default 0.1 = 10 %).

    Returns:
        Annualized IRR as a float (e.g. 0.15 = 15 %).
        Returns 0.0 when no valid IRR can be computed (empty cashflows,
        single flow without both signs, etc.).

    Edge cases:
        - Empty cashflows → 0.0
        - current_value ≤ 0  → 0.0
        - Only one sign (all positive or all negative) → 0.0
        - Complex rate convergence → -0.99 (effectively -99 %)
    """
    if current_date is None:
        current_date = date.today()

    # ------------------------------------------------------------------
    # Guard: no cashflows or zero/negative terminal value → no return
    # ------------------------------------------------------------------
    if not cashflows or current_value <= 0:
        return 0.0

    all_cfs: list[tuple[date, float]] = list(cashflows) + [(current_date, current_value)]

    # ------------------------------------------------------------------
    # Need both positive and negative flows for a meaningful IRR
    # ------------------------------------------------------------------
    has_pos = any(v > 0 for _, v in all_cfs)
    has_neg = any(v < 0 for _, v in all_cfs)
    if not (has_pos and has_neg):
        return 0.0

    rate = guess
    base_date = all_cfs[0][0]

    # ------------------------------------------------------------------
    # Newton iteration  (max 100 steps)
    # ------------------------------------------------------------------
    for _ in range(100):
        npv = 0.0
        dnpv = 0.0
        for d, v in all_cfs:
            t = (d - base_date).days / 365.0
            factor = (1.0 + rate) ** (-t)  # = 1 / (1+rate)^t
            npv += v * factor
            dnpv += -t * v * factor / (1.0 + rate)

        # Derivative too small → can't take a step
        if abs(dnpv) < 1e-12:
            break

        new_rate = rate - npv / dnpv

        # Guard against complex results (rate < -1 makes (1+rate) negative)
        if isinstance(new_rate, complex):
            return -0.99

        # Clamp to avoid divergence / numerical instability
        if new_rate <= -0.999999:
            new_rate = -0.99
        elif new_rate > 10.0:
            new_rate = 5.0

        # Converged
        if abs(new_rate - rate) < 1e-8:
            rate = new_rate
            break

        rate = new_rate

    return rate if rate > -0.99 else -0.99
