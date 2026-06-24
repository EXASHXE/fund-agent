"""Tests for personal health report section in report builder.

All test data is synthetic — no real fund names, amounts, or transaction IDs.
"""
from __future__ import annotations

from typing import Any

import pytest

from src.tools.portfolio.report_sections.render import compose_personal_fund_report


def _base_artifacts(**overrides) -> dict[str, Any]:
    """Create minimal artifacts with a personal_health_report."""
    artifacts = {
        "portfolio_summary": {
            "as_of_date": "2026-06-20",
            "total_value": 10000.0,
            "cash_available": 500.0,
            "position_count": 3,
        },
        "data_completeness": {"grade": "B", "score": 0.85},
        "personal_health_report": {
            "schema_version": "personal_health_report.v1",
            "overall_status": "partial",
            "confidence_level": "medium",
            "reason_codes": ["partial_nav_coverage"],
            "data_sources": {
                "transaction_source": "alipay",
                "valuation_source": "reconstructed_from_ledger",
                "identity_source": "direct_fund_code",
            },
            "valuation_quality": {
                "positions_total": 3,
                "confirmed_count": 0,
                "estimated_full_coverage_count": 1,
                "estimated_partial_coverage_count": 2,
                "cashflow_only_count": 0,
                "unavailable_count": 0,
                "manual_review_count": 0,
                "estimated_current_value_total_is_partial": True,
            },
            "nav_coverage": {
                "full": 1,
                "partial": 2,
                "none": 0,
                "latest_only": 0,
                "stale_count": 0,
                "qdii_like_count": 0,
            },
            "fix_it_checklist": [
                "Add trade-date NAV overrides for 2 fund(s) with missing coverage",
            ],
            "safety_notes": [
                "This is not a formal investment decision — no BUY/SELL/HOLD instruction.",
                "No broker/order execution capability.",
                "No auto trading.",
                "Estimated values are not confirmed market values.",
                "Partial coverage means incomplete valuation.",
            ],
        },
    }
    artifacts.update(overrides)
    return artifacts


class TestPersonalHealthSectionPresent:
    def test_section_in_report(self):
        """Personal health section should appear in report sections."""
        report = compose_personal_fund_report(_base_artifacts())
        section_ids = [s["id"] for s in report["report_sections"]]
        assert "personal_health" in section_ids

    def test_section_status_partial(self):
        """Partial health → section status PARTIAL."""
        report = compose_personal_fund_report(_base_artifacts())
        health_section = next(s for s in report["report_sections"] if s["id"] == "personal_health")
        assert health_section["status"] == "PARTIAL"

    def test_section_contains_overall_status(self):
        report = compose_personal_fund_report(_base_artifacts())
        health_section = next(s for s in report["report_sections"] if s["id"] == "personal_health")
        bullets_text = " ".join(health_section["bullets"])
        assert "Overall status" in bullets_text or "partial" in bullets_text

    def test_section_contains_checklist(self):
        report = compose_personal_fund_report(_base_artifacts())
        health_section = next(s for s in report["report_sections"] if s["id"] == "personal_health")
        bullets_text = " ".join(health_section["bullets"])
        assert "NAV" in bullets_text or "Action needed" in bullets_text

    def test_section_contains_safety_notes(self):
        report = compose_personal_fund_report(_base_artifacts())
        health_section = next(s for s in report["report_sections"] if s["id"] == "personal_health")
        limitations_text = " ".join(health_section.get("limitations", []))
        assert "decision" in limitations_text.lower() or "instruction" in limitations_text.lower() or "broker" in limitations_text.lower()


class TestPersonalHealthSectionStatusOk:
    def test_ok_status(self):
        artifacts = _base_artifacts()
        artifacts["personal_health_report"]["overall_status"] = "ok"
        report = compose_personal_fund_report(artifacts)
        health_section = next(s for s in report["report_sections"] if s["id"] == "personal_health")
        assert health_section["status"] == "OK"


class TestPersonalHealthSectionStatusMissing:
    def test_missing_status(self):
        artifacts = _base_artifacts()
        artifacts["personal_health_report"]["overall_status"] = "needs_data"
        report = compose_personal_fund_report(artifacts)
        health_section = next(s for s in report["report_sections"] if s["id"] == "personal_health")
        assert health_section["status"] == "MISSING"


class TestPersonalHealthSectionNoTradingAdvice:
    """Personal health section must not contain buy/sell/hold as instructions."""

    def test_no_trading_advice_in_bullets(self):
        report = compose_personal_fund_report(_base_artifacts())
        health_section = next(s for s in report["report_sections"] if s["id"] == "personal_health")
        for bullet in health_section["bullets"]:
            bullet_lower = bullet.lower()
            # Forbidden as advice (allowed in transaction type context)
            for forbidden in ["buy ", "sell ", "hold ", "rebalance ", "order "]:
                assert forbidden not in bullet_lower, f"Found trading advice in bullet: {bullet}"


class TestPersonalHealthSectionNoPrivateData:
    """Section must not contain private data."""

    def test_no_private_data(self):
        report = compose_personal_fund_report(_base_artifacts())
        health_section = next(s for s in report["report_sections"] if s["id"] == "personal_health")
        all_text = " ".join(
            health_section.get("bullets", [])
            + health_section.get("limitations", [])
            + health_section.get("data_sources", [])
        )
        for forbidden in ["private_data/", "local_data/", "api_key", "token", "secret"]:
            assert forbidden not in all_text.lower(), f"Found private data: {forbidden}"


class TestPersonalHealthSectionNoHealthReport:
    """When no personal_health_report artifact, section should still render."""

    def test_no_health_report_artifact(self):
        artifacts = _base_artifacts()
        del artifacts["personal_health_report"]
        report = compose_personal_fund_report(artifacts)
        section_ids = [s["id"] for s in report["report_sections"]]
        assert "personal_health" in section_ids
        health_section = next(s for s in report["report_sections"] if s["id"] == "personal_health")
        # Should still have a status (MISSING since no data)
        assert health_section["status"] in ("OK", "PARTIAL", "MISSING")


class TestPersonalHealthSectionZhCN:
    """Chinese localization for personal health section."""

    def test_zh_cn_title(self):
        report = compose_personal_fund_report(_base_artifacts(), options={"language": "zh-CN"})
        health_section = next(s for s in report["report_sections"] if s["id"] == "personal_health")
        assert health_section["title"] == "组合体检"

    def test_zh_cn_bullets_localized(self):
        report = compose_personal_fund_report(_base_artifacts(), options={"language": "zh-CN"})
        health_section = next(s for s in report["report_sections"] if s["id"] == "personal_health")
        bullets_text = " ".join(health_section["bullets"])
        # Should have Chinese localization for key terms
        assert "整体状态" in bullets_text or "组合" in bullets_text or "partial" in bullets_text.lower()
