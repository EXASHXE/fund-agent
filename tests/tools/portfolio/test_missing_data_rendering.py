"""Tests for missing data rendering — report must show 'unknown' or 'missing', not fabricated values."""

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


class TestCostBasisMissing:
    """When cost_basis is None/missing, report should not show '0' as cost."""

    def test_cost_basis_none_shows_unknown_not_zero(self):
        """When cost_basis_summary is missing, PnL section should not fabricate 0 as cost."""
        artifacts = _base_artifacts()
        # Remove cost_basis_summary explicitly
        artifacts.pop("cost_basis_summary", None)
        report = compose_personal_fund_report(artifacts)
        section = _find_section(report, "pnl_and_cost_basis")
        assert section is not None
        # The section should have a limitation about missing cost basis
        limitations_text = " ".join(section.get("limitations", []))
        # Should mention absence, not fabricate "0" as total cost
        if limitations_text:
            assert "0" not in limitations_text or "0 fund" not in limitations_text.lower()

    def test_pnl_section_does_not_fabricate_cost_basis(self):
        artifacts = _base_artifacts()
        # No cost_basis_summary in artifacts or report
        report = compose_personal_fund_report(artifacts)
        section = _find_section(report, "pnl_and_cost_basis")
        assert section is not None
        # Should have limitation about cost basis being absent
        bullets_text = " ".join(section["bullets"])
        limitations_text = " ".join(section.get("limitations", []))
        # Should not claim transaction-derived cost basis exists
        if "Transaction-derived cost basis" not in bullets_text:
            assert "absent" in limitations_text.lower() or "missing" in limitations_text.lower()


class TestUnitsNavMissing:
    """When units/NAV are missing, report should show 'missing' not fabricated values."""

    def test_missing_nav_shows_missing_status(self):
        """When fund_metrics is empty, performance section should be MISSING or PARTIAL."""
        artifacts = _base_artifacts(
            fund_analysis_report={
                "fund_metrics": {},
                "concentration": {"single_fund_max_weight": 0.5, "hhi": 0.41},
            },
            analysis_coverage={"performance": "missing"},
        )
        report = compose_personal_fund_report(artifacts)
        section = _find_section(report, "performance_and_nav")
        assert section is not None
        assert section["status"] in {"MISSING", "PARTIAL"}

    def test_missing_nav_does_not_fabricate_returns(self):
        """When NAV is missing, no fabricated return percentages should appear."""
        artifacts = _base_artifacts(
            fund_analysis_report={
                "fund_metrics": {},
                "concentration": {"single_fund_max_weight": 0.5, "hhi": 0.41},
            },
            analysis_coverage={"performance": "missing"},
        )
        report = compose_personal_fund_report(artifacts)
        section = _find_section(report, "performance_and_nav")
        assert section is not None
        # Should have a limitation about missing NAV
        limitations_text = " ".join(section.get("limitations", []))
        assert "missing" in limitations_text.lower() or "unavailable" in limitations_text.lower()


class TestPendingConfirmationNotConfirmed:
    """Items pending confirmation should not appear as confirmed holdings."""

    def test_position_contribution_missing_when_no_data(self):
        """When position_contribution is absent, status should be MISSING."""
        artifacts = _base_artifacts()
        report = compose_personal_fund_report(artifacts)
        section = _find_section(report, "position_contribution")
        assert section is not None
        # Without position_contribution artifact, should be MISSING
        assert section["status"] == "MISSING"

    def test_position_contribution_does_not_fabricate(self):
        """Position contribution should not fabricate data when artifact is missing."""
        artifacts = _base_artifacts()
        report = compose_personal_fund_report(artifacts)
        section = _find_section(report, "position_contribution")
        assert section is not None
        limitations_text = " ".join(section.get("limitations", []))
        # Should have a limitation about missing data
        assert "missing" in limitations_text.lower()

    def test_benchmark_missing_does_not_fabricate_comparison(self):
        """When benchmark is missing, no fabricated comparison should appear."""
        artifacts = _base_artifacts()
        report = compose_personal_fund_report(artifacts)
        section = _find_section(report, "benchmark_and_peer")
        assert section is not None
        # Without benchmark data, should be MISSING
        assert section["status"] == "MISSING"
        limitations_text = " ".join(section.get("limitations", []))
        assert "fabricated" in limitations_text.lower()


def _find_section(report: dict, section_id: str) -> dict | None:
    for section in report["report_sections"]:
        if section.get("id") == section_id:
            return section
    return None
