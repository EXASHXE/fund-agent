"""Tests for report helpers — _money_or_missing must return N/A, not '0.00'.

When value is None or likely_missing=True, the helper must return
a missing indicator string, not a formatted zero.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.tools.portfolio.report_sections.helpers import _money, _money_or_missing  # noqa: E402


# ---------------------------------------------------------------------------
# Tests: _money_or_missing
# ---------------------------------------------------------------------------


class TestMoneyOrMissing:
    """Validate _money_or_missing returns N/A for None/likely_missing."""

    def test_none_returns_zh_na(self):
        """None value must return '无法计算' in Chinese."""
        assert _money_or_missing(None) == "无法计算"

    def test_none_with_en_lang(self):
        """None value with lang='en' must return 'N/A'."""
        assert _money_or_missing(None, lang="en") == "N/A"

    def test_likely_missing_returns_zh_na(self):
        """likely_missing=True with a zero value must return '无法计算'."""
        assert _money_or_missing(0, likely_missing=True) == "无法计算"

    def test_likely_missing_with_en_lang(self):
        """likely_missing=True with lang='en' must return 'N/A'."""
        assert _money_or_missing(0, likely_missing=True, lang="en") == "N/A"

    def test_real_value_returns_formatted(self):
        """Real positive value must return formatted money string."""
        result = _money_or_missing(50000)
        assert result == "50,000.00"

    def test_zero_not_likely_missing_returns_zero(self):
        """current_value=0 with likely_missing=False must return '0.00'."""
        result = _money_or_missing(0, likely_missing=False)
        assert result == "0.00"

    def test_zero_default_not_likely_missing(self):
        """current_value=0 without likely_missing flag must return '0.00'."""
        result = _money_or_missing(0)
        assert result == "0.00"

    def test_none_takes_precedence_over_likely_missing(self):
        """None value must return N/A even if likely_missing=False."""
        assert _money_or_missing(None, likely_missing=False) == "无法计算"

    def test_string_value_formatted(self):
        """String numeric value must be formatted like _money()."""
        result = _money_or_missing("12345.67")
        assert result == "12,345.67"

    def test_string_none_returns_na(self):
        """String 'None' is unparseable, should return N/A."""
        result = _money_or_missing("not_a_number")
        assert result == "无法计算"

    def test_negative_value_formatted(self):
        """Negative value must be formatted normally."""
        result = _money_or_missing(-500)
        assert result == "-500.00"


class TestMoneyUnchanged:
    """Existing _money() behavior must remain unchanged."""

    def test_money_none_returns_zero(self):
        """_money(None) must still return '0.00' for backward compatibility."""
        assert _money(None) == "0.00"

    def test_money_zero_returns_zero(self):
        """_money(0) must still return '0.00'."""
        assert _money(0) == "0.00"

    def test_money_positive_returns_formatted(self):
        """_money(50000) must return '50,000.00'."""
        assert _money(50000) == "50,000.00"
