"""Verify docs/skill-io-examples.md reflects current v0.4.8-dev report contract."""

from __future__ import annotations

from pathlib import Path


DOC_PATH = Path("docs/skill-io-examples.md")


def test_doc_exists():
    assert DOC_PATH.exists()


def test_mentions_report_sections():
    content = DOC_PATH.read_text(encoding="utf-8")
    assert "report_sections" in content, "missing report_sections in skill-io-examples"


def test_mentions_report_outline():
    content = DOC_PATH.read_text(encoding="utf-8")
    assert "report_outline" in content, "missing report_outline in skill-io-examples"


def test_mentions_report_quality_gate():
    content = DOC_PATH.read_text(encoding="utf-8")
    assert "report_quality_gate" in content, "missing report_quality_gate in skill-io-examples"


def test_mentions_data_completeness():
    content = DOC_PATH.read_text(encoding="utf-8")
    assert "data_completeness" in content, "missing data_completeness in skill-io-examples"


def test_mentions_analysis_coverage():
    content = DOC_PATH.read_text(encoding="utf-8")
    assert "analysis_coverage" in content, "missing analysis_coverage in skill-io-examples"


def test_does_not_imply_fund_analysis_returns_decision():
    content = DOC_PATH.read_text(encoding="utf-8")
    # The fund_analysis output section should not claim Decision is produced
    # Find the fund_analysis output block
    assert "FundAnalysisSkill does not produce Decision" in content or \
           "does not produce `Decision`" in content or \
           "not produce Decision or ExecutionLedger" in content, \
           "skill-io-examples should state fund_analysis does not produce Decision"


def test_mentions_compose_personal_fund_report():
    content = DOC_PATH.read_text(encoding="utf-8")
    assert "compose_personal_fund_report" in content, "missing reference to report composer"


def test_mentions_deterministic():
    content = DOC_PATH.read_text(encoding="utf-8")
    assert "deterministic" in content.lower(), "should mention report sections are deterministic"
