"""Host-owned data provider contracts.

Defines normalized interfaces, config, result, and registry types for
external data adapters. This package makes NO network calls and imports
NO provider SDKs. Actual network-enabled adapters live in
examples/host_data_adapters/ or optional host-specific packages.
"""

from __future__ import annotations

from .provider_contracts import (
    FundDataProvider,
    NewsDataProvider,
    ProviderCapability,
    StockDataProvider,
)
from .provider_config import ProviderConfig, ProviderCredentials
from .provider_result import ProviderResult
from .provider_registry import ProviderRegistry

__all__ = [
    "FundDataProvider",
    "NewsDataProvider",
    "ProviderCapability",
    "ProviderConfig",
    "ProviderCredentials",
    "ProviderRegistry",
    "ProviderResult",
]
