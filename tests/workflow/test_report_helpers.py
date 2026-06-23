"""Tests for shared report helpers — verify dedup and theme_text behavior."""

from __future__ import annotations

from src.tools.workflow.report_helpers import dedupe_preserve_order, theme_text


class TestDedupePreserveOrder:
    def test_empty(self):
        assert dedupe_preserve_order([]) == []

    def test_no_duplicates(self):
        assert dedupe_preserve_order(["a", "b", "c"]) == ["a", "b", "c"]

    def test_duplicates_preserve_first_order(self):
        assert dedupe_preserve_order(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]

    def test_single_element(self):
        assert dedupe_preserve_order(["x"]) == ["x"]


class TestThemeText:
    def test_empty_artifacts(self):
        assert theme_text({}) == ""

    def test_dict_values_joined_and_lowercased(self):
        artifacts = {
            "fund_profiles": {"name": "TechFund"},
            "portfolio_summary": {"theme": "AI"},
        }
        result = theme_text(artifacts)
        assert "techfund" in result
        assert "ai" in result
        assert result == result.lower()

    def test_non_dict_values_skipped(self):
        artifacts = {
            "fund_profiles": "not a dict",
            "portfolio_summary": {"valid": "yes"},
        }
        result = theme_text(artifacts)
        assert "yes" in result
        assert "not a dict" not in result

    def test_known_keys_checked(self):
        for key in (
            "fund_profiles",
            "portfolio_summary",
            "position_summary",
            "exposure_summary",
            "fund_analysis_report",
        ):
            result = theme_text({key: {"marker": "FOUND"}})
            assert "found" in result
