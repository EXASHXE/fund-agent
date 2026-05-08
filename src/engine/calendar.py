"""
交易日历模块：基于 AKShare 获取 A 股有效交易日，缓存 2 小时。
"""
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Set


def _fetch_trade_dates() -> Set[date]:
    """从 AKShare 拉取全量交易日历。"""
    try:
        import akshare as ak
        import pandas as pd
        df = ak.tool_trade_date_hist_sina()
        dates = set()
        for _, row in df.iterrows():
            d = row["trade_date"]
            if isinstance(d, str):
                d = datetime.strptime(d[:10], "%Y-%m-%d").date()
            elif isinstance(d, pd.Timestamp):
                d = d.date()
            elif isinstance(d, date):
                pass
            else:
                continue
            dates.add(d)
        return dates
    except Exception:
        return set()


_trade_dates_cache: Set[date] = None
_cache_time: datetime = None
_CACHE_TTL = 7200  # 2 小时


def get_trade_calendar() -> Set[date]:
    """获取交易日集合（带缓存）。"""
    global _trade_dates_cache, _cache_time
    now = datetime.now()
    if _trade_dates_cache is None or _cache_time is None or (now - _cache_time).total_seconds() > _CACHE_TTL:
        _trade_dates_cache = _fetch_trade_dates()
        _cache_time = now
    return _trade_dates_cache


def is_trade_day(d: date) -> bool:
    """判断是否为 A 股交易日。"""
    return d in get_trade_calendar()


def next_trade_day(d: date) -> date:
    """返回 d 当天或之后第一个交易日（含当日）。"""
    cal = get_trade_calendar()
    cursor = d
    while cursor not in cal:
        cursor += timedelta(days=1)
    return cursor
