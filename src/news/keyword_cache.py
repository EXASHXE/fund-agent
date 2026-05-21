"""新闻关键词缓存：加载和验证缓存的基金搜索关键词。"""
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

CACHE_VERSION = "news_keyword_profiles.v1"
REQUEST_VERSION = "news_keyword_request.v1"
MAX_CACHE_AGE_DAYS = 14


def default_keyword_cache_path() -> str:
    return str(Path(__file__).resolve().parents[2] / "data" / "cache" / "news_keyword_profiles.json")


def load_valid_keyword_cache(path: str, holding_codes: List[str], today: date) -> Optional[Dict[str, Any]]:
    payload = _read_json(path)
    if not payload:
        return None

    version = payload.get("cache_version", "")
    if version != CACHE_VERSION:
        return None

    cache_codes = sorted(payload.get("holding_codes", []))
    if cache_codes != sorted(holding_codes):
        return None

    generated = _parse_date(payload.get("generated_at"))
    if generated and (today - generated).days > MAX_CACHE_AGE_DAYS:
        return None

    funds = payload.get("funds", {})
    if not funds:
        return None
    for code in holding_codes:
        entry = funds.get(code, {})
        if not entry or not entry.get("keywords"):
            return None
    return payload


def _read_json(path: str) -> Optional[Dict[str, Any]]:
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _parse_date(value) -> Optional[date]:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
