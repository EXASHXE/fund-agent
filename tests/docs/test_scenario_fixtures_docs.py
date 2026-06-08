"""Docs tests for scenario fixture README."""

from __future__ import annotations

from pathlib import Path

README_PATH = Path("examples/scenarios/README.md")


def _content() -> str:
    return README_PATH.read_text(encoding="utf-8").lower()


def test_scenario_readme_mentions_redemption_fee_risk():
    assert "redemption_fee_risk" in _content()


def test_scenario_readme_mentions_overlap_diagnostics():
    assert "overlap_diagnostics" in _content()


def test_scenario_readme_mentions_theme_overweight_diagnostics():
    assert "theme_overweight_diagnostics" in _content()


def test_scenario_readme_mentions_dca_drawdown_diagnostics():
    assert "dca_drawdown_diagnostics" in _content()


def test_scenario_readme_mentions_cash_budget_diagnostics():
    assert "cash_budget_diagnostics" in _content()


def test_scenario_readme_mentions_formal_decisions_require_decision_support():
    text = _content()
    assert "decision_support" in text


def test_scenario_readme_mentions_fake_sample_data():
    assert "fake" in _content() or "sample" in _content()
