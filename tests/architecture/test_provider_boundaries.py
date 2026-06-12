"""Architecture boundary tests for provider and network isolation — v1.7.1.

Ensures core runtime does not import provider SDKs, network clients,
or host adapter modules. Ensures no committed secrets. Ensures
credential redaction in trace/gate output.
"""

from __future__ import annotations

import ast
import json
import os
import re

import pytest

from tests.architecture.conftest import ROOT, cached_dir_imports


PROJECT_ROOT = str(ROOT)

FORBIDDEN_IN_CORE = [
    "akshare",
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "tavily",
    "exa",
    "firecrawl",
    "finnhub",
    "reddit",
    "openai",
    "anthropic",
    "langchain",
    "eastmoney_adapter",
    "xueqiu_adapter",
    "akshare_adapter",
]

CORE_DIRS = [
    "src/skills_runtime",
    "src/tools",
    "src/schemas",
    "src/graph",
    "src/skillpack",
    "src/host_data",
]

ALLOWED_PLACEHOLDERS = [
    "null",
    "YOUR_API_KEY",
    "<redacted>",
    "${ENV_NAME}",
    "NEWS_API_KEY",
    "XUEQIU_COOKIE",
    "EASTMONEY_COOKIE",
    "TAVILY_API_KEY",
    "EXA_API_KEY",
    "SERPAPI_API_KEY",
    "CUSTOM_NEWS_MCP_TOKEN",
    "FUND_AGENT_USER_AGENT",
    "XUEQIU_TOKEN",
]


def _get_imports(dirpath: str) -> set[str]:
    return set(cached_dir_imports(dirpath))


def _assert_no_imports_matching(dirpath: str, patterns: list[str], label: str):
    imports = _get_imports(dirpath)
    violations = [i for i in imports if any(p in i for p in patterns)]
    assert not violations, f"{label}: {violations}"


@pytest.mark.parametrize("dirpath,label", [(d, d) for d in CORE_DIRS])
def test_core_dirs_no_provider_sdk_imports(dirpath, label):
    _assert_no_imports_matching(dirpath, FORBIDDEN_IN_CORE, f"{label} must not import provider SDKs or network clients")


def test_host_data_contracts_no_network():
    _assert_no_imports_matching(
        "src/host_data",
        ["requests", "httpx", "aiohttp", "urllib3", "socket", "akshare"],
        "src/host_data must not make network calls",
    )


def test_fund_analysis_no_provider_imports():
    _assert_no_imports_matching(
        "src/skills_runtime/fund_analysis",
        FORBIDDEN_IN_CORE,
        "src/skills_runtime/fund_analysis must not import provider SDKs",
    )


def test_decision_support_no_provider_imports():
    _assert_no_imports_matching(
        "src/skills_runtime/decision_support",
        FORBIDDEN_IN_CORE,
        "src/skills_runtime/decision_support must not import provider SDKs",
    )


def test_workflow_tools_no_provider_imports():
    _assert_no_imports_matching(
        "src/tools/workflow",
        FORBIDDEN_IN_CORE,
        "src/tools/workflow must not import provider SDKs",
    )


def test_no_committed_secrets_in_config():
    config_path = os.path.join(PROJECT_ROOT, "config", "providers.example.yaml")
    if not os.path.exists(config_path):
        pytest.skip("config/providers.example.yaml not found")
    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()

    real_secret_patterns = [
        r'(?:api_key|token|cookie|password|secret)\s*[:=]\s*["\'][A-Za-z0-9+/=]{10,}["\']',
        r'xueqiu_cookie\s*[:=]\s*["\'][^"\']+["\']',
        r'eastmoney_cookie\s*[:=]\s*["\'][^"\']+["\']',
    ]

    for pattern in real_secret_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        assert not matches, f"Possible committed secret in config: {matches}"


def test_no_committed_secrets_in_adapter_examples():
    adapters_dir = os.path.join(PROJECT_ROOT, "examples", "host_data_adapters")
    if not os.path.exists(adapters_dir):
        pytest.skip("examples/host_data_adapters not found")
    for filename in os.listdir(adapters_dir):
        if not filename.endswith(".py"):
            continue
        filepath = os.path.join(adapters_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        real_secret_patterns = [
            r'(?:api_key|token|cookie|password|secret)\s*=\s*["\'][A-Za-z0-9+/=]{10,}["\']',
        ]
        for pattern in real_secret_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            assert not matches, f"Possible committed secret in {filename}: {matches}"


def test_examples_host_data_adapters_may_import_provider_sdks():
    adapters_dir = os.path.join(PROJECT_ROOT, "examples", "host_data_adapters")
    if not os.path.exists(adapters_dir):
        pytest.skip("examples/host_data_adapters not found")
    akshare_file = os.path.join(adapters_dir, "akshare_adapter.py")
    if not os.path.exists(akshare_file):
        pytest.skip("akshare_adapter.py not found")
    with open(akshare_file, "r", encoding="utf-8") as f:
        content = f.read()
    assert "import akshare" in content or "akshare" in content


def test_core_does_not_import_host_data_adapters():
    for dirpath in CORE_DIRS:
        _assert_no_imports_matching(
            dirpath,
            ["host_data_adapters", "akshare_adapter", "eastmoney_adapter", "xueqiu_adapter"],
            f"{dirpath} must not import host_data_adapters",
        )


def test_no_cookie_like_values_in_config():
    config_path = os.path.join(PROJECT_ROOT, "config", "providers.example.yaml")
    if not os.path.exists(config_path):
        pytest.skip("config/providers.example.yaml not found")
    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()
    cookie_value_pattern = r'(?:cookie|session_id|sess)\s*[:=]\s*["\'][A-Za-z0-9+/=._-]{8,}["\']'
    matches = re.findall(cookie_value_pattern, content, re.IGNORECASE)
    assert not matches, f"Possible cookie value in config: {matches}"


def test_no_token_like_values_in_config():
    config_path = os.path.join(PROJECT_ROOT, "config", "providers.example.yaml")
    if not os.path.exists(config_path):
        pytest.skip("config/providers.example.yaml not found")
    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()
    token_value_pattern = r'(?:bearer|authorization|access_token)\s*[:=]\s*["\'][A-Za-z0-9+/=._-]{10,}["\']'
    matches = re.findall(token_value_pattern, content, re.IGNORECASE)
    assert not matches, f"Possible token value in config: {matches}"


def test_no_api_key_like_values_in_config():
    config_path = os.path.join(PROJECT_ROOT, "config", "providers.example.yaml")
    if not os.path.exists(config_path):
        pytest.skip("config/providers.example.yaml not found")
    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()
    api_key_value_pattern = r'(?:api_key|apikey|api-secret)\s*[:=]\s*["\'][A-Za-z0-9+/=]{20,}["\']'
    matches = re.findall(api_key_value_pattern, content, re.IGNORECASE)
    assert not matches, f"Possible API key value in config: {matches}"


def test_no_authorization_header_hardcoded():
    adapters_dir = os.path.join(PROJECT_ROOT, "examples", "host_data_adapters")
    if not os.path.exists(adapters_dir):
        pytest.skip("examples/host_data_adapters not found")
    for filename in os.listdir(adapters_dir):
        if not filename.endswith(".py"):
            continue
        filepath = os.path.join(adapters_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        auth_patterns = [
            r'["\']Authorization["\']\s*:\s*["\']Bearer\s+[A-Za-z0-9+/=._-]{10,}["\']',
            r'["\']Authorization["\']\s*:\s*["\']Basic\s+[A-Za-z0-9+/=._-]{10,}["\']',
        ]
        for pattern in auth_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            assert not matches, f"Hardcoded Authorization header in {filename}: {matches}"


def test_provider_result_redacted_in_to_dict():
    from src.host_data.provider_config import ProviderConfig, ProviderCredentialSpec, ProviderCredentials

    config = ProviderConfig(
        provider_name="test",
        credential_spec=ProviderCredentialSpec(api_key_env="MY_KEY"),
        credentials=ProviderCredentials(api_key="real-secret-key-12345"),
    )
    d = config.to_dict()
    creds_dict = d["credentials"]
    assert creds_dict["api_key"] == "<redacted>"
    assert "real-secret-key" not in json.dumps(d)


def test_provider_smoke_json_redacts_credentials():
    from examples.host_data_adapters.provider_smoke import _redact_result

    d = {
        "ok": True,
        "provenance": {
            "source": "test",
            "api_key": "sk-1234567890abcdef",
            "cookie": "session=abc123def456",
            "token": "bearer-token-value-here",
            "authorization": "Bearer real-auth-token",
        },
    }
    redacted = _redact_result(d)
    prov = redacted["provenance"]
    assert prov["api_key"] == "<redacted>"
    assert prov["cookie"] == "<redacted>"
    assert prov["token"] == "<redacted>"
    assert prov["authorization"] == "<redacted>"
    assert prov["source"] == "test"


def test_host_data_no_direct_network_imports():
    _assert_no_imports_matching(
        "src/host_data",
        ["requests", "httpx", "aiohttp", "urllib3", "socket", "akshare"],
        "src/host_data must not import network clients or provider SDKs",
    )
