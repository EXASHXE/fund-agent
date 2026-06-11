"""MCP harness fake mode integration test.

Dev-only harness test. Validates that fake MCP responses can be normalized
into fund_analysis-compatible payload fields without network or credentials.
Covers all 6 MCP->fund_analysis mappings.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.dev.mcp_harness.normalize_mcp_responses import (
    load_fake_responses,
    normalize_all,
    normalize_news_evidence,
    normalize_sentiment_evidence,
    normalize_web_search,
)


def test_fake_responses_file_is_valid_json():
    raw = load_fake_responses()
    assert isinstance(raw, dict)
    assert "news_evidence" in raw
    assert "sentiment_evidence" in raw
    assert "benchmark_history" in raw


def test_normalize_all_produces_fund_analysis_compatible_fields():
    raw = load_fake_responses()
    result = normalize_all(raw)
    assert isinstance(result["news_evidence"], list)
    assert isinstance(result["sentiment_evidence"], list)
    assert isinstance(result["benchmark_history"], dict)
    assert isinstance(result["fund_profiles"], dict)
    assert isinstance(result["fee_schedules"], dict)
    assert isinstance(result["redemption_rules"], dict)


def test_normalize_news_evidence_preserves_claims():
    raw = load_fake_responses()
    normalized = normalize_news_evidence(raw["news_evidence"])
    assert len(normalized) > 0
    assert normalized[0]["headline"] != ""
    assert normalized[0]["date"] != ""


def test_normalize_sentiment_evidence_extracts_fund_code():
    raw = load_fake_responses()
    normalized = normalize_sentiment_evidence(raw["sentiment_evidence"])
    assert len(normalized) > 0
    assert normalized[0]["fund_code"] != ""


def test_normalize_all_does_not_require_network():
    result = normalize_all()
    assert "news_evidence" in result
    assert result["news_evidence"] or result["sentiment_evidence"]


def test_financial_news_maps_to_news_evidence():
    raw = load_fake_responses()
    assert "financial_news" in raw
    subset = {"financial_news": raw["financial_news"]}
    result = normalize_all(subset)
    assert isinstance(result["news_evidence"], list)
    assert len(result["news_evidence"]) > 0
    assert result["news_evidence"][0]["headline"] != ""


def test_web_search_maps_to_news_evidence():
    raw = load_fake_responses()
    assert "web_search" in raw
    subset = {"web_search": raw["web_search"]}
    result = normalize_all(subset)
    assert isinstance(result["news_evidence"], list)
    assert len(result["news_evidence"]) > 0
    assert result["news_evidence"][0]["source"] == "web_search"


def test_web_search_normalizer_directly():
    raw = load_fake_responses()
    normalized = normalize_web_search(raw["web_search"])
    assert len(normalized) > 0
    assert normalized[0]["headline"] != ""
    assert normalized[0]["source"] == "web_search"


def test_social_sentiment_maps_to_sentiment_evidence():
    raw = load_fake_responses()
    assert "social_sentiment" in raw
    subset = {"social_sentiment": raw["social_sentiment"]}
    result = normalize_all(subset)
    assert isinstance(result["sentiment_evidence"], list)
    assert len(result["sentiment_evidence"]) > 0
    assert result["sentiment_evidence"][0]["fund_code"] != ""


def test_benchmark_price_history_maps_to_benchmark_history():
    raw = load_fake_responses()
    assert "benchmark_price_history" in raw
    subset = {"benchmark_price_history": raw["benchmark_price_history"]}
    result = normalize_all(subset)
    assert isinstance(result["benchmark_history"], dict)
    assert len(result["benchmark_history"]) > 0


def test_fund_metadata_lookup_maps_to_fund_profiles():
    raw = load_fake_responses()
    assert "fund_metadata_lookup" in raw
    subset = {"fund_metadata_lookup": raw["fund_metadata_lookup"]}
    result = normalize_all(subset)
    assert isinstance(result["fund_profiles"], dict)
    assert "110011" in result["fund_profiles"]


def test_fund_fee_schedule_maps_to_fee_schedules():
    raw = load_fake_responses()
    assert "fund_fee_schedule" in raw
    subset = {"fund_fee_schedule": raw["fund_fee_schedule"]}
    result = normalize_all(subset)
    assert isinstance(result["fee_schedules"], dict)
    assert "110011" in result["fee_schedules"]


def test_redemption_rules_passthrough():
    raw = load_fake_responses()
    assert "redemption_rules" in raw
    subset = {"redemption_rules": raw["redemption_rules"]}
    result = normalize_all(subset)
    assert isinstance(result["redemption_rules"], dict)


def test_normalize_all_with_mixed_mcp_and_legacy_keys():
    raw = load_fake_responses()
    result = normalize_all(raw)
    assert len(result["news_evidence"]) > 0
    assert len(result["sentiment_evidence"]) > 0
    assert len(result["benchmark_history"]) > 0
    assert len(result["fund_profiles"]) > 0
    assert len(result["fee_schedules"]) > 0
    assert len(result["redemption_rules"]) > 0


def test_normalize_all_empty_input():
    result = normalize_all({})
    assert result["news_evidence"] == []
    assert result["sentiment_evidence"] == []
    assert result["benchmark_history"] == {}
    assert result["fund_profiles"] == {}
    assert result["fee_schedules"] == {}
    assert result["redemption_rules"] == {}


def test_no_core_runtime_imports_in_harness():
    import importlib
    mod = importlib.import_module("tools.dev.mcp_harness.normalize_mcp_responses")
    assert mod.__file__ is not None
    source = open(mod.__file__, encoding="utf-8").read()
    forbidden = ["from src.", "import src."]
    for pattern in forbidden:
        assert pattern not in source, f"harness must not import core runtime: {pattern}"


def test_harness_output_can_be_used_by_fund_analysis():
    from src.schemas.skill import SkillInput
    from src.skills_runtime.fund_analysis import FundAnalysisSkill

    harness_data = normalize_all()
    payload = {
        "portfolio": {
            "as_of_date": "2026-06-01",
            "total_value": 100000.0,
            "cash_available": 10000.0,
            "positions": [
                {
                    "fund_code": "110011",
                    "fund_name": "Example Equity Fund",
                    "current_value": 90000.0,
                    "total_cost": 70000.0,
                    "shares": 60000.0,
                    "target_weight": 0.9,
                    "tags": ["equity"],
                },
            ],
        },
        "fund_profiles": harness_data["fund_profiles"],
        "nav_history": {
            "110011": [
                {"date": "2025-06-01", "nav": 1.1},
                {"date": "2026-06-01", "nav": 1.5},
            ],
        },
        "fee_schedules": harness_data["fee_schedules"],
        "redemption_rules": harness_data["redemption_rules"],
        "benchmark_history": harness_data["benchmark_history"],
        "news_evidence": harness_data["news_evidence"],
        "sentiment_evidence": harness_data["sentiment_evidence"],
        "risk_profile": {"risk_level": "moderate"},
        "constraints": {"min_trade_amount": 100.0, "forbidden_actions": []},
    }

    output = FundAnalysisSkill().run(
        SkillInput(
            task_id="mcp-harness-test",
            step_id="fund-analysis",
            skill_name="fund_analysis",
            payload=payload,
        )
    )
    assert output.status in ("OK", "PARTIAL")
    assert "analysis_plan" in output.artifacts
    assert "decision" not in output.artifacts
