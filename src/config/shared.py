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
