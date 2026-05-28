from datetime import date
from unittest.mock import patch

import pandas as pd

from src.services.report_service import render_analysis_report


def test_report_service_writes_evidence_and_post_processed_report(tmp_path):
    output = tmp_path / "report.md"
    score = {
        "fund_code": "000001",
        "fund_name": "测试基金",
        "macro_score": 15,
        "meso_score": 22,
        "micro_score": 39,
        "composite_score": 76,
    }

    with patch("src.output.report.generate_report", return_value="raw report") as generate, \
         patch("src.output.validator.post_process_report", return_value="processed report") as post_process:
        result = render_analysis_report(
            output_path=str(output),
            report_date=date(2026, 5, 22),
            analyzer=None,
            scores=[score],
            correlations=pd.DataFrame(),
            stress_results=[],
            holdings_data={"by_fund": {}, "funds": []},
            news_data=[],
            recommendations=[],
            recommendation_status="skipped",
            unscores=[],
            workflow_context={"portfolio_risk_matrix": {}},
            holding_count=0,
        )

    assert output.read_text(encoding="utf-8") == "processed report"
    assert result.report_path == str(output)
    assert result.evidence["schema_version"] == "report_evidence.v2"
    assert result.evidence_path.endswith(".evidence.json")
    assert generate.called
    post_process.assert_called_once()


def test_report_service_validates_final_agent_report(tmp_path):
    output = tmp_path / "report.md"
    agent_decisions = {"fund_scores": {"000001": {}}, "recommendations": []}

    with patch("src.output.report.generate_report", return_value="final report"), \
         patch("src.output.validator.post_process_report", return_value="final report"), \
         patch("src.output.validator.validate_final_report") as validate:
        render_analysis_report(
            output_path=str(output),
            report_date=date(2026, 5, 22),
            analyzer=None,
            scores=[],
            correlations=pd.DataFrame(),
            stress_results=[],
            holdings_data={"by_fund": {}, "funds": []},
            news_data=[],
            recommendations=[],
            recommendation_status="skipped",
            unscores=[],
            workflow_context={"portfolio_risk_matrix": {}},
            agent_decisions=agent_decisions,
            holding_count=3,
        )

    validate.assert_called_once_with("final report", "2026-05-22", 3)
