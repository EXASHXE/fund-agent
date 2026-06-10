"""Professional diagnostic rules for fund_analysis.

Local-only, deterministic, host-data-only rules. These rules do NOT fetch data,
call providers, use LLMs, or make formal decisions. All analysis is derived from
host-supplied payload fields and existing computed metrics.
"""

from __future__ import annotations

from typing import Any

from .context import CoreMetricsBundle, PortfolioInputBundle


def _dt(date_str: str) -> str:
    return str(date_str or "").strip()


def _dict(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _list(v: Any) -> list[Any]:
    return v if isinstance(v, list) else []


def _classify_fee_items(
    affected_funds: list[dict[str, Any]],
    positions_index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    fee_items: list[dict[str, Any]] = []
    for af in affected_funds:
        fund_code = af.get("fund_code", "")
        fee_pct = af.get("fee_pct")
        holding_days = af.get("holding_days")
        threshold_days = af.get("threshold_days")
        pos = positions_index.get(fund_code, {})
        current_value = float(pos.get("current_value", 0) or 0)
        invested_raw = pos.get("total_cost") or pos.get("invested_amount")
        absolute_pnl: float | None = None
        pnl_pct: float | None = None
        if invested_raw is not None:
            try:
                invested = float(invested_raw)
                absolute_pnl = round(current_value - invested, 2)
                if invested > 0:
                    pnl_pct = round(absolute_pnl / invested, 6)
            except (TypeError, ValueError):
                pass

        level = "warning"
        reason = ""
        fee_pct_val = float(fee_pct) if fee_pct is not None else 0.0
        holding_days_val = int(holding_days) if holding_days is not None else 0
        threshold_days_val = int(threshold_days) if threshold_days is not None else 7

        # blocker: short holding + high fee (>=1%) + loss or unknown PnL
        if holding_days_val < threshold_days_val and fee_pct_val >= 0.01 and (absolute_pnl is None or absolute_pnl < 0):
            level = "blocker"
            reason = f"Short holding ({holding_days_val}d < {threshold_days_val}d), high fee ({fee_pct_val:.1%}), position at loss or PnL unknown"
        elif holding_days_val < threshold_days_val and fee_pct_val >= 0.01:
            level = "warning"
            reason = f"Short holding ({holding_days_val}d < {threshold_days_val}d), fee {fee_pct_val:.1%}, but position profitable"
        elif holding_days_val < threshold_days_val and fee_pct_val > 0:
            level = "warning"
            reason = f"Short holding ({holding_days_val}d < {threshold_days_val}d) with small fee {fee_pct_val:.1%}"
        elif fee_pct_val >= 0.01:
            level = "warning"
            reason = f"High redemption fee {fee_pct_val:.1%}"
        else:
            level = "warning"
            reason = "Fee schedule present but details incomplete"

        fee_items.append({
            "fund_code": fund_code,
            "fund_name": str(pos.get("fund_name", pos.get("name", fund_code))),
            "level": level,
            "reason": reason,
            "fee_pct": fee_pct_val,
            "holding_days": holding_days_val,
            "threshold_days": threshold_days_val,
            "current_value": current_value,
            "absolute_pnl": absolute_pnl,
            "pnl_pct": pnl_pct,
        })
    return fee_items


# ── 1. Short-holding redemption fee risk ────────────────────────────────────

def compute_redemption_fee_risk(
    bundle: PortfolioInputBundle,
    metrics: CoreMetricsBundle,
) -> dict[str, Any] | None:
    """Detect positions with recent buys that may incur short-holding redemption fees.

    Uses:
    - bundle.transactions (list of dicts)
    - bundle.redemption_rules (dict keyed by fund_code)
    - bundle.fee_schedules (dict keyed by fund_code)
    - bundle.positions (list of dicts)
    - bundle.as_of_date
    """
    transactions = bundle.transactions
    if not isinstance(transactions, list) or not transactions:
        return None

    as_of_str = _dt(bundle.as_of_date)
    if not as_of_str:
        return None

    redemption_rules = _dict(bundle.redemption_rules)
    if not redemption_rules:
        return None

    positions_index = {
        p["fund_code"]: p
        for p in bundle.positions
        if isinstance(p, dict) and p.get("fund_code")
    }
    if not positions_index:
        return None

    affected_funds: list[dict[str, Any]] = []
    as_of_date = as_of_str

    for fund_code in sorted(positions_index.keys()):
        rules = _dict(redemption_rules.get(fund_code))
        if not rules:
            continue

        threshold_days = rules.get("holding_period_days") or rules.get("min_holding_days") or rules.get("short_holding_days")
        try:
            threshold_days = int(threshold_days) if threshold_days is not None else 7
        except (TypeError, ValueError):
            threshold_days = 7

        short_fee_pct = rules.get("redemption_fee_pct") or rules.get("short_redemption_fee_pct")
        if short_fee_pct is None:
            short_fee_pct = rules.get("fee_pct")

        if short_fee_pct is not None and float(short_fee_pct) <= 0:
            continue

        fund_txns = [
            t for t in transactions
            if isinstance(t, dict) and t.get("fund_code") == fund_code
            and str(t.get("action", "")).upper() == "BUY"
        ]
        if not fund_txns:
            continue

        recent_buys: list[dict[str, Any]] = []
        for txn in fund_txns:
            txn_date = _dt(txn.get("date"))
            if not txn_date:
                continue
            try:
                from datetime import date
                buy_dt = date.fromisoformat(txn_date)
                eval_dt = date.fromisoformat(as_of_date)
                holding = (eval_dt - buy_dt).days
            except (ValueError, TypeError):
                continue

            if threshold_days is not None and holding < threshold_days:
                recent_buys.append({
                    "date": txn_date,
                    "amount": float(txn.get("amount", 0)),
                    "holding_days": holding,
                })

        if not recent_buys:
            continue

        for buy in recent_buys:
            pos = positions_index.get(fund_code, {})
            affected_funds.append({
                "fund_code": fund_code,
                "fund_name": str(pos.get("fund_name", pos.get("name", fund_code))),
                "recent_buy_date": buy["date"],
                "holding_days": buy["holding_days"],
                "threshold_days": threshold_days,
                "fee_pct": float(short_fee_pct) if short_fee_pct is not None else None,
                "estimated_recent_amount": buy["amount"],
                "warning": (
                    f"Recent buy of {buy['amount']:.0f} on {buy['date']} "
                    f"({buy['holding_days']}d ago) is within {threshold_days}-day "
                    f"fee window. Redemption may incur ~{float(short_fee_pct) * 100:.1f}% fee."
                ) if short_fee_pct is not None else (
                    f"Recent buy of {buy['amount']:.0f} on {buy['date']} "
                    f"({buy['holding_days']}d ago) is within {threshold_days}-day "
                    f"holding period. Check redemption fee rules."
                ),
            })

    if not affected_funds:
        return None

    highest_fee = max(
        (f["fee_pct"] for f in affected_funds if f["fee_pct"] is not None),
        default=None,
    )

    fee_items = _classify_fee_items(affected_funds, positions_index)
    has_blocker = any(fi["level"] == "blocker" for fi in fee_items)
    has_warning = any(fi["level"] == "warning" for fi in fee_items)

    return {
        "as_of_date": as_of_date,
        "affected_funds": affected_funds,
        "fee_items": fee_items,
        "has_blocker": has_blocker,
        "has_warning": has_warning,
        "summary": {
            "affected_count": len(affected_funds),
            "highest_fee_pct": highest_fee,
            "note": "host-provided rules and transaction data only; no fee data was fetched",
        },
    }


# ── 2. Overlap diagnostics ──────────────────────────────────────────────────

def compute_overlap_diagnostics(
    bundle: PortfolioInputBundle,
    metrics: CoreMetricsBundle,
) -> dict[str, Any] | None:
    """Detect overlapping holdings and themes across multiple funds.

    Uses:
    - bundle.holdings (dict keyed by fund_code)
    - bundle.fund_profiles (dict keyed by fund_code)
    - bundle.positions (list of dicts)
    - metrics.portfolio_summary
    """
    holdings = _dict(bundle.holdings)
    if not holdings or len(holdings) < 2:
        return None

    fund_profiles = _dict(bundle.fund_profiles)
    fund_codes = [
        p["fund_code"] for p in bundle.positions
        if isinstance(p, dict) and p.get("fund_code") and p.get("fund_code") in holdings
    ]
    if len(fund_codes) < 2:
        return None

    total_value = float(bundle.portfolio.get("total_value", 0) or 0)

    # Build holding name -> {fund_code: weight_in_fund} mapping
    holding_funds: dict[str, dict[str, float]] = {}
    for fc in fund_codes:
        fund_holdings = holdings.get(fc)
        if not isinstance(fund_holdings, list):
            continue
        for h in fund_holdings:
            if not isinstance(h, dict):
                continue
            name = str(h.get("name", h.get("ticker", ""))).strip()
            if not name:
                continue
            weight = float(h.get("weight", 0) or 0)
            holding_funds.setdefault(name, {})[fc] = weight

    position_values = {
        p["fund_code"]: float(p.get("current_value", 0) or 0)
        for p in bundle.positions
        if isinstance(p, dict) and p.get("fund_code")
    }

    overlapping_holdings: list[dict[str, Any]] = []
    overlapping_themes: dict[str, set[str]] = {}
    overlapping_regions: dict[str, set[str]] = {}

    for holding_name, funds_weights in sorted(holding_funds.items()):
        if len(funds_weights) >= 2:
            fund_list = sorted(funds_weights.keys())
            overlapping_holdings.append({
                "holding_name": holding_name,
                "funds": fund_list,
                "combined_fund_weight": round(sum(funds_weights.values()), 4),
            })

    # Theme/region overlap from profiles
    for fc in fund_codes:
        profile = _dict(fund_profiles.get(fc))
        theme = profile.get("theme", "")
        if theme:
            overlapping_themes.setdefault(str(theme), set()).add(fc)
        region = profile.get("region", "")
        if region:
            overlapping_regions.setdefault(str(region), set()).add(fc)

    theme_output: list[dict[str, Any]] = []
    for theme, funds in sorted(overlapping_themes.items()):
        if len(funds) >= 2:
            combined_weight = 0.0
            if total_value > 0:
                for f in funds:
                    combined_weight += position_values.get(f, 0) / total_value
            theme_output.append({
                "theme": theme,
                "funds": sorted(funds),
                "combined_portfolio_weight": round(combined_weight, 4),
            })

    region_output: list[dict[str, Any]] = []
    for region, funds in sorted(overlapping_regions.items()):
        if len(funds) >= 2:
            combined_weight = 0.0
            if total_value > 0:
                for f in funds:
                    combined_weight += position_values.get(f, 0) / total_value
            region_output.append({
                "region": region,
                "funds": sorted(funds),
                "combined_portfolio_weight": round(combined_weight, 4),
            })

    if not overlapping_holdings and not theme_output and not region_output:
        return None

    highest_overlap = (
        theme_output[0]["theme"] if theme_output
        else overlapping_holdings[0]["holding_name"] if overlapping_holdings
        else ""
    )

    return {
        "overlapping_holdings": overlapping_holdings,
        "overlapping_themes": theme_output,
        "overlapping_regions": region_output,
        "summary": {
            "overlap_count": len(overlapping_holdings) + len(theme_output) + len(region_output),
            "highest_overlap_theme": (
                theme_output[0]["theme"]
                if theme_output
                else (
                    overlapping_holdings[0]["holding_name"]
                    if overlapping_holdings
                    else None
                )
            ),
            "note": "host-provided holdings and profile data only",
        },
    }


# ── 3. Theme overweight diagnostics ──────────────────────────────────────────

def compute_theme_overweight_diagnostics(
    bundle: PortfolioInputBundle,
    metrics: CoreMetricsBundle,
) -> dict[str, Any] | None:
    """Detect theme concentration beyond risk profile or constraint limits.

    Uses:
    - metrics.exposures
    - metrics.industry_exposure
    - bundle.risk_profile
    - bundle.constraints
    - bundle.fund_profiles
    - bundle.positions
    """
    risk_profile = _dict(bundle.risk_profile)
    constraints = _dict(bundle.constraints)
    max_theme = None
    for key in ("max_theme_weight", "max_single_theme_weight"):
        val = risk_profile.get(key) or constraints.get(key)
        if val is not None:
            try:
                max_theme = float(val)
                break
            except (TypeError, ValueError):
                pass

    # Derive theme weights from exposures (theme:total_value ratios)
    exposures = _dict(metrics.exposures)
    if not exposures:
        return None

    total_value = float(bundle.portfolio.get("total_value", 0) or 0)
    if total_value <= 0:
        return None

    theme_weights: dict[str, float] = {}
    fund_to_theme: dict[str, str] = {}
    for fc in bundle.fund_codes:
        profile = _dict(bundle.fund_profiles.get(fc))
        theme = profile.get("theme", "")
        if not theme:
            continue
        fund_to_theme[fc] = theme
        pos_val = 0.0
        for p in bundle.positions:
            if isinstance(p, dict) and p.get("fund_code") == fc:
                pos_val = float(p.get("current_value", 0) or 0)
                break
        theme_weights[theme] = theme_weights.get(theme, 0.0) + pos_val / total_value

    if not theme_weights:
        return None

    overweight_themes: list[dict[str, Any]] = []
    for theme in sorted(theme_weights.keys()):
        weight = theme_weights[theme]
        excess = None
        if max_theme is not None and weight > max_theme:
            excess = round(weight - max_theme, 4)
        if max_theme is not None and weight > max_theme * 0.75:
            funds = [fc for fc, t in fund_to_theme.items() if t == theme]
            overweight_themes.append({
                "theme": theme,
                "weight": round(weight, 4),
                "limit": max_theme,
                "excess": excess,
                "funds": sorted(funds),
            })

    if not overweight_themes:
        return None

    max_weight_theme = max(overweight_themes, key=lambda t: t["weight"])
    return {
        "limits": {"max_theme_weight": max_theme},
        "overweight_themes": overweight_themes,
        "summary": {
            "overweight_count": len(overweight_themes),
            "max_theme": max_weight_theme["theme"],
            "max_theme_weight": max_weight_theme["weight"],
        },
    }


# ── 4. DCA drawdown diagnostics ──────────────────────────────────────────────

def compute_dca_drawdown_diagnostics(
    bundle: PortfolioInputBundle,
    metrics: CoreMetricsBundle,
) -> dict[str, Any] | None:
    """Review DCA plans for funds experiencing recent drawdowns.

    Uses:
    - bundle.dca_plans
    - bundle.nav_history
    - bundle.risk_profile
    - metrics.dca_review
    - metrics.fund_metrics
    """
    dca_plans = _dict(bundle.dca_plans)
    if not dca_plans:
        return None

    nav_history = _dict(bundle.nav_history)
    fund_metrics = _dict(metrics.fund_metrics)
    reviewed_funds: list[dict[str, Any]] = []
    reviewed_count = 0
    funds_with_drawdown = 0

    for plan_id, plan in sorted(dca_plans.items()):
        if not isinstance(plan, dict):
            continue
        fund_code = str(plan.get("fund_code", ""))
        if not fund_code:
            continue

        reviewed_count += 1
        amount = float(plan.get("monthly_amount", plan.get("amount", 0)) or 0)
        cadence = str(plan.get("schedule", plan.get("cadence", "")))
        nav_points = nav_history.get(fund_code, [])

        recent_return = None
        max_drawdown = None
        f_metrics = fund_metrics.get(fund_code, {})

        if isinstance(f_metrics, dict):
            recent_return = f_metrics.get("total_return")
            max_drawdown = f_metrics.get("max_drawdown")

        diagnostic = ""
        dca_status = "active"
        if max_drawdown is not None and float(max_drawdown) > 0.10:
            funds_with_drawdown += 1
            dca_status = "under_drawdown"
            diagnostic = (
                f"Fund {fund_code} has max drawdown {float(max_drawdown):.1%}. "
                f"DCA may benefit from buying at lower NAV, but review risk tolerance."
            )
        elif recent_return is not None and float(recent_return) < -0.05:
            funds_with_drawdown += 1
            dca_status = "under_drawdown"
            diagnostic = (
                f"Fund {fund_code} has recent return {float(recent_return):.1%}. "
                f"Continue DCA if conviction holds; formal DCA change requires decision_support."
            )
        else:
            dca_status = "active"
            diagnostic = "DCA continuing within normal range"

        reviewed_funds.append({
            "fund_code": fund_code,
            "dca_status": dca_status,
            "recent_return": recent_return,
            "max_drawdown": max_drawdown,
            "plan_amount": amount,
            "cadence": cadence,
            "diagnostic": diagnostic,
        })

    if not reviewed_funds:
        return None

    return {
        "reviewed_funds": reviewed_funds,
        "summary": {
            "reviewed_count": reviewed_count,
            "funds_with_drawdown": funds_with_drawdown,
            "note": "diagnostic only; formal DCA change requires decision_support",
        },
    }


# ── 5. Cash reserve / short-term budget diagnostics ──────────────────────────

def compute_cash_budget_diagnostics(
    bundle: PortfolioInputBundle,
    metrics: CoreMetricsBundle,
) -> dict[str, Any] | None:
    """Detect cash below liquidity reserve or short-term budget constraints.

    Uses:
    - bundle.portfolio (cash_available, total_value)
    - bundle.risk_profile (liquidity_reserve_pct, short_term_trade_budget_pct)
    - metrics.trade_budget
    - metrics.short_term_budget
    - bundle.constraints
    """
    risk_profile = _dict(bundle.risk_profile)
    total_value = float(bundle.portfolio.get("total_value", 0) or 0)
    cash_available = float(bundle.portfolio.get("cash_available", 0) or 0)

    if total_value <= 0:
        return None

    cash_ratio = round(cash_available / total_value, 4) if total_value > 0 else 0.0

    liquidity_reserve_pct = None
    try:
        liquidity_reserve_pct = float(risk_profile.get("liquidity_reserve_pct", 0.1))
    except (TypeError, ValueError):
        pass

    short_term_pct = None
    try:
        short_term_pct = float(risk_profile.get("short_term_trade_budget_pct", 0.1))
    except (TypeError, ValueError):
        pass

    errors: list[str] = []

    reserve_gap = None
    if liquidity_reserve_pct is not None:
        reserve = total_value * liquidity_reserve_pct
        if cash_available < reserve:
            reserve_gap = round(reserve - cash_available, 2)
            errors.append(
                f"Cash {cash_available:.0f} is below {liquidity_reserve_pct:.0%} "
                f"liquidity reserve ({reserve:.0f}). Gap: {reserve_gap:.0f}."
            )

    short_term_status = "ok"
    remaining_budget = None
    if short_term_pct is not None:
        short_term_budget_total = total_value * short_term_pct
        budget_used = 0.0
        if isinstance(metrics.short_term_budget, dict):
            budget_used = float(metrics.short_term_budget.get("used", 0) or 0)
        remaining_budget = round(short_term_budget_total - budget_used, 2)
        if remaining_budget < 0:
            short_term_status = "exceeded"
            errors.append(
                f"Short-term trade budget exceeded by {abs(remaining_budget):.0f}. "
                f"Reduce short-term trades or increase budget allocation."
            )
        elif short_term_pct is not None and remaining_budget < short_term_budget_total * 0.1:
            short_term_status = "near_limit"

    return {
        "cash_ratio": cash_ratio,
        "liquidity_reserve_pct": liquidity_reserve_pct,
        "reserve_gap": reserve_gap,
        "short_term_budget_status": short_term_status,
        "remaining_budget": remaining_budget,
        "errors": errors,
    }


# ── Orchestration ────────────────────────────────────────────────────────────

def run_professional_diagnostics(
    *,
    bundle: PortfolioInputBundle,
    metrics: CoreMetricsBundle,
    warnings: list[str],
) -> dict[str, Any]:
    """Run all professional diagnostic rules and return artifact-ready output.

    Args:
        bundle: Normalized input data.
        metrics: Computed core metrics.
        warnings: Existing warnings list (appended to in-place).

    Returns:
        Dict with diagnostic keys as artifacts, plus professional_warnings.
    """
    professional_warnings: list[str] = []
    diagnostics: dict[str, Any] = {}

    redemption = compute_redemption_fee_risk(bundle, metrics)
    if redemption is not None:
        diagnostics["redemption_fee_risk"] = redemption
        for item in redemption.get("affected_funds", []):
            professional_warnings.append(item.get("warning", ""))

    overlap = compute_overlap_diagnostics(bundle, metrics)
    if overlap is not None:
        diagnostics["overlap_diagnostics"] = overlap
        othemes = overlap.get("overlapping_themes", [])
        if len(othemes) >= 2:
            professional_warnings.append(
                f"Portfolio holds {len(othemes)} overlapping themes. "
                f"Highest: {overlap['summary'].get('highest_overlap_theme', 'N/A')}"
            )

    theme_over = compute_theme_overweight_diagnostics(bundle, metrics)
    if theme_over is not None:
        diagnostics["theme_overweight_diagnostics"] = theme_over
        for t in theme_over.get("overweight_themes", []):
            if t.get("excess") is not None:
                professional_warnings.append(
                    f"Theme '{t['theme']}' at {t['weight']:.1%} exceeds limit "
                    f"{t['limit']:.1%} by {t['excess']:.1%}"
                )

    dca = compute_dca_drawdown_diagnostics(bundle, metrics)
    if dca is not None:
        diagnostics["dca_drawdown_diagnostics"] = dca
        for f in dca.get("reviewed_funds", []):
            if f.get("dca_status") == "under_drawdown":
                professional_warnings.append(f.get("diagnostic", ""))

    cash = compute_cash_budget_diagnostics(bundle, metrics)
    if cash is not None:
        diagnostics["cash_budget_diagnostics"] = cash
        for err in cash.get("errors", []):
            professional_warnings.append(err)

    diagnostics["professional_warnings"] = professional_warnings

    return diagnostics
