"""Provider health check helpers.

Deterministic, no network calls. Actual health checks are performed
by host-owned adapter implementations.
"""

from __future__ import annotations

from .provider_result import ProviderResult


def check_credentials_available(
    provider_name: str,
    capability: str,
    require_credentials: bool,
    has_credentials: bool,
) -> ProviderResult | None:
    if require_credentials and not has_credentials:
        return ProviderResult.missing_credentials(provider_name, capability)
    return None
