"""Architecture boundary tests for provider and network isolation — v1.7.

Ensures core runtime does not import provider SDKs, network clients,
or host adapter modules.
"""

from __future__ import annotations

import ast
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

    placeholder_patterns = [
        r'\bapi_key:\s*null\b',
        r'\btoken:\s*null\b',
        r'\bcookie:\s*null\b',
        r'\bapi_key_env:\s*null\b',
        r'\btoken_env:\s*null\b',
        r'\bcookie_env:\s*\w+\b',
        r'\$\{[\w_]+\}',
        r'YOUR_API_KEY',
        r'<redacted>',
    ]

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
