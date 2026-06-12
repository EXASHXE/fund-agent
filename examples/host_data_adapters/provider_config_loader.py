"""Provider config loader — loads providers.example.yaml into ProviderConfig objects.

Loads env var names into ProviderCredentialSpec.
Optionally resolves credential values from env when resolve_env=True.
Uses yaml.safe_load for safe parsing.
Never prints actual credential values.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml

from src.host_data.provider_config import (
    ProviderConfig,
    ProviderCredentialSpec,
    ProviderCredentials,
    resolve_credentials_from_env,
)


_DEFAULT_YAML_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "providers.example.yaml"


def _parse_credential_spec(cred_block: dict[str, Any] | None) -> ProviderCredentialSpec:
    if not cred_block:
        return ProviderCredentialSpec()

    extra_header_envs: dict[str, str] = {}
    raw_extra_headers = cred_block.get("extra_header_envs")
    if isinstance(raw_extra_headers, dict):
        for k, v in raw_extra_headers.items():
            if v:
                extra_header_envs[k] = v

    extra_envs: dict[str, str] = {}
    raw_extra_envs = cred_block.get("extra_envs")
    if isinstance(raw_extra_envs, dict):
        for k, v in raw_extra_envs.items():
            if v:
                extra_envs[k] = v

    return ProviderCredentialSpec(
        api_key_env=cred_block.get("api_key_env") or None,
        token_env=cred_block.get("token_env") or None,
        cookie_env=cred_block.get("cookie_env") or None,
        user_agent_env=cred_block.get("user_agent_env") or None,
        extra_header_envs=extra_header_envs,
        extra_envs=extra_envs,
    )


def load_provider_configs(
    yaml_path: str | Path | None = None,
    resolve_env: bool = False,
    env: Mapping[str, str] | None = None,
) -> dict[str, ProviderConfig]:
    path = Path(yaml_path) if yaml_path else _DEFAULT_YAML_PATH
    if not path.exists():
        raise FileNotFoundError(f"Provider config YAML not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    providers_raw = raw.get("providers", {})
    configs: dict[str, ProviderConfig] = {}

    for name, entry in providers_raw.items():
        cred_block = entry.get("credentials", {})
        spec = _parse_credential_spec(cred_block)

        credentials = ProviderCredentials()
        if resolve_env:
            credentials = resolve_credentials_from_env(spec, env=env)

        config = ProviderConfig(
            provider_name=name,
            enabled=entry.get("enabled", True),
            priority=entry.get("priority", 100),
            timeout_seconds=entry.get("timeout_seconds", 10.0),
            rate_limit_per_minute=entry.get("rate_limit_per_minute"),
            credential_spec=spec,
            credentials=credentials,
            cache_ttl_seconds=entry.get("cache_ttl_seconds"),
            require_credentials=entry.get("require_credentials", False),
            allowed_domains=entry.get("allowed_domains", []),
            compliance_notes=entry.get("notes", []),
            capabilities=entry.get("capabilities", []),
        )
        configs[name] = config

    return configs


def _print_credential_status(spec: ProviderCredentialSpec, credentials: ProviderCredentials) -> list[str]:
    lines: list[str] = []

    def _status(env_name: str | None, resolved: str | None, label: str) -> str:
        if not env_name:
            return f"    {label}: not configured"
        configured = "yes" if resolved else "no"
        return f"    {label}: env={env_name}, resolved={configured}"

    lines.append(_status(spec.api_key_env, credentials.api_key, "api_key"))
    lines.append(_status(spec.token_env, credentials.token, "token"))
    lines.append(_status(spec.cookie_env, credentials.cookie, "cookie"))
    lines.append(_status(spec.user_agent_env, credentials.user_agent, "user_agent"))
    for header_name, env_name in spec.extra_header_envs.items():
        resolved = credentials.extra_headers.get(header_name)
        lines.append(_status(env_name, resolved, f"extra_header.{header_name}"))
    for key, env_name in spec.extra_envs.items():
        resolved = credentials.extra.get(key)
        lines.append(_status(env_name, resolved, f"extra.{key}"))
    return lines


if __name__ == "__main__":
    configs = load_provider_configs(resolve_env=False)
    for name, cfg in configs.items():
        print(f"\n--- {name} ---")
        print(f"  enabled: {cfg.enabled}")
        print(f"  priority: {cfg.priority}")
        print(f"  require_credentials: {cfg.require_credentials}")
        print(f"  capabilities: {cfg.capabilities}")
        print(f"  credential spec:")
        for line in _print_credential_status(cfg.credential_spec, cfg.credentials):
            print(line)
        if cfg.compliance_notes:
            print(f"  notes: {cfg.compliance_notes}")
