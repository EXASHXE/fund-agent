"""Deterministic fund_analysis report i18n tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from src.schemas.skill import SkillInput
from src.skills_runtime.fund_analysis.skill import FundAnalysisSkill
from src.tools.portfolio.report_composer import render_report_markdown


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "examples" / "user_flows" / "semiconductor_profit_protection.json"
FORMAL_DECISION_ARTIFACTS = {"decision", "decisions", "execution_ledger", "execution_ledgers"}


def _payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _run(payload: dict):
    return FundAnalysisSkill().run(
        SkillInput(
            task_id="report-i18n",
            step_id="fund-analysis",
            skill_name="fund_analysis",
            payload=payload,
        )
    )


def test_zh_cn_report_contains_chinese_titles_and_deterministic_facts() -> None:
    payload = _payload()
    payload["report_options"] = {
        **payload.get("report_options", {}),
        "language": "zh-CN",
        "detail_level": "professional",
    }

    output = _run(payload)

    assert output.status in {"OK", "PARTIAL"}
    markdown = render_report_markdown(output.artifacts["report_sections"])
    assert markdown.startswith("# 个人基金报告\n")
    for title in ("## 组合概览", "## 持仓快照", "## 仓位贡献", "## 盈利保护", "## 证据状态"):
        assert title in markdown
    assert "组合总市值" in markdown
    assert "数据完整度" in markdown
    assert "未生成正式决策" in markdown
    assert "已抓取实时" not in markdown
    assert "## Decision" not in markdown
    assert "ExecutionLedger" not in markdown


def test_unknown_language_falls_back_to_english_report() -> None:
    payload = _payload()
    payload["report_options"] = {
        **payload.get("report_options", {}),
        "language": "fr-FR",
    }

    output = _run(payload)
    markdown = render_report_markdown(output.artifacts["report_sections"])

    assert markdown.startswith("# Personal fund report\n")
    assert "## Executive summary" in markdown
    assert "## 组合概览" not in markdown


def test_v1_artifact_sections_appear_when_professional_report_requested() -> None:
    payload = _payload()
    payload["report_options"] = {
        **payload.get("report_options", {}),
        "detail_level": "professional",
    }

    output = _run(payload)
    section_ids = [section["id"] for section in output.artifacts["report_sections"]]

    for section_id in (
        "position_contribution",
        "profit_protection",
        "benchmark_divergence",
        "right_side_confirmation",
        "event_hype_failure",
        "cash_deployment",
        "evidence_status",
        "action_watchlist",
        "missing_data",
        "suggested_next_checks",
        "uncertainty_note",
    ):
        assert section_id in section_ids


def test_fund_analysis_report_i18n_does_not_emit_formal_decision_artifacts() -> None:
    payload = copy.deepcopy(_payload())
    payload["report_options"] = {
        **payload.get("report_options", {}),
        "language": "zh-CN",
        "detail_level": "professional",
    }

    output = _run(payload)

    assert FORMAL_DECISION_ARTIFACTS.isdisjoint(output.artifacts)
