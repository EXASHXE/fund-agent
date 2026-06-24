"""Unit tests for fund_analysis core metrics computation."""


from src.skills_runtime.fund_analysis.input_stage import (
    collect_fund_codes,
    dict_or_empty,
    is_number,
    latest_nav_by_fund,
    missing_data_warnings,
)


class TestCollectFundCodes:
    def test_extracts_fund_codes(self):
        positions = [
            {"fund_code": "110011", "current_value": 10000},
            {"fund_code": "110012", "current_value": 20000},
        ]
        result = collect_fund_codes(positions)
        assert result == ["110011", "110012"]

    def test_skips_non_dict_positions(self):
        positions = [
            {"fund_code": "110011"},
            "not a dict",
            None,
        ]
        result = collect_fund_codes(positions)
        assert result == ["110011"]

    def test_skips_missing_fund_code(self):
        positions = [
            {"fund_code": "110011"},
            {"current_value": 10000},  # no fund_code
        ]
        result = collect_fund_codes(positions)
        assert result == ["110011"]


class TestDictOrEmpty:
    def test_dict_passthrough(self):
        assert dict_or_empty({"a": 1}) == {"a": 1}

    def test_none_returns_empty(self):
        assert dict_or_empty(None) == {}

    def test_string_returns_empty(self):
        assert dict_or_empty("not a dict") == {}


class TestIsNumber:
    def test_int(self):
        assert is_number(42) is True

    def test_float(self):
        assert is_number(3.14) is True

    def test_string_number(self):
        assert is_number("3.14") is True

    def test_string_text(self):
        assert is_number("hello") is False

    def test_none(self):
        assert is_number(None) is False


class TestLatestNavByFund:
    def test_extracts_latest_nav(self):
        nav_history = {
            "110011": [
                {"date": "2025-01-01", "nav": 1.0},
                {"date": "2025-06-01", "nav": 1.2},
            ]
        }
        result = latest_nav_by_fund(nav_history)
        assert result == {"110011": 1.2}

    def test_empty_nav_history(self):
        result = latest_nav_by_fund({})
        assert result == {}


class TestMissingDataWarnings:
    def test_warns_on_missing_profile(self):
        result = missing_data_warnings(
            fund_codes=["110011"],
            fund_profiles={},
            nav_history={"110011": []},
            holdings={"110011": []},
        )
        assert any("Missing fund profile" in w for w in result)

    def test_no_warnings_when_all_present(self):
        result = missing_data_warnings(
            fund_codes=["110011"],
            fund_profiles={"110011": {"name": "Test"}},
            nav_history={"110011": [{"date": "2025-01-01", "nav": 1.0}]},
            holdings={"110011": [{"name": "A"}]},
        )
        assert result == []

    def test_warns_on_missing_nav_history(self):
        result = missing_data_warnings(
            fund_codes=["110011"],
            fund_profiles={"110011": {"name": "Test"}},
            nav_history={},
            holdings={"110011": [{"name": "A"}]},
        )
        assert any("Missing NAV history" in w for w in result)

    def test_warns_on_missing_holdings(self):
        result = missing_data_warnings(
            fund_codes=["110011"],
            fund_profiles={"110011": {"name": "Test"}},
            nav_history={"110011": [{"date": "2025-01-01", "nav": 1.0}]},
            holdings={},
        )
        assert any("Missing holdings" in w for w in result)
