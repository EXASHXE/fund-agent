"""Provider capability enum and data provider protocol definitions.

This module defines interfaces only. No network calls, no provider SDKs.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol, runtime_checkable

from .provider_result import ProviderResult


class ProviderCapability(StrEnum):
    FUND_NAV_HISTORY = "FUND_NAV_HISTORY"
    FUND_PROFILE = "FUND_PROFILE"
    FUND_HOLDINGS = "FUND_HOLDINGS"
    FUND_FEE_SCHEDULE = "FUND_FEE_SCHEDULE"
    FUND_REDEMPTION_RULES = "FUND_REDEMPTION_RULES"
    FUND_RANKING = "FUND_RANKING"
    INDEX_HISTORY = "INDEX_HISTORY"
    STOCK_QUOTE = "STOCK_QUOTE"
    STOCK_HISTORY = "STOCK_HISTORY"
    MARKET_NEWS = "MARKET_NEWS"
    SOCIAL_SENTIMENT = "SOCIAL_SENTIMENT"
    SEARCH = "SEARCH"


@runtime_checkable
class FundDataProvider(Protocol):
    name: str
    capabilities: set[ProviderCapability]

    def health_check(self) -> ProviderResult: ...

    def get_fund_nav_history(self, fund_code: str, start: str, end: str) -> ProviderResult: ...

    def get_fund_profile(self, fund_code: str) -> ProviderResult: ...

    def get_fund_holdings(self, fund_code: str, as_of: str | None = None) -> ProviderResult: ...

    def get_fee_schedule(self, fund_code: str) -> ProviderResult: ...

    def get_redemption_rules(self, fund_code: str) -> ProviderResult: ...


@runtime_checkable
class StockDataProvider(Protocol):
    name: str
    capabilities: set[ProviderCapability]

    def health_check(self) -> ProviderResult: ...

    def get_stock_quote(self, symbol: str) -> ProviderResult: ...

    def get_stock_history(self, symbol: str, start: str, end: str) -> ProviderResult: ...


@runtime_checkable
class NewsDataProvider(Protocol):
    name: str
    capabilities: set[ProviderCapability]

    def health_check(self) -> ProviderResult: ...

    def search_news(self, query: str, since: str | None = None) -> ProviderResult: ...
