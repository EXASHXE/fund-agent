"""Tests for deterministic report-quality helpers."""

from __future__ import annotations

import json

from src.tools.portfolio.report_quality import (
    build_report_limitations,
    calculate_data_completeness,
    summarize_analysis_coverage,
)


class TestCalculateDataCompleteness:
    def test_grade_a_when_all_required_present(self):
        payload = {
            "portfolio": {
                "as_of_date": "2026-06-01",
                "total_value": 200000,
                "cash_available": 20000,
                "positions": [{"fund_code": "110011", "current_value": 30000, "total_cost": 32000}],
            },
            "fund_profiles": {"110011": {"fund_code": "110011", "name": "Fund"}},
            "nav_history": {"110011": [{"date": "2026-06-01", "nav": 1.2}]},
            "holdings": {"110011": [{"name": "A", "weight": 0.08}]},
            "risk_profile": {"risk_level": "moderate"},
            "constraints": {"min_trade_amount": 100},
        }
        result = calculate_data_completeness(payload)
        assert result["grade"] in ("A", "B")  # B without any optional, but all required
        assert result["score"] >= 0.5
        assert "Portfolio Snapshot" in map(str, result["available_sections"])
        assert len(result["critical_missing"]) == 0

    def test_grade_lower_when_holdings_missing(self):
        payload = {
            "portfolio": {
                "as_of_date": "2026-06-01",
                "total_value": 200000,
                "positions": [{"fund_code": "110011", "current_value": 30000}],
            },
            "fund_profiles": {"110011": {"fund_code": "110011"}},
            "nav_history": {"110011": [{"date": "2026-06-01", "nav": 1.2}]},
            "holdings": {},
            "risk_profile": {},
            "constraints": {},
        }
        result = calculate_data_completeness(payload)
        assert result["grade"] in ("C", "D")
        assert "Holdings" in result["missing_sections"]

    def test_derived_portfolio_counts_as_portfolio_available(self):
        payload = {
            "transactions": [
                {"action": "BUY", "fund_code": "110011", "date": "2026-01-01", "amount": 10000, "nav": 1.0, "shares": 10000},
            ],
            "current_nav": {"110011": 1.20},
            "as_of_date": "2026-06-01",
            "fund_profiles": {"110011": {"fund_code": "110011"}},
            "nav_history": {"110011": [{"date": "2026-06-01", "nav": 1.2}]},
            "holdings": {"110011": []},
            "risk_profile": {},
            "constraints": {},
        }
        result = calculate_data_completeness(payload)
        assert "Portfolio Snapshot" not in result["missing_sections"]

    def test_limitations_are_deterministic(self):
        payload = {
            "portfolio": {
                "as_of_date": "2026-06-01",
                "total_value": 200000,
                "positions": [{"fund_code": "110011", "current_value": 30000}],
            },
            "fund_profiles": {},
            "nav_history": {},
            "holdings": {},
            "risk_profile": {},
            "constraints": {},
        }
        result1 = calculate_data_completeness(payload)
        result2 = calculate_data_completeness(payload)
        assert result1 == result2
        assert isinstance(result1["limitations"], list)

    def test_json_serializable(self):
        payload = {
            "portfolio": {
                "as_of_date": "2026-06-01",
                "total_value": 200000,
                "positions": [{"fund_code": "110011", "current_value": 30000}],
            },
            "fund_profiles": {"110011": {"fund_code": "110011"}},
            "nav_history": {"110011": []},
            "holdings": {"110011": []},
            "risk_profile": {},
            "constraints": {},
        }
        result = calculate_data_completeness(payload)
        dumped = json.dumps(result)
        assert isinstance(dumped, str)
        loaded = json.loads(dumped)
        assert loaded == result

    def test_all_optional_present_yields_high_score(self):
        payload = {
            "portfolio": {
                "as_of_date": "2026-06-01",
                "total_value": 200000,
                "positions": [{"fund_code": "110011", "current_value": 30000, "total_cost": 32000}],
            },
            "fund_profiles": {"110011": {"fund_code": "110011"}},
            "nav_history": {"110011": [{"date": "2026-06-01", "nav": 1.2}]},
            "holdings": {"110011": [{"name": "A", "weight": 0.08}]},
            "risk_profile": {"risk_level": "moderate"},
            "constraints": {"min_trade_amount": 100},
            "benchmark_history": {"bench": [{"date": "2026-06-01", "value": 100}]},
            "peer_group": {"110011": {"rank": 3, "total": 50}},
            "factor_exposures": {"value": 0.8},
            "manager_profiles": {"110011": {"tenure": "5 years"}},
            "fee_schedules": {"110011": {"management_fee": 0.015}},
            "redemption_rules": {"110011": {"lockup": "30 days"}},
            "fund_flow": {"110011": {"inflow": 1000000}},
            "macro_events": [{"type": "rate_hike", "date": "2026-05-01"}],
            "user_investment_plan": {"monthly": 5000},
        }
        result = calculate_data_completeness(payload)
        assert result["grade"] == "A"
        assert result["score"] >= 0.9

    def test_grade_a_when_full_required_and_most_optional_present(self):
        payload = {
            "portfolio": {
                "as_of_date": "2026-06-01",
                "total_value": 200000,
                "positions": [{"fund_code": "110011", "current_value": 30000, "total_cost": 32000}],
            },
            "fund_profiles": {"110011": {"fund_code": "110011"}},
            "nav_history": {"110011": [{"date": "2026-06-01", "nav": 1.2}]},
            "holdings": {"110011": [{"name": "A", "weight": 0.08}]},
            "risk_profile": {"risk_level": "moderate"},
            "constraints": {"min_trade_amount": 100},
            "benchmark_history": {"bench": [{"date": "2026-06-01", "value": 100}]},
            "peer_group": {"110011": {"rank": 3, "total": 50}},
            "factor_exposures": {"value": {"110011": 0.8}},
            "manager_profiles": {"110011": {"tenure_years": 5}},
            "fee_schedules": {"110011": {"management_fee": 0.015}},
            "redemption_rules": {"110011": {"lockup_days": 30}},
        }
        result = calculate_data_completeness(payload)
        assert result["grade"] == "A"

    def test_grade_b_when_required_present_and_optional_mostly_missing(self):
        payload = {
            "portfolio": {
                "as_of_date": "2026-06-01",
                "total_value": 200000,
                "positions": [{"fund_code": "110011", "current_value": 30000, "total_cost": 32000}],
            },
            "fund_profiles": {"110011": {"fund_code": "110011"}},
            "nav_history": {"110011": [{"date": "2026-06-01", "nav": 1.2}]},
            "holdings": {"110011": [{"name": "A", "weight": 0.08}]},
            "risk_profile": {"risk_level": "moderate"},
            "constraints": {"min_trade_amount": 100},
        }
        result = calculate_data_completeness(payload)
        assert result["grade"] == "B"
        assert "Peer Group" in result["optional_missing"]

    def test_grade_c_when_nav_and_holdings_missing_but_portfolio_exists(self):
        payload = {
            "portfolio": {
                "as_of_date": "2026-06-01",
                "total_value": 200000,
                "positions": [{"fund_code": "110011", "current_value": 30000}],
            },
            "fund_profiles": {"110011": {"fund_code": "110011"}},
            "risk_profile": {"risk_level": "moderate"},
            "constraints": {"min_trade_amount": 100},
        }
        result = calculate_data_completeness(payload)
        assert result["grade"] == "C"
        assert "Nav History" in result["missing_sections"]
        assert "Holdings" in result["missing_sections"]

    def test_grade_d_when_no_usable_portfolio(self):
        payload = {
            "fund_profiles": {"110011": {"fund_code": "110011"}},
            "nav_history": {"110011": [{"date": "2026-06-01", "nav": 1.2}]},
            "holdings": {"110011": [{"name": "A", "weight": 0.08}]},
            "risk_profile": {"risk_level": "moderate"},
            "constraints": {"min_trade_amount": 100},
        }
        result = calculate_data_completeness(payload)
        assert result["grade"] == "D"
        assert "Portfolio Snapshot" in result["critical_missing"]

    def test_derived_portfolio_with_unresolved_events_lowers_grade(self):
        payload = {
            "transactions": [
                {"action": "BUY", "fund_code": "110011", "date": "2026-01-01", "amount": 10000, "nav": 1.0, "shares": 10000},
            ],
            "current_nav": {"110011": 1.20},
            "as_of_date": "2026-06-01",
            "fund_profiles": {"110011": {"fund_code": "110011"}},
            "nav_history": {"110011": [{"date": "2026-06-01", "nav": 1.2}]},
            "holdings": {"110011": [{"name": "A", "weight": 0.08}]},
            "risk_profile": {"risk_level": "moderate"},
            "constraints": {"min_trade_amount": 100},
            "benchmark_history": {"bench": [{"date": "2026-06-01", "value": 100}]},
            "peer_group": {"110011": {"rank": 3, "total": 50}},
            "factor_exposures": {"value": {"110011": 0.8}},
            "manager_profiles": {"110011": {"tenure_years": 5}},
            "fee_schedules": {"110011": {"management_fee": 0.015}},
            "redemption_rules": {"110011": {"lockup_days": 30}},
        }
        result = calculate_data_completeness(
            payload,
            {"invalid_events_count": 0, "unresolved_events_count": 1},
        )
        assert result["grade"] == "B"
        assert any("ledger" in item.lower() for item in result["limitations"])

    def test_output_order_is_deterministic(self):
        payload = {
            "constraints": {"min_trade_amount": 100},
            "risk_profile": {"risk_level": "moderate"},
            "holdings": {"110011": [{"name": "A", "weight": 0.08}]},
            "nav_history": {"110011": [{"date": "2026-06-01", "nav": 1.2}]},
            "fund_profiles": {"110011": {"fund_code": "110011"}},
            "portfolio": {
                "positions": [{"fund_code": "110011", "current_value": 30000}],
                "total_value": 30000,
            },
        }
        result = calculate_data_completeness(payload)
        assert result["available_sections"][:7] == [
            "Portfolio Snapshot",
            "Current Value Or Nav",
            "Fund Profiles",
            "Nav History",
            "Holdings",
            "Risk Profile",
            "Constraints",
        ]

    def test_no_portfolio_produces_critical_missing(self):
        payload = {
            "fund_profiles": {"110011": {"fund_code": "110011"}},
            "nav_history": {"110011": []},
            "holdings": {"110011": []},
            "risk_profile": {},
            "constraints": {},
        }
        result = calculate_data_completeness(payload)
        assert "Portfolio Snapshot" in result["critical_missing"]


class TestSummarizeAnalysisCoverage:
    def test_full_payload_produces_available_coverage(self):
        payload = {
            "portfolio": {
                "as_of_date": "2026-06-01",
                "total_value": 200000,
                "positions": [{"fund_code": "110011", "current_value": 30000, "total_cost": 32000}],
            },
            "fund_profiles": {"110011": {"fund_code": "110011"}},
            "nav_history": {"110011": [{"date": "2026-06-01", "nav": 1.2}]},
            "holdings": {"110011": [{"name": "A", "weight": 0.08}]},
            "risk_profile": {"risk_level": "moderate"},
            "constraints": {"min_trade_amount": 100},
            "research_planning": True,
        }
        artifacts = {
            "portfolio_summary": {"total_value": 200000},
            "research_query_plan": {"queries": []},
        }
        coverage = summarize_analysis_coverage(payload, artifacts)
        assert coverage["portfolio"] == "available"
        assert coverage["performance"] in ("available", "partial")
        assert coverage["holdings"] == "available"
        assert coverage["research_plan"] == "available"

    def test_derived_portfolio_shows_derived(self):
        payload = {
            "transactions": [
                {"action": "BUY", "fund_code": "110011", "date": "2026-01-01", "amount": 10000, "nav": 1.0, "shares": 10000},
            ],
            "current_nav": {"110011": 1.20},
            "as_of_date": "2026-06-01",
            "fund_profiles": {"110011": {"fund_code": "110011"}},
            "nav_history": {"110011": []},
            "holdings": {"110011": []},
            "risk_profile": {},
            "constraints": {},
        }
        artifacts = {"source_of_truth": "derived_from_transactions"}
        coverage = summarize_analysis_coverage(payload, artifacts)
        assert coverage["portfolio"] == "derived"

    def test_optional_missing_sections(self):
        payload = {
            "portfolio": {
                "as_of_date": "2026-06-01",
                "total_value": 200000,
                "positions": [{"fund_code": "110011", "current_value": 30000}],
            },
            "fund_profiles": {"110011": {"fund_code": "110011"}},
            "nav_history": {"110011": []},
            "holdings": {"110011": []},
            "risk_profile": {},
            "constraints": {},
        }
        artifacts = {}
        coverage = summarize_analysis_coverage(payload, artifacts)
        assert coverage["benchmark"] == "missing"
        assert coverage["peer"] == "missing"
        assert coverage["factor"] == "missing"
        assert coverage["fees"] == "missing"
        assert coverage["redemption"] == "missing"

    def test_research_plan_not_requested(self):
        payload = {
            "portfolio": {
                "as_of_date": "2026-06-01",
                "total_value": 200000,
                "positions": [{"fund_code": "110011", "current_value": 30000}],
            },
            "fund_profiles": {"110011": {}},
            "nav_history": {"110011": []},
            "holdings": {"110011": []},
            "risk_profile": {},
            "constraints": {},
        }
        coverage = summarize_analysis_coverage(payload, {})
        assert coverage["research_plan"] == "not_requested"

    def test_research_plan_requested_but_missing(self):
        payload = {
            "portfolio": {
                "as_of_date": "2026-06-01",
                "total_value": 200000,
                "positions": [{"fund_code": "110011", "current_value": 30000}],
            },
            "fund_profiles": {"110011": {}},
            "nav_history": {"110011": []},
            "holdings": {"110011": []},
            "risk_profile": {},
            "constraints": {},
            "research_planning": True,
        }
        coverage = summarize_analysis_coverage(payload, {})
        assert coverage["research_plan"] == "missing_inputs"


class TestBuildReportLimitations:
    def test_includes_completeness_limitations(self):
        completeness = calculate_data_completeness(
            {
                "portfolio": {
                    "as_of_date": "2026-06-01",
                    "total_value": 200000,
                    "positions": [{"fund_code": "110011", "current_value": 30000}],
                },
                "fund_profiles": {},
                "nav_history": {},
                "holdings": {},
                "risk_profile": {},
                "constraints": {},
            }
        )
        limitations = build_report_limitations(completeness)
        assert len(limitations) > 0
        # Should include a grade-based statement for low grades
        assert any("grade" in lim.lower() or "broker" in lim.lower() for lim in limitations)

    def test_includes_ledger_quality_limitations(self):
        completeness = calculate_data_completeness(
            {
                "portfolio": {"as_of_date": "2026-06-01", "total_value": 200000, "positions": []},
                "fund_profiles": {},
                "nav_history": {},
                "holdings": {},
                "risk_profile": {},
                "constraints": {},
            }
        )
        ledger_quality = {
            "invalid_events_count": 2,
            "unresolved_events_count": 1,
            "is_complete": False,
            "limitations": ["2 transaction event(s) were invalid and excluded"],
        }
        limitations = build_report_limitations(completeness, ledger_quality)
        assert any("invalid" in lim.lower() for lim in limitations)

    def test_includes_missing_data_strings(self):
        completeness = calculate_data_completeness(
            {
                "portfolio": {"as_of_date": "2026-06-01", "total_value": 200000, "positions": []},
                "fund_profiles": {},
                "nav_history": {},
                "holdings": {},
                "risk_profile": {},
                "constraints": {},
            }
        )
        missing = ["NAV history missing for fund_code=110011"]
        limitations = build_report_limitations(completeness, missing_data=missing)
        assert any("nav" in lim.lower() for lim in limitations)

    def test_json_serializable(self):
        completeness = calculate_data_completeness(
            {
                "portfolio": {"as_of_date": "2026-06-01", "total_value": 200000, "positions": []},
                "fund_profiles": {},
                "nav_history": {},
                "holdings": {},
                "risk_profile": {},
                "constraints": {},
            }
        )
        limitations = build_report_limitations(completeness)
        dumped = json.dumps(limitations)
        assert isinstance(dumped, str)
