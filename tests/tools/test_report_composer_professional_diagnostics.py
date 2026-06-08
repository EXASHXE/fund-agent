"""Report composer tests for professional diagnostics section."""

from __future__ import annotations

from typing import Any

from src.tools.portfolio.report_composer import (
    compose_personal_fund_report,
    render_report_markdown,
)


def _compose(artifacts: dict[str, Any]) -> dict[str, Any]:
    return compose_personal_fund_report(artifacts, warnings=[])


def _markdown(artifacts: dict[str, Any]) -> str:
    composed = _compose(artifacts)
    return render_report_markdown(composed)


def _section_by_id(sections: list[dict[str, Any]], sid: str) -> dict:
    for s in sections:
        if s.get("id") == sid:
            return s
    return {}


def test_report_includes_professional_diagnostics_section_when_diagnostics_present():
    artifacts = {
        "fund_analysis_report": {},
        "professional_diagnostics": {
            "cash_budget_diagnostics": {
                "cash_ratio": 0.05,
                "liquidity_reserve_pct": 0.10,
                "short_term_budget_status": "ok",
            },
            "professional_warnings": [],
        },
        "data_completeness": {"grade": "B", "score": 0.85},
        "analysis_coverage": {},
        "report_limitations": [],
    }
    composed = _compose(artifacts)
    sections = composed["report_sections"]
    prof = _section_by_id(sections, "professional_diagnostics")
    assert prof, "Missing professional_diagnostics section"
    assert prof["status"] == "OK"
    bullets = prof.get("bullets", [])
    assert any("Cash ratio" in b for b in bullets)


def test_report_marks_professional_diagnostics_missing_when_absent():
    artifacts = {
        "fund_analysis_report": {},
        "data_completeness": {"grade": "B", "score": 0.85},
        "analysis_coverage": {},
        "report_limitations": [],
    }
    composed = _compose(artifacts)
    prof = _section_by_id(composed["report_sections"], "professional_diagnostics")
    assert prof["status"] == "MISSING"
    assert any("host-supplied" in l.lower() for l in prof.get("limitations", []))


def test_report_section_contains_redemption_fee_bullets():
    artifacts = {
        "fund_analysis_report": {},
        "redemption_fee_risk": {
            "as_of_date": "2026-01-01",
            "affected_funds": [
                {
                    "fund_code": "F001", "fund_name": "Test Fund",
                    "estimated_recent_amount": 10000.0,
                    "threshold_days": 7, "fee_pct": 0.015,
                    "warning": "test warning",
                }
            ],
            "summary": {"affected_count": 1, "highest_fee_pct": 0.015},
        },
        "professional_diagnostics": {
            "redemption_fee_risk": {
                "as_of_date": "2026-01-01",
                "affected_funds": [
                    {
                        "fund_code": "F001", "fund_name": "Test Fund",
                        "estimated_recent_amount": 10000.0,
                        "threshold_days": 7, "fee_pct": 0.015,
                        "warning": "test warning",
                    }
                ],
                "summary": {"affected_count": 1, "highest_fee_pct": 0.015},
            },
            "professional_warnings": ["test warning"],
        },
        "data_completeness": {"grade": "B", "score": 0.85},
        "analysis_coverage": {},
        "report_limitations": [],
    }
    composed = _compose(artifacts)
    prof = _section_by_id(composed["report_sections"], "professional_diagnostics")
    bullets = prof.get("bullets", [])
    assert any("redemption" in b.lower() or "fee" in b.lower() for b in bullets)
    assert prof["status"] == "PARTIAL"


def test_report_section_contains_overlap_bullets():
    artifacts = {
        "fund_analysis_report": {},
        "overlap_diagnostics": {
            "overlapping_holdings": [{"holding_name": "Shared Stock A", "funds": ["F001", "F002"]}],
            "overlapping_themes": [],
            "overlapping_regions": [],
            "summary": {"overlap_count": 1, "highest_overlap_theme": "Shared Stock A"},
        },
        "professional_diagnostics": {
            "overlap_diagnostics": {
                "overlapping_holdings": [{"holding_name": "Shared Stock A", "funds": ["F001", "F002"]}],
                "overlapping_themes": [],
                "overlapping_regions": [],
                "summary": {"overlap_count": 1, "highest_overlap_theme": "Shared Stock A"},
            },
            "professional_warnings": [],
        },
        "data_completeness": {"grade": "B", "score": 0.85},
        "analysis_coverage": {},
        "report_limitations": [],
    }
    composed = _compose(artifacts)
    prof = _section_by_id(composed["report_sections"], "professional_diagnostics")
    bullets = prof.get("bullets", [])
    assert any("overlap" in b.lower() for b in bullets)


def test_markdown_contains_professional_diagnostics_heading():
    artifacts = {
        "fund_analysis_report": {},
        "professional_diagnostics": {
            "professional_warnings": [],
        },
        "data_completeness": {"grade": "B", "score": 0.85},
        "analysis_coverage": {},
        "report_limitations": [],
    }
    md = _markdown(artifacts)
    assert "## Professional diagnostics" in md


def test_markdown_does_not_contain_formal_decision_headings():
    artifacts = {
        "fund_analysis_report": {},
        "professional_diagnostics": {
            "cash_budget_diagnostics": {"cash_ratio": 0.05},
            "professional_warnings": [],
        },
        "data_completeness": {"grade": "B", "score": 0.85},
        "analysis_coverage": {},
        "report_limitations": [],
    }
    md = _markdown(artifacts).lower()
    assert "## decision" not in md
    assert "## decisions" not in md
    assert "## execution ledger" not in md


def test_theme_overweight_bullets_appear():
    artifacts = {
        "fund_analysis_report": {},
        "theme_overweight_diagnostics": {
            "overweight_themes": [
                {"theme": "ai", "weight": 0.45, "limit": 0.35, "excess": 0.10, "funds": ["F001"]},
            ],
            "summary": {"overweight_count": 1, "max_theme": "ai", "max_theme_weight": 0.45},
        },
        "professional_diagnostics": {
            "theme_overweight_diagnostics": {
                "overweight_themes": [
                    {"theme": "ai", "weight": 0.45, "limit": 0.35, "excess": 0.10, "funds": ["F001"]},
                ],
                "summary": {"overweight_count": 1, "max_theme": "ai", "max_theme_weight": 0.45},
            },
            "professional_warnings": ["Theme 'ai' at 45.0% exceeds limit 35.0% by 10.0%"],
        },
        "data_completeness": {"grade": "B", "score": 0.85},
        "analysis_coverage": {},
        "report_limitations": [],
    }
    composed = _compose(artifacts)
    prof = _section_by_id(composed["report_sections"], "professional_diagnostics")
    bullets = prof.get("bullets", [])
    assert any("theme" in b.lower() for b in bullets)
