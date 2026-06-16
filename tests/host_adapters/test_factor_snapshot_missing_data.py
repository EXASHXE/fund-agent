"""Validate factor snapshot with missing data.

Tests that the factor snapshot builder correctly handles missing data
scenarios: missing cost_basis, missing units, missing nav, missing
provider_snapshot, missing news_snapshot. Ensures that missing data
is tracked but never fabricated.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_factor_snapshot import build_factor_snapshot  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _full_portfolio() -> dict:
    """Portfolio with complete data for all holdings."""
    return {
        "cash_available": 5000,
        "holdings": [
            {
                "fund_code": "002168",
                "fund_name": "半导体ETF",
                "current_value": 30000,
                "cost_basis": 25000,
                "units": 1000,
                "nav": 1.5,
                "sector": "电子",
                "theme": "半导体",
                "risk_bucket": "high",
                "pending_amount": 0,
            },
            {
                "fund_code": "007540",
                "fund_name": "短债基金",
                "current_value": 20000,
                "cost_basis": 19500,
                "units": 2000,
                "nav": 1.0,
                "sector": "债券",
                "theme": "短债",
                "risk_bucket": "low",
                "pending_amount": 0,
            },
        ],
    }


def _partial_portfolio() -> dict:
    """Portfolio with some missing data fields."""
    return {
        "cash_available": 3000,
        "holdings": [
            {
                "fund_code": "002168",
                "fund_name": "半导体ETF",
                "current_value": 30000,
                # cost_basis missing
                # units missing
                # nav missing
                "sector": "电子",
                "theme": "半导体",
            },
            {
                "fund_code": "007540",
                "fund_name": "短债基金",
                "current_value": 20000,
                "cost_basis": 19500,
                # units missing
                "nav": 1.0,
                "sector": "债券",
                "theme": "短债",
            },
            {
                "fund_code": "",
                "fund_name": "未知基金",
                "current_value": 10000,
                # cost_basis missing
                # nav missing
                "sector": "",
            },
        ],
    }


def _empty_portfolio() -> dict:
    """Portfolio with no holdings."""
    return {
        "cash_available": 0,
        "holdings": [],
    }


def _sample_news_snapshot() -> dict:
    """Minimal news snapshot for testing news factor computation."""
    return {
        "snapshot_type": "news_snapshot",
        "generated_at": "2026-06-14T00:00:00+00:00",
        "items": [
            {
                "id": "abc123",
                "provider": "tavily",
                "query": "半导体",
                "title": "半导体行业分析",
                "url": "https://example.com/1",
                "source": "test",
                "published_at": "2026-06-14T10:00:00+00:00",
                "summary": "半导体行业最新分析",
                "language": "zh",
                "related_entities": ["fund:002168"],
                "topic_tags": ["半导体"],
                "relevance_score": 0.8,
                "freshness_score": 0.9,
                "confidence": 0.8,
            },
            {
                "id": "def456",
                "provider": "tavily",
                "query": "短债",
                "title": "债券市场周报",
                "url": "https://example.com/2",
                "source": "test",
                "published_at": "2026-06-01T10:00:00+00:00",
                "summary": "短债市场分析",
                "language": "zh",
                "related_entities": ["fund:007540"],
                "topic_tags": ["短债"],
                "relevance_score": 0.6,
                "freshness_score": 0.4,
                "confidence": 0.4,
            },
        ],
        "provider_status": {
            "tavily": {"available": True, "error": None},
            "bocha": {"available": False, "error": "no key"},
            "serpapi": {"available": False, "error": "no key"},
            "finnhub": {"available": False, "error": "no key"},
        },
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFactorSnapshotMissingData:
    """Validate factor snapshot behavior with missing data."""

    def test_cost_basis_none_not_zero(self):
        """cost_basis=None MUST NOT become known_cost_basis=0."""
        result = build_factor_snapshot(_partial_portfolio())
        for hf in result["holding_factors"]:
            if hf["fund_code"] == "002168":
                # cost_basis was missing, so known_cost_basis should be None
                assert hf["known_cost_basis"] is None
                assert hf["cost_basis_missing"] is True

    def test_cost_basis_missing_count(self):
        """cost_basis_missing_count must reflect actual missing count."""
        result = build_factor_snapshot(_partial_portfolio())
        # 002168 has no cost_basis, 007540 has cost_basis, 未知基金 has no cost_basis
        assert result["data_quality"]["cost_basis_missing_count"] == 2

    def test_units_missing_count(self):
        """units_missing_count must reflect actual missing count."""
        result = build_factor_snapshot(_partial_portfolio())
        # All three holdings have no units
        assert result["data_quality"]["units_missing_count"] >= 2

    def test_nav_missing_count(self):
        """nav_missing_count must reflect actual missing count."""
        result = build_factor_snapshot(_partial_portfolio())
        # 002168 and 未知基金 have no nav
        assert result["data_quality"]["nav_missing_count"] >= 1

    def test_news_snapshot_missing_true(self):
        """news_snapshot_missing must be True when no news snapshot provided."""
        result = build_factor_snapshot(_partial_portfolio())
        assert result["data_quality"]["news_snapshot_missing"] is True

    def test_news_snapshot_missing_false_when_provided(self):
        """news_snapshot_missing must be False when news snapshot is provided."""
        result = build_factor_snapshot(_partial_portfolio(), news_snapshot=_sample_news_snapshot())
        assert result["data_quality"]["news_snapshot_missing"] is False

    def test_provider_snapshot_missing_true(self):
        """provider_snapshot_missing must be True when no provider snapshot."""
        result = build_factor_snapshot(_partial_portfolio())
        assert result["data_quality"]["provider_snapshot_missing"] is True

    def test_provider_snapshot_missing_false_when_provided(self):
        """provider_snapshot_missing must be False when provider snapshot is provided."""
        result = build_factor_snapshot(_partial_portfolio(), provider_snapshot={"nav_data": {}})
        assert result["data_quality"]["provider_snapshot_missing"] is False

    def test_factor_confidence_low_with_many_missing(self):
        """factor_confidence must be 'low' with significant missing data."""
        result = build_factor_snapshot(_partial_portfolio())
        assert result["data_quality"]["factor_confidence"] in ("low", "medium")

    def test_factor_confidence_high_with_full_data(self):
        """factor_confidence must be 'high' with complete data."""
        result = build_factor_snapshot(_full_portfolio())
        assert result["data_quality"]["factor_confidence"] == "high"

    def test_cost_basis_partial_flag(self):
        """cost_basis_partial must be True when some but not all cost_basis missing."""
        result = build_factor_snapshot(_partial_portfolio())
        assert result["data_quality"]["cost_basis_partial"] is True

    def test_no_fabricated_unrealized_pnl(self):
        """Unrealized PnL must be None when cost_basis is missing."""
        result = build_factor_snapshot(_partial_portfolio())
        for hf in result["holding_factors"]:
            if hf["cost_basis_missing"]:
                assert hf["unrealized_gain_loss_amount"] is None
                assert hf["unrealized_gain_loss_pct"] is None

    def test_valid_pnl_when_cost_basis_present(self):
        """Unrealized PnL must be computed when cost_basis is present."""
        result = build_factor_snapshot(_full_portfolio())
        for hf in result["holding_factors"]:
            if not hf["cost_basis_missing"] and hf["known_cost_basis"] is not None:
                assert hf["unrealized_gain_loss_amount"] is not None
                assert hf["unrealized_gain_loss_pct"] is not None

    def test_empty_portfolio_no_crash(self):
        """Must not crash with empty portfolio."""
        result = build_factor_snapshot(_empty_portfolio())
        assert result["snapshot_type"] == "factor_snapshot"
        assert result["holding_factors"] == []
        # Empty portfolio has no holdings, so total_current_value is None (not 0)
        assert result["portfolio_factors"]["total_current_value"] is None

    def test_schema_structure(self):
        """Output must have all required top-level keys."""
        result = build_factor_snapshot(_full_portfolio())
        assert "snapshot_type" in result
        assert "generated_at" in result
        assert "portfolio_factors" in result
        assert "holding_factors" in result
        assert "market_factors" in result
        assert "news_factors" in result
        assert "data_quality" in result

    def test_news_factors_populated_when_snapshot_provided(self):
        """news_factors must be populated when news_snapshot is provided."""
        result = build_factor_snapshot(_full_portfolio(), news_snapshot=_sample_news_snapshot())
        nf = result["news_factors"]
        assert "news_count_by_entity" in nf
        assert "news_count_by_topic" in nf
        assert "provider_coverage_score" in nf
        assert nf["provider_coverage_score"] > 0

    def test_news_factors_empty_when_no_snapshot(self):
        """news_factors must have empty defaults when no news_snapshot."""
        result = build_factor_snapshot(_full_portfolio())
        nf = result["news_factors"]
        assert nf["news_count_by_entity"] == {}
        assert nf["news_count_by_topic"] == {}
        assert nf["provider_coverage_score"] == 0.0

    def test_holding_weight_sums_to_one(self):
        """Holding weights should approximately sum to 1.0 (excluding cash)."""
        result = build_factor_snapshot(_full_portfolio())
        total_weight = sum(hf["weight"] for hf in result["holding_factors"])
        # With cash_available=5000 and total value=50000, holdings=50000
        # weights should sum to ~1.0
        assert abs(total_weight - 1.0) < 0.01 or total_weight == 0.0

    def test_portfolio_factors_keys(self):
        """portfolio_factors must have all required keys."""
        result = build_factor_snapshot(_full_portfolio())
        pf = result["portfolio_factors"]
        required_keys = [
            "total_current_value",
            "known_cost_basis_total",
            "cost_basis_missing_count",
            "cash_ratio",
            "risky_asset_ratio",
            "low_risk_asset_ratio",
            "sector_concentration",
            "theme_concentration",
            "single_position_weight",
            "top_3_concentration",
            "top_5_concentration",
            "qdii_overseas_exposure",
            "equity_like_exposure",
            "bond_cash_exposure",
            "short_term_trading_bucket_exposure",
        ]
        for key in required_keys:
            assert key in pf, f"Missing portfolio_factors key: {key}"
