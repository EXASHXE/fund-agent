"""Provider config loader — loads providers.example.yaml into ProviderConfig objects.

Resolves env var names from YAML entries without reading actual env values.
Uses yaml.safe_load for safe parsing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.host_data.provider_config import ProviderConfig, ProviderCredentials


_DEFAULT_YAML_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "providers.example.yaml"


def _resolve_credentials(cred_block: dict[str, Any] | None) -> ProviderCredentials:
    if not cred_block:
        return ProviderCredentials()

    return ProviderCredentials(
        api_key=cred_block.get("api_key_env") or None,
        token=cred_block.get("token_env") or None,
        cookie=cred_block.get("cookie_env") or None,
        user_agent=cred_block.get("user_agent_env") or None,
    )


def load_provider_configs(yaml_path: str | Path | None = None) -> dict[str, ProviderConfig]:
    path = Path(yaml_path) if yaml_path else _DEFAULT_YAML_PATH
    if not path.exists():
        raise FileNotFoundError(f"Provider config YAML not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    providers_raw = raw.get("providers", {})
    configs: dict[str, ProviderConfig] = {}

    for name, entry in providers_raw.items():
        cred_block = entry.get("credentials", {})
        credentials = _resolve_credentials(cred_block)

        config = ProviderConfig(
            provider_name=name,
            enabled=entry.get("enabled", True),
            priority=entry.get("priority", 100),
            timeout_seconds=entry.get("timeout_seconds", 10.0),
            rate_limit_per_minute=entry.get("rate_limit_per_minute"),
            credentials=credentials,
            cache_ttl_seconds=entry.get("cache_ttl_seconds"),
            require_credentials=entry.get("require_credentials", False),
            allowed_domains=entry.get("allowed_domains", []),
            compliance_notes=entry.get("notes", []),
            capabilities=entry.get("capabilities", []),
        )
        configs[name] = config

    return configs


if __name__ == "__main__":
    configs = load_provider_configs()
    for name, cfg in configs.items():
        print(f"\n--- {name} ---")
        print(f"  enabled: {cfg.enabled}")
        print(f"  priority: {cfg.priority}")
        print(f"  require_credentials: {cfg.require_credentials}")
        print(f"  capabilities: {cfg.capabilities}")
        print(f"  credentials (env var names): {cfg.credentials.redacted()}")
        if cfg.compliance_notes:
            print(f"  notes: {cfg.compliance_notes}")
