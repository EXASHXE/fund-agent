"""Providers facade -- stable public import path.

Exposes provider contract types only. Does NOT import example host
adapters or network clients.
"""
from __future__ import annotations

from src.host_data.fallback_policy import select_provider_order
from src.host_data.provider_config import (
    ProviderConfig,
    ProviderCredentialSpec,
    ProviderCredentials,
    resolve_credentials_from_env,
)
from src.host_data.provider_contracts import (
    FundDataProvider,
    NewsDataProvider,
    ProviderCapability,
    StockDataProvider,
)
from src.host_data.provider_registry import ProviderRegistry
from src.host_data.provider_result import ProviderResult
from src.host_data.reconciliation import compare_provider_results

__all__ = [
    "FundDataProvider",
    "NewsDataProvider",
    "ProviderCapability",
    "ProviderConfig",
    "ProviderCredentialSpec",
    "ProviderCredentials",
    "ProviderRegistry",
    "ProviderResult",
    "compare_provider_results",
    "resolve_credentials_from_env",
    "select_provider_order",
]
