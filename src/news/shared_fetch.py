"""Shared AKShare fetch adapter — re-exports module-private helpers from news_fetcher.

This module exists to decouple the new pipeline from news_fetcher internals,
so that news_fetcher (old pipeline code) can be moved to deprecated/ without
breaking new pipeline imports.

All functions are thin wrappers around the original private helpers.
"""
from __future__ import annotations

from src.news.news_fetcher import (
    _cached_ak_call as _orig_cached_ak_call,
    _fetch_sina_roll_news_df as _orig_fetch_sina_roll_news_df,
    _normalize_company_name as _orig_normalize_company_name,
    _pick_first as _orig_pick_first,
)

# Re-export as public names (no underscore prefix)
cached_ak_call = _orig_cached_ak_call
fetch_sina_roll_news_df = _orig_fetch_sina_roll_news_df
normalize_company_name = _orig_normalize_company_name
pick_first = _orig_pick_first

__all__ = [
    "cached_ak_call",
    "fetch_sina_roll_news_df",
    "normalize_company_name",
    "pick_first",
]
