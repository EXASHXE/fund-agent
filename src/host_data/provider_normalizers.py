"""Provider data normalizers.

Normalize raw provider responses into consistent shapes.
Deterministic, no network calls.
"""

from __future__ import annotations

from typing import Any


def normalize_nav_history(raw: list[dict] | dict | None, provider: str) -> dict[str, Any]:
    if not raw:
        return {"nav_points": [], "warnings": ["EMPTY_RESULT"]}
    if isinstance(raw, dict):
        items = raw.get("data", raw.get("items", []))
    else:
        items = raw
    if not isinstance(items, list):
        return {"nav_points": [], "warnings": ["UNEXPECTED_FORMAT"]}
    nav_points: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            nav_points.append({
                "date": item.get("date", item.get("nav_date", "")),
                "nav": item.get("nav", item.get("unit_nav", item.get("dwjz", 0))),
                "acc_nav": item.get("acc_nav", item.get("ljjz", None)),
            })
    return {"nav_points": nav_points, "warnings": []}


def normalize_fund_profile(raw: dict | None, provider: str) -> dict[str, Any]:
    if not raw:
        return {"profile": {}, "warnings": ["EMPTY_RESULT"]}
    if isinstance(raw, dict):
        return {
            "profile": {
                "fund_code": raw.get("fund_code", raw.get("code", "")),
                "fund_name": raw.get("fund_name", raw.get("name", "")),
                "fund_type": raw.get("fund_type", raw.get("type", "")),
                "inception_date": raw.get("inception_date", raw.get("establish_date", "")),
                "manager": raw.get("manager", raw.get("fund_manager", "")),
            },
            "warnings": [],
        }
    return {"profile": {}, "warnings": ["UNEXPECTED_FORMAT"]}


def normalize_stock_quote(raw: dict | None, provider: str) -> dict[str, Any]:
    if not raw:
        return {"quote": {}, "warnings": ["EMPTY_RESULT"]}
    if isinstance(raw, dict):
        return {
            "quote": {
                "symbol": raw.get("symbol", raw.get("code", "")),
                "name": raw.get("name", ""),
                "price": raw.get("price", raw.get("current", raw.get("close", 0))),
                "change_pct": raw.get("change_pct", raw.get("changepercent", None)),
                "volume": raw.get("volume", raw.get("vol", None)),
            },
            "warnings": [],
        }
    return {"quote": {}, "warnings": ["UNEXPECTED_FORMAT"]}
