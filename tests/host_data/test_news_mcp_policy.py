"""Tests for news MCP/API key policy — ensures documentation and config mention credentials."""

from __future__ import annotations

import os
import re

import pytest

from tests.architecture.conftest import ROOT


class TestNewsMcppolicy:
    def test_providers_yaml_mentions_news_api_key(self):
        config_path = ROOT / "config" / "providers.example.yaml"
        if not config_path.exists():
            pytest.skip("config/providers.example.yaml not found")
        content = config_path.read_text(encoding="utf-8")
        assert "NEWS_API_KEY" in content

    def test_providers_yaml_mentions_tavily_api_key(self):
        config_path = ROOT / "config" / "providers.example.yaml"
        if not config_path.exists():
            pytest.skip("config/providers.example.yaml not found")
        content = config_path.read_text(encoding="utf-8")
        assert "TAVILY_API_KEY" in content

    def test_providers_yaml_mentions_exa_api_key(self):
        config_path = ROOT / "config" / "providers.example.yaml"
        if not config_path.exists():
            pytest.skip("config/providers.example.yaml not found")
        content = config_path.read_text(encoding="utf-8")
        assert "EXA_API_KEY" in content

    def test_providers_yaml_mentions_serpapi_api_key(self):
        config_path = ROOT / "config" / "providers.example.yaml"
        if not config_path.exists():
            pytest.skip("config/providers.example.yaml not found")
        content = config_path.read_text(encoding="utf-8")
        assert "SERPAPI_API_KEY" in content

    def test_providers_yaml_mentions_custom_news_mcp_token(self):
        config_path = ROOT / "config" / "providers.example.yaml"
        if not config_path.exists():
            pytest.skip("config/providers.example.yaml not found")
        content = config_path.read_text(encoding="utf-8")
        assert "CUSTOM_NEWS_MCP_TOKEN" in content

    def test_news_research_skill_mentions_mcp_boundary(self):
        skill_path = ROOT / "skills" / "news-research" / "SKILL.md"
        if not skill_path.exists():
            pytest.skip("skills/news-research/SKILL.md not found")
        content = skill_path.read_text(encoding="utf-8")
        assert "MCPHostAdapter" in content or "MCP" in content
        assert "MISSING_MCP_CAPABILITY" in content or "MISSING_CREDENTIALS" in content

    def test_news_research_skill_no_hardcoded_keys(self):
        skill_path = ROOT / "skills" / "news-research" / "SKILL.md"
        if not skill_path.exists():
            pytest.skip("skills/news-research/SKILL.md not found")
        content = skill_path.read_text(encoding="utf-8")
        real_key_patterns = [
            r'(?:api_key|token|secret)\s*[:=]\s*["\'][A-Za-z0-9+/=]{20,}["\']',
        ]
        for pattern in real_key_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            assert not matches, f"Possible hardcoded key in SKILL.md: {matches}"

    def test_data_provider_contract_mentions_news_mcp(self):
        contract_path = ROOT / "docs" / "design" / "data-provider-contract.v1.md"
        if not contract_path.exists():
            pytest.skip("data-provider-contract.v1.md not found")
        content = contract_path.read_text(encoding="utf-8")
        assert "NEWS_API_KEY" in content or "news_mcp" in content.lower() or "News MCP" in content

    def test_providers_yaml_news_error_codes_documented(self):
        config_path = ROOT / "config" / "providers.example.yaml"
        if not config_path.exists():
            pytest.skip("config/providers.example.yaml not found")
        content = config_path.read_text(encoding="utf-8")
        assert "MISSING_MCP_CAPABILITY" in content or "MCP_CALL_FAILED" in content
