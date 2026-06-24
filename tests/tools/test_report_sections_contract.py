"""Tests for report sections contract — each builder must return valid section shape."""

import pytest

from src.tools.portfolio.report_sections.registry import (
    SECTION_ORDER,
    ZH_CN_SECTION_TITLES,
    section_registry,
)


class TestSectionRegistry:
    def test_section_order_has_expected_entries(self):
        # Section count may grow as new sections are added (e.g. factor_analysis, news_and_events)
        # The contract is that SECTION_ORDER is a tuple of (id, title) pairs
        assert len(SECTION_ORDER) >= 27
        # Verify all entries are (str, str) tuples
        for entry in SECTION_ORDER:
            assert isinstance(entry, tuple) and len(entry) == 2
            assert isinstance(entry[0], str) and isinstance(entry[1], str)

    def test_registry_matches_section_order(self):
        for section_id, title_en in SECTION_ORDER:
            assert section_id in section_registry
            assert section_registry[section_id].title_en == title_en

    def test_every_section_has_zh_cn_title(self):
        for section_id, _ in SECTION_ORDER:
            assert section_id in ZH_CN_SECTION_TITLES, f"Missing ZH_CN title for {section_id}"

    def test_registry_entries_have_required_fields(self):
        for section_id, _ in SECTION_ORDER:
            entry = section_registry[section_id]
            assert entry.section_id == section_id
            assert isinstance(entry.title_en, str)
            assert len(entry.title_en) > 0
            assert isinstance(entry.title_zh, str)
            assert len(entry.title_zh) > 0
            assert entry.required_keys == ("id", "title", "status")


class TestSectionBuilderContract:
    """Each builder, when called with minimal valid input, must return a dict
    with at least id, title, and status keys."""

    def test_compose_personal_fund_report_returns_required_keys(self):
        from src.tools.portfolio.report_sections.render import compose_personal_fund_report

        result = compose_personal_fund_report({}, warnings=[])
        assert "report_sections" in result
        assert "report_outline" in result
        assert "quality_gate" in result

    def test_compose_personal_fund_report_sections_have_required_keys(self):
        from src.tools.portfolio.report_sections.render import compose_personal_fund_report

        result = compose_personal_fund_report({}, warnings=[])
        for section in result["report_sections"]:
            assert "id" in section
            assert "title" in section
            assert "status" in section
            assert section["status"] in {"OK", "PARTIAL", "MISSING"}

    def test_backward_compat_import_from_report_composer(self):
        """Verify that the old import path still works via the re-export shim."""
        from src.tools.portfolio.report_composer import (
            SECTION_ORDER as so,
            compose_personal_fund_report as cpfr,
            render_report_markdown as rrm,
            section_registry as sr,
            SectionBuilder as SB,
            ZH_CN_SECTION_TITLES as zh,
        )

        assert len(so) >= 27
        assert callable(cpfr)
        assert callable(rrm)
        assert isinstance(sr, dict)
        assert SB is not None
        assert len(zh) >= 27
