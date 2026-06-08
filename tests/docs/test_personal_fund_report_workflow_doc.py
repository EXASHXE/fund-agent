"""Personal fund report workflow doc tests."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "workflows" / "personal-fund-report.md"


def test_personal_fund_report_workflow_doc_exists_and_names_core_flow():
    assert DOC.exists()
    text = DOC.read_text(encoding="utf-8")
    required = [
        "分析下我的基金给出报告",
        "FundAnalysisSkill",
        "DecisionSupportSkill",
        "EvidenceGraph",
        "host owns data fetching",
    ]
    lower_text = " ".join(text.lower().split())
    for term in required:
        assert term.lower() in lower_text
