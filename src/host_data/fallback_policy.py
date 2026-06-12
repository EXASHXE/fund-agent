"""Deterministic fallback policy for provider selection.

No network calls. Returns provider names sorted by priority,
filtered by capability and enabled status.
"""

from __future__ import annotations

from .provider_contracts import ProviderCapability
from .provider_registry import ProviderRegistry


def select_provider_order(
    capability: ProviderCapability | str,
    registry: ProviderRegistry,
    preferred: list[str] | None = None,
) -> list[str]:
    cap_str = str(capability)
    capable = registry.providers_for_capability(cap_str)
    if not capable:
        return []

    preferred_set = set(preferred or [])
    preferred_providers = [p for p in capable if p.provider_name in preferred_set]
    other_providers = [p for p in capable if p.provider_name not in preferred_set]

    result: list[str] = []
    for p in preferred_providers:
        if p.enabled and cap_str in p.capabilities:
            result.append(p.provider_name)
    for p in other_providers:
        result.append(p.provider_name)
    return result
