"""Tests for analyze-portfolio and render-report CLI subcommands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.fund_agent.cli import main as cli_main


def _write_temp_json(data: dict, tmpdir: Path) -> str:
    p = tmpdir / "input.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(p)


def _minimal_portfolio(**overrides):
    base = {
        "schema_version": "fund_portfolio_input.v1",
        "as_of_date": "2024-12-31",
        "holdings": [
            {"fund_code": "000001", "fund_name": "Demo Fund", "current_value": 50000}
        ],
    }
    base.update(overrides)
    return base


class TestAnalyzePortfolioCLI:
    def test_missing_input(self):
        with pytest.raises(SystemExit) as exc_info:
            cli_main(["analyze-portfolio"])
        assert exc_info.value.code != 0

    def test_nonexistent_input(self):
        rc = cli_main(["analyze-portfolio", "--input", "/nonexistent/path.json"])
        assert rc != 0

    def test_valid_input_json(self, tmp_path):
        input_path = _write_temp_json(_minimal_portfolio(), tmp_path)
        rc = cli_main(["analyze-portfolio", "--input", input_path])
        assert rc == 0

    def test_valid_input_pretty(self, tmp_path):
        input_path = _write_temp_json(_minimal_portfolio(), tmp_path)
        rc = cli_main(["analyze-portfolio", "--input", input_path, "--pretty"])
        assert rc == 0

    def test_invalid_json(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("not valid json{{{", encoding="utf-8")
        rc = cli_main(["analyze-portfolio", "--input", str(p)])
        assert rc != 0


class TestAnalyzePortfolioMarkdownOutput:
    def test_markdown_output_contains_final_report_sections(self, tmp_path):
        input_path = _write_temp_json(_minimal_portfolio(), tmp_path)
        output_path = str(tmp_path / "report.md")
        rc = cli_main(["analyze-portfolio", "--input", input_path, "--format", "markdown", "--output", output_path])
        assert rc == 0
        content = Path(output_path).read_text(encoding="utf-8")
        assert "基金组合分析报告" in content
        assert "直接回答" in content or "组合概览" in content

    def test_markdown_has_real_content_not_only_headings(self, tmp_path):
        input_path = _write_temp_json(_minimal_portfolio(), tmp_path)
        output_path = str(tmp_path / "report.md")
        rc = cli_main(["analyze-portfolio", "--input", input_path, "--format", "markdown", "--output", output_path])
        assert rc == 0
        content = Path(output_path).read_text(encoding="utf-8")
        non_empty_bullets = [
            line for line in content.splitlines()
            if line.strip().startswith("- ") and len(line.strip()) > 3
        ]
        assert len(non_empty_bullets) >= 3, "markdown has fewer than 3 real bullet lines"

    def test_no_default_placeholders_only(self, tmp_path):
        input_path = _write_temp_json(_minimal_portfolio(), tmp_path)
        output_path = str(tmp_path / "report.md")
        rc = cli_main(["analyze-portfolio", "--input", input_path, "--format", "markdown", "--output", output_path])
        assert rc == 0
        content = Path(output_path).read_text(encoding="utf-8")
        placeholders = ["组合数据待补充", "风险评估待补充", "持仓诊断待补充", "数据缺口待补充"]
        placeholder_count = sum(1 for p in placeholders if p in content)
        assert placeholder_count <= 1, (
            f"found {placeholder_count} default placeholders: {[p for p in placeholders if p in content]}"
        )

    def test_report_only_states_decision_support_not_called(self, tmp_path):
        portfolio = _minimal_portfolio(analysis_mode="report_only")
        input_path = _write_temp_json(portfolio, tmp_path)
        output_path = str(tmp_path / "report.md")
        cli_main(["analyze-portfolio", "--input", input_path, "--format", "markdown", "--output", output_path])
        content = Path(output_path).read_text(encoding="utf-8")
        assert "未调用决策支持" in content or "报告模式" in content

    def test_missing_provider_snapshot_in_limitations(self, tmp_path):
        portfolio = _minimal_portfolio()
        input_path = _write_temp_json(portfolio, tmp_path)
        output_path = str(tmp_path / "report.md")
        cli_main(["analyze-portfolio", "--input", input_path, "--format", "markdown", "--output", output_path])
        content = Path(output_path).read_text(encoding="utf-8")
        assert "数据" in content or "限制" in content or "缺失" in content

    def test_missing_cost_basis_in_markdown(self, tmp_path):
        portfolio = _minimal_portfolio()
        portfolio["holdings"][0]["cost_basis"] = None
        input_path = _write_temp_json(portfolio, tmp_path)
        output_path = str(tmp_path / "report.md")
        cli_main(["analyze-portfolio", "--input", input_path, "--format", "markdown", "--output", output_path])
        content = Path(output_path).read_text(encoding="utf-8")
        assert "成本基础" in content or "cost_basis" in content.lower() or "cost" in content.lower()

    def test_json_output_includes_final_report(self, tmp_path, capsys):
        input_path = _write_temp_json(_minimal_portfolio(), tmp_path)
        rc = cli_main(["analyze-portfolio", "--input", input_path, "--pretty"])
        assert rc == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "final_report" in output
        report = output["final_report"]
        assert "report_sections" in report
        assert "quality_gate" in report

    def test_json_output_includes_warnings(self, tmp_path, capsys):
        input_path = _write_temp_json(_minimal_portfolio(), tmp_path)
        rc = cli_main(["analyze-portfolio", "--input", input_path, "--pretty"])
        assert rc == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "warnings" in output
        assert isinstance(output["warnings"], list)

    def test_json_output_includes_raw_final_report_sections(self, tmp_path, capsys):
        input_path = _write_temp_json(_minimal_portfolio(), tmp_path)
        rc = cli_main(["analyze-portfolio", "--input", input_path, "--pretty"])
        assert rc == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        sections = output.get("final_report", {}).get("report_sections", [])
        assert len(sections) > 0
        section_ids = {s["id"] for s in sections if isinstance(s, dict)}
        assert "executive_summary" in section_ids or "portfolio_snapshot" in section_ids

    def test_no_broker_execution_instruction(self, tmp_path):
        input_path = _write_temp_json(_minimal_portfolio(), tmp_path)
        output_path = str(tmp_path / "report.md")
        cli_main(["analyze-portfolio", "--input", input_path, "--format", "markdown", "--output", output_path])
        content = Path(output_path).read_text(encoding="utf-8")
        lower = content.lower()
        for forbidden in ["买入指令", "卖出指令", "下单", "执行交易", "订单", "委托下单", "限价单"]:
            assert forbidden not in lower, f"forbidden broker instruction: {forbidden}"
        assert "不包含经纪执行" in content or "不执行" in content


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
