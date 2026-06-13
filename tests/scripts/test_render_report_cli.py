"""Tests for render-report CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.fund_agent.cli import main as cli_main


def _write_temp_json(data: dict, tmpdir: Path) -> str:
    p = tmpdir / "report_input.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(p)


class TestRenderReportCLI:
    def test_missing_input(self):
        with pytest.raises(SystemExit) as exc_info:
            cli_main(["render-report"])
        assert exc_info.value.code != 0

    def test_valid_input_stdout(self, tmp_path):
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
        output_path = str(tmp_path / "report.md")
        rc = cli_main(["render-report", "--input", input_path, "--output", output_path])
        assert rc == 0
        assert Path(output_path).exists()
        content = Path(output_path).read_text(encoding="utf-8")
        assert "基金组合分析报告" in content
        assert "风险提示" in content

    def test_report_only_no_decision(self, tmp_path):
        report = {
            "report_sections": [],
            "analysis_mode": "report_only",
            "quality_gate": {"status": "PASS"},
        }
        input_path = _write_temp_json(report, tmp_path)
        output_path = str(tmp_path / "report.md")
        cli_main(["render-report", "--input", input_path, "--output", output_path])
        content = Path(output_path).read_text(encoding="utf-8")
        assert "未调用决策支持" in content or "报告模式" in content
