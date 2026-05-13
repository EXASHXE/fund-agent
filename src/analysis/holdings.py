"""
持仓分析模块：单基金收益/趋势/定投明细 + 组合汇总。

依赖数据库中的 FundHolding（买入记录）、FundDCA（定投策略）、FundNAV（净值历史）。

手续费率：0.15%（按购买金额计算，买入时扣除）
"""
import pandas as pd
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

FEE_RATE = 0.0015  # 0.15% 购买手续费

# 基金代码 → 跟踪指数映射（用于净值估算）
_TRACK_INDEX_MAP = {
    "008253": ".IXIC",   # 华宝致远混合 → 纳斯达克
    "017436": ".IXIC",   # 华宝纳斯达克精选 → 纳斯达克
    "378006": ".IXIC",   # 摩根全球新兴市场 → 近似用纳斯达克
    "001198": "sh000300",  # 东方惠灵活配置 → 沪深300
    "018380": "sh000300",  # 新能源车电池 → 近似用沪深300
    "021620": ".IXIC",   # 石油天然气 → 近似用纳斯达克
}

# 基金跟踪敏感度（beta）：估值时对指数变动的缩放系数
# < 1.0 表示基金波动小于指数（含费率拖累、汇率影响）
_TRACK_BETA_MAP = {
    "008253": 0.60,    # 华宝致远混合 — QDII 主动管理，费率/汇率拖累大
    "017436": 0.70,    # 华宝纳斯达克精选 — 高度跟踪纳斯达克但含汇率折损
    "378006": 0.65,    # 摩根新兴市场 — 与纳斯达克相关度偏低
    "001198": 1.00,    # 东方惠灵活配置 — A股灵活配置
    "018380": 1.05,    # 新能源电池ETF — 行业弹性更高
    "021620": 0.50,    # 石油天然气 — 商品属性，与股指相关性极弱
}


def _fetch_index_latest(symbol: str) -> Optional[float]:
    """获取指数最新收盘价。"""
    try:
        import akshare as ak
        if symbol.startswith(".IXIC"):
            df = ak.index_us_stock_sina(symbol=symbol)
            if len(df) > 0:
                return float(df.iloc[-1]["close"])
        elif symbol.startswith("sh") or symbol.startswith("sz"):
            df = ak.stock_zh_index_daily(symbol=symbol)
            if len(df) > 0:
                return float(df.iloc[-1]["close"])
    except Exception:
        pass
    return None


def _get_index_close_on(symbol: str, target: date) -> Optional[float]:
    """获取指数在指定日期的收盘价（向前查找最近交易日）。"""
    try:
        import akshare as ak
        target_str = target.isoformat()
        if symbol.startswith(".IXIC"):
            df = ak.index_us_stock_sina(symbol=symbol)
            df["date"] = pd.to_datetime(df["date"])
            match = df[df["date"] <= target_str]
            if len(match) > 0:
                return float(match.iloc[-1]["close"])
        elif symbol.startswith("sh") or symbol.startswith("sz"):
            df = ak.stock_zh_index_daily(symbol=symbol)
            df["date"] = pd.to_datetime(df["date"])
            match = df[df["date"] <= target_str]
            if len(match) > 0:
                return float(match.iloc[-1]["close"])
    except Exception:
        pass
    return None


def estimate_current_nav(fund_code: str, last_nav: float,
                         last_nav_date: date, target_date: date) -> Optional[float]:
    """估算基金在 target_date 的最新净值。

    当 AKShare 净值数据滞后（如 QDII T+2 延迟、节假日），
    使用基金跟踪指数的涨跌幅来估算最新净值。
    返回估算净值，若无法估算则返回 None。
    """
    index_symbol = _TRACK_INDEX_MAP.get(fund_code)
    if not index_symbol:
        return None
    if not last_nav or last_nav <= 0 or not last_nav_date:
        return None

    try:
        import pandas as pd
        base_close = _get_index_close_on(index_symbol, last_nav_date)
        latest_close = _get_index_close_on(index_symbol, target_date)
        if base_close and latest_close and base_close > 0:
            beta = _TRACK_BETA_MAP.get(fund_code, 1.0)
            index_change = latest_close / base_close
            scaled_change = 1.0 + (index_change - 1.0) * beta
            return round(last_nav * scaled_change, 4)
    except Exception:
        pass
    return None


def calc_xirr(cashflows: List[Tuple[date, float]],
              current_value: float,
              current_date: date) -> float:
    """XIRR 年化收益率计算（牛顿迭代法，不依赖 scipy）。"""
    if len(cashflows) < 2:
        return 0.0

    all_flows = list(cashflows) + [(current_date, current_value)]
    dates = [d for d, _ in all_flows]
    amounts = [a for _, a in all_flows]

    base_date = dates[0]
    days = [(d - base_date).days for d in dates]

    def npv(rate):
        total = 0.0
        for i, amt in enumerate(amounts):
            total += amt / ((1 + rate) ** (days[i] / 365.0))
        return total

    def npv_deriv(rate):
        total = 0.0
        for i, amt in enumerate(amounts):
            t = days[i] / 365.0
            total -= amt * t / ((1 + rate) ** (t + 1))
        return total

    # Newton's method
    rate = 0.1
    for _ in range(100):
        f = npv(rate)
        df = npv_deriv(rate)
        if abs(df) < 1e-12:
            break
        new_rate = rate - f / df
        if abs(new_rate - rate) < 1e-8:
            return new_rate
        rate = new_rate
        if rate < -0.99:
            rate = -0.5
        elif rate > 10.0:
            rate = 5.0

    return rate if -0.99 < rate < 10.0 else 0.0


def _to_date(d) -> date:
    """安全转换为 date 对象。"""
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


def _find_closest_nav(nav_records: List[Dict], target_date: date, max_window: int = 5) -> Optional[float]:
    """在净值记录中查找与申购日期最匹配的净值。

    基金申购净值确认规则：
    - 境内基金 T 日 15:00 前申购 → T 日净值；15:00 后 → T+1 日净值
    - QDII 基金 → 通常 T+1 或 T+2 日净值
    - 由于无法获知具体下单时间，优先匹配当日(N+0)，其次前瞻 N+1/N+2，
      若前瞻窗口内无数据（节假日/数据缺失），则退回到最近可用净值。

    排序优先级：(diff >= 0 优先于 diff < 0) 且 abs(diff) 越小越优先。
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


def _is_business_day(d: date) -> bool:
    """判断是否为交易日（简化：排除周六日）。"""
    return d.weekday() < 5


def _next_business_day(d: date) -> date:
    """获取下一个交易日。"""
    nxt = d + timedelta(days=1)
    while not _is_business_day(nxt):
        nxt += timedelta(days=1)
    return nxt


def _next_dca_date(current: date, frequency: str, day_of_week: str = None) -> date:
    """计算下一个定投日期。"""
    if frequency == "daily":
        nxt = current + timedelta(days=1)
        while not _is_business_day(nxt):
            nxt += timedelta(days=1)
        return nxt
    elif frequency == "weekly":
        if day_of_week:
            dow_map = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4}
            target_dow = dow_map.get(day_of_week, current.weekday())
            nxt = current + timedelta(days=7)
            days_ahead = target_dow - nxt.weekday()
            if days_ahead < 0:
                days_ahead += 7
            nxt = nxt + timedelta(days=days_ahead)
        else:
            nxt = current + timedelta(days=7)
        return nxt
    elif frequency == "biweekly":
        nxt = current + timedelta(days=14)
        while not _is_business_day(nxt):
            nxt += timedelta(days=1)
        return nxt
    elif frequency == "monthly":
        nxt = current + timedelta(days=30)
        while not _is_business_day(nxt):
            nxt += timedelta(days=1)
        return nxt
    else:
        return current + timedelta(days=7)


def _simulate_dca(
    start_date: date,
    end_date: date,
    amount: float,
    frequency: str,
    nav_records: List[Dict],
    day_of_week: str = None,
) -> List[Dict]:
    """模拟定投执行记录，跳过非交易日。"""
    records = []
    current = start_date
    # 如果起始日不是交易日，跳到下一个
    if not _is_business_day(current):
        current = _next_business_day(current)
    if current > end_date:
        return records

    cum_shares = 0.0
    prev_value = 0.0
    period = 0

    while current <= end_date:
        nav = _find_closest_nav(nav_records, current)
        if nav and nav > 0:
            net_amt = amount * (1 - FEE_RATE)
            shares = net_amt / nav
            cum_shares += shares
            current_value = cum_shares * nav

            period_return = "N/A"
            if period > 0 and prev_value > 0:
                period_return = f"{(current_value - prev_value) / prev_value * 100:+.1f}%"

            records.append({
                "date": current,
                "amount": amount,
                "net_amount": round(amount * (1 - FEE_RATE), 2),
                "fee": round(amount * FEE_RATE, 2),
                "nav": round(nav, 4),
                "shares": round(shares, 4),
                "cum_shares": round(cum_shares, 4),
                "period_return": period_return,
            })
            prev_value = current_value

        current = _next_dca_date(current, frequency, day_of_week)
        period += 1

    return records


def analyze_holding(
    fund_code: str,
    fund_name: str,
    purchases: List[Dict],
    dca_strategy: Optional[Dict],
    nav_records: List[Dict],
    current_nav: float,
    current_date: date,
) -> Dict:
    """单基金持仓分析。"""
    result = {
        "fund_code": fund_code,
        "fund_name": fund_name,
        "total_cost": 0.0,
        "total_shares": 0.0,
        "current_value": 0.0,
        "profit": 0.0,
        "return_pct": 0.0,
        "annual_return": 0.0,
        "dca_records": [],
        "dca_enabled": False,
        "dca_avg_cost": 0.0,
        "nav_trend": [],
        "value_trend": [],
    }

    cost = 0.0
    shares = 0.0
    cashflows = []

    # 最新净值日期（后续购买如无匹配净值则跳过，避免用过期净值估算当日买入）
    max_nav_date = None
    for r in nav_records:
        d = _to_date(r.get("date"))
        if d and (max_nav_date is None or d > max_nav_date):
            max_nav_date = d

    # 处理手动买入（含手续费）
    for p in purchases:
        amt = p.get("amount", 0)
        buy_date = _to_date(p.get("date"))
        if not buy_date:
            continue
        # 跳过净值数据覆盖不到的近期买入（如 QDII T+2 延迟期间的 DCA）
        if max_nav_date and buy_date > max_nav_date:
            continue
        net_amt = amt * (1 - FEE_RATE)  # 扣除手续费后的净申购额
        nav = p.get("nav")
        if nav and nav > 0:
            s = net_amt / nav
        else:
            nav = _find_closest_nav(nav_records, buy_date)
            s = net_amt / nav if nav else 0

        cost += amt  # 总成本包含手续费
        shares += s
        cashflows.append((buy_date, -amt))

    # 处理定投
    if dca_strategy and dca_strategy.get("enabled"):
        dca_amount = dca_strategy.get("amount", 0)
        dca_freq = dca_strategy.get("frequency", "weekly")
        dca_start = dca_strategy.get("start_date")
        dca_dow = dca_strategy.get("day_of_week")

        if dca_amount and dca_start and dca_freq:
            result["dca_enabled"] = True
            sim_records = _simulate_dca(
                dca_start, current_date, dca_amount, dca_freq,
                nav_records, dca_dow
            )
            for rec in sim_records:
                cost += rec["amount"]  # 含手续费
                shares += rec["shares"]  # net_amt/nav 已计算
                d = _to_date(rec["date"])
                cashflows.append((d, -rec["amount"]))
            result["dca_records"] = sim_records

    result["total_cost"] = round(cost, 2)
    result["total_shares"] = round(shares, 4)
    result["current_value"] = round(shares * current_nav, 2)
    result["profit"] = round(result["current_value"] - cost, 2)
    result["return_pct"] = round(
        (result["profit"] / cost * 100) if cost > 0 else 0, 2
    )
    result["annual_return"] = round(
        calc_xirr(cashflows, result["current_value"], current_date) * 100, 2
    )

    # 定投平均成本
    dca_records = result["dca_records"]
    if dca_records:
        total_dca_cost = sum(r["amount"] for r in dca_records)
        total_dca_shares = sum(r["shares"] for r in dca_records)
        result["dca_avg_cost"] = round(
            total_dca_cost / total_dca_shares if total_dca_shares else 0, 4
        )

    # 净值/价值趋势（最近 90 天）
    cutoff = current_date - timedelta(days=90)
    for rec in nav_records:
        d = _to_date(rec.get("date"))
        nav_val = rec.get("nav", 0)
        if d and d >= cutoff and nav_val:
            result["nav_trend"].append((d, nav_val))
            result["value_trend"].append((d, round(shares * nav_val, 2)))

    return result


def portfolio_summary(holding_analyses: List[Dict]) -> Dict:
    """组合汇总。"""
    total_cost = sum(h["total_cost"] for h in holding_analyses)
    total_value = sum(h["current_value"] for h in holding_analyses)
    total_profit = total_value - total_cost
    total_pending = sum(h.get("pending_amount", 0) for h in holding_analyses)

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
        "fund_count": len(holding_analyses),
        "funds": funds,
        "by_fund": {h["fund_code"]: h for h in holding_analyses},
    }
