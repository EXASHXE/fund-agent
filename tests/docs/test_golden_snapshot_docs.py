"""Documentation coverage for golden fund_analysis snapshots."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "tests" / "golden" / "README.md"


def test_golden_snapshot_readme_exists() -> None:
    assert README.exists()


def test_golden_snapshot_readme_states_boundaries() -> None:
    text = README.read_text(encoding="utf-8").lower()
    assert "fake/sample" in text
    assert "not investment advice" in text
    assert "not real-time market data" in text
    assert "not real personal holdings" in text
    assert "external hosts own real data fetching" in text
    assert "provider sdk integration" in text
    assert "scripts/update_fund_analysis_golden.py" in text
    assert "intentional review" in text
