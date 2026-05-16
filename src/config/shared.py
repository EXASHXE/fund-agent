import os
import re as _re
from datetime import date, datetime
from typing import Optional


def today() -> date:
    """返回当前日期，支持 FUND_MOCK_DATE 环境变量注入（用于回测/重放）。"""
    mock = os.environ.get("FUND_MOCK_DATE")
    if mock:
        try:
            return datetime.strptime(mock[:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    return date.today()


def now() -> datetime:
    """返回当前时间，支持 FUND_MOCK_DATE 注入。"""
    mock = os.environ.get("FUND_MOCK_DATE")
    if mock:
        try:
            d = datetime.strptime(mock[:10], "%Y-%m-%d").date()
            return datetime(d.year, d.month, d.day, 23, 0, 0)
        except ValueError:
            pass
    return datetime.now()


def report_cutoff_hour() -> int:
    """基金净值基本完成更新后的报告截点（北京时间）。"""
    raw = os.environ.get("FUND_REPORT_CUTOFF_HOUR", "21")
    try:
        return int(raw)
    except ValueError:
        return 21


def report_cutoff_minute() -> int:
    raw = os.environ.get("FUND_REPORT_CUTOFF_MINUTE", "30")
    try:
        return int(raw)
    except ValueError:
        return 30


def effective_report_date(current: datetime = None) -> date:
    """返回应出具报告的交易日。

    交易日 21:30 前，公募基金尤其 QDII 净值通常尚未完全更新，使用上一交易日口径。
    21:30 后或非交易日，使用最近一个已完成披露的交易日。
    """
    from datetime import timedelta
    from src.engine.calendar import is_trade_day, previous_trade_day

    current = current or now()
    cutoff = current.replace(
        hour=report_cutoff_hour(),
        minute=report_cutoff_minute(),
        second=0,
        microsecond=0,
    )
    candidate = current.date()
    if is_trade_day(candidate) and current < cutoff:
        candidate = candidate - timedelta(days=1)
    return previous_trade_day(candidate)


def to_date(d) -> Optional[date]:
    if d is None:
        return None
    if isinstance(d, date):
        return d
    if isinstance(d, str):
        try:
            return datetime.strptime(str(d)[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def cleanup_bak_files(config_path: str, keep: int = 2):
    pattern = f"{config_path}.*.bak"
    files = __import__("glob").glob(pattern)
    files_with_date = []
    for f in files:
        m = _re.search(r"(\d{4}-\d{2}-\d{2})\.bak$", f)
        if m:
            files_with_date.append((m.group(1), f))
    files_with_date.sort(key=lambda x: x[0], reverse=True)
    for _, old in files_with_date[keep:]:
        try:
            os.remove(old)
        except OSError:
            pass


def fmt_date(d) -> str:
    if isinstance(d, str):
        return d
    if isinstance(d, date):
        return d.isoformat()
    return str(d)
