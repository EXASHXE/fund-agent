"""Provider result dataclass.

Normalized output shape for all host-owned data adapters.
Includes provenance, freshness, confidence, and error metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProviderResult:
    ok: bool
    provider: str
    capability: str
    symbol: str | None = None
    fund_code: str | None = None
    as_of: str | None = None
    freshness: str = "unknown"
    confidence: str = "low"
    data: dict | list | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)
    raw_sample: dict | list | str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "provider": self.provider,
            "capability": self.capability,
            "symbol": self.symbol,
            "fund_code": self.fund_code,
            "as_of": self.as_of,
            "freshness": self.freshness,
            "confidence": self.confidence,
            "data": self.data,
            "warnings": self.warnings,
            "errors": self.errors,
            "provenance": self.provenance,
            "raw_sample": self.raw_sample,
        }

    @classmethod
    def missing_credentials(cls, provider: str, capability: str) -> ProviderResult:
        return cls(
            ok=False,
            provider=provider,
            capability=capability,
            errors=["MISSING_CREDENTIALS"],
            confidence="low",
            freshness="unknown",
        )

    @classmethod
    def missing_dependency(cls, provider: str, capability: str) -> ProviderResult:
        return cls(
            ok=False,
            provider=provider,
            capability=capability,
            errors=["MISSING_DEPENDENCY"],
            confidence="low",
            freshness="unknown",
        )

    @classmethod
    def provider_blocked(cls, provider: str, capability: str, reason: str = "") -> ProviderResult:
        return cls(
            ok=False,
            provider=provider,
            capability=capability,
            errors=["PROVIDER_BLOCKED", reason] if reason else ["PROVIDER_BLOCKED"],
            confidence="low",
            freshness="unknown",
        )

    @classmethod
    def provider_auth_required(cls, provider: str, capability: str) -> ProviderResult:
        return cls(
            ok=False,
            provider=provider,
            capability=capability,
            errors=["PROVIDER_AUTH_REQUIRED"],
            confidence="low",
            freshness="unknown",
        )

    @classmethod
    def provider_rate_limited(cls, provider: str, capability: str) -> ProviderResult:
        return cls(
            ok=False,
            provider=provider,
            capability=capability,
            errors=["PROVIDER_RATE_LIMITED"],
            confidence="low",
            freshness="unknown",
        )

    @classmethod
    def empty_result(cls, provider: str, capability: str) -> ProviderResult:
        return cls(
            ok=False,
            provider=provider,
            capability=capability,
            errors=["EMPTY_RESULT"],
            confidence="low",
            freshness="unknown",
        )

    @classmethod
    def partial(cls, provider: str, capability: str, warnings: list[str] | None = None) -> ProviderResult:
        return cls(
            ok=False,
            provider=provider,
            capability=capability,
            errors=["PARTIAL"],
            warnings=warnings or [],
            confidence="low",
            freshness="unknown",
        )
