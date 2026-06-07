"""Documentation coverage for personal fund scenario fixtures."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "examples" / "scenarios" / "README.md"

SCENARIO_FIXTURES = [
    "cn_fund_7d_redemption_fee.json",
    "cn_fund_qdii_sp500_overlap.json",
    "cn_fund_ai_semiconductor_overweight.json",
    "cn_fund_dca_drawdown_review.json",
    "cn_fund_ledger_derived_snapshot.json",
]


def test_scenario_fixtures_readme_exists_and_mentions_each_fixture() -> None:
    assert README.exists()
    text = README.read_text(encoding="utf-8")
    for fixture_name in SCENARIO_FIXTURES:
        assert fixture_name in text


def test_scenario_fixtures_readme_states_boundaries() -> None:
    text = README.read_text(encoding="utf-8").lower()
    assert "fake/sample data" in text
    assert "not investment advice" in text
    assert "not real-time market data" in text
    assert "not real personal holdings" in text
    assert "external hosts own real data fetching" in text
    assert "provider sdk integration" in text
    assert "formal decisions require" in text
    assert "decision_support" in text
    assert "fund_analysis" in text
    assert "analysis artifacts" in text
    assert "reports only" in text


def test_scenario_fixtures_readme_includes_bridge_command_examples() -> None:
    text = README.read_text(encoding="utf-8")
    assert "--validate-input" in text
    assert "--emit-report markdown" in text
