"""Tests for provider config loader — env name / credential resolution."""

from __future__ import annotations

import pytest
import yaml

from src.host_data.provider_config import (
    ProviderConfig,
    ProviderCredentialSpec,
    ProviderCredentials,
    credentials_missing,
    resolve_credentials_from_env,
)


def _make_example_yaml() -> str:
    return yaml.dump({
        "providers": {
            "akshare": {
                "enabled": True,
                "priority": 10,
                "require_credentials": False,
                "credentials": {
                    "api_key_env": None,
                    "token_env": None,
                    "cookie_env": None,
                    "user_agent_env": "FUND_AGENT_USER_AGENT",
                },
                "capabilities": ["FUND_NAV_HISTORY"],
            },
            "xueqiu": {
                "enabled": False,
                "priority": 30,
                "require_credentials": True,
                "credentials": {
                    "api_key_env": None,
                    "token_env": "XUEQIU_TOKEN",
                    "cookie_env": "XUEQIU_COOKIE",
                    "user_agent_env": "FUND_AGENT_USER_AGENT",
                },
                "capabilities": ["STOCK_QUOTE"],
            },
            "news_mcp": {
                "enabled": False,
                "priority": 40,
                "require_credentials": True,
                "credentials": {
                    "api_key_env": "NEWS_API_KEY",
                    "token_env": None,
                    "cookie_env": None,
                    "extra_envs": {
                        "TAVILY_API_KEY": "TAVILY_API_KEY",
                    },
                },
                "capabilities": ["MARKET_NEWS"],
            },
        }
    })


class TestProviderCredentialSpec:
    def test_stores_env_names(self):
        spec = ProviderCredentialSpec(
            api_key_env="MY_API_KEY",
            token_env="MY_TOKEN",
            cookie_env="MY_COOKIE",
            user_agent_env="MY_UA",
        )
        assert spec.api_key_env == "MY_API_KEY"
        assert spec.token_env == "MY_TOKEN"
        assert spec.cookie_env == "MY_COOKIE"
        assert spec.user_agent_env == "MY_UA"

    def test_to_dict_shows_env_names(self):
        spec = ProviderCredentialSpec(api_key_env="MY_API_KEY", cookie_env="MY_COOKIE")
        d = spec.to_dict()
        assert d["api_key_env"] == "MY_API_KEY"
        assert d["cookie_env"] == "MY_COOKIE"

    def test_defaults_none(self):
        spec = ProviderCredentialSpec()
        assert spec.api_key_env is None
        assert spec.token_env is None
        assert spec.cookie_env is None
        assert spec.user_agent_env is None


class TestProviderCredentials:
    def test_redacted_never_exposes_values(self):
        creds = ProviderCredentials(
            api_key="secret-key-123",
            token="secret-token-456",
            cookie="secret-cookie-789",
            user_agent="TestAgent/1.0",
            extra_headers={"X-Custom": "header-val"},
            extra={"foo": "bar"},
        )
        redacted = creds.redacted()
        assert redacted["api_key"] == "<redacted>"
        assert redacted["token"] == "<redacted>"
        assert redacted["cookie"] == "<redacted>"
        assert redacted["user_agent"] == "TestAgent/1.0"
        assert redacted["extra_headers"]["X-Custom"] == "<redacted>"
        assert redacted["extra"]["foo"] == "<redacted>"

    def test_has_any_ignores_empty_strings(self):
        assert not ProviderCredentials(api_key="").has_any()
        assert not ProviderCredentials(api_key="  ").has_any()
        assert ProviderCredentials(api_key="val").has_any()

    def test_has_any_ignores_user_agent(self):
        assert not ProviderCredentials(user_agent="TestAgent/1.0").has_any()


class TestResolveCredentialsFromEnv:
    def test_resolves_from_fake_env(self):
        spec = ProviderCredentialSpec(
            api_key_env="MY_API_KEY",
            cookie_env="MY_COOKIE",
            user_agent_env="MY_UA",
        )
        env = {"MY_API_KEY": "real-key", "MY_COOKIE": "real-cookie", "MY_UA": "TestUA"}
        creds = resolve_credentials_from_env(spec, env=env)
        assert creds.api_key == "real-key"
        assert creds.cookie == "real-cookie"
        assert creds.user_agent == "TestUA"

    def test_missing_env_produces_none(self):
        spec = ProviderCredentialSpec(api_key_env="MISSING_KEY")
        creds = resolve_credentials_from_env(spec, env={})
        assert creds.api_key is None

    def test_empty_string_treated_as_missing(self):
        spec = ProviderCredentialSpec(api_key_env="EMPTY_KEY")
        creds = resolve_credentials_from_env(spec, env={"EMPTY_KEY": ""})
        assert creds.api_key is None

    def test_none_env_name_produces_none(self):
        spec = ProviderCredentialSpec(api_key_env=None)
        creds = resolve_credentials_from_env(spec, env={})
        assert creds.api_key is None

    def test_extra_envs_resolved(self):
        spec = ProviderCredentialSpec(
            extra_envs={"TAVILY_API_KEY": "TAVILY_API_KEY"},
        )
        env = {"TAVILY_API_KEY": "tavily-real-key"}
        creds = resolve_credentials_from_env(spec, env=env)
        assert creds.extra["TAVILY_API_KEY"] == "tavily-real-key"

    def test_extra_header_envs_resolved(self):
        spec = ProviderCredentialSpec(
            extra_header_envs={"X-Api-Key": "MY_HEADER_KEY"},
        )
        env = {"MY_HEADER_KEY": "header-real-key"}
        creds = resolve_credentials_from_env(spec, env=env)
        assert creds.extra_headers["X-Api-Key"] == "header-real-key"


class TestCredentialsMissing:
    def test_no_missing_when_not_required(self):
        config = ProviderConfig(
            provider_name="test",
            require_credentials=False,
            credential_spec=ProviderCredentialSpec(api_key_env="MY_KEY"),
            credentials=ProviderCredentials(),
        )
        assert credentials_missing(config) == []

    def test_missing_when_required_and_absent(self):
        config = ProviderConfig(
            provider_name="test",
            require_credentials=True,
            credential_spec=ProviderCredentialSpec(api_key_env="MY_KEY"),
            credentials=ProviderCredentials(),
        )
        missing = credentials_missing(config)
        assert len(missing) == 1
        assert "MY_KEY" in missing[0]

    def test_not_missing_when_resolved(self):
        config = ProviderConfig(
            provider_name="test",
            require_credentials=True,
            credential_spec=ProviderCredentialSpec(api_key_env="MY_KEY"),
            credentials=ProviderCredentials(api_key="real-key"),
        )
        assert credentials_missing(config) == []

    def test_missing_cookie_and_token(self):
        config = ProviderConfig(
            provider_name="test",
            require_credentials=True,
            credential_spec=ProviderCredentialSpec(
                token_env="MY_TOKEN",
                cookie_env="MY_COOKIE",
            ),
            credentials=ProviderCredentials(),
        )
        missing = credentials_missing(config)
        assert len(missing) == 2

    def test_empty_string_credential_counted_as_missing(self):
        config = ProviderConfig(
            provider_name="test",
            require_credentials=True,
            credential_spec=ProviderCredentialSpec(api_key_env="MY_KEY"),
            credentials=ProviderCredentials(api_key="  "),
        )
        missing = credentials_missing(config)
        assert len(missing) == 1


class TestLoadProviderConfigs:
    def test_env_names_in_spec_not_credentials(self, tmp_path):
        from examples.host_data_adapters.provider_config_loader import load_provider_configs

        yaml_path = tmp_path / "test_providers.yaml"
        yaml_path.write_text(_make_example_yaml(), encoding="utf-8")

        configs = load_provider_configs(str(yaml_path), resolve_env=False)

        xueqiu = configs["xueqiu"]
        assert xueqiu.credential_spec.cookie_env == "XUEQIU_COOKIE"
        assert xueqiu.credential_spec.token_env == "XUEQIU_TOKEN"
        assert xueqiu.credentials.cookie is None
        assert xueqiu.credentials.token is None

    def test_resolve_env_true_populates_credentials(self, tmp_path):
        from examples.host_data_adapters.provider_config_loader import load_provider_configs

        yaml_path = tmp_path / "test_providers.yaml"
        yaml_path.write_text(_make_example_yaml(), encoding="utf-8")

        fake_env = {
            "XUEQIU_COOKIE": "real-cookie",
            "XUEQIU_TOKEN": "real-token",
            "NEWS_API_KEY": "real-news-key",
            "TAVILY_API_KEY": "real-tavily-key",
        }
        configs = load_provider_configs(str(yaml_path), resolve_env=True, env=fake_env)

        xueqiu = configs["xueqiu"]
        assert xueqiu.credentials.cookie == "real-cookie"
        assert xueqiu.credentials.token == "real-token"

        news = configs["news_mcp"]
        assert news.credentials.api_key == "real-news-key"
        assert news.credentials.extra["TAVILY_API_KEY"] == "real-tavily-key"

    def test_missing_env_values_produce_empty_credentials(self, tmp_path):
        from examples.host_data_adapters.provider_config_loader import load_provider_configs

        yaml_path = tmp_path / "test_providers.yaml"
        yaml_path.write_text(_make_example_yaml(), encoding="utf-8")

        configs = load_provider_configs(str(yaml_path), resolve_env=True, env={})

        xueqiu = configs["xueqiu"]
        assert xueqiu.credentials.cookie is None
        assert xueqiu.credentials.token is None

    def test_redacted_output_no_real_values(self, tmp_path):
        from examples.host_data_adapters.provider_config_loader import load_provider_configs

        yaml_path = tmp_path / "test_providers.yaml"
        yaml_path.write_text(_make_example_yaml(), encoding="utf-8")

        fake_env = {"XUEQIU_COOKIE": "super-secret-cookie", "XUEQIU_TOKEN": "super-secret-token"}
        configs = load_provider_configs(str(yaml_path), resolve_env=True, env=fake_env)

        xueqiu = configs["xueqiu"]
        d = xueqiu.to_dict()
        cred_dict = d["credentials"]
        assert cred_dict["cookie"] == "<redacted>"
        assert cred_dict["token"] == "<redacted>"
        assert "super-secret" not in str(d)

    def test_require_credentials_missing_detectable(self, tmp_path):
        from examples.host_data_adapters.provider_config_loader import load_provider_configs

        yaml_path = tmp_path / "test_providers.yaml"
        yaml_path.write_text(_make_example_yaml(), encoding="utf-8")

        configs = load_provider_configs(str(yaml_path), resolve_env=True, env={})

        xueqiu = configs["xueqiu"]
        missing = credentials_missing(xueqiu)
        assert len(missing) > 0
        assert any("XUEQIU_COOKIE" in m for m in missing)
        assert any("XUEQIU_TOKEN" in m for m in missing)

    def test_akshare_no_credential_spec(self, tmp_path):
        from examples.host_data_adapters.provider_config_loader import load_provider_configs

        yaml_path = tmp_path / "test_providers.yaml"
        yaml_path.write_text(_make_example_yaml(), encoding="utf-8")

        configs = load_provider_configs(str(yaml_path), resolve_env=False)

        akshare = configs["akshare"]
        assert akshare.credential_spec.api_key_env is None
        assert akshare.credential_spec.cookie_env is None
        assert akshare.credential_spec.user_agent_env == "FUND_AGENT_USER_AGENT"
