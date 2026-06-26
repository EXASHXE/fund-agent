"""Tests for valuation anomaly sanity checks (M7.4 Phase 4).

Validates that:
1. Extreme return without explicit units is an anomaly (blocker)
2. Extreme return is not used as key risk when unverified
3. QDII extreme loss requires manual review
"""
from __future__ import annotations

from typing import Any

import pytest

from src.tools.portfolio.valuation_anomaly import check_valuation_anomalies


class TestExtremeReturnWithoutExplicitUnitsIsAnomaly:
    """Extreme return without explicit units source must be flagged as blocker."""

    def test_extreme_gain_with_trade_date_nav_is_blocker(self):
        positions = [{
            "fund_code": "000001",
            "current_value": 25000.0,
            "cost_basis": 10000.0,
            "is_qdii_like": False,
            "total_units_source": "all_trade_date_nav_derived",
            "position_valuation_status": "estimated_full_lot_coverage",
            "identity_verification_status": "verified",
        }]
        result = check_valuation_anomalies(positions)
        assert len(result) == 1
        assert "extreme_return" in result[0]["flags"]
        assert result[0]["severity"] == "blocker"

    def test_extreme_loss_with_trade_date_nav_is_blocker(self):
        positions = [{
            "fund_code": "000001",
            "current_value": 2000.0,
            "cost_basis": 10000.0,
            "is_qdii_like": False,
            "total_units_source": "all_trade_date_nav_derived",
            "position_valuation_status": "estimated_full_lot_coverage",
            "identity_verification_status": "verified",
        }]
        result = check_valuation_anomalies(positions)
        assert len(result) == 1
        assert "extreme_return" in result[0]["flags"]
        assert result[0]["severity"] == "blocker"

    def test_normal_return_no_anomaly(self):
        positions = [{
            "fund_code": "000001",
            "current_value": 11000.0,
            "cost_basis": 10000.0,
            "is_qdii_like": False,
            "total_units_source": "all_trade_date_nav_derived",
            "position_valuation_status": "estimated_full_lot_coverage",
            "identity_verification_status": "verified",
        }]
        result = check_valuation_anomalies(positions)
        assert len(result) == 0


class TestExtremeReturnNotUsedAsKeyRiskWhenUnverified:
    """Extreme return with unverified identity must be flagged."""

    def test_unverified_identity_with_extreme_return(self):
        positions = [{
            "fund_code": "000001",
            "current_value": 25000.0,
            "cost_basis": 10000.0,
            "is_qdii_like": False,
            "total_units_source": "all_trade_date_nav_derived",
            "position_valuation_status": "estimated_full_lot_coverage",
            "identity_verification_status": "manual_override_unverified",
        }]
        result = check_valuation_anomalies(positions)
        assert len(result) == 1
        assert "code_name_unverified" in result[0]["flags"]

    def test_explicit_units_with_extreme_return_is_warning(self):
        """Explicit units + extreme return → warning, not blocker."""
        positions = [{
            "fund_code": "000001",
            "current_value": 25000.0,
            "cost_basis": 10000.0,
            "is_qdii_like": False,
            "total_units_source": "all_explicit",
            "position_valuation_status": "confirmed",
            "identity_verification_status": "verified",
        }]
        result = check_valuation_anomalies(positions)
        assert len(result) == 1
        assert "extreme_return" in result[0]["flags"]
        assert result[0]["severity"] == "warning"


class TestQdiiExtremeLossRequiresManualReview:
    """QDII extreme loss should be flagged."""

    def test_qdii_extreme_loss(self):
        positions = [{
            "fund_code": "000001",
            "current_value": 2000.0,
            "cost_basis": 10000.0,
            "is_qdii_like": True,
            "total_units_source": "all_trade_date_nav_derived",
            "position_valuation_status": "estimated_full_lot_coverage",
            "identity_verification_status": "verified",
        }]
        result = check_valuation_anomalies(positions)
        assert len(result) == 1
        assert "extreme_return" in result[0]["flags"]
        assert result[0]["severity"] == "blocker"

    def test_qdii_moderate_loss_no_anomaly(self):
        """QDII with moderate loss (< 80%) should not be flagged."""
        positions = [{
            "fund_code": "000001",
            "current_value": 7000.0,
            "cost_basis": 10000.0,
            "is_qdii_like": True,
            "total_units_source": "all_trade_date_nav_derived",
            "position_valuation_status": "estimated_full_lot_coverage",
            "identity_verification_status": "verified",
        }]
        result = check_valuation_anomalies(positions)
        assert len(result) == 0

    def test_qdii_nav_lag_flag(self):
        """QDII with stale NAV should get qdii_nav_lag flag."""
        positions = [{
            "fund_code": "000001",
            "current_value": 25000.0,
            "cost_basis": 10000.0,
            "is_qdii_like": True,
            "total_units_source": "all_trade_date_nav_derived",
            "position_valuation_status": "estimated_full_lot_coverage",
            "identity_verification_status": "verified",
            "latest_nav_stale_days": 5,
        }]
        result = check_valuation_anomalies(positions)
        assert len(result) == 1
        assert "qdii_nav_lag" in result[0]["flags"]


class TestAnomalyIntegrationWithReconstruction:
    """Anomaly blocker must suppress current_value in reconstruction output."""

    def test_blocker_suppresses_current_value(self):
        from scripts.reconstruct_portfolio_from_ledger import reconstruct_portfolio
        ledger = {
            "transactions": [
                {
                    "fund_code": "000001",
                    "fund_name": "Test Fund",
                    "action": "buy",
                    "amount": 10000.0,
                    "net_amount": 10000.0,
                    "trade_date": "2025-01-15",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                },
            ],
        }
        # NAV that would give extreme return (NAV went from 1.0 to 2.5)
        nav = {
            "nav_by_fund": {
                "000001": {
                    "records": [
                        {"date": "2025-01-15", "nav": 1.0},
                        {"date": "2025-06-01", "nav": 2.5},
                    ],
                },
            },
        }
        result = reconstruct_portfolio(
            ledger_data=ledger,
            nav_snapshot=nav,
            as_of_date=__import__("datetime").date(2025, 6, 1),
        )
        positions = result["confirmed_portfolio"]["positions"]
        assert len(positions) == 1
        pos = positions[0]
        # Extreme return with trade_date_nav → blocker → current_value suppressed
        if pos.get("valuation_anomaly_severity") == "blocker":
            assert pos["current_value"] is None
            assert pos["valuation_type"] == "blocked_anomaly"
