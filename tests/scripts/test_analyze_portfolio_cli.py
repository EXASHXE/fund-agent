"""Tests for analyze-portfolio and render-report CLI subcommands."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from src.fund_agent.cli import main as cli_main


def _write_temp_json(data: dict, tmpdir: Path) -> str:
    p = tmpdir / "input.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(p)


class TestAnalyzePortfolioCLI:
    def test_missing_input(self):
        with pytest.raises(SystemExit) as exc_info:
            cli_main(["analyze-portfolio"])
        assert exc_info.value.code != 0

    def test_nonexistent_input(self):
        rc = cli_main(["analyze-portfolio", "--input", "/nonexistent/path.json"])
        assert rc != 0

    def test_valid_input_json(self, tmp_path):
        portfolio = {
            "schema_version": "fund_portfolio_input.v1",
            "as_of_date": "2024-12-31",
            "holdings": [
                {"fund_code": "000001", "fund_name": "Demo Fund", "current_value": 50000}
            ],
        }
        input_path = _write_temp_json(portfolio, tmp_path)
        rc = cli_main(["analyze-portfolio", "--input", input_path])
        assert rc == 0

    def test_valid_input_pretty(self, tmp_path):
        portfolio = {
            "schema_version": "fund_portfolio_input.v1",
            "as_of_date": "2024-12-31",
            "holdings": [
                {"fund_code": "000001", "fund_name": "Demo Fund", "current_value": 50000}
            ],
        }
        input_path = _write_temp_json(portfolio, tmp_path)
        rc = cli_main(["analyze-portfolio", "--input", input_path, "--pretty"])
        assert rc == 0

    def test_markdown_output(self, tmp_path):
        portfolio = {
            "schema_version": "fund_portfolio_input.v1",
            "as_of_date": "2024-12-31",
            "holdings": [
                {"fund_code": "000001", "fund_name": "Demo Fund", "current_value": 50000}
            ],
        }
        input_path = _write_temp_json(portfolio, tmp_path)
        output_path = str(tmp_path / "report.md")
        rc = cli_main(["analyze-portfolio", "--input", input_path, "--format", "markdown", "--output", output_path])
        assert rc == 0
        assert Path(output_path).exists()

    def test_invalid_json(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("not valid json{{{", encoding="utf-8")
        rc = cli_main(["analyze-portfolio", "--input", str(p)])
        assert rc != 0


class TestRenderReportCLI:
    def test_missing_input(self):
        with pytest.raises(SystemExit) as exc_info:
            cli_main(["render-report"])
        assert exc_info.value.code != 0

    def test_valid_input(self, tmp_path):
        report = {
            "report_sections": [],
            "analysis_mode": "report_only",
            "quality_gate": {"status": "PASS"},
        }
        input_path = _write_temp_json(report, tmp_path)
        rc = cli_main(["render-report", "--input", input_path])
        assert rc == 0

    def test_output_to_file(self, tmp_path):
        report = {
            "report_sections": [],
            "analysis_mode": "report_only",
            "quality_gate": {"status": "PASS"},
        }
        input_path = _write_temp_json(report, tmp_path)
        output_path = str(tmp_path / "output.md")
        rc = cli_main(["render-report", "--input", input_path, "--output", output_path])
        assert rc == 0
        assert Path(output_path).exists()
        content = Path(output_path).read_text(encoding="utf-8")
        assert "基金组合分析报告" in content
