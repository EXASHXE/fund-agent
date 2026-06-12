"""Provider credentials and configuration dataclasses.

Credentials are loaded from environment variables or host config only.
No real API keys, cookies, or tokens may be committed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProviderCredentials:
    api_key: str | None = None
    token: str | None = None
    cookie: str | None = None
    user_agent: str | None = None
    extra_headers: dict[str, str] = field(default_factory=dict)
    extra: dict[str, str] = field(default_factory=dict)

    def has_any(self) -> bool:
        return bool(self.api_key or self.token or self.cookie)

    def redacted(self) -> dict[str, Any]:
        return {
            "api_key": "<redacted>" if self.api_key else None,
            "token": "<redacted>" if self.token else None,
            "cookie": "<redacted>" if self.cookie else None,
            "user_agent": self.user_agent,
            "extra_headers": {k: "<redacted>" for k in self.extra_headers} if self.extra_headers else {},
            "extra": {k: "<redacted>" for k in self.extra} if self.extra else {},
        }


@dataclass
class ProviderConfig:
    provider_name: str
    enabled: bool = True
    priority: int = 100
    timeout_seconds: float = 10.0
    rate_limit_per_minute: int | None = None
    credentials: ProviderCredentials = field(default_factory=ProviderCredentials)
    cache_ttl_seconds: int | None = None
    require_credentials: bool = False
    allowed_domains: list[str] = field(default_factory=list)
    compliance_notes: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "enabled": self.enabled,
            "priority": self.priority,
            "timeout_seconds": self.timeout_seconds,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "credentials": self.credentials.redacted(),
            "cache_ttl_seconds": self.cache_ttl_seconds,
            "require_credentials": self.require_credentials,
            "allowed_domains": self.allowed_domains,
            "compliance_notes": self.compliance_notes,
            "capabilities": self.capabilities,
        }
