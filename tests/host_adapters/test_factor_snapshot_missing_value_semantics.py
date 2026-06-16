"""Validate factor snapshot current_value=0 heuristic.

When most holdings have current_value=0 (explicitly zero, not None),
the factor snapshot should treat this as "likely missing" rather than
"known to be zero". The 80% heuristic triggers when >=80% of holdings
have current_value that is 0 or None.
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


def _all_zero_portfolio() -> dict:
    """Portfolio where ALL holdings have current_value=0 — the real-world bug case."""
    return {
        "cash_available": 0,
        "holdings": [
            {
                "fund_code": "001234",
                "fund_name": "基金A",
                "current_value": 0,
                "cost_basis": 10000,
                "sector": "股票",
            },
            {
                "fund_code": "005678",
                "fund_name": "基金B",
                "current_value": 0,
                "cost_basis": 20000,
                "sector": "债券",
            },
            {
                "fund_code": "009012",
                "fund_name": "基金C",
                "current_value": 0,
                "cost_basis": 15000,
                "sector": "混合",
            },
        ],
    }


def _most_zero_portfolio() -> dict:
    """Portfolio where 80%+ holdings have current_value=0 but one has a real value."""
    return {
        "cash_available": 0,
        "holdings": [
            {"fund_code": "001", "fund_name": "基金1", "current_value": 0, "sector": "股票"},
            {"fund_code": "002", "fund_name": "基金2", "current_value": 0, "sector": "债券"},
            {"fund_code": "003", "fund_name": "基金3", "current_value": 0, "sector": "混合"},
            {"fund_code": "004", "fund_name": "基金4", "current_value": 0, "sector": "QDII"},
            {"fund_code": "005", "fund_name": "基金5", "current_value": 5000, "sector": "货币"},
        ],
    }


def _mixed_none_and_zero_portfolio() -> dict:
    """Portfolio with mix of None and 0 current_value — both should count as likely-missing."""
    return {
        "cash_available": 0,
        "holdings": [
            {"fund_code": "001", "fund_name": "基金1", "current_value": 0, "sector": "股票"},
            {"fund_code": "002", "fund_name": "基金2", "sector": "债券"},  # None
            {"fund_code": "003", "fund_name": "基金3", "current_value": 0, "sector": "混合"},
            {"fund_code": "004", "fund_name": "基金4", "sector": "QDII"},  # None
            {"fund_code": "005", "fund_name": "基金5", "current_value": 0, "sector": "货币"},
        ],
    }


def _normal_portfolio() -> dict:
    """Portfolio with real current_value — heuristic should NOT trigger."""
    return {
        "cash_available": 5000,
        "holdings": [
            {
                "fund_code": "002168",
                "fund_name": "半导体ETF",
                "current_value": 30000,
                "cost_basis": 25000,
                "sector": "电子",
            },
            {
                "fund_code": "007540",
                "fund_name": "短债基金",
                "current_value": 20000,
                "cost_basis": 19500,
                "sector": "债券",
            },
        ],
    }


def _below_threshold_portfolio() -> dict:
    """Portfolio where <80% are zero — heuristic should NOT trigger."""
    return {
        "cash_available": 0,
        "holdings": [
            {"fund_code": "001", "fund_name": "基金1", "current_value": 0, "sector": "股票"},
            {"fund_code": "002", "fund_name": "基金2", "current_value": 50000, "sector": "债券"},
            {"fund_code": "003", "fund_name": "基金3", "current_value": 30000, "sector": "混合"},
            {"fund_code": "004", "fund_name": "基金4", "current_value": 20000, "sector": "QDII"},
            {"fund_code": "005", "fund_name": "基金5", "current_value": 10000, "sector": "货币"},
        ],
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFactorSnapshotCurrentValueZeroHeuristic:
    """Validate the 80% heuristic for current_value=0."""

    def test_all_zero_triggers_likely_missing(self):
        """When all holdings have current_value=0, current_value_likely_missing=True."""
        result = build_factor_snapshot(_all_zero_portfolio())
        assert result["data_quality"]["current_value_likely_missing"] is True

    def test_all_zero_sets_total_current_value_none(self):
        """When heuristic triggers, total_current_value must be None."""
        result = build_factor_snapshot(_all_zero_portfolio())
        assert result["portfolio_factors"]["total_current_value"] is None

    def test_all_zero_zero_value_count(self):
        """zero_value_count must reflect holdings with current_value=0."""
        result = build_factor_snapshot(_all_zero_portfolio())
        assert result["data_quality"]["zero_value_count"] == 3

    def test_all_zero_current_value_missing_count(self):
        """current_value_missing_count must reflect holdings with current_value=None."""
        result = build_factor_snapshot(_all_zero_portfolio())
        # All have current_value=0 (not None), so missing_count=0
        assert result["data_quality"]["current_value_missing_count"] == 0

    def test_most_zero_triggers_likely_missing(self):
        """When 80%+ holdings have current_value=0, likely_missing=True."""
        result = build_factor_snapshot(_most_zero_portfolio())
        assert result["data_quality"]["current_value_likely_missing"] is True

    def test_most_zero_sets_total_current_value_none(self):
        """When heuristic triggers, total_current_value must be None."""
        result = build_factor_snapshot(_most_zero_portfolio())
        assert result["portfolio_factors"]["total_current_value"] is None

    def test_mixed_none_and_zero_triggers_likely_missing(self):
        """Mix of None and 0 values should both count toward the 80% threshold."""
        result = build_factor_snapshot(_mixed_none_and_zero_portfolio())
        # 5 holdings, all are either 0 or None → 100% → triggers
        assert result["data_quality"]["current_value_likely_missing"] is True

    def test_mixed_none_and_zero_counts(self):
        """zero_value_count and current_value_missing_count must be tracked separately."""
        result = build_factor_snapshot(_mixed_none_and_zero_portfolio())
        # 3 holdings with current_value=0, 2 with None
        assert result["data_quality"]["zero_value_count"] == 3
        assert result["data_quality"]["current_value_missing_count"] == 2

    def test_normal_portfolio_no_likely_missing(self):
        """Normal portfolio with real values must NOT trigger the heuristic."""
        result = build_factor_snapshot(_normal_portfolio())
        assert result["data_quality"].get("current_value_likely_missing") is not True

    def test_normal_portfolio_total_current_value_present(self):
        """Normal portfolio must have total_current_value computed."""
        result = build_factor_snapshot(_normal_portfolio())
        assert result["portfolio_factors"]["total_current_value"] == 50000.0

    def test_below_threshold_no_likely_missing(self):
        """Portfolio with <80% zero values must NOT trigger the heuristic."""
        result = build_factor_snapshot(_below_threshold_portfolio())
        assert result["data_quality"].get("current_value_likely_missing") is not True

    def test_below_threshold_total_current_value_computed(self):
        """Below-threshold portfolio must have total_current_value computed."""
        result = build_factor_snapshot(_below_threshold_portfolio())
        assert result["portfolio_factors"]["total_current_value"] == 110000.0

    def test_uncertainty_note_when_likely_missing(self):
        """When likely_missing=True, uncertainty_note must be present."""
        result = build_factor_snapshot(_all_zero_portfolio())
        assert result["data_quality"]["uncertainty_note"] is not None
        assert (
            "市值" in result["data_quality"]["uncertainty_note"] or "缺失" in result["data_quality"]["uncertainty_note"]
        )

    def test_holding_factors_current_value_zero_stays_zero(self):
        """Individual holding current_value=0 must stay 0.0 in holding_factors."""
        result = build_factor_snapshot(_all_zero_portfolio())
        for hf in result["holding_factors"]:
            assert hf["current_value"] == 0.0

    def test_holding_factors_current_value_missing_flag(self):
        """Holdings with current_value=0 should NOT have current_value_missing=True."""
        result = build_factor_snapshot(_all_zero_portfolio())
        for hf in result["holding_factors"]:
            assert hf["current_value_missing"] is False

    def test_holding_weight_none_when_likely_missing(self):
        """When heuristic triggers, holding weights must be None (cannot compute)."""
        result = build_factor_snapshot(_all_zero_portfolio())
        for hf in result["holding_factors"]:
            assert hf["weight"] is None

    def test_empty_portfolio_no_likely_missing(self):
        """Empty portfolio should not trigger likely_missing (no holdings to evaluate)."""
        result = build_factor_snapshot({"holdings": []})
        # Empty portfolio: no holdings, so no heuristic needed
        assert result["data_quality"].get("current_value_likely_missing") is not True
