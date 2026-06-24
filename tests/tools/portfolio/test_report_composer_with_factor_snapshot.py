"""Tests for factor_snapshot integration in report composition."""

from __future__ import annotations

from src.tools.portfolio.report_composer import compose_personal_fund_report


def _base_artifacts(**overrides):
    artifacts = {
        "portfolio_summary": {
            "as_of_date": "2026-06-01",
            "total_value": 200000,
            "cash_available": 20000,
            "position_count": 2,
            "position_weights": {"110011": 0.4, "220022": 0.5},
        },
        "position_summary": {
            "110011": {"fund_code": "110011", "current_value": 80000, "total_cost": 75000},
            "220022": {"fund_code": "220022", "current_value": 100000, "total_cost": 95000},
        },
        "pnl_summary": {
            "total_cost": 170000,
            "total_value": 180000,
            "unrealized_pnl": 10000,
            "unrealized_pnl_pct": 0.058824,
            "positions": {"110011": {"unrealized_pnl": 5000}},
        },
        "exposure_summary": {
            "fund_type_exposure": {"equity": 0.4, "bond": 0.5},
            "industry_exposure": {"industry:tech": 0.2},
            "theme_exposure": {"tag:growth": 0.4},
        },
        "risk_flags": [],
        "suggested_rebalance_plan": {"suggested_trade_plan": [], "warnings": [], "total_trade_amount": 0},
        "fund_analysis_report": {
            "fund_metrics": {"110011": {"total_return": 0.1}},
            "concentration": {"single_fund_max_weight": 0.5, "hhi": 0.41},
            "trade_budget": {
                "max_buy_amount": 10000,
                "max_sell_amount": 15000,
                "liquidity_reserve": 20000,
            },
        },
        "data_completeness": {
            "score": 0.85,
            "grade": "B",
            "available_sections": ["Portfolio Snapshot", "Fund Profiles"],
            "missing_sections": [],
            "optional_missing": ["Peer Group"],
            "limitations": [],
        },
        "analysis_coverage": {
            "performance": "available",
            "research_plan": "not_requested",
        },
        "report_limitations": ["Optional peer data is unavailable."],
    }
    artifacts.update(overrides)
    return artifacts


def _factor_snapshot_with_factors():
    return {
        "factors": {
            "momentum": 0.35,
            "value": -0.12,
            "quality": 0.28,
            "low_volatility": 0.15,
        },
        "data_quality": {
            "grade": "B",
            "coverage": 0.82,
        },
        "provider_status": {
            "available_providers": ["barra"],
        },
    }


def _factor_snapshot_empty_factors():
    return {
        "factors": {},
        "data_quality": {
            "grade": "D",
            "coverage": 0.1,
        },
    }


class TestFactorAnalysisSectionPresent:
    """When factor_snapshot is present, the section should be rendered."""

    def test_factor_snapshot_present_produces_section(self):
        artifacts = _base_artifacts(factor_snapshot=_factor_snapshot_with_factors())
        report = compose_personal_fund_report(artifacts)
        section = _find_section(report, "factor_analysis")
        assert section is not None
        assert section["status"] in {"OK", "PARTIAL"}

    def test_factor_snapshot_renders_factor_dimensions(self):
        artifacts = _base_artifacts(factor_snapshot=_factor_snapshot_with_factors())
        report = compose_personal_fund_report(artifacts)
        section = _find_section(report, "factor_analysis")
        assert section is not None
        bullets_text = " ".join(section["bullets"])
        assert "momentum" in bullets_text
        assert "value" in bullets_text
        assert "4 factor dimension" in bullets_text

    def test_factor_snapshot_renders_data_quality(self):
        artifacts = _base_artifacts(factor_snapshot=_factor_snapshot_with_factors())
        report = compose_personal_fund_report(artifacts)
        section = _find_section(report, "factor_analysis")
        assert section is not None
        bullets_text = " ".join(section["bullets"])
        assert "grade" in bullets_text.lower() or "B" in bullets_text
        assert "coverage" in bullets_text.lower() or "0.82" in bullets_text

    def test_factor_snapshot_empty_factors_produces_partial(self):
        artifacts = _base_artifacts(factor_snapshot=_factor_snapshot_empty_factors())
        report = compose_personal_fund_report(artifacts)
        section = _find_section(report, "factor_analysis")
        assert section is not None
        assert section["status"] == "PARTIAL"


class TestFactorAnalysisSectionAbsent:
    """When factor_snapshot is absent, the section should have status MISSING."""

    def test_factor_snapshot_absent_produces_missing_status(self):
        artifacts = _base_artifacts()
        report = compose_personal_fund_report(artifacts)
        section = _find_section(report, "factor_analysis")
        assert section is not None
        assert section["status"] == "MISSING"

    def test_factor_snapshot_absent_mentions_not_provided(self):
        artifacts = _base_artifacts()
        report = compose_personal_fund_report(artifacts)
        section = _find_section(report, "factor_analysis")
        assert section is not None
        limitations_text = " ".join(section.get("limitations", []))
        assert "not provided" in limitations_text.lower() or "not fabricated" in limitations_text.lower()


class TestFactorAnalysisNoFakePrecision:
    """Factor analysis should not fabricate data or fake precision."""

    def test_no_fake_precision_in_factor_values(self):
        """Factor values should come from the snapshot, not be fabricated."""
        snapshot = _factor_snapshot_with_factors()
        artifacts = _base_artifacts(factor_snapshot=snapshot)
        report = compose_personal_fund_report(artifacts)
        section = _find_section(report, "factor_analysis")
        assert section is not None
        # Values should match what was provided
        bullets_text = " ".join(section["bullets"])
        # 0.3500 is the _fixed(0.35, 4) representation
        assert "0.3500" in bullets_text

    def test_no_fabricated_factors_when_snapshot_empty(self):
        """When factor snapshot has no factors, no fabricated factor names should appear."""
        artifacts = _base_artifacts(factor_snapshot=_factor_snapshot_empty_factors())
        report = compose_personal_fund_report(artifacts)
        section = _find_section(report, "factor_analysis")
        assert section is not None
        # Should not fabricate factor names like "alpha", "beta" etc
        bullets_text = " ".join(section["bullets"]).lower()
        fabricated_names = ["alpha", "beta", "gamma", "size_factor", "market_factor"]
        for name in fabricated_names:
            assert name not in bullets_text


def _find_section(report: dict, section_id: str) -> dict | None:
    for section in report["report_sections"]:
        if section.get("id") == section_id:
            return section
    return None
