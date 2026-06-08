"""Decision support fixture documentation tests."""

from __future__ import annotations

from pathlib import Path


FIXTURES_DIR = Path("examples/decision_support")
README_PATH = FIXTURES_DIR / "README.md"

EXPECTED_FIXTURES = [
    "single_active_buy_with_evidence.json",
    "single_active_buy_without_evidence_invalid.json",
    "single_passive_hold_without_evidence.json",
    "trade_plan_selected_trade_with_caps.json",
    "trade_plan_forbidden_action_skipped.json",
    "trade_plan_no_evidence_downgraded.json",
]


def _content() -> str:
    return README_PATH.read_text(encoding="utf-8").lower()


def test_fixture_readme_exists():
    assert README_PATH.exists()


def test_readme_mentions_every_fixture_file():
    text = _content()
    for name in EXPECTED_FIXTURES:
        assert name in text, f"README must mention fixture file: {name}"


def test_readme_states_fake_sample_data_only():
    text = _content()
    assert "fake" in text or "sample" in text


def test_readme_states_not_investment_advice():
    text = _content()
    assert "not investment advice" in text


def test_readme_states_not_real_time_market_data():
    text = _content()
    assert "not real-time" in text or "not real time" in text


def test_readme_states_not_real_personal_holdings():
    text = _content()
    assert "not real" in text
    assert "personal" in text or "holding" in text


def test_readme_states_host_owns_data_fetching_and_provider():
    text = _content()
    assert "host owns" in text or "host" in text


def test_readme_states_decision_support_may_emit_formal_decision():
    text = _content()
    assert "formal decision" in text or "formal `decision`" in text or (
        "decision" in text and "executionledger" in text
    )


def test_readme_states_decision_support_does_not_execute_trades():
    text = _content()
    assert "does not execute trade" in text or "does not execute" in text


def test_readme_states_fund_analysis_plans_are_not_formal_orders():
    text = _content()
    assert "not a formal" in text or "not formal" in text or (
        "suggested_rebalance_plan" in text
    )
