"""Validate that fund_name and fund_code entities are always generated from portfolio_input.

These entities must be generated regardless of whether provider_snapshot or
fund_profile_snapshot is available, because portfolio_input is always present.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_knowledge_graph_context import build_kg_context  # noqa: E402


def _portfolio_two_holdings() -> dict:
    """Portfolio with two holdings, no provider data."""
    return {
        "holdings": [
            {
                "fund_code": "002168",
                "fund_name": "半导体ETF",
                "current_value": 30000,
                "sector": "电子",
            },
            {
                "fund_code": "007540",
                "fund_name": "短债基金A",
                "current_value": 20000,
                "sector": "债券",
            },
        ],
    }


def _portfolio_name_only() -> dict:
    """Portfolio with a holding that has fund_name but no fund_code."""
    return {
        "holdings": [
            {
                "fund_name": "未知基金",
                "current_value": 5000,
                "sector": "",
            },
        ],
    }


def _portfolio_code_only() -> dict:
    """Portfolio with a holding that has fund_code but no fund_name."""
    return {
        "holdings": [
            {
                "fund_code": "123456",
                "current_value": 8000,
                "sector": "混合",
            },
        ],
    }


class TestFundNameFundCodeEntitiesAlwaysGenerated:
    """fund_name and fund_code entities must always be generated from portfolio_input."""

    def test_fund_name_entities_present_without_provider(self):
        """fund_name entities must exist even when no provider_snapshot."""
        result = build_kg_context(_portfolio_two_holdings())
        entities = result["entities"]
        assert "fund_name:半导体ETF" in entities
        assert "fund_name:短债基金A" in entities

    def test_fund_code_entities_present_without_provider(self):
        """fund entities (by fund_code) must exist even when no provider_snapshot."""
        result = build_kg_context(_portfolio_two_holdings())
        entities = result["entities"]
        assert "fund:002168" in entities
        assert "fund:007540" in entities

    def test_fund_name_entity_when_no_code(self):
        """fund_name entity must still be generated when fund_code is missing."""
        result = build_kg_context(_portfolio_name_only())
        entities = result["entities"]
        assert "fund_name:未知基金" in entities

    def test_fund_code_entity_when_no_name(self):
        """fund entity must still be generated when fund_name is missing."""
        result = build_kg_context(_portfolio_code_only())
        entities = result["entities"]
        assert "fund:123456" in entities

    def test_fund_name_entities_with_provider_snapshot(self):
        """fund_name entities must still be present when provider_snapshot is provided."""
        provider = {"fund_profiles": [], "fund_holdings": []}
        result = build_kg_context(_portfolio_two_holdings(), provider_snapshot=provider)
        entities = result["entities"]
        assert "fund_name:半导体ETF" in entities
        assert "fund_name:短债基金A" in entities

    def test_fund_code_entities_with_provider_snapshot(self):
        """fund entities must still be present when provider_snapshot is provided."""
        provider = {"fund_profiles": [], "fund_holdings": []}
        result = build_kg_context(_portfolio_two_holdings(), provider_snapshot=provider)
        entities = result["entities"]
        assert "fund:002168" in entities
        assert "fund:007540" in entities

    def test_fund_name_entities_with_fund_profile_snapshot(self):
        """fund_name entities must still be present when fund_profile_snapshot is provided."""
        fps = {"fund_profiles": {}, "fund_holdings": {}}
        result = build_kg_context(_portfolio_two_holdings(), fund_profile_snapshot=fps)
        entities = result["entities"]
        assert "fund_name:半导体ETF" in entities
        assert "fund_name:短债基金A" in entities

    def test_entities_detail_has_fund_name_type(self):
        """entities_detail must include entries with entity_type='fund_name'."""
        result = build_kg_context(_portfolio_two_holdings())
        detail_types = {e["entity_type"] for e in result["entities_detail"]}
        assert "fund_name" in detail_types

    def test_entities_detail_has_fund_type(self):
        """entities_detail must include entries with entity_type='fund'."""
        result = build_kg_context(_portfolio_two_holdings())
        detail_types = {e["entity_type"] for e in result["entities_detail"]}
        assert "fund" in detail_types
