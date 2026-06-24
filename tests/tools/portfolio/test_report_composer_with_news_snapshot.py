"""Tests for news_snapshot integration in report composition."""

from __future__ import annotations

import json

from src.tools.portfolio.report_composer import (
    compose_personal_fund_report,
    render_report_markdown,
)


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


def _news_snapshot_with_items():
    return {
        "items": [
            {
                "source": "reuters",
                "title": "Tech sector rallies on earnings",
                "url": "https://example.com/news/1",
                "entity": "tech_sector",
                "topic": "earnings",
            },
            {
                "source": "bloomberg",
                "title": "Bond yields rise",
                "url": "https://example.com/news/2",
                "entity": "bond_market",
                "topic": "rates",
            },
        ],
        "provider_status": {
            "available_providers": ["reuters", "bloomberg"],
            "failed_providers": [],
        },
        "coverage_gaps": [],
    }


def _news_snapshot_with_coverage_gaps():
    return {
        "items": [
            {
                "source": "reuters",
                "title": "Partial coverage only",
                "url": "https://example.com/news/3",
                "entity": "market",
            },
        ],
        "provider_status": {
            "available_providers": ["reuters"],
            "failed_providers": ["bloomberg"],
        },
        "coverage_gaps": ["sentiment", "social_media"],
    }


class TestNewsAndEventsSectionPresent:
    """When news_snapshot is present with items, the section should have status OK or PARTIAL."""

    def test_news_snapshot_present_produces_section_with_ok_status(self):
        artifacts = _base_artifacts(news_snapshot=_news_snapshot_with_items())
        report = compose_personal_fund_report(artifacts)
        section = _find_section(report, "news_and_events")
        assert section is not None
        assert section["status"] in {"OK", "PARTIAL"}

    def test_news_snapshot_with_gaps_produces_partial_status(self):
        artifacts = _base_artifacts(news_snapshot=_news_snapshot_with_coverage_gaps())
        report = compose_personal_fund_report(artifacts)
        section = _find_section(report, "news_and_events")
        assert section is not None
        assert section["status"] == "PARTIAL"

    def test_news_items_rendered_with_source_title_url(self):
        artifacts = _base_artifacts(news_snapshot=_news_snapshot_with_items())
        report = compose_personal_fund_report(artifacts)
        section = _find_section(report, "news_and_events")
        assert section is not None
        bullets_text = " ".join(section["bullets"])
        # Source should appear
        assert "reuters" in bullets_text
        # Title should appear
        assert "Tech sector rallies on earnings" in bullets_text
        # URL should appear
        assert "https://example.com/news/1" in bullets_text

    def test_news_snapshot_shows_provider_status(self):
        artifacts = _base_artifacts(news_snapshot=_news_snapshot_with_items())
        report = compose_personal_fund_report(artifacts)
        section = _find_section(report, "news_and_events")
        assert section is not None
        bullets_text = " ".join(section["bullets"])
        assert "reuters" in bullets_text
        assert "bloomberg" in bullets_text

    def test_news_snapshot_shows_coverage_gaps(self):
        artifacts = _base_artifacts(news_snapshot=_news_snapshot_with_coverage_gaps())
        report = compose_personal_fund_report(artifacts)
        section = _find_section(report, "news_and_events")
        assert section is not None
        bullets_text = " ".join(section["bullets"])
        assert "sentiment" in bullets_text or "social_media" in bullets_text


class TestNewsAndEventsSectionAbsent:
    """When news_snapshot is absent, the section should have status MISSING."""

    def test_news_snapshot_absent_produces_missing_status(self):
        artifacts = _base_artifacts()
        report = compose_personal_fund_report(artifacts)
        section = _find_section(report, "news_and_events")
        assert section is not None
        assert section["status"] == "MISSING"

    def test_news_snapshot_absent_mentions_not_provided(self):
        artifacts = _base_artifacts()
        report = compose_personal_fund_report(artifacts)
        section = _find_section(report, "news_and_events")
        assert section is not None
        limitations_text = " ".join(section.get("limitations", []))
        assert "not provided" in limitations_text.lower() or "not fabricated" in limitations_text.lower()

    def test_news_snapshot_empty_dict_produces_partial(self):
        artifacts = _base_artifacts(news_snapshot={})
        report = compose_personal_fund_report(artifacts)
        section = _find_section(report, "news_and_events")
        assert section is not None
        # Empty dict means snapshot is present but has no items
        assert section["status"] in {"PARTIAL", "MISSING"}


class TestNewsAndEventsNoApiKeys:
    """No API keys or Authorization headers should appear in rendered output."""

    def test_no_api_keys_in_rendered_output(self):
        snapshot = _news_snapshot_with_items()
        # Add a sensitive field that should NOT appear
        snapshot["api_key"] = "sk-secret-key-12345"
        snapshot["authorization"] = "Bearer token-abc"
        artifacts = _base_artifacts(news_snapshot=snapshot)
        report = compose_personal_fund_report(artifacts)
        rendered = render_report_markdown(report)
        assert "sk-secret-key-12345" not in rendered
        assert "Bearer token-abc" not in rendered

    def test_no_api_keys_in_json_output(self):
        snapshot = _news_snapshot_with_items()
        snapshot["api_key"] = "sk-secret-key-12345"
        artifacts = _base_artifacts(news_snapshot=snapshot)
        report = compose_personal_fund_report(artifacts)
        section = _find_section(report, "news_and_events")
        assert section is not None
        dumped = json.dumps(section)
        # The builder should not propagate api_key into bullets/limitations
        assert "sk-secret-key-12345" not in dumped


def _find_section(report: dict, section_id: str) -> dict | None:
    for section in report["report_sections"]:
        if section.get("id") == section_id:
            return section
    return None
