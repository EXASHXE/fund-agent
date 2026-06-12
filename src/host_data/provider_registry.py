"""Provider registry — tracks available providers and their capabilities.

Deterministic, no network calls.
"""

from __future__ import annotations

from typing import Any

from .provider_config import ProviderConfig
from .provider_contracts import ProviderCapability


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, ProviderConfig] = {}

    def register(self, config: ProviderConfig) -> None:
        self._providers[config.provider_name] = config

    def get(self, provider_name: str) -> ProviderConfig | None:
        return self._providers.get(provider_name)

    def list_providers(self) -> list[str]:
        return sorted(self._providers.keys())

    def enabled_providers(self) -> list[ProviderConfig]:
        return sorted(
            [p for p in self._providers.values() if p.enabled],
            key=lambda p: p.priority,
        )

    def providers_for_capability(self, capability: ProviderCapability | str) -> list[ProviderConfig]:
        cap_str = str(capability)
        return sorted(
            [
                p for p in self._providers.values()
                if p.enabled and cap_str in p.capabilities
            ],
            key=lambda p: p.priority,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "providers": {
                name: config.to_dict() for name, config in self._providers.items()
            },
        }
