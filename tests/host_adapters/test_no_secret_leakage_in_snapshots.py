"""Validate no API key leakage in any snapshot output.

Tests that none of the three snapshot builders leak API keys into their
output JSON. Checks all output fields recursively for known API key patterns
and environment variable names.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_knowledge_graph_context import build_kg_context
from scripts.build_news_snapshot import build_news_snapshot
from scripts.build_factor_snapshot import build_factor_snapshot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Patterns that should NEVER appear in snapshot output
_SENSITIVE_PATTERNS = [
    re.compile(r"TAVILY_API_KEY", re.IGNORECASE),
    re.compile(r"BOCHA_API_KEY", re.IGNORECASE),
    re.compile(r"SERPAPI_API_KEY", re.IGNORECASE),
    re.compile(r"FINNHUB_API_KEY", re.IGNORECASE),
    re.compile(r"api[_-]?key", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"bearer\s+", re.IGNORECASE),
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),  # OpenAI-style key
    re.compile(r"[a-f0-9]{32}"),  # Hex key pattern (32+ hex chars)
]

# Environment variable names that hold API keys
_KEY_ENV_VARS = [
    "TAVILY_API_KEY",
    "BOCHA_API_KEY",
    "SERPAPI_API_KEY",
    "FINNHUB_API_KEY",
]


def _check_dict_for_leaks(obj: dict, path: str = "") -> list[str]:
    """Recursively check a dict for potential API key leaks."""
    leaks: list[str] = []
    text = json.dumps(obj, ensure_ascii=False)

    for pattern in _SENSITIVE_PATTERNS:
        matches = pattern.findall(text)
        if matches:
            # Filter out false positives: "api_key" as a field name in provider_status is OK
            # Only flag if it's an actual key value, not a field name
            for match in matches:
                match_lower = match.lower()
                # Allow "api_key" as part of error messages like "TAVILY_API_KEY not set"
                if match_lower in ("api_key", "apikey"):
                    # Check if it's just a field name reference, not a value
                    continue
                if match_lower in ("secret",):
                    continue
                if match_lower == "token":
                    # "token" in context of "investment token" etc is OK
                    continue
                leaks.append(f"Pattern '{pattern.pattern}' matched '{match}' at {path}")

    return leaks


def _sample_portfolio() -> dict:
    """Sample portfolio for testing."""
    return {
        "cash_available": 5000,
        "holdings": [
            {
                "fund_code": "002168",
                "fund_name": "半导体ETF",
                "current_value": 30000,
                "cost_basis": 25000,
                "sector": "电子",
                "theme": "半导体",
                "risk_bucket": "high",
            },
        ],
    }


def _sample_kg_context() -> dict:
    """Sample KG context for testing."""
    return {
        "snapshot_type": "knowledge_graph_context",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "portfolio_summary": {"holding_count": 1, "total_value": 30000},
        "entities": ["fund:002168"],
        "fund_entities": [
            {
                "fund_code": "002168",
                "fund_name": "半导体ETF",
                "sector": "电子",
                "theme_tags": ["半导体"],
                "risk_bucket": "high",
            },
        ],
        "watch_topics": ["半导体"],
        "query_plan": [
            {
                "query_id": "abc123",
                "query": "半导体ETF",
                "entities": ["fund:002168"],
                "topic_tags": ["半导体"],
            },
        ],
        "missing_data": {
            "fund_code_missing": [],
            "units_missing": [],
            "nav_missing": [],
            "cost_basis_missing": [],
            "provider_snapshot_missing": True,
            "manual_transactions_missing": True,
        },
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNoSecretLeakageInSnapshots:
    """Validate that no API keys or secrets appear in snapshot outputs."""

    def test_kg_context_no_key_leakage(self):
        """KG context snapshot must not contain any API keys."""
        # Set some fake API keys in env to ensure they don't leak
        fake_env = {
            "TAVILY_API_KEY": "tvly-fake-key-12345678",
            "BOCHA_API_KEY": "bcha-fake-key-12345678",
            "SERPAPI_API_KEY": "srpi-fake-key-12345678",
            "FINNHUB_API_KEY": "fnhb-fake-key-12345678",
        }
        with patch.dict(os.environ, fake_env, clear=False):
            result = build_kg_context(_sample_portfolio())

        output_json = json.dumps(result, ensure_ascii=False)
        # None of the fake key values should appear in output
        for key_name, key_val in fake_env.items():
            assert key_val not in output_json, f"API key value for {key_name} leaked in KG context output"

    def test_news_snapshot_no_key_leakage(self):
        """News snapshot must not contain any API keys."""
        fake_env = {
            "TAVILY_API_KEY": "tvly-fake-key-12345678",
            "BOCHA_API_KEY": "bcha-fake-key-12345678",
        }
        with patch.dict(os.environ, fake_env, clear=False):
            result = build_news_snapshot(_sample_kg_context())

        output_json = json.dumps(result, ensure_ascii=False)
        for key_name, key_val in fake_env.items():
            assert key_val not in output_json, f"API key value for {key_name} leaked in news snapshot output"

    def test_factor_snapshot_no_key_leakage(self):
        """Factor snapshot must not contain any API keys."""
        fake_env = {
            "TAVILY_API_KEY": "tvly-fake-key-12345678",
            "BOCHA_API_KEY": "bcha-fake-key-12345678",
        }
        with patch.dict(os.environ, fake_env, clear=False):
            result = build_factor_snapshot(_sample_portfolio())

        output_json = json.dumps(result, ensure_ascii=False)
        for key_name, key_val in fake_env.items():
            assert key_val not in output_json, f"API key value for {key_name} leaked in factor snapshot output"

    def test_kg_context_no_env_var_names_as_values(self):
        """KG context must not have env var names as values (only as references in error messages is OK)."""
        result = build_kg_context(_sample_portfolio())
        output_json = json.dumps(result, ensure_ascii=False)
        # The key variable names themselves should not appear as values
        # (they might appear in error messages which is acceptable)
        for key_name in _KEY_ENV_VARS:
            # Check it's not a standalone value (i.e., not just in an error message)
            # A standalone value would be like "value": "TAVILY_API_KEY"
            pattern = f'": "{key_name}"'
            assert pattern not in output_json, f"Env var name {key_name} appears as a value in KG context"

    def test_news_snapshot_provider_status_no_key_values(self):
        """provider_status in news snapshot must not contain actual key values."""
        fake_env = {
            "TAVILY_API_KEY": "tvly-fake-key-12345678",
        }
        with patch.dict(os.environ, fake_env, clear=False):
            result = build_news_snapshot(_sample_kg_context())

        # Check provider_status doesn't contain the actual key value
        ps_json = json.dumps(result["provider_status"], ensure_ascii=False)
        assert "tvly-fake-key-12345678" not in ps_json

    def test_no_bearer_tokens_in_output(self):
        """No 'Bearer <token>' patterns should appear in any snapshot."""
        fake_env = {
            "TAVILY_API_KEY": "tvly-fake-key-12345678",
            "BOCHA_API_KEY": "bcha-fake-key-12345678",
        }
        with patch.dict(os.environ, fake_env, clear=False):
            kg = build_kg_context(_sample_portfolio())
            news = build_news_snapshot(_sample_kg_context())
            factor = build_factor_snapshot(_sample_portfolio())

        for name, snapshot in [("kg", kg), ("news", news), ("factor", factor)]:
            output = json.dumps(snapshot, ensure_ascii=False)
            assert "Bearer " not in output, f"Bearer token found in {name} snapshot"

    def test_no_long_hex_strings_in_output(self):
        """No long hex strings (potential key hashes) should appear as values in snapshots."""
        fake_env = {
            "TAVILY_API_KEY": "tvly-fake-key-12345678",
        }
        with patch.dict(os.environ, fake_env, clear=False):
            kg = build_kg_context(_sample_portfolio())
            news = build_news_snapshot(_sample_kg_context())
            factor = build_factor_snapshot(_sample_portfolio())

        for name, snapshot in [("kg", kg), ("news", news), ("factor", factor)]:
            output = json.dumps(snapshot, ensure_ascii=False)
            # Check for hex strings longer than 40 chars (SHA-1+)
            hex_matches = re.findall(r"[a-f0-9]{40,}", output)
            assert len(hex_matches) == 0, f"Long hex string found in {name} snapshot: {hex_matches}"

    def test_round_trip_json_no_key_leakage(self):
        """Serialize → deserialize → re-serialize must not introduce key leakage."""
        fake_env = {
            "TAVILY_API_KEY": "tvly-fake-key-12345678",
        }
        with patch.dict(os.environ, fake_env, clear=False):
            result = build_kg_context(_sample_portfolio())

        # Round-trip through JSON
        json_str = json.dumps(result, ensure_ascii=False)
        parsed = json.loads(json_str)
        json_str2 = json.dumps(parsed, ensure_ascii=False)

        assert "tvly-fake-key-12345678" not in json_str2
