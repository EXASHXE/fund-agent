"""Provider contracts for fund universe, NAV, and profile — M7.20.

Defines abstract interfaces (Protocols) for fund data providers.
Core code must depend on these contracts, not on concrete implementations.
Concrete providers are injected at the orchestration boundary.

Key rules:
- Core never imports online provider implementations.
- Provider failures must not crash analysis; fallback to local cache.
- Fuzzy top-1 results from any provider must NOT auto-verify.
- Multi-source same code/full_name can boost confidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


# ── Provider diagnostics ─────────────────────────────────────────────────

@dataclass
class ProviderDiagnostics:
    """Standard diagnostics for any fund data provider."""

    provider_name: str = ""
    loaded: bool = False
    request_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    last_error_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "loaded": self.loaded,
            "request_count": self.request_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "last_error_type": self.last_error_type,
        }

    def record_success(self) -> None:
        self.request_count += 1
        self.success_count += 1

    def record_failure(self, error_type: str = "") -> None:
        self.request_count += 1
        self.failure_count += 1
        if error_type:
            self.last_error_type = error_type


# ── Fund Universe Provider ───────────────────────────────────────────────

@runtime_checkable
class FundUniverseProvider(Protocol):
    """Protocol for fund universe data providers.

    Provides fund name → code lookup from a universe of known funds.
    """

    def lookup_by_name(self, name: str) -> list[dict[str, Any]]:
        """Look up fund entries by name.

        Returns list of dicts with at least: fund_code, fund_name, source.
        """
        ...

    def get_diagnostics(self) -> ProviderDiagnostics:
        """Return provider diagnostics."""
        ...


# ── NAV Provider ─────────────────────────────────────────────────────────

@runtime_checkable
class NAVProvider(Protocol):
    """Protocol for NAV (Net Asset Value) data providers.

    Provides historical and latest NAV data for a given fund code.
    """

    def get_latest_nav(self, fund_code: str) -> dict[str, Any] | None:
        """Get the latest NAV for a fund.

        Returns dict with: nav, nav_date, source. None if unavailable.
        """
        ...

    def get_trade_date_nav(self, fund_code: str, trade_date: str) -> dict[str, Any] | None:
        """Get NAV for a specific trade date.

        Returns dict with: nav, nav_date, source. None if unavailable.
        """
        ...

    def get_diagnostics(self) -> ProviderDiagnostics:
        """Return provider diagnostics."""
        ...


# ── Fund Profile Provider ────────────────────────────────────────────────

@runtime_checkable
class FundProfileProvider(Protocol):
    """Protocol for fund profile data providers.

    Provides fund metadata (type, manager, inception date, etc.).
    """

    def get_profile(self, fund_code: str) -> dict[str, Any] | None:
        """Get fund profile information.

        Returns dict with at least: fund_code, fund_type, source. None if unavailable.
        """
        ...

    def get_diagnostics(self) -> ProviderDiagnostics:
        """Return provider diagnostics."""
        ...


# ── Multi-source confidence boost ────────────────────────────────────────

def compute_multisource_confidence(
    sources: list[dict[str, Any]],
) -> str:
    """Compute confidence level when multiple sources agree.

    Rules:
    - 1 source with exact match → high
    - 2+ sources with same code → high (boosted)
    - 1 source with fuzzy match → medium
    - 0 sources → low

    Multi-source agreement on same code can boost confidence from medium to high,
    but fuzzy top-1 from any single source must NOT auto-verify.
    """
    if not sources:
        return "low"

    # Check for exact matches
    exact_matches = [s for s in sources if s.get("match_type") == "exact"]
    if exact_matches:
        # Multiple exact matches from different sources → boosted
        exact_codes = set(s.get("fund_code") for s in exact_matches if s.get("fund_code"))
        if len(exact_codes) >= 2:
            return "high_boosted"
        if len(exact_matches) >= 2:
            return "high_boosted"
        return "high"

    # Check for fuzzy matches
    fuzzy_matches = [s for s in sources if s.get("match_type") == "fuzzy"]
    if fuzzy_matches:
        # Multiple fuzzy matches agreeing on same code → medium (not auto-verify)
        fuzzy_codes = set(s.get("fund_code") for s in fuzzy_matches if s.get("fund_code"))
        if len(fuzzy_codes) == 1 and len(fuzzy_matches) >= 2:
            return "medium_boosted"
        return "medium"

    return "low"


# ── Skeleton providers (for contract testing) ────────────────────────────

class SkeletonFundUniverseProvider:
    """Skeleton implementation for testing provider contracts.

    Not intended for production use. Returns empty results.
    """

    def __init__(self, provider_name: str = "skeleton_universe") -> None:
        self._diag = ProviderDiagnostics(provider_name=provider_name)

    def lookup_by_name(self, name: str) -> list[dict[str, Any]]:
        self._diag.record_success()
        return []

    def get_diagnostics(self) -> ProviderDiagnostics:
        return self._diag


class SkeletonNAVProvider:
    """Skeleton implementation for testing NAV provider contracts."""

    def __init__(self, provider_name: str = "skeleton_nav") -> None:
        self._diag = ProviderDiagnostics(provider_name=provider_name)

    def get_latest_nav(self, fund_code: str) -> dict[str, Any] | None:
        self._diag.record_success()
        return None

    def get_trade_date_nav(self, fund_code: str, trade_date: str) -> dict[str, Any] | None:
        self._diag.record_success()
        return None

    def get_diagnostics(self) -> ProviderDiagnostics:
        return self._diag


class SkeletonFundProfileProvider:
    """Skeleton implementation for testing profile provider contracts."""

    def __init__(self, provider_name: str = "skeleton_profile") -> None:
        self._diag = ProviderDiagnostics(provider_name=provider_name)

    def get_profile(self, fund_code: str) -> dict[str, Any] | None:
        self._diag.record_success()
        return None

    def get_diagnostics(self) -> ProviderDiagnostics:
        return self._diag


class FailingProvider:
    """Provider that always fails, for testing fallback behavior."""

    def __init__(self, provider_name: str = "failing_provider", error_type: str = "network_error") -> None:
        self._diag = ProviderDiagnostics(provider_name=provider_name)
        self._error_type = error_type

    def lookup_by_name(self, name: str) -> list[dict[str, Any]]:
        self._diag.record_failure(self._error_type)
        return []

    def get_latest_nav(self, fund_code: str) -> dict[str, Any] | None:
        self._diag.record_failure(self._error_type)
        return None

    def get_trade_date_nav(self, fund_code: str, trade_date: str) -> dict[str, Any] | None:
        self._diag.record_failure(self._error_type)
        return None

    def get_profile(self, fund_code: str) -> dict[str, Any] | None:
        self._diag.record_failure(self._error_type)
        return None

    def get_diagnostics(self) -> ProviderDiagnostics:
        return self._diag
