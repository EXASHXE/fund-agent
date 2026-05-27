"""Portfolio holdings computation from the transaction ledger."""

from __future__ import annotations

from datetime import date, timedelta

from src.config.shared import (
    dca_effective_date,
    effective_report_date,
    today as shared_today,
)


def compute_holdings(store, config, codes, analyzer=None):
    """Compute portfolio holdings from the transaction ledger and NAV evidence."""
    from src.engine.events import generate_events
    from src.engine.calculator import compute_fund
    from src.analysis.holdings import portfolio_summary
    from src.db.database import get_session

    session = get_session()
    report_day = effective_report_date()
    dca_today = dca_effective_date()
    settle_today = shared_today()
    analyses = []
    calibration_warnings = []

    for code in codes:
        try:
            holding_config = next((h for h in config.holdings if h.code == code), None)
            if not holding_config:
                continue

            fund = store.get_fund(code) or {
                "id": None,
                "code": code,
                "name": holding_config.name or code,
            }
            purchases = [
                {
                    "date": p.date,
                    "amount": p.amount,
                    "nav": p.nav,
                    "after_1500": p.after_1500,
                }
                for p in holding_config.purchases
            ]

            dca_strategy = None
            if holding_config and holding_config.dca and holding_config.dca.enabled:
                dca = holding_config.dca
                dca_strategy = {
                    "enabled": True,
                    "frequency": dca.frequency.value,
                    "amount": dca.amount,
                    "start_date": dca.start_date,
                    "day_of_week": dca.day_of_week,
                }

            configured_fee_rate = getattr(holding_config, "fee_rate", None)
            fee_rate = float(0.0015 if configured_fee_rate is None else configured_fee_rate)
            configured_settle_delay = getattr(holding_config, "settle_delay", None)
            settle_delay = int(1 if configured_settle_delay is None else configured_settle_delay)

            calibrations = []
            if holding_config and hasattr(holding_config, "calibrations"):
                for calibration in holding_config.calibrations:
                    calibrations.append({
                        "date": calibration.cal_date,
                        "actual_shares": calibration.actual_shares,
                    })

            nav_map = {}
            current_nav = 1.0
            last_nav_date = None
            if analyzer and code in analyzer.funds:
                nav_df = analyzer.funds[code].get("nav")
                if nav_df is not None and hasattr(nav_df, "iterrows") and len(nav_df) > 0:
                    for idx, row in nav_df.iterrows():
                        day = idx.date() if hasattr(idx, "date") else idx
                        nav_val = float(row.get("单位净值", 0))
                        if nav_val:
                            nav_map[day] = nav_val
                    if nav_map:
                        last_nav_date = max(nav_map.keys())
                        current_nav = nav_map[last_nav_date]

            if not nav_map:
                from src.db.database import get_nav_history

                if fund.get("id"):
                    nav_list = get_nav_history(session, fund["id"])
                    for nav in nav_list:
                        nav_map[nav.date] = float(nav.nav)
                    if nav_map:
                        last_nav_date = max(nav_map.keys())
                        current_nav = nav_map[last_nav_date]

            events = generate_events(purchases, dca_strategy, calibrations, dca_today)
            result = compute_fund(events, nav_map, fee_rate, settle_delay, settle_today)

            display_value = result["current_asset"]
            display_profit = result["confirmed_pnl"]
            display_return_pct = result["confirmed_return_pct"]
            purchase_amount = round(sum(float(p.get("amount", 0) or 0) for p in purchases), 2)
            total_cost = result["total_cost"]
            total_shares = result["total_shares"]
            avg_cost = result["avg_cost"]
            pending_amount = result["pending_amount"]

            week_start_nav = _match_nav_on_or_before(nav_map, report_day - timedelta(days=7))
            week_start_value = round(total_shares * week_start_nav, 2) if week_start_nav else None
            week_profit = round(display_value - week_start_value, 2) if week_start_value else None
            week_return_pct = round(week_profit / week_start_value * 100, 2) if week_start_value else None

            day_profit = None
            day_return_pct = None
            if nav_map and last_nav_date:
                previous_nav_dates = [day for day in nav_map.keys() if day < last_nav_date]
                if previous_nav_dates:
                    previous_nav = nav_map[max(previous_nav_dates)]
                    previous_value = round(total_shares * previous_nav, 2)
                    day_profit = round(display_value - previous_value, 2)
                    day_return_pct = round(day_profit / previous_value * 100, 2) if previous_value else None

            dca_records = _simulate_dca_for_report(dca_strategy, nav_map, report_day) if dca_strategy else []

            if result.get("has_calibration_error"):
                for rejected in result.get("calibrations_rejected", []):
                    print(
                        f"  [CALIB WARN] {code}: {rejected['reason']} "
                        f"(计算={rejected['computed_shares']}, 真实={rejected['actual_shares']}, "
                        f"偏差={rejected['delta_pct']}%)"
                    )
                    calibration_warnings.append({
                        "code": code,
                        "name": fund.get("name", code),
                        "rejected": rejected,
                    })

            analyses.append({
                "fund_code": code,
                "fund_name": fund.get("name", code),
                "total_cost": total_cost,
                "total_shares": total_shares,
                "simulated_shares": result["total_shares"],
                "current_nav": result["current_nav"],
                "nav_date": max(nav_map.keys()).isoformat() if nav_map else None,
                "current_value": display_value,
                "profit": display_profit,
                "return_pct": display_return_pct,
                "portfolio_pnl": result["portfolio_pnl"],
                "annual_return": round(result["xirr"] * 100, 1),
                "avg_cost": avg_cost,
                "pending_amount": round(pending_amount, 2),
                "purchase_amount": purchase_amount,
                "week_start_value": week_start_value,
                "week_profit": week_profit,
                "week_return_pct": week_return_pct,
                "day_profit": day_profit,
                "day_return_pct": day_return_pct,
                "dca_records": dca_records,
                "dca_enabled": bool(dca_strategy),
                "dca_avg_cost": 0.0,
                "nav_trend": [],
                "value_trend": [],
                "engine_events": result["events_detail"],
                "calibrations_applied": result["calibrations_applied"],
                "calibrations_rejected": result.get("calibrations_rejected", []),
                "xirr": result["xirr"],
                "settle_delay": settle_delay,
                "fund_type": getattr(holding_config, "type", ""),
                "days_held": (
                    report_day - min(p["date"] for p in purchases if p.get("date"))
                ).days if purchases else 0,
            })

        except Exception as exc:
            print(f"  [WARN] {code} 持仓分析失败: {exc}")

    result = portfolio_summary(analyses)
    if calibration_warnings:
        result["calibration_warnings"] = calibration_warnings
    return result


def _match_nav_on_or_before(nav_map: dict, target: date):
    if not nav_map:
        return None
    candidates = [day for day in nav_map.keys() if day <= target]
    if not candidates:
        return None
    return nav_map[max(candidates)]


def _simulate_dca_for_report(dca_strategy: dict, nav_map: dict, today) -> list:
    from src.engine.events import _generate_dca_dates

    records = []
    dca_start = dca_strategy.get("start_date")
    if not dca_start:
        return records
    dates = _generate_dca_dates(
        dca_start, today,
        dca_strategy.get("frequency", "weekly"),
        dca_strategy.get("day_of_week"),
    )
    cum_shares = 0.0
    prev_value = 0.0
    period = 0
    fee = dca_strategy.get("fee_rate", 0.0015)

    for day in dates:
        nav = _match_nav_from_map(nav_map, day)
        if not nav:
            continue
        net = dca_strategy["amount"] / (1 + fee)
        shares = round(net / nav, 4)
        cum_shares += shares
        current_value = round(cum_shares * nav, 2)
        period_return = "N/A"
        if period > 0 and prev_value > 0:
            period_return = f"{(current_value - prev_value) / prev_value * 100:+.1f}%"
        records.append({
            "date": day, "amount": dca_strategy["amount"],
            "nav": round(nav, 4), "shares": shares,
            "cum_shares": round(cum_shares, 4),
            "period_return": period_return,
        })
        prev_value = current_value
        period += 1
    return records


def _match_nav_from_map(nav_map: dict, target) -> float:
    day = target.date() if hasattr(target, "date") else target
    if day in nav_map:
        return nav_map[day]
    for offset in range(1, 6):
        next_day = day + timedelta(days=offset)
        if next_day in nav_map:
            return nav_map[next_day]
    for offset in range(1, 4):
        previous_day = day - timedelta(days=offset)
        if previous_day in nav_map:
            return nav_map[previous_day]
    return None
