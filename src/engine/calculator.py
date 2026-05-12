"""
核心计算引擎：事件驱动状态机 + XIRR + 校准平账。

处理 BUY/CALIBRATE 事件。
净值匹配始终用 settle_delay=1（AKShare 净值日期即为有效申购净值日）。
PENDING 判断基于 fund settle_delay（1=T+1国内, 2=T+2 QDII）：若结算日尚未到达，标记为 PENDING。
校准偏差超过 3% 时拒绝并报警。
"""
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from src.engine.events import FundEvent, EventType, resolve_nav_date

CALIBRATION_MAX_DELTA_PCT = 0.03


def _settlement_date(purchase_date: date, settle_delay: int) -> date:
    """计算买入的份额确认到账日（交易日顺延）。

    国内 (settle_delay=1): T+1 交易日到账
    QDII (settle_delay=2): T+2 交易日到账

    示例：
    - 周四 QDII 买入 → 周五+1T → 周一+1T → 周二到账
    - 周五 QDII 买入 → 周一+1T → 周二+1T → 周三到账
    """
    from src.engine.calendar import next_trade_day
    result = purchase_date
    for _ in range(settle_delay):
        result = next_trade_day(result + timedelta(days=1))
    return result


def compute_fund(
    events: List[FundEvent],
    nav_map: Dict[date, float],
    fee_rate: float,
    settle_delay: int,
    today: date,
) -> Dict:
    total_shares = 0.0
    total_cost = 0.0
    cashflows: List[Tuple[date, float]] = []
    calibrations_applied = []
    calibrations_rejected = []
    events_detail = []

    sorted_nav_dates = sorted(nav_map.keys())
    last_nav_date = sorted_nav_dates[-1] if sorted_nav_dates else None
    current_nav = nav_map[last_nav_date] if last_nav_date else 1.0

    for event in events:
        if event.event_type == EventType.BUY:
            if event.amount <= 0:
                continue

            settle_date = _settlement_date(event.event_date, settle_delay)
            if settle_date >= today:
                events_detail.append({
                    "type": "BUY",
                    "status": "PENDING",
                    "purchase_date": event.event_date.isoformat(),
                    "amount": event.amount,
                    "reason": f"尚未到账 (预计 {settle_date}, sett_delay={settle_delay})",
                })
                continue

            # 净值匹配：所有基金统一用 settle_delay=1
            # AKShare 净值日期即为申购有效净值日，不受结算延迟影响
            nav_date = resolve_nav_date(event.event_date, event.after_1500, settle_delay=1)

            nav = _match_nav(nav_map, nav_date)
            if nav is None or nav <= 0:
                events_detail.append({
                    "type": "BUY",
                    "status": "SKIPPED",
                    "purchase_date": event.event_date.isoformat(),
                    "nav_date": nav_date.isoformat(),
                    "amount": event.amount,
                    "reason": f"净值日期 {nav_date} 无数据",
                })
                continue

            net_amount = event.amount / (1.0 + fee_rate)
            new_shares = round(net_amount / nav, 2)

            total_shares += new_shares
            total_cost += event.amount
            cashflows.append((event.event_date, -event.amount))

            events_detail.append({
                "type": "BUY",
                "status": "CONFIRMED",
                "purchase_date": event.event_date.isoformat(),
                "nav_date": nav_date.isoformat(),
                "settle_date": settle_date.isoformat(),
                "amount": event.amount,
                "fee_rate": fee_rate,
                "net_amount": round(net_amount, 2),
                "nav": round(nav, 4),
                "new_shares": new_shares,
                "after_1500": event.after_1500,
            })

        elif event.event_type == EventType.CALIBRATE:
            if event.actual_shares <= 0:
                continue

            delta = event.actual_shares - total_shares
            delta_pct = abs(delta) / event.actual_shares if event.actual_shares > 0 else 0

            if delta_pct > CALIBRATION_MAX_DELTA_PCT:
                calibrations_rejected.append({
                    "date": event.event_date.isoformat(),
                    "actual_shares": event.actual_shares,
                    "computed_shares": round(total_shares, 4),
                    "delta": round(delta, 4),
                    "delta_pct": round(delta_pct * 100, 2),
                    "reason": f"偏差 {delta_pct:.2%} 超过 {CALIBRATION_MAX_DELTA_PCT:.0%} 阈值，引擎计算与真实份额不符",
                })
                events_detail.append({
                    "type": "CALIBRATE",
                    "status": "REJECTED",
                    "date": event.event_date.isoformat(),
                    "actual_shares": event.actual_shares,
                    "computed_shares": round(total_shares, 4),
                    "delta": round(delta, 4),
                    "delta_pct": round(delta_pct * 100, 2),
                })
            else:
                total_shares = event.actual_shares
                calibrations_applied.append({
                    "date": event.event_date.isoformat(),
                    "actual_shares": event.actual_shares,
                    "computed_shares": round(event.actual_shares - delta, 4),
                    "delta": round(delta, 4),
                    "delta_pct": round(delta_pct * 100, 2),
                })
                events_detail.append({
                    "type": "CALIBRATE",
                    "status": "APPLIED",
                    "date": event.event_date.isoformat(),
                    "actual_shares": event.actual_shares,
                    "prev_shares": round(event.actual_shares - delta, 4),
                    "delta": round(delta, 4),
                    "delta_pct": round(delta_pct * 100, 2),
                })

    current_asset = round(total_shares * current_nav, 2)
    profit = round(current_asset - total_cost, 2)
    return_pct = round(profit / total_cost * 100, 2) if total_cost > 0 else 0.0

    xirr_val = _calc_xirr(cashflows, current_asset, today)

    return {
        "total_cost": round(total_cost, 2),
        "total_shares": round(total_shares, 2),
        "current_nav": round(current_nav, 4),
        "current_asset": current_asset,
        "profit": profit,
        "return_pct": return_pct,
        "xirr": round(xirr_val, 4),
        "cashflows": [(d.isoformat(), v) for d, v in cashflows],
        "calibrations_applied": calibrations_applied,
        "calibrations_rejected": calibrations_rejected,
        "has_calibration_error": len(calibrations_rejected) > 0,
        "events_detail": events_detail,
    }


def _match_nav(nav_map: Dict[date, float], target: date) -> Optional[float]:
    if target in nav_map:
        return nav_map[target]
    for i in range(1, 6):
        d = target + timedelta(days=i)
        if d in nav_map:
            return nav_map[d]
    for i in range(1, 4):
        d = target - timedelta(days=i)
        if d in nav_map:
            return nav_map[d]
    return None


def _calc_xirr(cashflows, current_value, today, guess=0.1):
    if not cashflows or current_value <= 0:
        return 0.0
    all_cfs = list(cashflows) + [(today, current_value)]
    has_pos = any(v > 0 for _, v in all_cfs)
    has_neg = any(v < 0 for _, v in all_cfs)
    if not (has_pos and has_neg):
        return 0.0
    rate = guess
    for _ in range(100):
        npv = 0.0
        dnpv = 0.0
        for d, v in all_cfs:
            t = (d - all_cfs[0][0]).days / 365.0
            factor = (1.0 + rate) ** (-t)
            npv += v * factor
            dnpv += -t * v * factor * (1.0 / (1.0 + rate))
        if abs(dnpv) < 1e-12:
            break
        new_rate = rate - npv / dnpv
        if abs(new_rate - rate) < 1e-8:
            rate = new_rate
            break
        rate = new_rate
    return rate if rate > -0.99 else -0.99


def compute_portfolio(fund_results: Dict[str, Dict]) -> Dict:
    total_cost = sum(r["total_cost"] for r in fund_results.values())
    total_asset = sum(r["current_asset"] for r in fund_results.values())
    total_profit = total_asset - total_cost
    total_return = round(total_profit / total_cost * 100, 2) if total_cost > 0 else 0.0
    calibration_errors = []
    for code, r in fund_results.items():
        if r.get("calibrations_rejected"):
            calibration_errors.append({"code": code, "rejected": r["calibrations_rejected"]})
    return {
        "total_cost": round(total_cost, 2),
        "total_asset": round(total_asset, 2),
        "total_profit": round(total_profit, 2),
        "total_return_pct": total_return,
        "fund_count": len(fund_results),
        "calibration_errors": calibration_errors,
    }
