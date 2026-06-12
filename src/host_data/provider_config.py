"""Provider credentials and configuration dataclasses.

Credentials are loaded from environment variables or host config only.
No real API keys, cookies, or tokens may be committed.

ProviderCredentialSpec stores env var names (safe to log/commit).
ProviderCredentials stores resolved secret values (never logged/committed).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass
class ProviderCredentialSpec:
    api_key_env: str | None = None
    token_env: str | None = None
    cookie_env: str | None = None
    user_agent_env: str | None = None
    extra_header_envs: dict[str, str] = field(default_factory=dict)
    extra_envs: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "api_key_env": self.api_key_env,
            "token_env": self.token_env,
            "cookie_env": self.cookie_env,
            "user_agent_env": self.user_agent_env,
            "extra_header_envs": dict(self.extra_header_envs),
            "extra_envs": dict(self.extra_envs),
        }


@dataclass
class ProviderCredentials:
    api_key: str | None = None
    token: str | None = None
    cookie: str | None = None
    user_agent: str | None = None
    extra_headers: dict[str, str] = field(default_factory=dict)
    extra: dict[str, str] = field(default_factory=dict)

    def has_any(self) -> bool:
        return bool(
            (self.api_key and self.api_key.strip())
            or (self.token and self.token.strip())
            or (self.cookie and self.cookie.strip())
        )

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
    credential_spec: ProviderCredentialSpec = field(default_factory=ProviderCredentialSpec)
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
            "credential_spec": self.credential_spec.to_dict(),
            "credentials": self.credentials.redacted(),
            "cache_ttl_seconds": self.cache_ttl_seconds,
            "require_credentials": self.require_credentials,
            "allowed_domains": self.allowed_domains,
            "compliance_notes": self.compliance_notes,
            "capabilities": self.capabilities,
        }


def resolve_credentials_from_env(
    spec: ProviderCredentialSpec,
    env: Mapping[str, str] | None = None,
) -> ProviderCredentials:
    source = env if env is not None else os.environ

    def _lookup(env_name: str | None) -> str | None:
        if not env_name:
            return None
        val = source.get(env_name)
        if val is not None and val.strip() == "":
            return None
        return val

    extra_headers: dict[str, str] = {}
    for header_name, env_name in spec.extra_header_envs.items():
        val = _lookup(env_name)
        if val is not None:
            extra_headers[header_name] = val

    extra: dict[str, str] = {}
    for key, env_name in spec.extra_envs.items():
        val = _lookup(env_name)
        if val is not None:
            extra[key] = val

    return ProviderCredentials(
        api_key=_lookup(spec.api_key_env),
        token=_lookup(spec.token_env),
        cookie=_lookup(spec.cookie_env),
        user_agent=_lookup(spec.user_agent_env),
        extra_headers=extra_headers,
        extra=extra,
    )


def credentials_missing(config: ProviderConfig) -> list[str]:
    missing: list[str] = []
    if not config.require_credentials:
        return missing

    spec = config.credential_spec
    creds = config.credentials

    if spec.api_key_env and not (creds.api_key and creds.api_key.strip()):
        missing.append(f"api_key (env: {spec.api_key_env})")
    if spec.token_env and not (creds.token and creds.token.strip()):
        missing.append(f"token (env: {spec.token_env})")
    if spec.cookie_env and not (creds.cookie and creds.cookie.strip()):
        missing.append(f"cookie (env: {spec.cookie_env})")

    if not missing and not creds.has_any():
        if not spec.api_key_env and not spec.token_env and not spec.cookie_env:
            missing.append("no credential spec defined but require_credentials is true")

    return missing
