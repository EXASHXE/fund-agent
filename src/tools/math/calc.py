"""Pure math/calculation functions extracted from src/analysis/ and src/engine/.

Extracted from:
  - src/analysis/holdings.py  -> calc_xirr, compute_hhi, _parse_weight_pct,
                                 _find_closest_nav, portfolio_summary
  - src/engine/calculator.py  -> _match_nav, _calc_xirr, compute_portfolio

All functions are PURE: zero IO, zero network, zero LLM calls.

NOTE: calc_xirr (from holdings.py) and _calc_xirr (from calculator.py) now
both delegate to the canonical xirr() in src.tools.math.xirr.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from src.tools.math.xirr import xirr


# ====================================================================
# From src/analysis/holdings.py
# ====================================================================


def _to_date(d):
    """Safely convert input to a date object."""
    if d is None:
        return None
    if isinstance(d, date):
        return d
    if isinstance(d, str):
        try:
            from datetime import datetime
            return datetime.strptime(str(d)[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def calc_xirr(
    cashflows: List[Tuple[date, float]],
    current_value: float,
    current_date: date,
) -> float:
    """XIRR 年化收益率计算（牛顿迭代法，不依赖 scipy）。

    Delegates to the canonical :func:`xirr` in ``src.tools.math.xirr``.

    Pure Newton's method — no IO, no network, no LLM.
    """
    return xirr(cashflows, current_value, current_date)


def compute_hhi(holdings_df: Any) -> Optional[float]:
    """计算赫芬达尔-赫施曼指数（HHI）。

    HHI = sum((weight_i * 100)^2) for top 10 holdings.
    范围: 0（完全分散）~ 10000（完全集中）。
    > 2500 = 高度集中，< 1500 = 分散。

    Pure pandas — no IO, no network, no LLM.
    """
    if holdings_df is None or getattr(holdings_df, "empty", True):
        return None
    try:
        hhi = 0.0
        for _, row in holdings_df.head(10).iterrows():
            weight_col = None
            for col in ["占净值比例", "持仓占比", "占比", "持股占比"]:
                if col in row and row.get(col) is not None:
                    weight_col = col
                    break
            if weight_col:
                w = _parse_weight_pct(row[weight_col])
                if w is not None:
                    hhi += w ** 2
        return round(hhi, 2)
    except Exception:
        return None


def _parse_weight_pct(value: Any) -> Optional[float]:
    """Parse holding weight into percentage points for HHI calculation.

    Pure string/float parsing — no IO, no network, no LLM.
    """
    raw_str = str(value).strip()
    had_percent = raw_str.endswith("%")
    raw = raw_str.replace("%", "")
    try:
        if not raw or raw.lower() in {"nan", "none", "null"}:
            return None
        weight = float(raw)
    except (TypeError, ValueError):
        return None
    # Only scale raw decimals (e.g. 0.025 → 2.5%), skip values already in % form
    if not had_percent and 0 < weight <= 1:
        return weight * 100
    return weight


def _find_closest_nav(
    nav_records: List[Dict],
    target_date: date,
    max_window: int = 5,
) -> Optional[float]:
    """在净值记录中查找与申购日期最匹配的净值。

    基金申购净值确认规则：
    - 境内基金 T 日 15:00 前申购 -> T 日净值；15:00 后 -> T+1 日净值
    - QDII 基金 -> 通常 T+1 或 T+2 日净值
    - 由于无法获知具体下单时间，优先匹配当日(N+0)，其次前瞻 N+1/N+2，
       若前瞻窗口内无数据（节假日/数据缺失），则退回到最近可用净值。

    排序优先级：(diff >= 0 优先于 diff < 0) 且 abs(diff) 越小越优先。

    Pure search logic — no IO, no network, no LLM.
    """
    if not nav_records or target_date is None:
        return None

    target = _to_date(target_date)
    if target is None:
        return None

    matches = []
    for rec in nav_records:
        d = _to_date(rec.get("date"))
        nav_val = rec.get("nav", 0)
        if d and nav_val:
            diff = (d - target).days
            if abs(diff) <= max_window:
                matches.append((diff, nav_val))

    if not matches:
        return None

    matches.sort(key=lambda x: (0 if x[0] >= 0 else 1, abs(x[0])))
    return matches[0][1]


def portfolio_summary(holding_analyses: List[Dict]) -> Dict:
    """组合汇总。

    Pure aggregation — no IO, no network, no LLM.
    """
    total_cost = sum(h["total_cost"] for h in holding_analyses)
    total_value = sum(h["current_value"] for h in holding_analyses)
    total_profit = total_value - total_cost
    total_pending = sum(h.get("pending_amount", 0) for h in holding_analyses)

    total_day_profit = sum(h.get("day_profit") or 0.0 for h in holding_analyses)
    prev_total_value = sum(
        (h["current_value"] - (h.get("day_profit") or 0.0))
        for h in holding_analyses
    )
    total_day_return_pct = (
        round(total_day_profit / prev_total_value * 100, 2)
        if prev_total_value > 0
        else 0.0
    )

    funds = []
    for h in holding_analyses:
        dca_status = "启用中" if (h.get("dca_records") or h.get("dca_enabled")) else "未设置"
        funds.append({
            "code": h["fund_code"],
            "name": h["fund_name"],
            "value": h["current_value"],
            "cost": h["total_cost"],
            "profit": h["profit"],
            "return_pct": h["return_pct"],
            "week_profit": h.get("week_profit"),
            "week_return_pct": h.get("week_return_pct"),
            "day_profit": h.get("day_profit"),
            "day_return_pct": h.get("day_return_pct"),
            "annual_return": h["annual_return"],
            "avg_cost": h.get("avg_cost", 0),
            "pending_amount": h.get("pending_amount", 0),
            "dca_status": dca_status,
        })

    return {
        "total_value": total_value,
        "total_cost": total_cost,
        "total_profit": total_profit,
        "total_pending": round(total_pending, 2),
        "total_return_pct": round(total_profit / total_cost * 100, 2) if total_cost else 0,
        "total_day_profit": round(total_day_profit, 2),
        "total_day_return_pct": total_day_return_pct,
        "fund_count": len(holding_analyses),
        "funds": funds,
        "by_fund": {h["fund_code"]: h for h in holding_analyses},
    }


# ====================================================================
# From src/engine/calculator.py
# ====================================================================


def _match_nav(
    nav_map: Dict[date, float],
    target: date,
    today: Optional[date] = None,
) -> Optional[float]:
    """Match NAV from nav_map, with forward/backward search windows.

    Pure dict lookup — no IO, no network, no LLM.
    """
    if target in nav_map:
        return nav_map[target]
    for i in range(1, 6):
        d = target + timedelta(days=i)
        if d in nav_map:
            return nav_map[d]
    if today and (today - target).days <= 3:
        return None
    for i in range(1, 4):
        d = target - timedelta(days=i)
        if d in nav_map:
            return nav_map[d]
    return None


def _calc_xirr(cashflows, current_value, today, guess=0.1):
    """XIRR via Newton's method (delegates to canonical xirr()).

    NOTE: This previously duplicated calc_xirr.  Both now delegate to
    the unified :func:`xirr` in ``src.tools.math.xirr``.

    Pure Newton's method — no IO, no network, no LLM.
    """
    return xirr(cashflows, current_value, current_date=today, guess=guess)


def compute_portfolio(fund_results: Dict[str, Dict]) -> Dict:
    """Aggregate fund results into portfolio-level summary.

    Pure aggregation — no IO, no network, no LLM.
    """
    total_cost = sum(r["total_cost"] for r in fund_results.values())
    total_asset = sum(r["current_asset"] for r in fund_results.values())
    total_profit = total_asset - total_cost
    total_return = round(total_profit / total_cost * 100, 2) if total_cost > 0 else 0.0
    total_pending = sum(r["pending_amount"] for r in fund_results.values())
    calibration_errors = []
    for code, r in fund_results.items():
        if r.get("calibrations_rejected"):
            calibration_errors.append({"code": code, "rejected": r["calibrations_rejected"]})
    return {
        "total_cost": round(total_cost, 2),
        "total_asset": round(total_asset, 2),
        "total_profit": round(total_profit, 2),
        "total_return_pct": total_return,
        "total_pending": round(total_pending, 2),
        "fund_count": len(fund_results),
        "calibration_errors": calibration_errors,
    }
